# -*- coding: utf-8 -*-
"""
卡死检测报告(freezeReporter)
============================
buildFreezeReport: 把报警数据组装成普通用户可读的报告
showFreezeReport: 轻量弹窗(复用 BsodMoudle 的 tkinter 弹窗)
"""

import os
import sys

# 复用蓝屏模块的弹窗实现(同一套 tkinter 报告窗口)
_BSOD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'BsodMoudle')
if _BSOD_DIR not in sys.path:
    sys.path.insert(0, _BSOD_DIR)


def buildFreezeReport(alert):
    """
    组装卡死检测报告文本
    :param alert: freezeMonitor 报警字典, 含 type/value/threshold/msg/time/top_processes/info
    :return: 报告文本<str>
    """
    lines = []
    lines.append("=" * 56)
    lines.append("             卡死检测报告")
    lines.append("=" * 56)
    lines.append(f"检测时间: {alert.get('time', '未知')}")
    lines.append(f"异常详情: {alert.get('msg', '')}")
    lines.append("-" * 56)

    info = alert.get("info", {})
    lines.append("【这是什么问题】")
    lines.append(f"  {info.get('meaning', '')}")
    lines.append("【你可以这样做】")
    lines.append(f"  {info.get('advice', '')}")
    lines.append("-" * 56)

    top = alert.get("top_processes") or []
    if top:
        lines.append("【谁在占用】")
        for i, p in enumerate(top[:5], 1):
            lines.append(f"  {i}. {p['name']} (PID {p['pid']})  "
                         f"CPU {p['cpu']:.0f}%  内存 {p['mem']:.1f}%")
    else:
        lines.append("【谁在占用】未采集到进程占用信息(权限不足或进程已退出)")

    lines.append("=" * 56)
    lines.append("提示: 单次卡死可能只是偶然, 若频繁出现请按建议排查。")
    return "\n".join(lines)


def showFreezeReport(report_text, title="卡死检测报告 - Windows 安全系统 2.0"):
    """
    弹出窗口展示报告(复用 BsodMoudle 的 tkinter 弹窗)
    :param report_text: 报告文本<str>
    :param title: 窗口标题<str>
    :return: None
    """
    try:
        from bsodReporter import showReport
        showReport(report_text, title=title)
    except ImportError as e:
        print(f"[freezeReporter] 弹窗不可用({e}), 报告仅打印:\n{report_text}")
