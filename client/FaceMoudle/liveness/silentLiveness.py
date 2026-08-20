# -*- coding: utf-8 -*-
"""
静默活体检测模块(silentLiveness)
=================================
第一层防御: 无需用户做任何动作,直接对单帧人脸区域做"真伪"判定。

分层逻辑:
1. 环境光/对比度质量检查: 感知环境亮度与对比度,光线异常直接拒绝(保证输入质量)
2. MiniFASNet 深度静默活体检测: 深度学习模型区分真人与照片/屏幕翻拍攻击

模型:
- 架构: MiniFASNet V2 SE(来自 Silent-Face-Anti-Spoofing, Apache-2.0)
- 输入: 128x128 RGB,归一化到 [0,1],CHW 格式
- 输出: 2 个 logits [real, spoof],logit_diff = real - spoof,>=0 判为真人
- 位置: FaceMoudle/liveness/models/minifasnet.onnx
"""

import os
import sys
import cv2
import numpy as np

# 限制 ONNX 推理线程数(必须在创建任何 session 前生效)
# 本文件位于 FaceMoudle/liveness/,上 2 级即 FaceMoudle 目录
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FACE_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _FACE_MOUDLE_DIR)
import modelConfig  # 导入即自动限制 InsightFace 推理线程数


# ====================================================================
# 质量检查阈值(光线/对比度)
# ====================================================================
BRIGHTNESS_LOW = 40.0     # 平均亮度过低(过暗)判异常
BRIGHTNESS_HIGH = 235.0   # 平均亮度过高(过曝/屏幕发光)判异常
CONTRAST_THRESHOLD = 30.0  # 灰度标准差过低(画面偏灰)判异常

# 模型输入尺寸
MODEL_IMG_SIZE = 128

# 人脸裁剪外扩系数(与 MiniFASNet 官方一致)
BBOX_EXPANSION_FACTOR = 1.5

# 默认阈值(对应 sigmoid 概率 0.5,即 logit_diff >= 0)
LOGIT_THRESHOLD = 0.0


def getModelPath():
    """
    获取 MiniFASNet onnx 模型文件路径
    :return: 模型文件绝对路径<str>
    """
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'minifasnet.onnx')


class SilentLivenessDetector:
    """
    静默活体检测器(质量检查 + MiniFASNet 深度检测)
    ==============================================
    对外接口 check(frame, faceBox) 返回 (是否真人, 置信分数, 明细)。
    """

    def __init__(self, modelPath=None):
        """
        初始化静默活体检测器
        :param modelPath: MiniFASNet onnx 模型路径<str>,默认使用模块内 models/minifasnet.onnx
        """
        if modelPath is None:
            modelPath = getModelPath()

        if not os.path.exists(modelPath):
            raise FileNotFoundError(f"MiniFASNet 模型不存在: {modelPath}")

        # 加载 onnx 模型(CPU 推理,线程数受限避免全核抢占 CPU 导致系统卡顿)
        self.session = modelConfig.createSession(modelPath)
        self.inputName = self.session.get_inputs()[0].name
        self.modelReady = True

    def _checkQuality(self, gray):
        """
        环境光/对比度质量检查(保证进入模型的图像质量合格)
        :param gray: 灰度图<np.ndarray>
        :return: (是否正常<bool>, 明细<dict>)
        """
        brightness = float(gray.mean())
        contrast = float(gray.std())
        isBadBrightness = brightness < BRIGHTNESS_LOW or brightness > BRIGHTNESS_HIGH
        isLowContrast = contrast < CONTRAST_THRESHOLD
        isOk = not (isBadBrightness or isLowContrast)
        return isOk, {
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "isBadBrightness": isBadBrightness,
            "isLowContrast": isLowContrast,
        }

    def _cropFace(self, frame, faceBox):
        """
        根据人脸框裁剪正方形人脸区域(带外扩)
        :param frame: BGR 图像矩阵<np.ndarray>
        :param faceBox: 人脸框 (x1, y1, x2, y2)<tuple>
        :return: 裁剪后的正方形人脸 BGR 区域<np.ndarray>
        """
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in faceBox]
        bw = x2 - x1
        bh = y2 - y1
        if bw <= 0 or bh <= 0:
            raise ValueError("非法人脸框")

        maxDim = max(bw, bh)
        centerX = x1 + bw / 2.0
        centerY = y1 + bh / 2.0
        cropSize = int(maxDim * BBOX_EXPANSION_FACTOR)
        cx1 = int(centerX - cropSize / 2.0)
        cy1 = int(centerY - cropSize / 2.0)
        cx2 = cx1 + cropSize
        cy2 = cy1 + cropSize

        # 越界区域用反射填充
        cropX1 = max(0, cx1)
        cropY1 = max(0, cy1)
        cropX2 = min(w, cx2)
        cropY2 = min(h, cy2)
        crop = frame[cropY1:cropY2, cropX1:cropX2]
        topPad = max(0, -cy1)
        leftPad = max(0, -cx1)
        bottomPad = max(0, cy2 - h)
        rightPad = max(0, cx2 - w)
        crop = cv2.copyMakeBorder(
            crop, topPad, bottomPad, leftPad, rightPad, cv2.BORDER_REFLECT_101
        )
        if crop.shape[0] != cropSize or crop.shape[1] != cropSize:
            crop = cv2.resize(crop, (cropSize, cropSize))
        return crop

    def _preprocess(self, faceCrop):
        """
        预处理: letterbox resize 到 128x128 → RGB → 归一化 /255 → CHW
        :param faceCrop: 正方形人脸 BGR 区域<np.ndarray>
        :return: 模型输入张量<np.ndarray>,形状 (1,3,128,128)
        """
        # letterbox resize 保持比例
        oldH, oldW = faceCrop.shape[:2]
        ratio = float(MODEL_IMG_SIZE) / max(oldH, oldW)
        newW = int(oldW * ratio)
        newH = int(oldH * ratio)
        interp = cv2.INTER_LANCZOS4 if ratio > 1.0 else cv2.INTER_AREA
        img = cv2.resize(faceCrop, (newW, newH), interpolation=interp)
        deltaW = MODEL_IMG_SIZE - newW
        deltaH = MODEL_IMG_SIZE - newH
        top, bottom = deltaH // 2, deltaH - deltaH // 2
        left, right = deltaW // 2, deltaW - deltaW // 2
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_REFLECT_101)

        # BGR → RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # 归一化到 [0,1] 并转 CHW
        img = img.transpose(2, 0, 1).astype(np.float32) / 255.0
        return img[np.newaxis, ...]

    def check(self, frame, faceBox):
        """
        对单帧人脸区域做静默活体检测(质量检查 + MiniFASNet)
        :param frame: BGR 图像矩阵<np.ndarray>
        :param faceBox: 人脸框 (x1, y1, x2, y2)<tuple>
        :return: 结果字典<dict>:
                 {
                     "isReal": bool,   # 是否判定为真人
                     "score": float,   # 置信分数 0~1(越大越像真人)
                     "detail": {...}   # 质量检查 + 模型输出明细
                 }
        """
        try:
            # 1. 裁剪人脸
            faceCrop = self._cropFace(frame, faceBox)
            gray = cv2.cvtColor(faceCrop, cv2.COLOR_BGR2GRAY)

            # 2. 环境光/对比度质量检查
            qualityOk, qualityDetail = self._checkQuality(gray)
            if not qualityOk:
                return {
                    "isReal": False,
                    "score": 0.0,
                    "detail": {"err": "光线/对比度异常", **qualityDetail}
                }

            # 3. MiniFASNet 推理
            batchInput = self._preprocess(faceCrop)
            logits = self.session.run([], {self.inputName: batchInput})[0][0]
            realLogit = float(logits[0])
            spoofLogit = float(logits[1])
            logitDiff = realLogit - spoofLogit
            isReal = logitDiff >= LOGIT_THRESHOLD
            # sigmoid 转为 0~1 置信分数
            score = round(1.0 / (1.0 + np.exp(-logitDiff)), 4)

            return {
                "isReal": isReal,
                "score": score,
                "detail": {
                    "logitDiff": round(logitDiff, 4),
                    "realLogit": round(realLogit, 4),
                    "spoofLogit": round(spoofLogit, 4),
                    **qualityDetail,
                }
            }
        except Exception as e:
            return {"isReal": False, "score": 0.0, "detail": {"err": str(e)}}


if __name__ == '__main__':
    # 简单自测: 若有图片参数则检测
    import sys
    det = SilentLivenessDetector()
    print(f"模型已加载: {getModelPath()}")
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        if img is not None:
            h, w = img.shape[:2]
            result = det.check(img, (0, 0, w, h))
            print(result)
