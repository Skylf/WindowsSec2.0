# -*- coding: utf-8 -*-
"""
水印修复引擎(inpainter)
========================
- fast: OpenCV inpaint(Telea), 零依赖零模型, 对简单背景效果好
- lama: LaMa ONNX(高质量, 无痕填充大面积区域), 需本地模型文件
  models/lama.onnx(约 200MB, 一次性放置后完全离线; 缺失时自动降级 fast)

模型放置(全程不上公网, 只需一次性手动放入):
  WatermarkMoudle/models/lama.onnx
  来源参考: HuggingFace Carve/LaMa-ONNX(big-lama 导出)
"""

import os

import cv2
import numpy as np

import gpuDetector
import log

# LaMa 模型路径
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
LAMA_MODEL_PATH = os.path.join(_MODEL_DIR, 'lama.onnx')

# LaMa 输入需为 8 的倍数(大 mask 训练尺寸)
_LAMA_ALIGN = 8


def hasLamaModel() -> bool:
    """LaMa 模型文件是否就绪"""
    ready = os.path.exists(LAMA_MODEL_PATH)
    log.debug("inpainter", f"LaMa 模型检查: {LAMA_MODEL_PATH} → {'就绪' if ready else '缺失'}")
    return ready


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
        log.info("inpainter", f"修复引擎初始化: mode={mode}, use_gpu={use_gpu}")
        if mode == "lama":
            self._loadLama(use_gpu)
        else:
            log.info("inpainter", "使用 fast 引擎(OpenCV Telea inpaint)")

    # ============================================================
    # 引擎加载
    # ============================================================
    def _loadLama(self, use_gpu):
        """加载 LaMa ONNX 模型(缺失时降级 fast 并提示)"""
        if not hasLamaModel():
            log.warn("inpainter", "⚠ LaMa 模型不存在, 降级为 fast 模式(OpenCV inpaint)")
            log.warn("inpainter", f"   请放置模型文件: {LAMA_MODEL_PATH}")
            self._mode = "fast"
            return
        try:
            import onnxruntime as ort
            providers = gpuDetector.getOnnxProviders(use_gpu)
            # 限制推理线程数(与项目 modelConfig 策略一致, 避免全核抢占)
            so = ort.SessionOptions()
            so.intra_op_num_threads = 4
            so.inter_op_num_threads = 1
            log.info("inpainter", f"加载 LaMa ONNX(线程: intra=4, inter=1)...")
            self._session = ort.InferenceSession(
                LAMA_MODEL_PATH, sess_options=so, providers=providers)
            self._input_names = [i.name for i in self._session.get_inputs()]
            gpu_used = "CUDAExecutionProvider" in providers
            log.info("inpainter",
                     f"LaMa 模型加载成功({gpu_used and 'GPU' or 'CPU'}), "
                     f"输入节点: {self._input_names}")
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
        """
        h, w = frame.shape[:2]
        # pad 到 8 的倍数
        pad_h = (_LAMA_ALIGN - h % _LAMA_ALIGN) % _LAMA_ALIGN
        pad_w = (_LAMA_ALIGN - w % _LAMA_ALIGN) % _LAMA_ALIGN
        img = cv2.copyMakeBorder(frame, 0, pad_h, 0, pad_w,
                                 cv2.BORDER_REFLECT_101)
        msk = cv2.copyMakeBorder(mask, 0, pad_h, 0, pad_w,
                                 cv2.BORDER_CONSTANT, value=0)

        img_t = img.astype(np.float32) / 255.0
        img_t = img_t.transpose(2, 0, 1)[np.newaxis, ...]      # (1,3,H,W)
        msk_t = (msk > 0).astype(np.float32)[np.newaxis, np.newaxis, ...]  # (1,1,H,W)

        # 输入名可能为 image/mask 或 img/mask 等, 按序传
        feeds = {}
        names = self._input_names or ["image", "mask"]
        for i, name in enumerate(names[:2]):
            feeds[name] = img_t if i == 0 else msk_t
        out = self._session.run(None, feeds)[0][0]             # (3,H,W)
        out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
        out = out.transpose(1, 2, 0)                            # HWC
        return out[:h, :w]

    def close(self):
        """释放引擎资源"""
        self._session = None
