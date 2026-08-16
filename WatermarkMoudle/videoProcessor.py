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
import numpy as np

import log
import watermarkConfig
from watermarkDetector import (detectWatermarkMask, refineMaskFromVideo,
                               WatermarkMasker, cropTemplate, bboxFromMask,
                               trackWatermark)
from inpainter import Inpainter


def normalizeBoxes(manual_bbox):
    """
    归一化手动区域为矩形列表(支持单个/多个)
    :param manual_bbox: (x1,y1,x2,y2) 或 [(x1,y1,x2,y2), ...]
    :return: 矩形列表<list<tuple>>
    """
    if manual_bbox is None:
        return []
    if isinstance(manual_bbox, (tuple, list)) and len(manual_bbox) == 4 \
            and all(isinstance(v, (int, float)) for v in manual_bbox):
        return [tuple(int(v) for v in manual_bbox)]
    boxes = []
    for b in manual_bbox:
        boxes.append(tuple(int(v) for v in b))
    return boxes


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
    out_path = os.path.join(out_dir, f"{base}{out_suffix}{ext or '.mp4'}")
    log.debug("videoProcessor",
              f"输出路径: {out_path}(目录 {out_dir}, 后缀 {out_suffix})")
    return out_path


def resolveOutputPath(input_path, output_path=None):
    """
    解析输出路径: 支持 文件路径 / 目录路径 / None(自动)
    :param input_path: 输入视频路径<str>
    :param output_path: None=自动 / 目录=目录内自动命名 / 文件=直接用
    :return: 输出文件路径<str>
    """
    if not output_path:
        out = buildOutputPath(input_path)
        log.info("videoProcessor", f"输出路径未指定, 自动生成: {out}")
        return out
    if os.path.isdir(output_path):
        out = buildOutputPath(input_path, output_dir=output_path)
        log.info("videoProcessor", f"输出为目录, 自动命名: {out}")
        return out
    log.info("videoProcessor", f"输出路径: {output_path}")
    return output_path


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
        log.error("videoProcessor", f"无法打开视频: {video_path}")
        raise IOError(f"无法打开视频: {video_path}")
    ret, first_frame = cap.read()
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if not ret:
        log.error("videoProcessor", f"读取视频首帧失败: {video_path}")
        raise IOError(f"读取视频首帧失败: {video_path}")
    log.info("videoProcessor",
             f"视频信息: {w}x{h}, {fps:.2f}fps, 总帧数 {total}, "
             f"模式 {mode}, 手动区域 {manual_bbox}")

    # 手动指定水印区域(支持单个/多个矩形)
    if manual_bbox is not None:
        boxes = normalizeBoxes(manual_bbox)
        if not boxes:
            raise IOError("手动水印区域为空")
        # 逐框细化(方差法收紧到水印像素本体), 并集生成 mask
        if progress_callback:
            progress_callback(8, f"细化水印区域(方差法, {len(boxes)} 块)...")
        union_mask = np.zeros(first_frame.shape[:2], dtype=np.uint8)
        refined_boxes = []
        refined_count = 0
        for i, box in enumerate(boxes):
            refined = refineMaskFromVideo(
                video_path, box,
                sample_frames=int(watermarkConfig.get("median_frames")),
                variance_ratio=float(watermarkConfig.get("variance_ratio")),
                noise_floor=float(watermarkConfig.get("noise_floor")),
                median_threshold=int(watermarkConfig.get("median_threshold")))
            if refined is not None:
                union_mask = cv2.bitwise_or(union_mask, refined)
                refined_boxes.append(bboxFromMask(refined))
                refined_count += 1
                log.info("videoProcessor",
                         f"框 {i + 1} 细化成功: {bboxFromMask(refined)}")
            else:
                x1, y1, x2, y2 = box
                union_mask[y1:y2, x1:x2] = 255
                refined_boxes.append(box)
                log.warn("videoProcessor",
                         f"框 {i + 1} 细化失败, 回退矩形: {box}")
        if union_mask.any():
            masker = WatermarkMasker(mode="static", mask=union_mask)
            note = (f"手动指定水印区域({len(boxes)} 块, "
                    f"{refined_count} 块已细化)")
            log.info("videoProcessor",
                     f"手动区域并集: {bboxFromMask(union_mask)}, {note}")
            return masker, bboxFromMask(union_mask), note
        masker = WatermarkMasker(mode="static", bbox=boxes[0],
                                 frame_shape=first_frame.shape)
        log.info("videoProcessor", f"手动指定水印区域: {boxes[0]}")
        return masker, boxes[0], "手动指定水印区域"

    # 自动检测(组合: 中值法+方差法, 覆盖不透明/半透明水印)
    if progress_callback:
        progress_callback(5, "自动检测水印位置(中值+方差组合法)...")
    inner_cb = None
    if progress_callback:
        def inner_cb(i, n):
            progress_callback(int(5 + 25 * i / n), f"水印检测采样 {i}/{n}")
    mask, detect_note = detectWatermarkMask(
        video_path,
        sample_frames=sample_frames or int(watermarkConfig.get("median_frames")),
        threshold=threshold if threshold is not None
        else int(watermarkConfig.get("median_threshold")),
        variance_ratio=float(watermarkConfig.get("variance_ratio")),
        noise_floor=float(watermarkConfig.get("noise_floor")),
        progress_callback=inner_cb)
    bbox = bboxFromMask(mask)

    if bbox is None:
        # 未检测到水印: 返回空 masker(全流程跳过修复, 原样复制)
        log.warn("videoProcessor", f"未检测到水印({detect_note})")
        if progress_callback:
            progress_callback(30, f"未检测到水印({detect_note})")
        return WatermarkMasker(mode="static", mask=None), None, detect_note

    if mode == "dynamic":
        # 动态模式: 用首帧水印区域做模板, 逐帧跟踪
        template = cropTemplate(first_frame, bbox)
        masker = WatermarkMasker(mode="dynamic", template=template)
        note = f"检测到水印区域 {bbox}, 动态跟踪模式"
        log.info("videoProcessor",
                 f"动态模式: 首帧裁剪模板 {template.shape[1]}x{template.shape[0]}, "
                 f"逐帧跟踪")
    else:
        masker = WatermarkMasker(mode="static", mask=mask)
        note = f"检测到水印区域 {bbox}, 静态模式"
        log.info("videoProcessor", f"静态模式: 水印区域 {bbox}")
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
        log.error("videoProcessor", f"无法打开视频: {input_path}")
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
        log.error("videoProcessor", f"无法创建输出视频: {output_path}")
        return {"success": False, "msg": f"无法创建输出视频: {output_path}",
                "frames": 0, "avg_ms": 0.0, "mode": inpainter.mode(),
                "cancelled": False}
    log.info("videoProcessor",
             f"开始处理: {input_path} → {output_path} "
             f"({total} 帧, {w}x{h}, {fps:.2f}fps, 引擎 {inpainter.mode()})")

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
                log.warn("videoProcessor", f"收到取消请求, 第 {frames} 帧中止")
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

            # 周期统计日志(每 100 帧): 平均耗时/修复帧数/吞吐
            if frames % 100 == 0:
                avg = sum(times) / len(times)
                elapsed = time.time() - start
                log.info("videoProcessor",
                         f"[{frames}/{total}] 平均帧耗时 {avg:.1f}ms, "
                         f"修复 {repaired} 帧, 吞吐 {frames / elapsed:.1f} fps")

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
    log.info("videoProcessor",
             f"{msg}: {frames} 帧, 耗时 {elapsed:.1f}s, 平均 {avg_ms:.1f}ms/帧, "
             f"修复 {repaired} 帧, 吞吐 {frames / elapsed if elapsed else 0:.1f} fps")
    if cancelled:
        # 取消时删除不完整输出
        try:
            os.remove(output_path)
            log.info("videoProcessor", f"已删除不完整输出: {output_path}")
        except OSError as e:
            log.warn("videoProcessor", f"删除不完整输出失败: {e}")
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
    :param output_path: None=自动 / 目录路径=目录内自动命名 / 文件路径=直接用
    :param mode: "static"/"dynamic"
    :param manual_bbox: 手动水印区域 (x1,y1,x2,y2) 或矩形列表(多选),
                        None=自动检测
    :param quality: "fast"/"lama", None=配置
    :param use_gpu: "auto"/"on"/"off", None=配置
    :param progress_callback: 进度回调(percent, info)
    :param cancel_event: 取消事件
    :return: 结果字典<dict>
    """
    log.info("videoProcessor", "=" * 56)
    log.info("videoProcessor", f"去水印任务启动: {input_path}")
    log.info("videoProcessor",
             f"参数: mode={mode}, quality={quality or '默认'}, "
             f"use_gpu={use_gpu or '默认'}, manual_bbox={manual_bbox}")
    out_path = resolveOutputPath(input_path, output_path)
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
        log.error("videoProcessor", f"定位水印失败: {e}")
        return {"success": False, "msg": str(e), "frames": 0,
                "avg_ms": 0.0, "mode": quality, "cancelled": False}

    # 2. 修复引擎
    if progress_callback:
        progress_callback(30, f"加载修复引擎({quality})...")
    inpainter = Inpainter(mode=quality, use_gpu=use_gpu)
    if inpainter.mode() != quality:
        log.warn("videoProcessor",
                 f"引擎降级: 请求 {quality} → 实际 {inpainter.mode()}")
        if progress_callback:
            progress_callback(30, f"引擎降级为 {inpainter.mode()}")

    # 3. 处理视频
    result = processVideo(input_path, out_path, masker, inpainter,
                          progress_callback=progress_callback,
                          cancel_event=cancel_event)
    # 动态模式: 附加跟踪统计
    if mode == "dynamic":
        stats = masker.trackStats()
        result["track_stats"] = stats
        log.info("videoProcessor",
                 f"动态跟踪统计: 共 {stats['total']} 帧, 命中 {stats['hit']}, "
                 f"丢失 {stats['miss']}(命中率 {stats['hit_rate']}%)")
    result["watermark_bbox"] = bbox
    result["note"] = note
    result["output_path"] = out_path
    inpainter.close()
    log.info("videoProcessor", f"任务结束: {result}")
    return result
