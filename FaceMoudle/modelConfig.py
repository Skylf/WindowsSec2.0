# -*- coding: utf-8 -*-
"""
ONNX Runtime 推理线程配置(modelConfig)
======================================
背景: 本机 32 逻辑核,onnxruntime 默认 intra_op_num_threads=0(全部核心并行)。
摄像头活体检测/录入流程中,任何一次 ONNX 推理都会让 32 个线程同时抢 CPU,
CPU 瞬时满载 → 系统级响应变慢 → 前台摄像头窗口出现鼠标/画面卡顿
(后台窗口没有焦点消息压力,所以"后台不卡、前台卡")。

本模块统一限制推理线程数(默认 4,可用环境变量 WSS_INFER_THREADS 覆盖),
并对 insightface 的 ModelRouter.get_model 做 monkey-patch,
使 FaceAnalysis 创建的每个 session 自动带上受限线程数的 SessionOptions。

使用方式:
- 直接 import 本模块即自动生效(幂等): import modelConfig
  (模块导入时会自动执行 applyInsightfaceThreadPatch,子进程 spawn 重新导入时同样生效)
- 自建 onnx session 的模块用 createSession() 替代 ort.InferenceSession(...)
"""

import os
import sys
import threading

# 默认推理线程数(可用环境变量 WSS_INFER_THREADS 覆盖)
# 4 线程足够跑满小模型(det_size=160 的检测/关键点),同时给主线程留出 CPU
DEFAULT_INFER_THREADS = 4

# patch 幂等锁与标志(多线程/多进程重复 import 时只 patch 一次)
_patchLock = threading.Lock()
_patched = False


def getInferThreads():
    """
    获取推理线程数(优先读环境变量 WSS_INFER_THREADS)
    :return: 线程数<int>,至少 1
    """
    try:
        value = int(os.environ.get('WSS_INFER_THREADS', str(DEFAULT_INFER_THREADS)))
        return max(1, value)
    except ValueError:
        return DEFAULT_INFER_THREADS


def createSessionOptions():
    """
    创建受限线程数的 SessionOptions(intra=推理线程数, inter=1)
    inter_op=1 避免多个模型 session 之间再开线程互相抢占
    :return: onnxruntime.SessionOptions
    """
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = getInferThreads()
    so.inter_op_num_threads = 1
    return so


def createSession(modelPath, providers=None):
    """
    创建受限线程数的推理 session(供自建 onnx session 的模块使用,如 MiniFASNet)
    :param modelPath: 模型文件路径<str>
    :param providers: 推理后端列表<list<str>>,默认 ['CPUExecutionProvider']
    :return: onnxruntime.InferenceSession
    """
    import onnxruntime as ort
    if providers is None:
        providers = ['CPUExecutionProvider']
    return ort.InferenceSession(
        modelPath,
        sess_options=createSessionOptions(),
        providers=providers
    )


def applyInsightfaceThreadPatch():
    """
    monkey-patch insightface 的 ModelRouter.get_model:
    创建 session 时注入受限线程数的 SessionOptions。
    幂等(线程安全),可多次调用;patch 失败不影响运行(打印警告后继续)。

    :return: None
    """
    global _patched
    if _patched:
        return
    with _patchLock:
        if _patched:
            return
        try:
            # 动态导入 insightface(此时才引入依赖,modelConfig 本身可独立使用)
            from insightface.model_zoo import model_zoo
            originalGetModel = model_zoo.ModelRouter.get_model

            def patchedGetModel(self, **kwargs):
                # 调用方未显式传 sess_options 时注入受限配置
                # (insightface 的 get_model 只透传 providers/provider_options,
                #  正常情况下这里永远会注入)
                if 'sess_options' not in kwargs:
                    kwargs['sess_options'] = createSessionOptions()
                return originalGetModel(self, **kwargs)

            model_zoo.ModelRouter.get_model = patchedGetModel
            _patched = True
            print(f"[modelConfig] 已限制 InsightFace 推理线程数: {getInferThreads()}")
        except Exception as e:
            print(f"[modelConfig] 警告: InsightFace 线程数 patch 失败(不影响功能): {e}")


# 模块导入时自动生效(幂等;子进程 spawn 重新导入本模块时同样生效)
applyInsightfaceThreadPatch()
