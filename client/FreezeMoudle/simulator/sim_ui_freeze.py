# -*- coding: utf-8 -*-
"""
界面冻结模拟器(sim_ui_freeze)
==============================
创建窗口后阻塞主线程 → 窗口无响应(演示"程序无响应/界面冻结"现象)。

说明: 检测器的 ui_freeze 维度探测的是系统桌面(explorer 任务栏)的消息响应,
本模拟器无法直接冻结 explorer; 配合 sim_cpu 满载运行可复现"系统繁忙
导致界面卡顿无响应"的真实场景, 用于观察检测器在系统级卡死下的表现。

用法:
  python simulator/sim_ui_freeze.py --freeze 10
参数:
  --freeze 窗口冻结秒数(默认 10, 期间窗口标题显示"无响应")
"""
import argparse
import time
import tkinter as tk


def main():
    parser = argparse.ArgumentParser(description="界面冻结模拟器")
    parser.add_argument("--freeze", type=float, default=10.0,
                        help="窗口冻结秒数(默认 10)")
    args = parser.parse_args()

    root = tk.Tk()
    root.title("模拟无响应窗口")
    root.geometry("360x220")

    label = tk.Label(root, text="窗口即将冻结(主线程阻塞)...",
                     font=("Microsoft YaHei", 12))
    label.pack(expand=True)

    def freeze():
        """阻塞主线程, 窗口无响应"""
        label.config(text=f"窗口已冻结 {args.freeze:.0f} 秒(无响应)...")
        root.update_idletasks()
        time.sleep(args.freeze)   # 主线程阻塞 → 窗口无响应
        label.config(text="窗口已恢复响应")
        root.update_idletasks()

    # 窗口显示 2 秒后冻结
    root.after(2000, freeze)
    root.mainloop()


if __name__ == '__main__':
    main()
