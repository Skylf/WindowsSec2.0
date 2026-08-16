# -*- coding: utf-8 -*-
"""
内存占用模拟器(sim_memory)
============================
持续分配内存并保持(对应检测维度: mem_high 内存过高 / swap_high 页面文件)。
用于测试卡死检测器的内存报警是否触发。

⚠ 危险警告: 内存占用过大会导致系统严重卡顿甚至无响应,
  请从较小值开始(--mb 256), 观察检测器报警后及时停止。

用法:
  python simulator/sim_memory.py --mb 512 --duration 15
参数:
  --mb       占用内存大小(单位 MB, 默认 512, 请谨慎)
  --duration 保持秒数(默认 15)
"""
import argparse
import time

# 单块大小: 16MB
_CHUNK_MB = 16


class MemoryHog:
    """内存占用模拟"""

    def __init__(self, mb=512):
        self._mb = max(16, mb)
        self._chunks = []

    def start(self):
        """分配内存并保持"""
        total = 0
        while total < self._mb:
            self._chunks.append(bytearray(_CHUNK_MB * 1024 * 1024))
            total += _CHUNK_MB
            print(f"[sim_memory] 已占用 {total} MB...", end="\r", flush=True)
            time.sleep(0.05)
        print(f"\n[sim_memory] 已占用 {total} MB, 保持中(按 Ctrl+C 释放)")

    def stop(self):
        """释放内存"""
        self._chunks.clear()
        print("[sim_memory] 已释放内存")


def main():
    parser = argparse.ArgumentParser(description="内存占用模拟器(⚠ 谨慎设置大小)")
    parser.add_argument("--mb", type=int, default=512, help="占用内存 MB(默认 512)")
    parser.add_argument("--duration", type=float, default=15.0, help="保持秒数(默认 15)")
    args = parser.parse_args()

    hog = MemoryHog(mb=args.mb)
    hog.start()
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        hog.stop()


if __name__ == '__main__':
    main()
