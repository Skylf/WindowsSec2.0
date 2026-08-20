# -*- coding: utf-8 -*-
"""
WatermarkMoudle 包
==================
视频去水印模块(本地文件, 全程不上公网):
- watermarkConfig.py    配置(GPU 开关/质量/检测参数, json 持久化)
- gpuDetector.py        GPU 资源检测(ONNX Runtime providers + 开关)
- watermarkDetector.py  水印定位(静态时域中值 / 动态模板跟踪)
- inpainter.py          修复引擎(fast=OpenCV / lama=ONNX 高质量)
- videoProcessor.py     视频处理主流程(定位→修复→输出, 进度/取消)
- runTest.py            命令行全流程(第二阶段)
"""
