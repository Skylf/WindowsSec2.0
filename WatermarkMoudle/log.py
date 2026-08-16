# -*- coding: utf-8 -*-
"""
水印模块日志(log)
=================
轻量分级控制台日志: 时间戳 + 级别 + 模块标记, 便于排查内部问题。

- 级别: DEBUG < INFO < WARN < ERROR
- DEBUG 默认关闭, 开 DEBUG 方式:
    * 环境变量 WM_DEBUG=1
    * 或 runTest.py --debug
- 所有输出带 flush(管道重定向时也能实时看到)
"""

import os
import sys
import time

_DEBUG = os.environ.get("WM_DEBUG", "0") == "1"
_LOCK = None

# 级别宽度(对齐用)
_LEVELS = {
    "DBG": "DBG",
    "INF": "INF",
    "WRN": "WRN",
    "ERR": "ERR",
}


def set_debug(on):
    """开/关 DEBUG 日志"""
    global _DEBUG
    _DEBUG = bool(on)


def is_debug():
    return _DEBUG


def _emit(level, tag, msg):
    ts = time.strftime("%H:%M:%S", time.localtime())
    line = f"[{ts}] [{_LEVELS.get(level, level)}] [{tag}] {msg}"
    try:
        print(line, flush=True)
    except OSError:
        pass   # 管道关闭等场景不崩溃


def debug(tag, msg):
    """调试日志(仅 WM_DEBUG=1 时输出)"""
    if _DEBUG:
        _emit("DBG", tag, msg)


def info(tag, msg):
    """常规日志"""
    _emit("INF", tag, msg)


def warn(tag, msg):
    """警告(降级/回退等)"""
    _emit("WRN", tag, msg)


def error(tag, msg):
    """错误"""
    _emit("ERR", tag, msg)
