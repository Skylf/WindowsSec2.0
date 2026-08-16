# -*- coding: utf-8 -*-
"""
进程风暴模拟器(sim_process_storm)
==================================
一次性启动大量子进程(对应检测维度: process_storm 进程数量异常)。
用于测试卡死检测器的进程数量报警是否触发。

用法:
  python simulator/sim_process_storm.py --count 100 --duration 15
参数:
  --count    启动的子进程数(默认 100)
  --duration 保持秒数(默认 15, 结束后自动终止全部子进程)
"""
import argparse
import subprocess
import sys
import time


class ProcessStorm:
    """进程风暴模拟"""

    def __init__(self, count=100, duration=15):
        self._count = max(5, count)
        self._duration = max(1, duration)
        self._procs = []

    def start(self):
        """启动 N 个子进程(每个睡眠 duration+10 秒后自然退出)"""
        print(f"[sim_process_storm] 启动 {self._count} 个子进程...")
        code = f"import time; time.sleep({self._duration + 10})"
        for i in range(self._count):
            try:
                self._procs.append(
                    subprocess.Popen([sys.executable, "-c", code],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL))
            except OSError as e:
                print(f"[sim_process_storm] 第 {i} 个启动失败: {e}")
                break
        print(f"[sim_process_storm] 已启动 {len(self._procs)} 个子进程")

    def stop(self):
        """终止全部子进程"""
        for p in self._procs:
            try:
                p.terminate()
            except OSError:
                pass
        for p in self._procs:
            try:
                p.wait(timeout=3)
            except Exception:
                pass
        print(f"[sim_process_storm] 已终止 {len(self._procs)} 个子进程")


def main():
    parser = argparse.ArgumentParser(description="进程风暴模拟器")
    parser.add_argument("--count", type=int, default=100, help="子进程数(默认 100)")
    parser.add_argument("--duration", type=float, default=15.0, help="保持秒数(默认 15)")
    args = parser.parse_args()

    storm = ProcessStorm(count=args.count, duration=int(args.duration))
    storm.start()
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        storm.stop()


if __name__ == '__main__':
    main()
