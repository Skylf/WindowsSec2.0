# Bug: 摄像头窗口前台时鼠标卡顿仍未根治(ONNX 全核推理 + 消息泵不足 + 录入循环未双线程化)

**日期**: 2026-08-15
**版本**: v0.2A
**优先级**: 高

## 现象
2026-08-14 的双线程修复(见 `2026-08-14_liveness-camera-window-foreground-lag.md`)实机验证后,
摄像头窗口切换为前台(获得焦点)时**依旧卡顿,鼠标都卡**。

## 根因(三层叠加,08-14 修复未覆盖)

### 1. ONNX Runtime 全核推理(主因,08-14 未发现)
- 本机 **32 逻辑核**,onnxruntime 默认 `intra_op_num_threads=0`(全部核心并行)。
- 活体检测流程共 5 个 ONNX session(det_10g / 2d106det / 1k3d68 / w600k_r50 / minifasnet),
  每次推理都会开 32 个线程抢 CPU → **CPU 瞬时满载,系统级响应变慢** → "鼠标都卡"。
- 双线程架构只解决了"推理阻塞显示",没解决"推理吃满 CPU";
  后台窗口无焦点消息压力所以不明显,前台窗口消息风暴下立刻暴露。

### 2. waitKey 消息泵不足(次因)
- `_runDetectLoop` 只显示节流(每 2 帧一次 imshow),但**非显示帧完全不调 waitKey** → 消息泵空转;
- `waitKey(1)` 仅 1ms,前台焦点窗口的 WM_MOUSEMOVE/WM_PAINT 消息处理不完 → 鼠标消息堆积。

### 3. inputter.py 录入循环仍是主线程推理(08-14 日志声称已修,实际只加了 shrinkFrame)
- `openCamera` 基准 EAR 采集循环、阶段判定+拍照循环、`collectFrontalPhotos` 循环
  仍在主线程直接 `detector.appDetect.get(frame)`,推理阻塞消息泵的问题原样存在。

## 修复

### 第 1 层: 限制 ONNX 推理线程数(治本)
- 新建 `FaceMoudle/modelConfig.py`:
  - monkey-patch `insightface.model_zoo.ModelRouter.get_model`,
    创建 session 时注入 `SessionOptions(intra_op_num_threads=4, inter_op_num_threads=1)`;
  - `createSession()` 供自建 session 使用(MiniFASNet);
  - 线程数可用环境变量 `WSS_INFER_THREADS` 覆盖;patch 幂等,子进程 spawn 重导入时同样生效。
- 接入点: `livenessDetector.py` / `silentLiveness.py` / `recognition.py` / `faceDataGetter.py` / `inputter.py`
  顶部统一导入(自动生效)。
- 效果: 32 线程 → 4 线程,CPU 不再满载;实测推理仍仅 5.1ms/帧(det_size=160),速度无损失。

### 第 2 层: 修复消息泵(`livenessDetector._runDetectLoop`)
- 新增常量 `WAITKEY_DELAY_MS = 10`;
- 显示帧: `imshow` + `waitKey(10)`;**非显示帧也调 `waitKey(10)`** 泵消息;
- `_runDetectLoop` 新增 `windowName` 参数(录入流程传 "Capture")。

### 第 3 层: inputter.py 三处摄像头循环双线程化
- 复用 `LivenessDetector._runDetectLoop`(infer=检测, onResult=判定/连拍保存, overlay=画面提示):
  - 基准 EAR 采集循环 → `_runDetectLoop`(同 calibrateBaseline 模式);
  - 阶段判定+拍照循环 → `_runDetectLoop`(拍够返回 True,超时走 timeout);
  - `collectFrontalPhotos` → `_runDetectLoop`;
- 主线程不再执行任何 `appDetect.get`;照片保存仍用主线程最新帧(与现状一致)。

## 验证
- 全部模块 `py_compile` 语法通过,import 正常;
- `test/3_verify_infer_threads.py`: MiniFASNet 与 FaceAnalysis 各模型 session
  `intra_op_num_threads` 均为 4(0=全核),patch 确认生效;
- 推理耗时实测 5.1ms/帧(线程数=4),速度无损失;
- 需实机运行录入(方式 2/3)与识别流程,确认窗口前台时鼠标/画面恢复流畅、
  任务管理器 CPU 占用不再长期 100%。
