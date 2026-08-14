# Bug: 活体检测画面卡顿(摄像头读取与模型推理串行执行)

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 高

## 现象
活体检测时,摄像头读取(cap.read)与模型推理(appDetect.get)在同一线程串行执行,
推理时画面无法更新,用户感知为明显卡顿。之前"跳帧 + 降低分辨率"只是缓解未根治。

## 根因
主线程里每帧依次执行:读帧 → 显示 → 模型推理 → 判定,
模型推理(CPU 约 30~100ms)阻塞了读帧与显示,导致帧率骤降。

## 修复(双线程架构)
修改 `FaceMoudle/faceInputer/livenessDetector.py`:
1. 重写 `runLivenessCheck` 为双线程版:
   - 主线程只负责 cap.read() + cv2.imshow(),保持画面流畅
   - 子线程 `inferenceWorker` 从 `frame_queue` 取帧执行 appDetect.get 推理,
     结果放入 `result_queue`
   - 主线程非阻塞 `result_queue.get(block=False)` 取结果做动作判定
   - 队列均 `maxsize=1` 只保留最新帧/结果,丢弃旧数据避免堆积
   - 新增 `clearQueues`(动作切换前清残留)与 `stopWorker`(终止子线程)
   - 用 try/finally 保证任何路径都终止子线程并关闭窗口
2. 新增 `checkActionWithFaces(faces, frame, actionName)` 复用已检测的人脸对象,
   避免主线程重复推理;`checkAction` 改为委托调用它(保持向后兼容)

## 验证
- `inspect.getsource` 确认双线程结构完整(threading/queue/frame_queue/result_queue/
  inferenceWorker/checkActionWithFaces/try-finally 均存在)
- `checkAction` 已委托给 `checkActionWithFaces`
- 模块导入语法正常
