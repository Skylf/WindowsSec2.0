# -*- coding: utf-8 -*-
"""
CPU 满载模拟器(sim_cpu)
========================
启动 N 个线程死循环, 占满 CPU(对应检测维度: cpu_high CPU 满载)。
用于测试卡死检测器的 CPU 报警是否触发。

用法:
  python simulator/sim_cpu.py --threads 4 --duration 10
参数:
  --threads  占用的线程数(默认 = CPU 核心数)
  --duration 持续秒数(默认 10)
"""
import argparse
import os
import threading
import time

import numpy as np


class CpuBurner:
    """多线程 CPU 满载模拟(每线程用 numpy 密集计算, 释放 GIL 吃满一核)"""

    def __init__(self, threads=None):
        self._threads = threads if threads else os.cpu_count() or 4
        self._stop = threading.Event()
        self._workers = []

    def start(self):
        """启动烧 CPU 线程"""
        self._stop.clear()
        for _ in range(self._threads):
            t = threading.Thread(target=self._burn, daemon=True)
            t.start()
            self._workers.append(t)
        print(f"[sim_cpu] 已启动 {self._threads} 个线程烧 CPU"
              f"(numpy 计算, 约占 {self._threads} 核)")

    def _burn(self):
        """
        死循环 numpy 矩阵乘法:
        numpy 底层计算释放 GIL → 每个线程真实吃满一个 CPU 核心
        (纯 Python 死循环受 GIL 限制, 多线程只能占 1 核)
        """
        a = np.random.rand(256, 256)
        b = np.random.rand(256, 256)
        while not self._stop.is_set():
            np.dot(a, b)

    def stop(self):
        """停止烧 CPU"""
        self._stop.set()
        for t in self._workers:
            t.join(timeout=1)
        print("[sim_cpu] 已停止")


def main():
    parser = argparse.ArgumentParser(description="CPU 满载模拟器")
    parser.add_argument("--threads", type=int, default=None,
                        help="占用线程数(默认=CPU核心数)")
    parser.add_argument("--duration", type=float, default=10.0,
                        help="持续秒数(默认 10)")
    args = parser.parse_args()

    burner = CpuBurner(threads=args.threads)
    burner.start()
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        burner.stop()


if __name__ == '__main__':
    main()
