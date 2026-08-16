# -*- coding: utf-8 -*-
"""
视频去水印命令行全流程 (runTest)
=================================
交互式菜单 + 命令行参数两种模式:

    python WatermarkMoudle/runTest.py                     # 交互式菜单
    python WatermarkMoudle/runTest.py --once <视频路径>     # 一键处理(默认参数)
    python WatermarkMoudle/runTest.py --once <视频路径> --mode dynamic --quality lama \
        --gpu on --output out.mp4                          # 全参数

全程本地处理, 不上公网。LaMa 模型缺失时自动降级 fast 模式。
"""
import argparse
import os
import sys
import threading

# 保证直接运行时可导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import log
import watermarkConfig
import gpuDetector
from videoProcessor import removeWatermark, buildOutputPath


# ====================================================================
# 命令行模式
# ====================================================================
def runOnce(args):
    """一键处理: --once 入口"""
    input_path = args.once
    if not os.path.isfile(input_path):
        print(f"[错误] 输入文件不存在: {input_path}")
        return 1
    ext = os.path.splitext(input_path)[1].lower()
    if ext not in (".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".ts"):
        print(f"[警告] 输入不是常见视频格式: {input_path}")

    print("=" * 56)
    print(f"输入: {input_path}")
    print(f"模式: {args.mode} | 质量: {args.quality or '默认'} | GPU: {args.gpu or '默认'}")
    print("=" * 56)

    # 进度显示(整行里程碑, 避免 \r 与日志行互相覆盖)
    last_milestone = -1

    def on_progress(percent, info):
        nonlocal last_milestone
        pct = int(percent)
        if pct != last_milestone and (pct % 10 == 0 or pct >= 100):
            last_milestone = pct
            log.info("runTest", f"[进度 {pct:3d}%] {info}")

    cancel_event = threading.Event()
    result = removeWatermark(
        input_path,
        output_path=args.output,
        mode=args.mode,
        manual_bbox=args.bbox,
        quality=args.quality,
        use_gpu=args.gpu,
        progress_callback=on_progress,
        cancel_event=cancel_event,
    )
    print()
    if result["success"]:
        print(f"[完成] {result['msg']}")
        print(f"  输出: {result['output_path']}")
        if result["watermark_bbox"]:
            print(f"  水印区域: {result['watermark_bbox']} | 说明: {result['note']}")
        else:
            print(f"  未检测到水印(原样复制): {result['note']}")
        print(f"  引擎: {result['mode']} | 平均帧耗时: {result['avg_ms']}ms")
        return 0
    print(f"[失败] {result['msg']}")
    return 1


# ====================================================================
# 交互式菜单
# ====================================================================
def interactive():
    print("=" * 56)
    print("视频去水印命令行工具 (WatermarkMoudle)")
    print("=" * 56)

    # 环境信息
    info = gpuDetector.detectGpu()
    cfg = watermarkConfig.load()
    print(f"CUDA 可用: {info['cuda_available']}")
    print(f"当前配置: 质量={cfg.get('quality')} | GPU={cfg.get('use_gpu')} | "
          f"采样帧={cfg.get('median_frames')} | 阈值={cfg.get('median_threshold')}")

    while True:
        print()
        print("1. 处理单个视频")
        print("2. 修改配置(质量/GPU/检测参数)")
        print("3. 查看 GPU/运行环境")
        print("0. 退出")
        choice = input("请选择: ").strip()
        if choice == "0":
            break
        if choice == "1":
            path = input("输入视频路径: ").strip().strip('"')
            if not os.path.isfile(path):
                print("[错误] 文件不存在")
                continue
            mode = input("水印类型 [static/dynamic] (回车=static): ").strip() or "static"
            quality = input(f"修复质量 [fast/lama] (回车={cfg.get('quality')}): ").strip() \
                or cfg.get("quality")
            gpu = input(f"GPU [auto/on/off] (回车={cfg.get('use_gpu')}): ").strip() \
                or cfg.get("use_gpu")
            output = input("输出路径或文件夹 (回车=自动生成): ").strip().strip('"') or None

            print(f"\n开始处理: {path} ({mode}/{quality}/{gpu})...")
            result = removeWatermark(path, output_path=output, mode=mode,
                                     quality=quality, use_gpu=gpu)
            if result["success"]:
                print(f"[完成] {result['msg']}")
                print(f"  输出: {result['output_path']} | 水印区域: {result['watermark_bbox']} "
                      f"| 说明: {result['note']}")
            else:
                print(f"[失败] {result['msg']}")
        elif choice == "2":
            editConfig()
        elif choice == "3":
            print(gpuDetector.summary())


def editConfig():
    cfg = watermarkConfig.load()
    print("当前配置:")
    for k, v in cfg.items():
        print(f"  {k} = {v}")
    print("(直接回车保持不变)")
    q = input(f"quality [fast/lama] (当前 {cfg['quality']}): ").strip()
    if q in ("fast", "lama"):
        cfg["quality"] = q
    g = input(f"use_gpu [auto/on/off] (当前 {cfg['use_gpu']}): ").strip()
    if g in ("auto", "on", "off"):
        cfg["use_gpu"] = g
    m = input(f"median_frames (当前 {cfg['median_frames']}): ").strip()
    if m.isdigit() and int(m) > 0:
        cfg["median_frames"] = int(m)
    t = input(f"median_threshold (当前 {cfg['median_threshold']}): ").strip()
    if t.isdigit():
        cfg["median_threshold"] = int(t)
    watermarkConfig.save(cfg)
    print("配置已保存:", watermarkConfig.config_path())


def main():
    parser = argparse.ArgumentParser(description="视频水印去除(本地离线)")
    parser.add_argument("--once", metavar="视频路径", help="一键处理模式")
    parser.add_argument("--mode", choices=["static", "dynamic"], default="static",
                        help="水印类型: static=静止 / dynamic=动态跟踪")
    parser.add_argument("--quality", choices=["fast", "lama"], default=None,
                        help="修复质量(默认取配置)")
    parser.add_argument("--gpu", choices=["auto", "on", "off"], default=None,
                        help="GPU 开关(默认取配置)")
    parser.add_argument("--output", help="输出文件路径或输出文件夹(默认输入同目录加后缀)")
    parser.add_argument("--bbox", type=lambda s: tuple(int(v) for v in
                        s.replace("(", "").replace(")", "").split(",")),
                        help="手动水印区域 x1,y1,x2,y2(跳过自动检测)")
    parser.add_argument("--debug", action="store_true",
                        help="输出 DEBUG 级详细日志(模板匹配得分/逐帧跟踪等)")
    args = parser.parse_args()

    if args.debug:
        log.set_debug(True)
        log.info("runTest", "DEBUG 日志已开启(WM_DEBUG=1)")

    if args.once:
        return runOnce(args)
    interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
