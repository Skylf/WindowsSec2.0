# Bug: 活体检测识别准确率低 + 动作逻辑混乱 + 画面卡顿

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 高

## 现象
1. 识别准确率几乎 100% 错误(活体检测通过后身份识别始终匹配不上)
2. 动作逻辑混乱: 左转还没做就判定通过,右转来不及做就超时失败
3. 摄像头窗口/鼠标明显卡顿(但 CPU 未满载)

## 根因
1. **识别准确率低**: `runLivenessRecognize` 用"5 个动作通过帧(侧脸/仰头/闭眼/张嘴)"
   的特征平均做身份识别,这些非正脸/表情帧与注册正脸特征差异极大,相似度必然很低。
2. **动作逻辑混乱**: `computeHeadPose` 用 solvePnP 算出的"绝对 Yaw/Pitch"直接判阈值,
   无标定相机下存在系统偏差,导致正面时 Yaw 已偏负(左转秒过、右转难过)。
3. **卡顿**: 摄像头采集分辨率未降低,主线程每帧 copy+putText+imshow 高频重绘阻塞 GUI。

## 修复(企业级多层防御改造)
新建 `FaceMoudle/liveness/` 活体检测模块(供录入与识别共用):

1. `silentLiveness.py` — 第一层静默活体检测(模糊/亮度/对比度/频域特征,
   无需外部模型,拦截照片/屏幕翻拍;预留 MiniFASNet 接口)
2. `livenessDetector.py` — 第二层主动动作检测:
   - 姿态基准校准(先采集正面基准 Yaw/Pitch/EAR,动作用相对偏移判定,消除系统偏差)
   - 双线程架构(主线程显示 + 子线程推理)
   - 显示节流 + 降分辨率(cap 640x480)缓解卡顿
   - 动作通过后采集"正脸帧"供识别使用
3. 改造 `inputter.openCameraWithLiveness` → 活体检测(静默+动作) + 图像收集(openCamera)
4. 改造 `recognition.runLivenessRecognize` → 活体检测(静默+动作) + 正脸帧识别
5. 重写 `faceInputer/runTest.py` → 录入后统一走 faceCheck → generateFaceFeature

## 验证
- liveness 包(相对导入)可正常 import,LivenessDetector 全部方法存在
- inputter / recognition / runTest 均可正常导入
- openCameraWithLiveness 内部走 `runLivenessCheck(collectFrontal=False)` + `openCamera()`
- runLivenessRecognize 内部走 `runLivenessCheck(collectFrontal=True)` + 正脸帧识别
