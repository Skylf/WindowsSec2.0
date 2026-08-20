# -*- coding: utf-8 -*-
"""
人脸录入生产业务流程(faceEnroll)
================================
仿照 runTest.py 方式3(活体检测录入)的完整流程, 去掉控制台交互,
供 FaceService 在后台线程调用, 经中介调度与 UI 通信。

流程: 活体录入采集(openCameraWithLiveness) → 图片清洗(faceCheck/handleNoFace/coverDict)
      → 特征提取保存(generateFaceFeature)

进度回调 stage 取值:
  "silent"/"action"/"frontal"  活体检测阶段(透传自 runLivenessCheck)
  "capture"                    正脸照片采集中
  "clean"                      图片检测与清洗中
  "extract"                    特征提取中
"""

import os
import sys

# 注入相关目录(本文件位于 <项目根>/FaceMoudle/faceInputer/)
# FaceMoudle / faceInputer / faceDetecter(faceDataGetter 所在)
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FACE_INPUTER_DIR = os.path.dirname(os.path.abspath(__file__))
_FACE_DETECTER_DIR = os.path.join(_FACE_MOUDLE_DIR, 'faceDetecter')
for _d in (_FACE_MOUDLE_DIR, _FACE_INPUTER_DIR, _FACE_DETECTER_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)


def runEnroll(user_name, progressCallback=None, frameCallback=None):
    """
    生产环境录入全流程(无控制台交互)
    :param user_name: 用户名<str>
    :param progressCallback: 阶段进度回调<Callable>, 签名 progressCallback(stage, detail)
    :param frameCallback: 帧回调(供 UI 内嵌显示), 签名 frameCallback(frame, prompt),
                          默认 None;传入后活体检测/照片采集阶段不再弹 OpenCV 窗口
    :return: 结果字典<dict>:
             成功: {"success": True, "msg": str, "step": "", "featurePath": str}
             失败: {"success": False, "msg": str, "step": str, "featurePath": ""}
    """
    def notify(stage, detail=""):
        """阶段进度回调包装(回调抛异常沿调用链向上传播, 供取消任务)"""
        if progressCallback is not None:
            progressCallback(stage, detail)

    # ── 参数校验 ──
    if not user_name or not user_name.strip():
        return {"success": False, "msg": "用户名不能为空",
                "step": "参数校验", "featurePath": ""}
    user_name = user_name.strip()

    # ── Step 1: 活体检测录入采集(摄像头, 耗时) ──
    import inputter
    notify("liveness", f"活体检测录入开始(用户: {user_name})")
    result = inputter.openCameraWithLiveness(
        user_name, progressCallback=progressCallback, frameCallback=frameCallback
    )
    if not result.get("success"):
        return {"success": False,
                "msg": result.get("msg", "活体录入失败"),
                "step": result.get("step", "活体录入"),
                "featurePath": ""}
    img_dir = result["imgDir"]

    # ── Step 2: 图片检测与清洗(faceCheck 多进程) ──
    notify("clean", "图片检测与清洗中...")
    shared_dict = inputter.faceCheck(img_dir)
    if not shared_dict:
        return {"success": False, "msg": "未检测到人脸图片",
                "step": "图片检测", "featurePath": ""}
    cleaned_dict = inputter.handleNoFace(shared_dict)
    final_dict = inputter.coverDict(shared_dict, cleaned_dict)
    if not final_dict:
        return {"success": False, "msg": "清洗后无可用人脸图片",
                "step": "图片清洗", "featurePath": ""}

    # ── Step 3: 特征提取与保存(多进程, 耗时) ──
    notify("extract", f"特征提取中({len(final_dict)} 张可用图)...")
    from faceDataGetter import generateFaceFeature, getFaceDataDir
    feature = generateFaceFeature(user_name, img_dir)
    if feature is None:
        return {"success": False, "msg": "特征提取失败",
                "step": "特征提取", "featurePath": ""}

    # ── 定位生成的特征文件(取该用户最新的 .npy) ──
    face_data_dir = getFaceDataDir()
    candidates = [
        os.path.join(face_data_dir, f)
        for f in os.listdir(face_data_dir)
        if f.startswith(f"{user_name}_") and f.endswith(".npy")
    ]
    feature_path = max(candidates, key=os.path.getmtime) if candidates else ""

    return {"success": True, "msg": "录入完成", "step": "",
            "featurePath": feature_path}
