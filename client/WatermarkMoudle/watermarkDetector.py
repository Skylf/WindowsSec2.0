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

import log


# ====================================================================
# 静态水印: 时域中值自动检测
# ====================================================================
# 面积过滤参数
MIN_AREA_RATIO = 0.0001    # 最小静止块面积: 0.01% 帧面积(边缘先验已滤内部噪声, 可更小)
MAX_AREA_RATIO = 0.15      # 最大静止块面积: 15% 帧面积(再大视为静止主体/背景)
MAX_TOTAL_RATIO = 0.25     # 静止块总面积上限: 25%(超出视为整屏静止, 拒检)


def _sampleFrames(video_path, count, progress_callback=None):
    """
    全片均匀采样帧(灰度), 避免只采片头导致静态场景误判为水印
    :param video_path: 视频路径<str>
    :param count: 期望采样帧数<int>
    :param progress_callback: 进度回调(i, total)
    :return: (帧列表<list<np.ndarray>>, 视频信息 dict)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log.error("watermarkDetector", f"无法打开视频: {video_path}")
        return None, None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    info = {"total": total, "fps": cap.get(cv2.CAP_PROP_FPS),
            "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    count = min(count, total) if total > 0 else count

    frames = []
    if total > count:
        # 均匀跳帧采样(随机场景均覆盖)
        indices = np.linspace(0, total - 1, count).astype(int)
        for i, idx in enumerate(indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret:
                log.warn("watermarkDetector",
                         f"跳帧读取失败(第 {idx} 帧), 回退顺序采样")
                frames = []
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            if progress_callback:
                progress_callback(i + 1, count)
        if not frames:
            # 回退: 顺序均匀采样(部分编码不支持随机跳帧)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            step = max(1, total // count)
            pos = 0
            for i in range(count):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                if progress_callback:
                    progress_callback(i + 1, count)
                pos += step
    else:
        # 视频很短: 顺序读取全部
        for i in range(count):
            ret, frame = cap.read()
            if not ret:
                log.warn("watermarkDetector", f"第 {i} 帧读取失败, 提前结束采样")
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            if progress_callback:
                progress_callback(i + 1, count)
    cap.release()
    return frames, info


def detectStaticMask(video_path, sample_frames=30, threshold=15,
                     progress_callback=None):
    """
    时域中值法自动检测静态水印 mask
    原理: 水印像素全片恒定; 背景随场景/运动变化。
    采样帧均匀分布全片(不是片头 30 帧), 场景切换后只有真水印保持静止;
    静止块超过帧面积 25% 视为静止背景并剔除(防整屏误判)。
    :param video_path: 视频路径<str>
    :param sample_frames: 采样帧数<int>, 默认 30(均匀分布全片)
    :param threshold: 静止判定阈值<int>(0-255), 差异小于此值视为静止(水印)
    :param progress_callback: 进度回调(frame_index, total)
    :return: 水印 mask<np.ndarray uint8>(0/255, 与视频同尺寸), 失败返回 None
    """
    log.info("watermarkDetector", f"开始静态水印检测: {video_path} "
                                  f"(采样 {sample_frames} 帧, 阈值 {threshold})")
    frames, info = _sampleFrames(video_path, sample_frames, progress_callback)
    if info is None:
        return None
    log.info("watermarkDetector",
             f"视频信息: {info['w']}x{info['h']}, {info['fps']:.2f}fps, "
             f"总帧数 {info['total']}")

    if not frames or len(frames) < 5:
        log.error("watermarkDetector", f"采样帧不足({len(frames)}), 无法检测")
        return None

    # 中值帧: 背景逐帧变化取中值, 水印静止保持原样
    log.debug("watermarkDetector", f"采样完成 {len(frames)} 帧, 计算时域中值帧...")
    stack = np.stack(frames).astype(np.float32)   # (N, H, W)
    median = np.median(stack, axis=0).astype(np.uint8)
    # 与首帧的差异: 水印区差异小(静止), 背景区差异大
    diff = cv2.absdiff(frames[0], median)
    mask = (diff < threshold).astype(np.uint8) * 255
    raw_ratio = float(mask.mean() / 255.0)
    log.debug("watermarkDetector",
              f"原始静止区占比 {raw_ratio * 100:.2f}%(阈值 {threshold})")

    # 形态学清理: 去噪点 + 闭合空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 面积过滤: 过小=噪声, 过大=静止背景, 均剔除
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clean = np.zeros_like(mask)
    frame_area = mask.shape[0] * mask.shape[1]
    min_area = frame_area * MIN_AREA_RATIO
    max_area = frame_area * MAX_AREA_RATIO
    kept = 0
    kept_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if min_area <= area <= max_area:
            cv2.drawContours(clean, [c], -1, 255, -1)
            kept += 1
            kept_area += area
    kept_ratio = kept_area / frame_area if frame_area else 0.0
    # 静止总面积过大 → 整屏/大半屏静止(静态场景), 拒绝检测
    if kept_ratio > MAX_TOTAL_RATIO:
        log.warn("watermarkDetector",
                 f"静止块总面积占比 {kept_ratio * 100:.1f}% > "
                 f"{MAX_TOTAL_RATIO * 100:.0f}%(疑似整屏静止背景), 拒绝检测")
        return None
    bbox = bboxFromMask(clean)
    log.info("watermarkDetector",
             f"检测完成: 轮廓 {len(contours)} 个, 保留 {kept} 个"
             f"(面积 {min_area:.0f}~{max_area:.0f}px), 最终水印占比 "
             f"{kept_ratio * 100:.2f}%, 区域 {bbox}")
    return clean


def _filterContours(mask):
    """
    轮廓面积过滤(过小=噪声, 过大=静止主体/背景)
    :param mask: 原始候选 mask<np.ndarray uint8>
    :return: (清理后 mask, 保留轮廓数, 保留面积占比)
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    clean = np.zeros_like(mask)
    frame_area = mask.shape[0] * mask.shape[1]
    min_area = frame_area * MIN_AREA_RATIO
    max_area = frame_area * MAX_AREA_RATIO
    kept = 0
    kept_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if min_area <= area <= max_area:
            cv2.drawContours(clean, [c], -1, 255, -1)
            kept += 1
            kept_area += area
    ratio = kept_area / frame_area if frame_area else 0.0
    return clean, kept, ratio


def _edgePrior(mask, zone_ratio=0.12):
    """
    边缘先验: 只保留与画面边缘带相交的候选块
    视频水印(台标/角标/半透明文字)几乎总在边缘 12% 带内,
    画面内部的静止物/低方差区域多为内容, 直接剔除。
    :param mask: 候选 mask<np.ndarray uint8>
    :param zone_ratio: 边缘带宽度占比(0-1)
    :return: 过滤后的 mask<np.ndarray uint8>
    """
    h, w = mask.shape
    zone = max(24, int(min(h, w) * zone_ratio))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    out = np.zeros_like(mask)
    kept = 0
    for i in range(1, num):
        bx, by, bw, bh = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], \
                         stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if bx < zone or by < zone or bx + bw > w - zone or by + bh > h - zone:
            out[labels == i] = 255
            kept += 1
    log.debug("watermarkDetector",
              f"边缘先验: {num - 1} 个候选块 → 保留 {kept} 个(边缘带 {zone}px)")
    return out


# ====================================================================
# 半透明水印: 时域方差法检测
# ====================================================================
def _varianceCandidates(stack, variance_ratio=0.75, noise_floor=4.0):
    """
    时域方差候选(核心统计): 噪声底 < std < 局部背景方差 × variance_ratio
    半透明水印像素方差 = (1-α)²·σ_BG², 介于背景与静止物之间。
    局部背景方差用大核均值滤波估计:
      - 均值把 std 估计的采样波动平均掉(背景 ratio 稳定 ≈ 1, 不会误入)
      - 文字像素占比小时对均值影响有限(文字 ratio 仍 ≈ 1-α < 阈值)
      - 中值/最大值滤波分别会被密集文字污染 / 被估计噪声放大
    :param stack: 灰度帧堆叠 (N,H,W) float32
    :param variance_ratio: 方差比阈值(0-1)
    :param noise_floor: 噪声底
    :return: 候选 mask<np.ndarray bool>
    """
    std = np.std(stack, axis=0)
    k = max(15, min(std.shape) // 24) | 1
    kernel = np.ones((k, k), dtype=np.float32) / (k * k)
    local_bg = cv2.filter2D(std, -1, kernel, borderType=cv2.BORDER_REFLECT)
    return (std > noise_floor) & (std < local_bg * variance_ratio)


def detectTransparentMask(video_path, sample_frames=30, variance_ratio=0.75,
                          noise_floor=4.0, progress_callback=None):
    """
    时域方差法检测半透明水印 mask
    原理: 半透明水印像素 = α·WM + (1-α)·BG, 其时域方差 = (1-α)²·σ_BG²
      - 背景像素:   方差 ≈ 局部背景方差(σ_BG, 运动/场景变化)
      - 半透明水印: 方差 = (1-α)²·σ_BG², 显著低于局部背景但仍高于噪声
      - 静止物体:   方差 ≈ 0(低于噪声底)
    判定: 噪声底 < 时域方差 < 局部背景方差 × variance_ratio → 水印候选
    :param video_path: 视频路径<str>
    :param sample_frames: 采样帧数<int>(均匀分布全片)
    :param variance_ratio: 方差比阈值<float>(0-1, 越小越严格, 0.75≈α≥0.25)
    :param noise_floor: 噪声底<float>(低于此方差视为静止物体, 剔除)
    :param progress_callback: 进度回调(i, total)
    :return: 水印 mask<np.ndarray uint8> 或 None
    """
    log.info("watermarkDetector",
             f"开始半透明水印检测(方差法): {video_path} "
             f"(采样 {sample_frames} 帧, 方差比 {variance_ratio}, "
             f"噪声底 {noise_floor})")
    frames, info = _sampleFrames(video_path, sample_frames, progress_callback)
    if info is None or not frames or len(frames) < 5:
        log.error("watermarkDetector", f"采样帧不足, 无法检测")
        return None

    stack = np.stack(frames).astype(np.float32)        # (N,H,W)
    cand = _varianceCandidates(stack, variance_ratio, noise_floor)
    mask = cand.astype(np.uint8) * 255
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k5)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k5)
    mask = _edgePrior(mask)

    clean, kept, ratio = _filterContours(mask)
    if kept == 0 or ratio > MAX_TOTAL_RATIO:
        log.info("watermarkDetector", "方差法: 未检测到半透明水印")
        return None
    bbox = bboxFromMask(clean)
    log.info("watermarkDetector",
             f"方差法检测完成: 保留 {kept} 个区域, 占比 {ratio * 100:.2f}%, "
             f"区域 {bbox}")
    return clean


# ====================================================================
# 组合检测: 中值法(不透明) + 方差法(半透明) → 并集
# ====================================================================
def refineMaskFromVideo(video_path, bbox, sample_frames=20,
                        variance_ratio=0.75, noise_floor=4.0,
                        median_threshold=15, progress_callback=None):
    """
    手动框内水印 mask 细化(方差法 + 中值法)
    用户圈定一个宽松区域后, 把 mask 收紧到真正的水印像素本体:
      - 半透明水印: 时域方差介于背景与噪声之间(方差法)
      - 不透明水印/静止图形: 与中值帧差异小(中值法)
    只修复这些像素, 周边背景保持原样 → 修复痕迹更小。
    :param video_path: 视频路径<str>
    :param bbox: 手动圈定区域 (x1,y1,x2,y2)
    :param sample_frames: 采样帧数<int>
    :param variance_ratio: 方差比阈值<float>
    :param noise_floor: 噪声底<float>
    :param median_threshold: 静止判定阈值<int>(0-255)
    :param progress_callback: 进度回调(i, total)
    :return: 细化后的 mask<np.ndarray uint8> 或 None(细化失败, 回退矩形)
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    if x2 <= x1 or y2 <= y1:
        return None
    log.info("watermarkDetector",
             f"手动框细化: 区域 {bbox}(方差比 {variance_ratio}, "
             f"噪声底 {noise_floor}, 中值阈值 {median_threshold})")
    frames, info = _sampleFrames(video_path, sample_frames, progress_callback)
    if info is None or not frames or len(frames) < 5:
        return None
    h, w = info["h"], info["w"]
    # 外扩分析边距(水印边缘像素需要邻域上下文)
    m = 16
    ax1, ay1 = max(0, x1 - m), max(0, y1 - m)
    ax2, ay2 = min(w, x2 + m), min(h, y2 + m)

    stack = np.stack(frames).astype(np.float32)
    # ── 半透明水印: 方差候选(介于背景与噪声之间) ──
    std = np.std(stack, axis=0)
    zone = std[ay1:ay2, ax1:ax2]
    k = max(15, min(zone.shape) // 24) | 1
    kernel = np.ones((k, k), dtype=np.float32) / (k * k)
    local_bg = cv2.filter2D(zone, -1, kernel, borderType=cv2.BORDER_REFLECT)
    cand_var = (zone > noise_floor) & (zone < local_bg * variance_ratio)
    # ── 不透明水印/静止图形: 与中值帧差异小(静止像素) ──
    median = np.median(stack, axis=0).astype(np.uint8)
    diff = cv2.absdiff(frames[0], median)
    cand_med = diff[ay1:ay2, ax1:ax2] < median_threshold
    cand = cand_var | cand_med
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[ay1:ay2, ax1:ax2][cand] = 255
    # 只保留落在用户框内的候选(外扩区仅用于方差估计)
    outside = np.ones_like(mask, dtype=bool)
    outside[y1:y2, x1:x2] = False
    mask[outside] = 0
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k5)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k5)
    # 膨胀覆盖笔画边缘(半透明文字边缘像素方差特征不完整)
    mask = cv2.dilate(mask, k5, iterations=2)

    kept = int((mask > 0).sum())
    if kept < max(50, (x2 - x1) * (y2 - y1) * 0.01):
        log.warn("watermarkDetector",
                 f"细化候选过少({kept}px), 回退矩形区域")
        return None
    log.info("watermarkDetector",
             f"细化完成: {kept}px({kept / ((x2-x1)*(y2-y1)) * 100:.0f}% "
             f"的框内区域), 区域 {bboxFromMask(mask)}")
    return mask
def detectWatermarkMask(video_path, sample_frames=30, threshold=15,
                        variance_ratio=0.75, noise_floor=4.0,
                        progress_callback=None):
    """
    组合水印检测(一次采样, 两种算法):
      1. 中值法  → 不透明水印(静止像素)
      2. 方差法  → 半透明水印(方差介于背景与噪声之间)
    结果取并集, 覆盖 B 站/平台类半透明水印场景。
    :return: (mask, 说明<str>) 或 (None, 说明)
    """
    log.info("watermarkDetector", f"开始组合水印检测: {video_path} "
                                  f"(采样 {sample_frames} 帧)")
    frames, info = _sampleFrames(video_path, sample_frames, progress_callback)
    if info is None:
        return None, "无法打开视频"
    if not frames or len(frames) < 5:
        return None, f"采样帧不足({len(frames)})"

    stack = np.stack(frames).astype(np.float32)        # (N,H,W)
    median = np.median(stack, axis=0).astype(np.uint8)
    diff = cv2.absdiff(frames[0], median)
    m_median = (diff < threshold).astype(np.uint8) * 255

    std = np.std(stack, axis=0)
    cand = _varianceCandidates(stack, variance_ratio, noise_floor)
    m_var = cand.astype(np.uint8) * 255

    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for m in (m_median, m_var):
        m[:] = cv2.morphologyEx(m, cv2.MORPH_OPEN, k5)
        m[:] = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k5)

    # 边缘先验: 只保留边缘带内的候选块(台标/角标位置), 剔除内部误检
    m_median = _edgePrior(m_median)
    m_var = _edgePrior(m_var)

    merged = cv2.bitwise_or(m_median, m_var)
    clean, kept, ratio = _filterContours(merged)

    notes = []
    if m_median.any():
        notes.append("中值法")
    if m_var.any():
        notes.append("方差法")
    if kept == 0 or ratio > MAX_TOTAL_RATIO:
        log.warn("watermarkDetector",
                 f"组合检测无有效区域(中值法{'命中' if '中值法' in notes else '未命中'}"
                 f", 方差法{'命中' if '方差法' in notes else '未命中'}), 拒绝")
        return None, "未检测到水印"
    bbox = bboxFromMask(clean)
    log.info("watermarkDetector",
             f"组合检测完成: 命中 {'+'.join(notes)}, 保留 {kept} 个区域, "
             f"占比 {ratio * 100:.2f}%, 区域 {bbox}")
    return clean, f"检测到水印区域 {bbox} ({'+'.join(notes)})"


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
        log.debug("watermarkDetector", f"模板({th}x{tw})大于帧({fh}x{fw}), 放弃跟踪")
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
            log.debug("watermarkDetector",
                      f"模板匹配得分 SQDIFF={min_val:.4f} CCOEFF={max_val:.4f}")
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
            log.debug("watermarkDetector",
                      f"邻域搜索未命中(上帧 {last_bbox}), 回退全帧搜索")
            # 邻域未命中 → 回退全帧搜索(容忍水印跳变)
        found = _best_in(frame, 0, 0)
        if found is None:
            log.warn("watermarkDetector", "全帧搜索未命中, 水印疑似丢失")
            return None
        x, y = found
        return x, y, x + tw, y + th
    except cv2.error as e:
        log.error("watermarkDetector", f"模板匹配异常: {e}")
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
        # 动态跟踪统计(排查跟踪丢失用)
        self._track_total = 0
        self._track_hit = 0
        self._track_miss = 0
        if mask is not None:
            self._static_mask = mask
            log.info("watermarkMasker", "静态模式: 使用自动检测 mask")
        elif bbox is not None and frame_shape is not None:
            h, w = frame_shape[:2]
            self._static_mask = np.zeros((h, w), dtype=np.uint8)
            x1, y1, x2, y2 = [int(v) for v in bbox]
            self._static_mask[y1:y2, x1:x2] = 255
            log.info("watermarkMasker",
                     f"静态模式: 手动指定水印区域 {bbox}(帧 {w}x{h})")
        else:
            self._static_mask = None
            log.warn("watermarkMasker", "静态模式: 无 mask/bbox, 全流程将原样复制")
        if mode == "dynamic":
            log.info("watermarkMasker",
                     f"动态模式: 模板 {template.shape[1]}x{template.shape[0]}, "
                     f"邻域搜索边距 20px, 混合评分(SQDIFF/CCOEFF)")

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
        self._track_total += 1
        if bbox is None:
            self._track_miss += 1
            if self._track_miss <= 3 or self._track_miss % 50 == 0:
                log.warn("watermarkMasker",
                         f"跟踪丢失 #{self._track_miss}(第 {frame_index} 帧)")
            return None
        self._track_hit += 1
        self._last_bbox = bbox
        log.debug("watermarkMasker",
                  f"第 {frame_index} 帧跟踪命中: {bbox}")
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        x1, y1, x2, y2 = bbox
        mask[y1:y2, x1:x2] = 255
        return mask

    def trackStats(self) -> dict:
        """
        动态跟踪统计(处理结束后调用)
        :return: {"total": int, "hit": int, "miss": int, "hit_rate": float}
        """
        rate = (self._track_hit / self._track_total * 100
                if self._track_total else 0.0)
        return {"total": self._track_total, "hit": self._track_hit,
                "miss": self._track_miss, "hit_rate": round(rate, 1)}
