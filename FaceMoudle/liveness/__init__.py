# -*- coding: utf-8 -*-
"""
活体检测模块(liveness)
=======================
供 FaceMoudle/faceInputer(录入) 与 FaceMoudle/facialRecognition(识别) 共用的
多层防御活体检测能力。

对外接口:
- LivenessDetector        : 主动动作活体检测器(集成静默检测)
- SilentLivenessDetector  : 静默活体检测器(第一层防御)
"""

from .livenessDetector import (
    LivenessDetector,
    ACTION_SEQUENCE,
    ACTION_TIMEOUT,
)
from .silentLiveness import SilentLivenessDetector

# 供外部 `from liveness import LivenessDetector` 直接使用
__all__ = [
    "LivenessDetector",
    "SilentLivenessDetector",
    "ACTION_SEQUENCE",
    "ACTION_TIMEOUT",
]
