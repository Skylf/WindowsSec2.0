# -*- coding: utf-8 -*-
"""
GPU 资源检测(gpuDetector)
=========================
检测 ONNX Runtime 可用的推理后端(CUDA / CPU), 供用户开关使用。
全程本地检测, 不上公网。

说明: GPU 加速需要安装 onnxruntime-gpu 且具备 NVIDIA 显卡 + CUDA 环境;
     仅安装 onnxruntime(CPU 版)时自动回退 CPU。
"""

import onnxruntime as ort

import log


def detectGpu() -> dict:
    """
    检测当前环境的 GPU 推理能力
    :return: {
        "cuda_available": bool,   # CUDA EP 是否可用
        "providers": [str],       # 可用 providers 列表
        "detail": str,            # 人类可读说明
    }
    """
    log.debug("gpuDetector", f"onnxruntime 版本: {ort.__version__}")
    try:
        providers = ort.get_available_providers()
        log.info("gpuDetector", f"ONNX Runtime 可用 providers: {providers}")
    except Exception as e:
        providers = []
        log.error("gpuDetector", f"获取 providers 失败: {e}")
    cuda = "CUDAExecutionProvider" in providers
    if cuda:
        detail = "检测到 CUDA 可用(onnxruntime-gpu), 推理可用 GPU 加速"
        log.info("gpuDetector", "CUDA 可用(onnxruntime-gpu 已安装)")
    else:
        detail = ("仅 CPU 可用。如需 GPU 加速: 1) 需 NVIDIA 显卡 2) 安装 "
                  "onnxruntime-gpu(pip install onnxruntime-gpu)")
        log.info("gpuDetector", "CUDA 不可用, 仅 CPU 推理")
    return {"cuda_available": cuda, "providers": providers, "detail": detail}


def getOnnxProviders(use_gpu="auto") -> list:
    """
    按开关解析 ONNX Runtime providers 列表
    :param use_gpu: "auto"(有则用)/"on"(强制 GPU, 不可用则 CPU)/"off"(仅 CPU)
    :return: providers 列表<list<str>>
    """
    info = detectGpu()
    cuda = info["cuda_available"]

    if use_gpu == "off":
        log.info("gpuDetector", "GPU 开关=off, 强制 CPU")
        return ["CPUExecutionProvider"]
    if use_gpu == "on":
        if cuda:
            log.info("gpuDetector", "GPU 开关=on, 使用 CUDA")
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        log.warn("gpuDetector", "开关为 on 但 CUDA 不可用, 回退 CPU")
        return ["CPUExecutionProvider"]
    # auto: 可用则用
    if cuda:
        log.info("gpuDetector", "GPU 开关=auto, CUDA 可用 → 使用 GPU")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    log.info("gpuDetector", "GPU 开关=auto, CUDA 不可用 → 使用 CPU")
    return ["CPUExecutionProvider"]


def summary(use_gpu="auto") -> str:
    """
    生成资源使用摘要(供 runTest/UI 展示)
    :param use_gpu: GPU 开关
    :return: 摘要文本<str>
    """
    info = detectGpu()
    providers = getOnnxProviders(use_gpu)
    gpu_used = "CUDAExecutionProvider" in providers
    return (f"GPU 开关: {use_gpu} | CUDA 可用: {'是' if info['cuda_available'] else '否'} "
            f"| 实际使用: {'GPU(CUDA)' if gpu_used else 'CPU'}")
