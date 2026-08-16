# 模型目录(models/)

本目录存放可选的高清修复模型, 全程本地推理, 不上公网。

## LaMa 高清修复模型(lama.onnx)

- 文件: `lama.onnx`(约 200MB)
- 来源: 开源项目 Carve/LaMa-ONNX(HuggingFace 托管)
- 放置: 将下载的 `lama.onnx` 放入本目录, 重启程序即可在
  「修复质量」中选择「高清(LaMa AI 模型)」
- 未放置时: 自动降级为「快速(OpenCV 算法)」, 并在处理日志中提示,
  功能不受影响

下载地址(任选):
- https://huggingface.co/Carve/LaMa-ONNX
- https://github.com/Sanster/lama-cleaner(项目主页, 含模型说明)

> 提示: 该文件体积较大, 不建议提交到 git;
> 需要时放入本目录即可, 程序自动检测。
