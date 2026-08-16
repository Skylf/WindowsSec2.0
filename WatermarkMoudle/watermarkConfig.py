# -*- coding: utf-8 -*-
"""
水印去除配置(watermarkConfig)
==============================
使用 GPU 开关 / 修复质量 / 检测参数, json 持久化(本地, 不上公网)。
"""

import json
import os

# 配置文件(本地持久化, 用户设置保留; 不入 git)
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "watermark_config.json")

# 默认配置
DEFAULT_CONFIG = {
    # ── 计算资源 ──
    "use_gpu": "auto",        # GPU 开关: auto(有则用)/on(强制)/off(仅CPU)

    # ── 修复质量 ──
    "quality": "fast",        # fast(OpenCV inpaint, 快, 零依赖) / lama(ONNX, 高质量, 需模型)

    # ── 水印定位 ──
    "detect_method": "median",   # median(时域中值自动检测) / manual(手动坐标)
    "median_frames": 30,         # 时域中值采样帧数
    "median_threshold": 15,      # 静止判定阈值(0-255, 越小越严格)

    # ── 输出 ──
    "output_dir": "",            # 输出目录, 空 = 输入同目录
    "output_suffix": "_nowm",    # 输出文件后缀
}

_config = None


def load():
    """加载配置(文件存在则合并覆盖默认)"""
    global _config
    if _config is not None:
        return _config
    _config = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                _config.update(saved)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watermarkConfig] 读取配置失败, 使用默认: {e}")
    return _config


def save():
    """保存当前配置到文件"""
    global _config
    if _config is None:
        load()
    try:
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[watermarkConfig] 保存配置失败: {e}")


def get(key):
    """读取配置项"""
    return load().get(key, DEFAULT_CONFIG.get(key))


def set(key, value):
    """设置配置项并保存"""
    cfg = load()
    if key in cfg:
        cfg[key] = value
        save()
    else:
        print(f"[watermarkConfig] 未知配置项: {key}")


def getUseGpu() -> str:
    """GPU 开关值: auto/on/off"""
    return str(get("use_gpu"))


def setUseGpu(mode):
    """设置 GPU 开关: auto/on/off"""
    if mode in ("auto", "on", "off"):
        set("use_gpu", mode)
