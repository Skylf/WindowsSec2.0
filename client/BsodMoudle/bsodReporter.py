# -*- coding: utf-8 -*-
"""
蓝屏报告(bsodReporter)
======================
buildReport: 把蓝屏事件 + 知识库解读组装成普通用户可读的报告文本
showReport: 轻量弹窗展示报告(tkinter, 独立于主控制面板 UI)
"""

from bsodKnowledge import getBsodInfo, formatCode


def buildReport(event):
    """
    组装蓝屏报告文本(时间 / 代码 / 通俗解读 / 原因 / 建议)
    :param event: checkLatestBugCheck 返回的事件<dict>, 含 time/code/params
    :return: 报告文本<str>
    """
    lines = []
    lines.append("=" * 56)
    lines.append("             蓝屏识别报告")
    lines.append("=" * 56)

    # 基本信息
    time_str = event.get("time", "未知")[:19].replace("T", " ") if event.get("time") else "未知"
    lines.append(f"发生时间: {time_str}")

    code = event.get("code")
    if code is not None:
        info = getBsodInfo(code)
        lines.append(f"蓝屏代码: {formatCode(code)}  ({info['name']})")
        lines.append("-" * 56)
        lines.append(f"【这是什么问题】")
        lines.append(f"  {info['meaning']}")
        lines.append(f"【常见原因】")
        lines.append(f"  {info['cause']}")
        lines.append(f"【你可以这样做】")
        lines.append(f"  {info['advice']}")
        params = event.get("params") or []
        if params:
            lines.append("-" * 56)
            lines.append(f"技术参数(供排查):")
            for i, p in enumerate(params[:4], 1):
                lines.append(f"  参数{i}: {p}")
    else:
        lines.append("蓝屏代码: 未解析到")
        lines.append("提示: 已检测到系统蓝屏记录, 但未能提取代码, 可查看 "
                     "\"事件查看器 → Windows 日志 → 系统 → 事件 1001\" 获取详情。")

    lines.append("=" * 56)
    lines.append("提示: 单次蓝屏可能只是偶然, 若频繁出现请按建议排查。")
    return "\n".join(lines)


def showReport(report_text, title="蓝屏识别报告 - Windows 安全系统 2.0"):
    """
    弹出窗口展示报告(轻量 tkinter 窗口, 非主控制面板 UI)
    :param report_text: 报告文本<str>
    :param title: 窗口标题<str>
    :return: None(窗口关闭后返回); 无图形环境时仅打印并返回
    """
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except ImportError:
        print("[bsodReporter] 无 tkinter, 报告仅打印到控制台:\n", report_text)
        return

    try:
        root = tk.Tk()
    except tk.TclError:
        # 无图形环境(如远程/服务会话)
        print("[bsodReporter] 无图形环境, 报告仅打印到控制台:\n", report_text)
        return

    root.title(title)
    root.geometry("760x560")
    root.minsize(600, 400)

    text = scrolledtext.ScrolledText(root, wrap="word", font=("Microsoft YaHei", 11),
                                     padx=12, pady=12)
    text.insert("1.0", report_text)
    text.config(state="disabled")   # 只读
    text.pack(fill="both", expand=True, padx=12, pady=(12, 6))

    btn_row = tk.Frame(root)
    btn_row.pack(fill="x", pady=(0, 12))
    tk.Button(btn_row, text="知道了", command=root.destroy,
              font=("Microsoft YaHei", 11), width=16,
              bg="#3B82F6", fg="#FFFFFF", activebackground="#2F6FD6",
              activeforeground="#FFFFFF", relief="flat", cursor="hand2"
              ).pack(pady=4)

    root.mainloop()
