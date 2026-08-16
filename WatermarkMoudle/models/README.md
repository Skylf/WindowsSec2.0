# 模型目录(models/)

本目录存放可选的高清修复模型, 全程本地推理, 不上公网。

## LaMa 高清修复模型

- 文件(任选其一, 约 200MB):
  - **`lama_fp32.onnx`(推荐)**: opset 17, torch.onnx.export 导出,
    兼容新版 onnxruntime
  - `lama.onnx`(备用): opset 18, dynamo 导出, 新版 onnxruntime
    可能因 DFT 算子检查拒绝加载, 且推理较慢
- 来源: 开源项目 Carve/LaMa-ONNX(HuggingFace 托管)
- 放置: 将模型文件放入本目录, 重启程序即可在「修复质量」中
  选择「高清(LaMa AI 模型)」
- 未放置时: 自动降级为「快速(OpenCV 算法)」, 并在日志中提示,
  功能不受影响

下载地址(国内可用 hf-mirror 镜像):
- https://hf-mirror.com/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx
- https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx
- 项目主页: https://huggingface.co/Carve/LaMa-ONNX

> 注意: 模型输入尺寸固定 512x512, 程序会自动缩放适配, 无需手动处理。
> 该文件体积较大, 不建议提交到 git; 需要时放入本目录即可, 程序自动检测。
