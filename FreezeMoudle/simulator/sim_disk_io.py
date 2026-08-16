# -*- coding: utf-8 -*-
"""
磁盘 IO 繁忙模拟器(sim_disk_io)
================================
循环读写临时文件, 制造持续磁盘读写(对应检测维度: disk_busy 磁盘 IO 繁忙)。
用于测试卡死检测器的磁盘 IO 报警是否触发。

用法:
  python simulator/sim_disk_io.py --mb 64 --duration 15
参数:
  --mb       每轮读写数据量(单位 MB, 默认 64)
  --duration 持续秒数(默认 15)
  --path     临时文件路径(默认 系统 temp 目录下 freeze_sim_io.tmp)
"""
import argparse
import os
import tempfile
import time


class DiskIoLoader:
    """磁盘 IO 模拟"""

    def __init__(self, mb=64, path=None):
        self._mb = max(1, mb)
        self._path = path or os.path.join(tempfile.gettempdir(), "freeze_sim_io.tmp")
        # 预生成数据块(1MB), 避免随机生成拖慢
        self._data = bytearray(1024 * 1024)

    def start(self):
        """循环读写制造 IO 压力"""
        print(f"[sim_disk_io] 开始循环读写: {self._path} (每轮 {self._mb} MB)")
        while True:
            try:
                with open(self._path, 'wb') as f:
                    for _ in range(self._mb):
                        f.write(self._data)
                with open(self._path, 'rb') as f:
                    while f.read(1024 * 1024):
                        pass
            except OSError as e:
                print(f"[sim_disk_io] 读写失败: {e}")
                break

    def stop(self):
        """清理临时文件"""
        try:
            os.remove(self._path)
        except OSError:
            pass
        print("[sim_disk_io] 已停止并清理临时文件")


def main():
    parser = argparse.ArgumentParser(description="磁盘 IO 繁忙模拟器")
    parser.add_argument("--mb", type=int, default=64, help="每轮读写 MB(默认 64)")
    parser.add_argument("--duration", type=float, default=15.0, help="持续秒数(默认 15)")
    parser.add_argument("--path", type=str, default=None, help="临时文件路径")
    args = parser.parse_args()

    loader = DiskIoLoader(mb=args.mb, path=args.path)
    import threading
    worker = threading.Thread(target=loader.start, daemon=True)
    worker.start()
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        loader.stop()


if __name__ == '__main__':
    main()
