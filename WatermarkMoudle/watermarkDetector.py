# -*- coding: utf-8 -*-
"""
水印定位器(watermarkDetector)
==============================
1. 静态水印: 时域中值法自动检测 mask
   原理: 静止水印像素在所有帧几乎恒定, 而背景逐帧变化;
   取 N 帧中值帧, 与单帧差异小的区域即为水印(零 AI, 快)。
2. 动态水印: 首帧定位水印(自动/手动) → 模板匹配逐帧跟踪位置
   适用滚动字幕 / 移动 LOGO。
"""

import cv2
import numpy as np


# ====================================================================
# 静态水印: 时域中值自动检测
# ====================================================================
def detectStaticMask(video_path, sample_frames=30, threshold=15,
                     progress_callback=None):
    """
    时域中值法自动检测静态水印 mask
    :param video_path: 视频路径<str>
    :param sample_frames: 采样帧数<int>, 默认 30
    :param threshold: 静止判定阈值<int>(0-255), 差异小于此值视为静止(水印)
    :param progress_callback: 进度回调(frame_index, total)
    :return: 水印 mask<np.ndarray uint8>(0/255, 与视频同尺寸), 失败返回 None
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[watermarkDetector] 无法打开视频: {video_path}")
        return None

    # 读取 N 帧(灰度)
    frames = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    count = min(sample_frames, total) if total > 0 else sample_frames
    for i in range(count):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        if progress_callback:
            progress_callback(i + 1, count)
    cap.release()

    if len(frames) < 5:
        print("[watermarkDetector] 采样帧不足, 无法检测")
        return None

    # 中值帧: 背景逐帧变化取中值, 水印静止保持原样
    stack = np.stack(frames).astype(np.float32)   # (N, H, W)
    median = np.median(stack, axis=0).astype(np.uint8)
    # 与首帧的差异: 水印区差异小(静止), 背景区差异大
    diff = cv2.absdiff(frames[0], median)
    mask = (diff < threshold).astype(np.uint8) * 255

    # 形态学清理: 去噪点 + 闭合空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 面积过滤: 过小的静止区域视为噪声
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clean = np.zeros_like(mask)
    min_area = mask.shape[0] * mask.shape[1] * 0.0005   # 0.05% 面积
    for c in contours:
        if cv2.contourArea(c) >= min_area:
            cv2.drawContours(clean, [c], -1, 255, -1)
    return clean


# ====================================================================
# 水印区域(bbox)工具
# ====================================================================
def bboxFromMask(mask):
    """
    从 mask 提取水印外接矩形
    :param mask: 水印 mask<np.ndarray uint8>
    :return: (x1, y1, x2, y2) 或 None(空 mask)
    """
    if mask is None:
        return None
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def cropTemplate(frame, bbox):
    """
    按 bbox 裁剪水印模板(动态跟踪用)
    :param frame: 帧<np.ndarray>
    :param bbox: (x1, y1, x2, y2)
    :return: 模板图<np.ndarray>
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    return frame[y1:y2, x1:x2].copy()


# ====================================================================
# 动态水印: 模板匹配逐帧跟踪
# ====================================================================
def trackWatermark(frame, template, search_margin=20, last_bbox=None):
    """
    模板匹配定位水印当前位置(动态水印逐帧跟踪)
    :param frame: 当前帧<np.ndarray BGR>
    :param template: 水印模板图<np.ndarray>(首帧裁剪)
    :param search_margin: 搜索外扩边距<int>, 以上一帧位置为中心外扩
    :param last_bbox: 上一帧水印位置 (x1,y1,x2,y2), 提供则优先在邻域搜索(防漂移)
    :return: (x1, y1, x2, y2) 或 None(未找到)
    """
    th, tw = template.shape[:2]
    fh, fw = frame.shape[:2]
    if th >= fh or tw >= fw:
        return None
    try:
        # 纯色/近纯色水印(如台标、压缩噪声)时 CCOEFF_NORMED 只测到噪声相关性,
        # 得分极低; 而 SQDIFF_NORMED 对平坦区域仍能精确命中 → 混合评分:
        #   - SQDIFF 得分极好(<0.1) 视为高置信命中, 优先采用
        #   - 否则 CCOEFF 得分 >=0.5 才采用(纹理丰富模板)
        #   - NaN 一律视为匹配失败
        def _best_in(roi, ox, oy):
            res_s = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
            min_val, _, min_loc, _ = cv2.minMaxLoc(res_s)
            res_c = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res_c)
            if min_val is not None and not np.isnan(float(min_val)) and float(min_val) < 0.10:
                return min_loc[0] + ox, min_loc[1] + oy
            if max_val is not None and not np.isnan(float(max_val)) and float(max_val) >= 0.5:
                return max_loc[0] + ox, max_loc[1] + oy
            return None

        if last_bbox is not None:
            lx1, ly1, lx2, ly2 = [int(v) for v in last_bbox]
            rx1, ry1 = max(0, lx1 - search_margin), max(0, ly1 - search_margin)
            rx2, ry2 = min(fw, lx2 + search_margin), min(fh, ly2 + search_margin)
            roi = frame[ry1:ry2, rx1:rx2]
            if roi.shape[0] >= th and roi.shape[1] >= tw:
                found = _best_in(roi, rx1, ry1)
                if found is not None:
                    x, y = found
                    return x, y, x + tw, y + th
            # 邻域未命中 → 回退全帧搜索(容忍水印跳变)
        found = _best_in(frame, 0, 0)
        if found is None:
            return None
        x, y = found
        return x, y, x + tw, y + th
    except cv2.error:
        return None


class WatermarkMasker:
    """
    水印 mask 生成器(每帧输出 mask, 供视频处理循环使用)
    =====================================================
    - 静态模式: mask 固定(自动检测或手动坐标)
    - 动态模式: 首帧模板 → 每帧模板匹配跟踪 → 生成该位置 mask
    """

    def __init__(self, mode="static", mask=None, template=None,
                 frame_shape=None, bbox=None):
        """
        :param mode: "static"(固定 mask) / "dynamic"(逐帧跟踪)
        :param mask: 静态模式的全帧 mask
        :param template: 动态模式的水印模板(首帧裁剪)
        :param frame_shape: 帧尺寸 (H, W), 静态模式生成 mask 用
        :param bbox: 手动指定水印区域 (x1,y1,x2,y2)(静态模式, 与 mask 二选一)
        """
        self._mode = mode
        self._template = template
        self._bbox = bbox
        self._last_bbox = None   # 动态跟踪: 上一帧水印位置
        if mask is not None:
            self._static_mask = mask
        elif bbox is not None and frame_shape is not None:
            h, w = frame_shape[:2]
            self._static_mask = np.zeros((h, w), dtype=np.uint8)
            x1, y1, x2, y2 = [int(v) for v in bbox]
            self._static_mask[y1:y2, x1:x2] = 255
        else:
            self._static_mask = None

    def getMask(self, frame, frame_index=0):
        """
        获取当前帧的水印 mask
        :param frame: 当前帧<np.ndarray BGR>
        :param frame_index: 帧序号<int>
        :return: mask<np.ndarray uint8>(0/255), 无法生成返回 None
        """
        if self._mode == "static":
            return self._static_mask
        # 动态: 逐帧跟踪(以上一帧位置为邻域搜索, 防漂移)
        if self._template is None or frame is None:
            return None
        bbox = trackWatermark(frame, self._template, last_bbox=self._last_bbox)
        if bbox is None:
            return None
        self._last_bbox = bbox
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        x1, y1, x2, y2 = bbox
        mask[y1:y2, x1:x2] = 255
        return mask
