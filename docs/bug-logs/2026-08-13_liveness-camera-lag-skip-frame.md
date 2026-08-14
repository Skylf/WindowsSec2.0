# Bug: 活体检测摄像头画面卡顿(每帧全量推理)

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 中

## 现象
活体检测/引导式采集时,摄像头画面明显卡顿,帧率从约 30fps 骤降到 10fps 左右。
原因:每一帧都调用 `appDetect.get(frame)` 做人脸检测 + 106 关键点提取,
CPU 推理每次约 60~100ms,成为瓶颈。

## 根因
1. `LivenessDetector.runLivenessCheck` / `collectBaselineEAR` 对每一帧都做模型推理,
   而动作是连续变化的,每秒 5~10 次检测已足够,无需逐帧判定
2. 检测分辨率 `det_size=(320,320)` 偏大,推理耗时高
3. `openCamera` 引导式采集同样每帧全量检测

## 修复
1. **跳帧检测**: 在三个检测循环内加入 `frame_count % 3 != 0` 跳过检测,
   每 3 帧才调用一次 `appDetect.get`,检测频率降到约 10 次/秒
   - `livenessDetector.runLivenessCheck`
   - `livenessDetector.collectBaselineEAR`
   - `inputter.openCamera` 的 baseline 采集与动作阶段两处循环
2. **降低检测分辨率**: `appDetect.prepare(det_size=(320,320))` → `det_size=(160,160)`,
   推理速度提升约 4 倍,活体检测只需判断动作幅度无需高精度
3. 顺带在 `runLivenessCheck` 循环内补充 ESC 中断处理(`用户中断`)

## 验证
- 源码检查确认三处循环均含 `frame_count % 3 != 0` 跳帧判断
- `__init__` 中 `det_size=(160, 160)`,`det_size=(320, 320)` 无残留
- 模块导入语法正常
