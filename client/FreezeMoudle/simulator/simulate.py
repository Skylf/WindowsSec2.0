# -*- coding: utf-8 -*-
"""
卡死模拟统一入口(simulate.py)
==============================
按类型启动卡死模拟, 用于测试 FreezeMoudle 检测器的业务功能。
每种模拟均可独立运行(见 README.md), 本入口提供统一菜单/参数。

用法:
  python simulator/simulate.py                    # 交互菜单
  python simulator/simulate.py --type cpu --duration 10
  python simulator/simulate.py --type memory --mb 512
类型:
  cpu        CPU 满载          (cpu_high)
  memory     内存占用          (mem_high / swap_high)
  disk_io    磁盘 IO 繁忙      (disk_busy)
  disk_full  磁盘空间不足      (disk_full)
  process    进程风暴          (process_storm)
  ui         界面冻结          (配合 cpu 观察 ui_freeze 场景)
"""
import argparse
import subprocess
import sys
import os

# 本目录
_SIM_DIR = os.path.dirname(os.path.abspath(__file__))

# 类型 → (脚本文件, 说明, 对应检测维度)
TYPES = {
    "cpu":      ("sim_cpu.py",          "CPU 满载", "cpu_high"),
    "memory":   ("sim_memory.py",       "内存占用", "mem_high / swap_high"),
    "disk_io":  ("sim_disk_io.py",      "磁盘 IO 繁忙", "disk_busy"),
    "disk_full": ("sim_disk_full.py",   "磁盘空间不足", "disk_full"),
    "process":  ("sim_process_storm.py", "进程风暴", "process_storm"),
    "ui":       ("sim_ui_freeze.py",    "界面冻结", "ui_freeze(配合 cpu)"),
}


def run_simulator(sim_type, extra_args=None):
    """启动指定类型的模拟脚本"""
    if sim_type not in TYPES:
        print(f"未知模拟类型: {sim_type}, 可选: {', '.join(TYPES)}")
        return
    script = os.path.join(_SIM_DIR, TYPES[sim_type][0])
    cmd = [sys.executable, script] + (extra_args or [])
    print(f"\n启动模拟: {TYPES[sim_type][1]}(对应检测: {TYPES[sim_type][2]})")
    try:
        subprocess.call(cmd)
    except KeyboardInterrupt:
        pass
    print(f"模拟结束: {TYPES[sim_type][1]}")


def interactive():
    """交互菜单"""
    print("=" * 56)
    print("           卡死模拟器(业务功能测试)")
    print("=" * 56)
    print("  1. CPU 满载      (cpu_high)")
    print("  2. 内存占用      (mem_high / swap_high)")
    print("  3. 磁盘 IO 繁忙  (disk_busy)")
    print("  4. 磁盘空间不足  (disk_full)")
    print("  5. 进程风暴      (process_storm)")
    print("  6. 界面冻结      (ui_freeze, 配合 CPU 模拟)")
    print("  0. 退出")
    choice = input("请选择模拟类型: ").strip()
    mapping = {"1": "cpu", "2": "memory", "3": "disk_io",
               "4": "disk_full", "5": "process", "6": "ui"}
    if choice == "0":
        return
    sim_type = mapping.get(choice)
    if not sim_type:
        print("输入无效")
        return
    run_simulator(sim_type)


def main():
    parser = argparse.ArgumentParser(description="卡死模拟统一入口")
    parser.add_argument("--type", type=str, default=None,
                        help="模拟类型: cpu/memory/disk_io/disk_full/process/ui")
    parser.add_argument("--duration", type=float, default=None, help="持续秒数")
    parser.add_argument("--threads", type=int, default=None, help="CPU 线程数")
    parser.add_argument("--mb", type=int, default=None, help="内存/磁盘 MB")
    parser.add_argument("--count", type=int, default=None, help="进程数")
    args = parser.parse_args()

    if args.type:
        extra = []
        if args.duration is not None:
            extra += ["--duration", str(args.duration)]
        if args.threads is not None and args.type == "cpu":
            extra += ["--threads", str(args.threads)]
        if args.mb is not None and args.type in ("memory", "disk_io", "disk_full"):
            extra += ["--mb", str(args.mb)]
        if args.count is not None and args.type == "process":
            extra += ["--count", str(args.count)]
        run_simulator(args.type, extra)
    else:
        interactive()


if __name__ == '__main__':
    main()
