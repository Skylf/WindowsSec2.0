# -*- coding: utf-8 -*-
"""
GPU 资源检测(gpuDetector)
=========================
检测 ONNX Runtime 可用的推理后端(CUDA / CPU), 供用户开关使用。
全程本地检测, 不上公网。

说明: GPU 加速需要安装 onnxruntime-gpu 且具备 NVIDIA 显卡 + CUDA 环境;
     仅安装 onnxruntime(CPU 版)时自动回退 CPU。
"""

import glob
import os
import sys

import log


def _addNvidiaDllDirs():
    """
    把 pip 安装的 NVIDIA 运行时 DLL 目录加入加载搜索路径
    (nvidia-cuda-runtime/cublas/cudnn/cufft 等包, 免系统级安装 CUDA 工具包)
    :return: 注入的目录列表<list<str>>
    """
    added = []
    candidates = []
    # 收集 site-packages 下 nvidia/*/bin 目录
    site_dirs = []
    try:
        import site
        site_dirs = list(site.getsitepackages())
    except Exception:
        pass
    if not site_dirs:
        try:
            import sysconfig
            site_dirs = [sysconfig.get_paths().get("purelib", "")]
        except Exception:
            pass
    for sp in site_dirs:
        candidates += glob.glob(os.path.join(sp, "nvidia", "*", "bin"))
    for d in sorted(set(candidates)):
        if not os.path.isdir(d):
            continue
        added.append(d)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(d)
        except (AttributeError, OSError):
            pass
    if added:
        log.info("gpuDetector", f"已注入 NVIDIA DLL 目录({len(added)} 个): "
                                f"{[os.path.basename(os.path.dirname(d)) for d in added]}")
    return added


# 模块加载时立即注入(onnxruntime 创建 CUDA 会话时按 PATH 查找 DLL)
_addNvidiaDllDirs()


def detectGpu() -> dict:
    """
    检测当前环境的 GPU 推理能力
    :return: {
        "cuda_available": bool,   # CUDA EP 是否可用
        "providers": [str],       # 可用 providers 列表
        "detail": str,            # 人类可读说明
    }
    """
    try:
        import onnxruntime as ort
        log.debug("gpuDetector", f"onnxruntime 版本: {ort.__version__}")
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


def verifyCuda() -> bool:
    """
    实测 CUDA EP 是否真正可用(创建最小会话跑一次)
    防止 providers 列表含 CUDA 但运行时库/驱动不匹配导致的谎报。
    onnx 包缺失时退化为仅检查 provider 列表。
    :return: 是否可用<bool>
    """
    try:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.log_severity_level = 3
        import numpy as np
        try:
            from onnx import helper, TensorProto
        except ImportError:
            log.debug("gpuDetector", "onnx 包缺失, 跳过 CUDA 实测(仅信任 provider 列表)")
            return True
        node = helper.make_node("Conv", ["X", "W"], ["Y"],
                                kernel_shape=[1, 1], pads=[0, 0, 0, 0])
        graph = helper.make_graph(
            [node], "cuda_probe",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, 1, 4, 4]),
             helper.make_tensor_value_info("W", TensorProto.FLOAT, [1, 1, 1, 1])],
            [helper.make_tensor_value_info("Y", TensorProto.FLOAT, [1, 1, 4, 4])],
            [helper.make_tensor("W", TensorProto.FLOAT, [1, 1, 1, 1],
                                np.ones(1, dtype=np.float32))])
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)],
                                  ir_version=10)   # onnxruntime 1.20 最高支持 IR 10
        sess = ort.InferenceSession(model.SerializeToString(),
                                    sess_options=so,
                                    providers=["CUDAExecutionProvider"])
        out = sess.run(None, {"X": np.ones((1, 1, 4, 4), dtype=np.float32)})
        if out is None or out[0].sum() < 1.0:
            return False
        log.info("gpuDetector", "CUDA 实测验证通过(最小会话推理成功)")
        return True
    except Exception as e:
        log.warn("gpuDetector", f"CUDA 实测验证失败: {str(e)[:200]}")
        return False


def getOnnxProviders(use_gpu="auto") -> list:
    """
    按开关解析 ONNX Runtime providers 列表(带 CUDA 实机验证, 防止谎报)
    :param use_gpu: "auto"(有则用)/"on"(强制 GPU, 不可用则 CPU)/"off"(仅 CPU)
    :return: providers 列表<list<str>>
    """
    info = detectGpu()
    cuda = info["cuda_available"]

    if use_gpu == "off":
        log.info("gpuDetector", "GPU 开关=off, 强制 CPU")
        return ["CPUExecutionProvider"]
    if cuda:
        # 实测 CUDA 能真正跑起来才用(驱动/运行库不匹配时回退 CPU)
        if verifyCuda():
            log.info("gpuDetector",
                     f"GPU 开关={use_gpu}, 使用 CUDA 加速")
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        log.warn("gpuDetector",
                 "CUDA 实测失败(驱动/运行库不匹配?), 回退 CPU")
        return ["CPUExecutionProvider"]
    if use_gpu == "on":
        log.warn("gpuDetector", "开关为 on 但 CUDA 不可用, 回退 CPU")
    else:
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
