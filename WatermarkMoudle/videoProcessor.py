# -*- coding: utf-8 -*-
"""
视频水印去除主流程(videoProcessor)
==================================
输入本地视频 → 定位水印 → 逐帧跟踪/修复 → 输出无痕视频。
全程本地处理, 不上公网; 支持进度回调与取消。
"""

import os
import time

import cv2

import watermarkConfig
from watermarkDetector import (detectStaticMask, WatermarkMasker, cropTemplate,
                               bboxFromMask, trackWatermark)
from inpainter import Inpainter


def buildOutputPath(input_path, output_dir=None, suffix=None):
    """
    构造输出视频路径(输入同目录 + 后缀)
    :param input_path: 输入视频路径<str>
    :param output_dir: 输出目录, None=配置或输入同目录
    :param suffix: 输出后缀, None=配置
    :return: 输出路径<str>
    """
    out_dir = output_dir or watermarkConfig.get("output_dir") or os.path.dirname(input_path)
    out_suffix = suffix if suffix is not None else watermarkConfig.get("output_suffix")
    base, ext = os.path.splitext(os.path.basename(input_path))
    return os.path.join(out_dir, f"{base}{out_suffix}{ext or '.mp4'}")


def prepareMasker(video_path, mode="static", manual_bbox=None,
                  sample_frames=None, threshold=None, progress_callback=None):
    """
    准备水印 mask 生成器(处理前调用一次)
    :param video_path: 视频路径<str>
    :param mode: "static"(固定) / "dynamic"(逐帧跟踪)
    :param manual_bbox: 手动水印区域 (x1,y1,x2,y2), 提供时跳过自动检测
    :param sample_frames: 自动检测采样帧数, None=配置
    :param threshold: 自动检测阈值, None=配置
    :param progress_callback: 检测进度回调(percent: 0-100, info: str)
    :return: (WatermarkMasker, 水印 bbox 或 None, 说明<str>)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"无法打开视频: {video_path}")
    ret, first_frame = cap.read()
    cap.release()
    if not ret:
        raise IOError(f"读取视频首帧失败: {video_path}")

    # 手动指定水印区域
    if manual_bbox is not None:
        masker = WatermarkMasker(mode="static", bbox=manual_bbox,
                                 frame_shape=first_frame.shape)
        return masker, tuple(int(v) for v in manual_bbox), "手动指定水印区域"

    # 自动检测(时域中值)
    if progress_callback:
        progress_callback(5, "自动检测水印位置(时域中值法)...")
    inner_cb = None
    if progress_callback:
        def inner_cb(i, n):
            progress_callback(int(5 + 25 * i / n), f"水印检测采样 {i}/{n}")
    mask = detectStaticMask(
        video_path,
        sample_frames=sample_frames or int(watermarkConfig.get("median_frames")),
        threshold=threshold if threshold is not None
        else int(watermarkConfig.get("median_threshold")),
        progress_callback=inner_cb)
    bbox = bboxFromMask(mask)

    if bbox is None:
        # 未检测到水印: 返回空 masker(全流程跳过修复, 原样复制)
        if progress_callback:
            progress_callback(30, "未检测到静态水印")
        return WatermarkMasker(mode="static", mask=None), None, "未检测到静态水印"

    if mode == "dynamic":
        # 动态模式: 用首帧水印区域做模板, 逐帧跟踪
        template = cropTemplate(first_frame, bbox)
        masker = WatermarkMasker(mode="dynamic", template=template)
        note = f"检测到水印区域 {bbox}, 动态跟踪模式"
    else:
        masker = WatermarkMasker(mode="static", mask=mask)
        note = f"检测到水印区域 {bbox}, 静态模式"
    if progress_callback:
        progress_callback(30, note)
    return masker, bbox, note


def processVideo(input_path, output_path, masker, inpainter,
                 progress_callback=None, cancel_event=None):
    """
    视频水印去除主流程
    :param input_path: 输入视频路径<str>
    :param output_path: 输出视频路径<str>
    :param masker: WatermarkMasker(每帧输出 mask)
    :param inpainter: Inpainter(修复引擎)
    :param progress_callback: 进度回调(percent: 0-100, info: str)
    :param cancel_event: 取消事件<threading.Event>, 置位则中止
    :return: {"success": bool, "msg": str, "frames": int, "avg_ms": float,
              "mode": str, "cancelled": bool}
    """
    start = time.time()
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return {"success": False, "msg": f"无法打开视频: {input_path}",
                "frames": 0, "avg_ms": 0.0, "mode": inpainter.mode(),
                "cancelled": False}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 输出目录
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'),
                             fps, (w, h))
    if not writer.isOpened():
        cap.release()
        return {"success": False, "msg": f"无法创建输出视频: {output_path}",
                "frames": 0, "avg_ms": 0.0, "mode": inpainter.mode(),
                "cancelled": False}

    frames = 0
    repaired = 0
    times = []
    cancelled = False
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames += 1

            # 取消检查
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break

            # 获取水印 mask 并修复
            t0 = time.time()
            mask = masker.getMask(frame, frames - 1)
            if mask is not None and mask.any():
                frame = inpainter.inpaint(frame, mask)
                repaired += 1
            times.append((time.time() - t0) * 1000)

            writer.write(frame)

            # 进度回调(每 5 帧或每帧)
            if progress_callback and (frames % 5 == 0 or frames == total):
                percent = int(frames / total * 100) if total else 100
                progress_callback(percent, f"处理中 {frames}/{total}"
                                          f" (修复 {repaired} 帧)")
    finally:
        cap.release()
        writer.release()

    avg_ms = sum(times) / len(times) if times else 0.0
    elapsed = time.time() - start
    msg = "处理完成" if not cancelled else "用户取消"
    if cancelled:
        # 取消时删除不完整输出
        try:
            os.remove(output_path)
        except OSError:
            pass
    return {"success": not cancelled, "msg": f"{msg}({frames} 帧, 耗时 {elapsed:.1f}s)",
            "frames": frames, "avg_ms": round(avg_ms, 1),
            "mode": inpainter.mode(), "cancelled": cancelled}


# ====================================================================
# 一站式接口: 检测 + 修复 + 输出
# ====================================================================
def removeWatermark(input_path, output_path=None, mode="static",
                    manual_bbox=None, quality=None, use_gpu=None,
                    progress_callback=None, cancel_event=None):
    """
    一站式视频去水印: 定位 → 修复 → 输出
    :param input_path: 输入视频路径<str>
    :param output_path: 输出路径, None=自动生成
    :param mode: "static"/"dynamic"
    :param manual_bbox: 手动水印区域 (x1,y1,x2,y2), None=自动检测
    :param quality: "fast"/"lama", None=配置
    :param use_gpu: "auto"/"on"/"off", None=配置
    :param progress_callback: 进度回调(percent, info)
    :param cancel_event: 取消事件
    :return: 结果字典<dict>
    """
    out_path = output_path or buildOutputPath(input_path)
    quality = quality or watermarkConfig.get("quality")
    use_gpu = use_gpu or watermarkConfig.get("use_gpu")

    # 1. 定位水印
    if progress_callback:
        progress_callback(0, "准备中...")
    try:
        masker, bbox, note = prepareMasker(
            input_path, mode=mode, manual_bbox=manual_bbox,
            progress_callback=progress_callback)
    except IOError as e:
        return {"success": False, "msg": str(e), "frames": 0,
                "avg_ms": 0.0, "mode": quality, "cancelled": False}

    # 2. 修复引擎
    if progress_callback:
        progress_callback(30, f"加载修复引擎({quality})...")
    inpainter = Inpainter(mode=quality, use_gpu=use_gpu)
    if inpainter.mode() != quality:
        if progress_callback:
            progress_callback(30, f"引擎降级为 {inpainter.mode()}")

    # 3. 处理视频
    result = processVideo(input_path, out_path, masker, inpainter,
                          progress_callback=progress_callback,
                          cancel_event=cancel_event)
    result["watermark_bbox"] = bbox
    result["note"] = note
    result["output_path"] = out_path
    inpainter.close()
    return result
