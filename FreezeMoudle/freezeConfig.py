# -*- coding: utf-8 -*-
"""
卡死检测配置(freezeConfig)
==========================
默认配置 + json 持久化(freeze_config.json, 不进 git)。
包含总开关(设置开关)与全部阈值。
"""

import json
import os

# 配置文件(本地持久化, 用户修改保留; 不入 git)
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "freeze_config.json")

# 默认配置
DEFAULT_CONFIG = {
    # ── 总开关(设置开关): False 时监控器拒绝启动 ──
    "enabled": True,

    # ── 采样与误报抑制 ──
    "sample_interval": 5.0,      # 采样间隔(秒)
    "confirm_count": 3,          # 连续确认次数: 异常持续 N 次采样才报警(抑制瞬时波动)
    "cooldown_seconds": 60,      # 报警冷却(秒): 同类型报警后冷却期内不重复

    # ── 阈值 ──
    "cpu_threshold": 90.0,       # CPU 使用率阈值(%)
    "mem_threshold": 90.0,       # 内存使用率阈值(%)
    "swap_threshold": 80.0,      # 交换内存(页面文件)使用率阈值(%)
    "disk_busy_threshold": 50.0, # 磁盘 IO 读写速率阈值(MB/s)
    "disk_free_threshold": 5.0,  # 系统盘剩余空间阈值(%)
    "process_count_threshold": 800,  # 进程数量阈值(进程风暴)
    "ui_timeout_ms": 5000,       # 界面无响应探测超时(毫秒, explorer 消息)
    "proc_cpu_threshold": 80.0,  # 单进程 CPU 占用阈值(%)(某进程吃满核)
    "response_delay_threshold": 1.0,  # 系统响应延迟阈值(秒, sleep 实测超时判定卡死)

    # ── 报告 ──
    "top_process_count": 5,      # 报告中"谁在占用"的进程数
    "disk_path": "C:\\",         # 磁盘空间检测路径(系统盘)

    # ── 忽略列表: 这些进程不计入"谁在占用"(如监控器自身) ──
    "ignore_processes": ["pythonw.exe", "python.exe"],
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
        print(f"[freezeConfig] 读取配置失败, 使用默认: {e}")
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
        print(f"[freezeConfig] 保存配置失败: {e}")


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
        print(f"[freezeConfig] 未知配置项: {key}")


def isEnabled():
    """检测总开关"""
    return bool(get("enabled"))


def setEnabled(enabled):
    """设置总开关"""
    set("enabled", bool(enabled))
