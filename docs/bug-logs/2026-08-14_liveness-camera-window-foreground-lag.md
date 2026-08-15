# Bug: 摄像头窗口前台时鼠标卡顿、画面一顿一顿

**日期**: 2026-08-14
**版本**: v0.2A
**优先级**: 高

## 现象
打开摄像头进入活体检测流程后，OpenCV 窗口显示摄像头画面：
- 窗口在后台（未获得焦点）运行时流畅不卡；
- 将窗口切换为前台（获得焦点）后，鼠标卡顿，窗口画面一顿一顿。

## 根因
主线程在多个摄像头循环阶段直接执行 CPU 密集推理 `self.appDetect.get(frame)`，
具体在 `runSilentCheck`、`calibrateBaseline`、`_collectFrontalFrame` 三个方法中（`_detectSingleAction` 已是双线程）。

`cv2.imshow` 只是排队画面，真正的窗口刷新与鼠标/键盘/重绘消息处理都发生在
`cv2.waitKey` 的消息泵中。当窗口在前台获得焦点时，Windows 会向窗口发送大量
`WM_MOUSEMOVE`（鼠标移动）、`WM_PAINT`（重绘）等消息，需要主线程在 `waitKey` 里及时泵消息。

但主线程被 `appDetect.get`（人脸检测 + 关键点等 Python/ONNX 推理）阻塞，无法及时泵消息，
导致前台窗口的鼠标消息与重绘堆积，表现为鼠标卡顿、画面一顿一顿。
窗口在后台时没有这些前台焦点消息压力，所以"不卡"。

## 根因（第二轮补充）
第一轮"子线程推理"修复后仍卡，进一步定位到两个叠加因素：

1. 摄像头返回高分辨率帧（`cap.set(640,480)` 对很多 DirectShow 摄像头不生效，实际返回 720p/1080p）。
   前台窗口可见时，`imshow` 需要对 720p/1080p 帧做实际屏幕重绘 + 每帧 `frame.copy()` + 推理预处理缩放，
   开销远大于后台（后台不可见时 HighGUI 跳过重绘）。

2. 录入流程 `FaceMoudle/faceInputer/inputter.py` 的三个摄像头循环（`openCamera` 的基准采集循环、
   主采集循环、`collectFrontalPhotos` 循环）仍是"主线程推理 + 未缩小帧 + 未设置分辨率"，完全未做优化。

## 修复
文件：`FaceMoudle/liveness/livenessDetector.py`

1. 新增通用方法 `_runDetectLoop(cap, inferFunc, onResult, timeout, overlayFunc)`
   - 子线程：从帧队列取帧执行 `inferFunc(frame)` 推理，结果放入结果队列
   - 主线程：读帧 -> 节流显示 + `waitKey` -> 送帧 -> 取结果 -> `onResult` 判定
   - 保证主线程永不执行耗时推理，消息泵得以及时响应

2. 将 `runSilentCheck`、`calibrateBaseline`、`_detectSingleAction`、`_collectFrontalFrame`
   全部改为通过 `_runDetectLoop` 执行（推理/静默判定放入子线程，主线程只负责显示与判定）。

3. 简化 `runAdaptiveActions`：移除内部 `frame_queue`/`result_queue`/worker 管理，
   改由每个动作的 `_detectSingleAction` 内部通过 `_runDetectLoop` 自行管理线程。

### 第二轮修复（缩小帧 + 录入流程同步）
1. 新增模块级 `shrinkFrame(frame, maxWidth=640)`：读帧后按宽度等比例缩小到 640 宽，
   大幅降低前台重绘、`frame.copy()`、推理预处理的像素量。

2. `_runDetectLoop` 读帧后统一调用 `shrinkFrame`。

3. 录入流程 `inputter.py` 的三个循环（`openCamera` 基准采集、主采集、`collectFrontalPhotos`）
   读帧后统一调用 `shrinkFrame`。

## 验证
- `python -c "import ast; ast.parse(...)"` 语法检查通过（livenessDetector.py 与 inputter.py）。
- Grep 确认 `frame_queue`/`result_queue` 仅存在于 `_runDetectLoop` 内部，无旧签名遗留调用。
- 需实际运行 `FaceMoudle/facialRecognition/runTest.py`（识别）与 `FaceMoudle/faceInputer/runTest.py`（录入），
  观察窗口在前台获得焦点时鼠标与画面是否恢复流畅。
