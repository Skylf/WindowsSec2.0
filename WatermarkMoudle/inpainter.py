# -*- coding: utf-8 -*-
"""
水印修复引擎(inpainter)
=======================
- fast: OpenCV inpaint(Telea), 零依赖零模型, 对简单背景效果好
- lama: LaMa ONNX(高质量, 无痕填充大面积区域), 需本地模型文件
  模型文件(约 200MB, 一次性放置后完全离线; 缺失时自动降级 fast):

    WatermarkMoudle/models/lama_fp32.onnx  (推荐, opset17, torch.onnx.export 导出)
    WatermarkMoudle/models/lama.onnx       (备用, opset18, dynamo 导出;
                                            新版 onnxruntime 可能因 DFT 算子拒绝加载)

  来源: HuggingFace Carve/LaMa-ONNX(下载后放入 models/ 目录即可)
  注意: 模型输入尺寸固定为 512x512, 推理时自动缩放适配,
        输出再缩放回原尺寸(LaMa 对分辨率不敏感, 质量损失极小)。
"""

import os

import cv2
import numpy as np

import gpuDetector
import log

# LaMa 模型路径(优先 fp32 推荐版)
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
LAMA_MODEL_PATH = os.path.join(_MODEL_DIR, 'lama_fp32.onnx')
LAMA_MODEL_PATH_LEGACY = os.path.join(_MODEL_DIR, 'lama.onnx')


def hasLamaModel() -> bool:
    """LaMa 模型文件是否就绪(任一版本)"""
    for p in (LAMA_MODEL_PATH, LAMA_MODEL_PATH_LEGACY):
        if os.path.exists(p):
            log.debug("inpainter", f"LaMa 模型: {p} 就绪")
            return True
    log.debug("inpainter",
              f"LaMa 模型缺失: {LAMA_MODEL_PATH} / {LAMA_MODEL_PATH_LEGACY}")
    return False


def lamaModelPath() -> str:
    """返回实际使用的模型路径(fp32 优先)"""
    if os.path.exists(LAMA_MODEL_PATH):
        return LAMA_MODEL_PATH
    return LAMA_MODEL_PATH_LEGACY


class Inpainter:
    """
    水印修复引擎
    ============
    mode: "fast"(OpenCV inpaint) / "lama"(ONNX, 高质量)
    use_gpu: "auto"/"on"/"off"
    """

    def __init__(self, mode="fast", use_gpu="auto"):
        self._mode = mode
        self._session = None
        self._input_names = None
        self._fixed_size = None   # 模型固定输入尺寸 (H, W) 或 None(动态)
        log.info("inpainter", f"修复引擎初始化: mode={mode}, use_gpu={use_gpu}")
        if mode == "lama":
            self._loadLama(use_gpu)
        else:
            log.info("inpainter", "使用 fast 引擎(OpenCV Telea inpaint)")

    # ============================================================
    # 引擎加载
    # ============================================================
    def _loadLama(self, use_gpu):
        """加载 LaMa ONNX 模型(缺失/失败时降级 fast 并提示)"""
        if not hasLamaModel():
            log.warn("inpainter", "⚠ LaMa 模型不存在, 降级为 fast 模式(OpenCV inpaint)")
            log.warn("inpainter",
                     f"   请放置模型文件: {LAMA_MODEL_PATH}(推荐) "
                     f"或 {LAMA_MODEL_PATH_LEGACY}")
            self._mode = "fast"
            return
        model_path = lamaModelPath()
        try:
            import onnxruntime as ort
            providers = gpuDetector.getOnnxProviders(use_gpu)
            # 限制推理线程数(与项目 modelConfig 策略一致, 避免全核抢占)
            so = ort.SessionOptions()
            so.intra_op_num_threads = 4
            so.inter_op_num_threads = 1
            log.info("inpainter",
                     f"加载 LaMa ONNX: {model_path}(线程: intra=4, inter=1)...")
            self._session = ort.InferenceSession(
                model_path, sess_options=so, providers=providers)
            self._input_names = [i.name for i in self._session.get_inputs()]
            # 解析输入尺寸: 第 2、3 维为整数 → 固定尺寸模型(LaMa 为 512x512)
            shape = self._session.get_inputs()[0].shape
            if len(shape) == 4 and isinstance(shape[2], int) \
                    and isinstance(shape[3], int):
                self._fixed_size = (shape[2], shape[3])
            gpu_used = "CUDAExecutionProvider" in providers
            log.info("inpainter",
                     f"LaMa 模型加载成功({gpu_used and 'GPU' or 'CPU'}), "
                     f"输入节点: {self._input_names}, 输入形状: {shape}, "
                     f"固定尺寸: {self._fixed_size}")
        except Exception as e:
            log.error("inpainter", f"LaMa 加载失败({e}), 降级为 fast 模式")
            self._mode = "fast"

    def mode(self) -> str:
        """当前实际引擎: fast/lama"""
        return self._mode

    # ============================================================
    # 修复
    # ============================================================
    def inpaint(self, frame, mask):
        """
        修复单帧水印区域
        :param frame: BGR 帧<np.ndarray>
        :param mask: 水印 mask<np.ndarray uint8>(0/255)
        :return: 修复后的帧<np.ndarray>
        """
        if frame is None or mask is None:
            log.warn("inpainter", "修复输入为空(frame/mask), 跳过本帧")
            return frame
        if self._mode == "lama" and self._session is not None:
            try:
                return self._inpaintLama(frame, mask)
            except Exception as e:
                log.error("inpainter", f"LaMa 推理失败({e}), 本帧回退 fast")
        return cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)

    def _inpaintLama(self, frame, mask):
        """
        LaMa ONNX 推理:
        输入 image [1,3,H,W] float32 /255, mask [1,1,H,W] float32(0/1)
        输出 [1,3,H,W]

        固定尺寸模型(512x512):
          - 只对水印区域裁剪 + 边距, 缩放/pad 到 512 推理, 结果贴回原位
          - 非水印区域保持原像素(不受缩放影响), 水印区全分辨率修复
        动态尺寸模型: 整帧 pad 到 8 的倍数推理。
        """
        h, w = frame.shape[:2]
        # LaMa 协议: 输入图像中 mask 区域必须置空(置 0), 且必须在裁剪/反射填充
        # 之前作用于整帧 —— 否则 BORDER_REFLECT_101 会把水印文字镜像进填充区,
        # 模型看到文字模式会原样重建文字
        frame = frame.copy()
        frame[mask > 0] = 0
        if self._fixed_size is not None:
            th, tw = self._fixed_size
            # ── 固定尺寸模型: 水印区域裁剪推理(保留全分辨率质量) ──
            ys, xs = np.where(mask > 0)
            if len(xs) == 0:
                return frame
            margin = 64   # 水印四周上下文边距(LaMa 借周边结构生成; 大边距融合更好)
            x1 = max(0, int(xs.min()) - margin)
            y1 = max(0, int(ys.min()) - margin)
            x2 = min(w, int(xs.max()) + 1 + margin)
            y2 = min(h, int(ys.max()) + 1 + margin)
            crop = frame[y1:y2, x1:x2]
            mcrop = mask[y1:y2, x1:x2]
            ch, cw = crop.shape[:2]
            if ch > th or cw > tw:
                # 区域比模型输入还大(超大水印): 整体缩放到模型尺寸
                img = cv2.resize(crop, (tw, th), interpolation=cv2.INTER_LINEAR)
                msk = cv2.resize(mcrop, (tw, th), interpolation=cv2.INTER_NEAREST)
                crop_out_h, crop_out_w = ch, cw
            else:
                # pad 到模型尺寸(图像反射填充, mask 补 0)
                pad_b = th - ch
                pad_r = tw - cw
                img = cv2.copyMakeBorder(crop, 0, pad_b, 0, pad_r,
                                         cv2.BORDER_REFLECT_101)
                msk = cv2.copyMakeBorder(mcrop, 0, pad_b, 0, pad_r,
                                         cv2.BORDER_CONSTANT, value=0)
                crop_out_h, crop_out_w = ch, cw
        else:
            # ── 动态尺寸模型: 整帧 pad 到 8 的倍数 ──
            pad_h = (8 - h % 8) % 8
            pad_w = (8 - w % 8) % 8
            img = cv2.copyMakeBorder(frame, 0, pad_h, 0, pad_w,
                                     cv2.BORDER_REFLECT_101)
            msk = cv2.copyMakeBorder(mask, 0, pad_h, 0, pad_w,
                                     cv2.BORDER_CONSTANT, value=0)
            crop_out_h, crop_out_w = h + pad_h, w + pad_w

        # LaMa 协议: 输入图像中 mask 区域必须置空(置 0),
        # 否则模型会把可见的原始内容(如水印文字)原样保留
        img = img.copy()
        img[msk > 0] = 0

        img_t = img.astype(np.float32) / 255.0
        img_t = img_t.transpose(2, 0, 1)[np.newaxis, ...]      # (1,3,H,W)
        msk_t = (msk > 0).astype(np.float32)[np.newaxis, np.newaxis, ...]  # (1,1,H,W)

        # 输入名可能为 image/mask 或 img/mask 等, 按序传
        feeds = {}
        names = self._input_names or ["image", "mask"]
        for i, name in enumerate(names[:2]):
            feeds[name] = img_t if i == 0 else msk_t
        out = self._session.run(None, feeds)[0][0]             # (3,H,W)
        # 输出范围自适应: 部分导出模型输出已是 0-255, 部分为 0-1
        if out.max() > 1.5:
            out = np.clip(out, 0, 255).astype(np.uint8)
        else:
            out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
        out = out.transpose(1, 2, 0)                            # HWC

        if self._fixed_size is not None:
            # 裁剪推理: 缩回裁剪尺寸 → 贴回原帧
            # 仅替换 mask 内像素, 边距等其余像素恢复原帧(逐像素保留)
            result = frame.copy()
            piece = cv2.resize(out, (crop_out_w, crop_out_h),
                               interpolation=cv2.INTER_LINEAR)
            patch = result[y1:y2, x1:x2]
            keep = mask[y1:y2, x1:x2] == 0
            patch[keep] = frame[y1:y2, x1:x2][keep]
            patch[~keep] = piece[~keep]
            return result
        return out[:h, :w]

    def close(self):
        """释放引擎资源"""
        self._session = None
