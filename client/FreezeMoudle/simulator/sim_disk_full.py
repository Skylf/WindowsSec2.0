# -*- coding: utf-8 -*-
"""
磁盘空间不足模拟器(sim_disk_full)
==================================
在指定位置写入大文件占用磁盘空间(对应检测维度: disk_full 磁盘空间不足)。
用于测试卡死检测器的磁盘空间报警是否触发。

⚠ 危险警告: 磁盘写满会导致系统异常, 请:
  1. 默认写入系统 temp 目录(可安全删除), 大小从 200MB 起步
  2. 指定 --path 到测试盘符时务必确认空间充足且文件可删
  3. 程序结束会自动删除生成的文件

用法:
  python simulator/sim_disk_full.py --mb 200 --duration 20
参数:
  --mb       占用空间 MB(默认 200)
  --duration 保持秒数(默认 20, 结束后自动删除)
  --path     写入路径(默认 系统 temp 目录下 freeze_sim_full.tmp)
"""
import argparse
import os
import tempfile
import time


class DiskFiller:
    """磁盘空间模拟"""

    def __init__(self, mb=200, path=None):
        self._mb = max(16, mb)
        self._path = path or os.path.join(tempfile.gettempdir(), "freeze_sim_full.tmp")

    def start(self):
        """写入大文件"""
        written = 0
        print(f"[sim_disk_full] 写入 {self._mb} MB 到: {self._path}")
        with open(self._path, 'wb') as f:
            chunk = bytearray(1024 * 1024)
            while written < self._mb:
                f.write(chunk)
                written += 1
                if written % 64 == 0:
                    print(f"[sim_disk_full] 已写入 {written} MB...")
        print(f"[sim_disk_full] 完成 {written} MB, 保持中(结束后自动删除)")

    def stop(self):
        """删除生成文件, 释放空间"""
        try:
            os.remove(self._path)
            print("[sim_disk_full] 已删除生成文件, 空间已释放")
        except OSError as e:
            print(f"[sim_disk_full] 删除文件失败(请手动清理 {self._path}): {e}")


def main():
    parser = argparse.ArgumentParser(description="磁盘空间不足模拟器(⚠ 谨慎)")
    parser.add_argument("--mb", type=int, default=200, help="占用空间 MB(默认 200)")
    parser.add_argument("--duration", type=float, default=20.0, help="保持秒数(默认 20)")
    parser.add_argument("--path", type=str, default=None, help="写入路径")
    args = parser.parse_args()

    filler = DiskFiller(mb=args.mb, path=args.path)
    filler.start()
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        filler.stop()


if __name__ == '__main__':
    main()
