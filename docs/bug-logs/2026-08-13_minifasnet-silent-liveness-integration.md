# Bug: 静默活体检测缺少深度模型 + 活体检测代码未完全分离

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 高

## 现象
1. 静默活体检测最初用传统图像特征(模糊/亮度/对比度/频域),无深度学习模型,
   抗攻击能力弱,不符合"企业级多层防御"要求
2. 活体检测代码未完全集中: 旧的 faceInputer/livenessDetector.py 仍被 openCamera 使用,
   与新 FaceMoudle/liveness/ 模块并存

## 根因
1. 之前未下载 MiniFASNet 深度静默活体模型,仅以传统特征替代
2. 迁移新模块时保留了旧文件,openCamera 引导采集仍依赖旧 livenessDetector.py

## 修复
1. **接入 MiniFASNet 深度静默活体模型**:
   - 下载模型到 FaceMoudle/liveness/models/minifasnet.onnx(1.82MB)
   - 来源: facenox/face-antispoof-onnx v1.0.0(MiniFASNet V2 SE, Apache-2.0)
   - 输入: 128x128 RGB,归一化 /255,CHW;输出: [real, spoof] logits
   - 重写 silentLiveness.py: 质量检查(光线/对比度) + MiniFASNet 推理,
     logit_diff = real - spoof >= 0 判真人
2. **彻底迁移并删除旧文件**:
   - openCamera 改为从 liveness.livenessDetector 导入 LivenessDetector + 关键点索引,
     内部自行定义绝对姿态阈值(引导采集用绝对角度,区别于活体验证的相对偏移)
   - 删除 faceInputer/livenessDetector.py 及其 pyc 缓存

## 验证
- MiniFASNet 模型加载成功(input name: input),推理正常
- liveness 包(相对导入)正常 import
- inputter/recognition/runTest 正常 import
- openCamera/openCameraWithLiveness 均指向新 liveness.livenessDetector
- 旧 faceInputer/livenessDetector.py 已删除
