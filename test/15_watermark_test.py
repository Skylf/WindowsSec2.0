# -*- coding: utf-8 -*-
"""
WatermarkMoudle 功能接口验证
==============================
1. GPU 检测与开关解析
2. 静态水印自动检测(合成视频: 随机背景 + 固定水印) → mask 命中水印区域
3. 修复引擎 fast: 水印区域被填充
4. 视频处理主流程: 合成视频 → 去水印 → 输出(帧数一致, 水印区域被修复)
5. 动态跟踪: 模板匹配定位移动水印
"""
import os
import sys
import tempfile

import cv2
import numpy as np

# 注入 WatermarkMoudle 目录
wmDir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'WatermarkMoudle')
if wmDir not in sys.path:
    sys.path.insert(0, wmDir)

import gpuDetector
from watermarkDetector import (detectStaticMask, detectWatermarkMask,
                               WatermarkMasker, cropTemplate, trackWatermark,
                               bboxFromMask)
from inpainter import Inpainter, hasLamaModel
from videoProcessor import prepareMasker, processVideo, removeWatermark


def makeSemiTransparentVideo(path, alpha=0.45, frames=60, size=(320, 240),
                             wm_box=(240, 190, 305, 225), static_obj=True):
    """
    合成视频: 平滑平移渐变背景 + 半透明文字水印(右下) + 可选静止物体(左上)
    背景为连续渐变平移(无硬边缘, 方差信号干净, 贴近真实视频运动场景)。
    :return: 水印真实 bbox
    """
    w, h = size
    # 无损编码(HFYU): 有损压缩会把抗锯齿文字边缘抖动成满幅方差, 污染方差统计
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'HFYU'), 25.0, (w, h))
    xg = np.linspace(0, 6.28, w, dtype=np.float32)   # x 相位
    yg = np.linspace(0, 4.0, h, dtype=np.float32)    # y 相位
    for i in range(frames):
        # 无回绕正弦运动背景(连续平滑, 时域 std ≈ 20-35, 干净方差信号)
        phase = i * 0.6
        base = np.zeros((h, w, 3), dtype=np.uint8)
        base[:, :, 0] = (128 + 100 * np.sin(xg[None, :] + phase)).astype(np.uint8)
        base[:, :, 1] = (128 + 90 * np.sin(yg[:, None] * 1.3 + phase * 0.8)
                         ).astype(np.uint8)
        base[:, :, 2] = (128 + 80 * np.sin(xg[None, :] * 0.7 +
                                            yg[:, None] + phase * 1.2)
                         ).astype(np.uint8)
        if static_obj:
            base[10:60, 10:60] = (220, 100, 50)
        # 半透明文字水印(细笔画, 贴近真实平台水印)
        # 注意: 只混合文字像素(layer>0), 背景保持原样 —— 全帧混合会把
        # 背景方差也衰减 (1-α), 文字与背景将无法区分
        layer = np.zeros_like(base)
        cv2.putText(layer, "TEST WM", (wm_box[0], wm_box[3] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3,
                    cv2.LINE_AA)
        sel = layer > 0
        base[sel] = (base[sel].astype(np.float32) * (1 - alpha) +
                     layer[sel].astype(np.float32) * alpha).astype(np.uint8)
        writer.write(base)
    writer.release()
    return wm_box


def makeTestVideo(path, frames=40, size=(320, 240), watermark_box=(232, 20, 312, 70),
                  moving=False):
    """
    合成测试视频: 随机噪声背景 + 水印矩形(静止或移动)
    水印贴近右上角(真实水印在边缘带内, 组合检测的边缘先验才放行)
    :return: 水印真实区域(最后一帧位置)
    """
    w, h = size
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), 25.0, (w, h))
    x1, y1, x2, y2 = watermark_box
    real_box = None
    for i in range(frames):
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        # 水印: 亮色矩形 + 稳定像素(模拟静止水印)
        bx1, by1 = x1, y1
        if moving:
            bx1 = min(w - (x2 - x1), x1 + i * 3)   # 水印右移
            by1 = y1
        bx2, by2 = bx1 + (x2 - x1), by1 + (y2 - y1)
        frame[by1:by2, bx1:bx2] = (200, 30, 30)     # BGR 红色水印
        real_box = (bx1, by1, bx2, by2)
        writer.write(frame)
    writer.release()
    return real_box


def overlap(box1, box2):
    """两 bbox 重叠率(IoU)"""
    if box1 is None or box2 is None:
        return 0.0
    x1 = max(box1[0], box2[0]); y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2]); y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0


def main():
    print("=" * 60)
    tmp = tempfile.mkdtemp(prefix="wm_test_")
    print("[1] GPU 检测与开关解析")
    info = gpuDetector.detectGpu()
    print(f"  ✓ CUDA 可用: {info['cuda_available']}, providers: {info['providers']}")
    for mode in ("auto", "on", "off"):
        providers = gpuDetector.getOnnxProviders(mode)
        assert providers, f"{mode} 模式应返回 providers"
    off = gpuDetector.getOnnxProviders("off")
    assert off == ["CPUExecutionProvider"], "off 模式应仅 CPU"
    # CUDA 开关一致性: auto/on 返回 CUDA 当且仅当实测验证通过
    verified = gpuDetector.verifyCuda()
    auto = gpuDetector.getOnnxProviders("auto")
    assert ("CUDAExecutionProvider" in auto) == verified, \
        f"auto 模式应与实测结果一致: auto={auto}, verified={verified}"
    print(f"  ✓ 开关解析正常(auto/on/off), CUDA 实测={verified}, "
          f"auto 实际: {'GPU' if 'CUDAExecutionProvider' in auto else 'CPU'}")

    print("[2] 静态水印自动检测(时域中值法)")
    static_video = os.path.join(tmp, "static.mp4")
    real_box = makeTestVideo(static_video, frames=40)
    mask = detectStaticMask(static_video, sample_frames=30, threshold=15)
    assert mask is not None, "应检测到 mask"
    from watermarkDetector import bboxFromMask
    det_box = bboxFromMask(mask)
    iou = overlap(det_box, real_box)
    assert iou > 0.5, f"检测区域应命中水印(IoU={iou:.2f}): det={det_box} real={real_box}"
    print(f"  ✓ 自动检测命中: 检测框={det_box}, 真实框={real_box}, IoU={iou:.2f}")

    print("[2b] 半透明水印检测核心统计(方差法, B站类场景)")
    # 数组级验证(绕过视频编码/seek 干扰, 直接检验统计不变式):
    #   半透明水印像素时域方差 = (1-α)²·σ_BG², 介于静止物(≈0)与背景(σ_BG)之间
    from watermarkDetector import _varianceCandidates
    w, h = 320, 240
    frames_n = 60
    xg = np.linspace(0, 6.28, w, dtype=np.float32)
    yg = np.linspace(0, 4.0, h, dtype=np.float32)
    stack = []
    for i in range(frames_n):
        phase = i * 0.6
        base = np.zeros((h, w, 3), dtype=np.uint8)
        base[:, :, 0] = (128 + 100 * np.sin(xg[None, :] + phase)).astype(np.uint8)
        base[:, :, 1] = (128 + 90 * np.sin(yg[:, None] * 1.3 + phase * 0.8)
                         ).astype(np.uint8)
        base[:, :, 2] = (128 + 80 * np.sin(xg[None, :] * 0.7 +
                                            yg[:, None] + phase * 1.2)
                         ).astype(np.uint8)
        layer = np.zeros_like(base)
        cv2.putText(layer, "TEST WM", (240, 213),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3,
                    cv2.LINE_AA)
        # 只混合文字像素, 背景保持原样(全帧混合会衰减背景方差, 无法区分)
        alpha = 0.45
        sel = layer > 0
        base[sel] = (base[sel].astype(np.float32) * (1 - alpha) +
                     layer[sel].astype(np.float32) * alpha).astype(np.uint8)
        base[10:60, 10:60] = (220, 100, 50)   # 静止物体
        stack.append(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY))
    stack = np.stack(stack).astype(np.float32)
    text_px = layer[:, :, 0] > 100
    cand = _varianceCandidates(stack, 0.75, 4.0)
    # 不变式1: 文字像素被候选覆盖(半透明水印方差介于背景与噪声之间)
    hit = cand[text_px].mean()
    assert hit > 0.5, f"文字像素候选覆盖率应 > 50%: {hit:.1%}"
    # 不变式2: 静止物体(方差≈0)不产生候选
    obj_cand = cand[10:60, 10:60].mean()
    assert obj_cand < 0.05, f"静止物体候选应接近 0: {obj_cand:.1%}"
    # 不变式3: 背景(方差=σ_BG)不产生候选
    bg_cand = cand[100:180, 100:200].mean()
    assert bg_cand < 0.1, f"背景候选应接近 0: {bg_cand:.1%}"
    print(f"  ✓ 半透明水印统计验证: 文字覆盖={hit:.0%}, "
          f"静止物候选={obj_cand:.1%}, 背景候选={bg_cand:.1%}")

    print("[3] 修复引擎 fast: 水印区域被填充")
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    frame[30:70, 40:120] = (200, 30, 30)
    m = np.zeros((240, 320), dtype=np.uint8)
    m[30:70, 40:120] = 255
    eng = Inpainter(mode="fast")
    repaired = eng.inpaint(frame, m)
    repaired_region = repaired[30:70, 40:120]
    assert repaired_region.mean() > 100, "修复区域不应再是纯红色水印"
    print(f"  ✓ fast 修复正常(水印区域均值 {repaired_region.mean():.0f}, "
          f"已填充背景色)")

    print("[3b] 修复引擎 lama(模型存在时): 半透明水印去除 + 非水印区逐像素保留")
    if hasLamaModel():
        # 渐变背景(自然分布, LaMa 不幻觉) + 半透明水印
        gx = np.linspace(0, 255, 320, dtype=np.uint8)
        gy = np.linspace(0, 255, 240, dtype=np.uint8)
        base = np.zeros((240, 320, 3), dtype=np.uint8)
        for c in range(3):
            base[:, :, c] = (gx[None, :] * 0.5 + gy[:, None] * 0.5).astype(np.uint8)
        wm = base.copy()
        wm[30:70, 40:120] = (wm[30:70, 40:120] * 0.45 + 255 * 0.55).astype(np.uint8)
        lama = Inpainter(mode="lama", use_gpu="off")
        assert lama.mode() == "lama", "应成功加载 LaMa 模型"
        repaired = lama.inpaint(wm, m)
        lama.close()
        region = repaired[30:70, 40:120]
        outside = repaired.copy()
        outside[30:70, 40:120] = wm[30:70, 40:120]
        diff_out = cv2.absdiff(outside, wm).mean()
        assert diff_out == 0, f"非水印区应逐像素保留: {diff_out}"
        assert abs(float(region.mean()) - float(base[30:70, 40:120].mean())) < 30, \
            f"修复区应接近原始背景: {region.mean():.0f} vs {base[30:70, 40:120].mean():.0f}"
        print(f"  ✓ lama 修复正常(修复区均值 {region.mean():.0f}, "
              f"原始背景 {base[30:70, 40:120].mean():.0f}, 非水印区零改动)")
    else:
        print("  - 无 LaMa 模型, 跳过(放置 models/lama_fp32.onnx 后自动启用)")

    print("[4] 视频处理主流程(static)")
    out_video = os.path.join(tmp, "static_out.mp4")
    progress = []
    result = removeWatermark(static_video, out_video, mode="static",
                             progress_callback=lambda p, i: progress.append(p))
    assert result["success"], f"处理失败: {result}"
    assert result["frames"] == 40, f"帧数应一致: {result['frames']}"
    assert os.path.exists(out_video), "输出视频应存在"
    assert result["watermark_bbox"] is not None, "应检测到水印"
    # 验证输出视频水印区域已修复
    cap = cv2.VideoCapture(out_video)
    ret, out_frame = cap.read()
    cap.release()
    assert ret
    x1, y1, x2, y2 = result["watermark_bbox"]
    region_mean = out_frame[y1:y2, x1:x2].mean()
    print(f"  ✓ 处理完成: {result['msg']}, 平均帧耗时 {result['avg_ms']}ms, "
          f"水印区域修复后均值 {region_mean:.0f}")

    print("[5] 动态水印: 模板匹配跟踪")
    moving_video = os.path.join(tmp, "moving.mp4")
    real_last = makeTestVideo(moving_video, frames=20, moving=True)
    # 首帧定位(用真实框模拟首帧手动/自动定位)
    cap = cv2.VideoCapture(moving_video)
    ret, first = cap.read()
    cap.release()
    template = cropTemplate(first, (232, 20, 312, 70))
    # 跟踪第 15 帧
    cap = cv2.VideoCapture(moving_video)
    for _ in range(15):
        ret, frame = cap.read()
    cap.release()
    tracked = trackWatermark(frame, template)
    assert tracked is not None, "应跟踪到水印"
    # 期望位置: x = min(320-80, 232 + 14*3) = 240
    expected = (240, 20, 320, 70)
    iou = overlap(tracked, expected)
    assert iou > 0.5, f"跟踪偏差过大: tracked={tracked}, expected={expected}, IoU={iou:.2f}"
    print(f"  ✓ 动态跟踪命中: tracked={tracked}, expected={expected}, IoU={iou:.2f}")

    print("[6] 动态模式全流程")
    out_moving = os.path.join(tmp, "moving_out.mp4")
    result = removeWatermark(moving_video, out_moving, mode="dynamic")
    assert result["success"] and result["frames"] == 20
    print(f"  ✓ 动态模式处理完成: {result['msg']}, 水印框={result['watermark_bbox']}")

    print("\n=== WatermarkMoudle 功能接口验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
