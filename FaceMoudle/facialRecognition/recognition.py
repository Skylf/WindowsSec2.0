# -*- coding: utf-8 -*-
"""
人脸识别模块(recognition)
=========================
负责人脸识别的 1:N 比对:从待识别图片中提取人脸特征,与已注册的特征向量计算余弦相似度,
判断是否为同一个人。

本文件为工具函数库,仅提供识别 API,不包含打开摄像头/选取文件等流程操作。
后续由流程脚本组合调用以下 API 完成完整的人脸识别流程:

1. loadRegisteredFeature  - 从 .npy 文件加载已注册的特征向量
2. extractCurrentFeature  - 从待识别图片提取人脸特征(512 维)
3. computeSimilarity      - 计算两个特征向量的余弦相似度
4. recognizeFace          - 完整识别 API(加载特征 → 提取 → 比对 → 返回结果)

技术要点:
- 已注册特征(normed_embedding)和待识别特征(normed_embedding)都已 L2 归一化
- 归一化向量的余弦相似度 = 点积(np.dot),范围 [-1, 1],越接近 1 越相似
- 默认阈值 0.85(严格安全场景),可根据场景调整:
  - 严格场景(安全门禁): 0.85(默认)
  - 普通场景(考勤): 0.6-0.8
  - 宽松场景(体验): 0.4-0.6
"""

# 标准库
import os  # 路径操作
import sys  # sys.path 注入(FaceMoudle 目录)

# 第三方库
import cv2       # 图像解码
import numpy as np  # 特征向量计算
from insightface.app import FaceAnalysis  # 人脸检测+识别模型

# 限制 ONNX 推理线程数(必须在创建任何 session 前生效)
# 本文件位于 FaceMoudle/facialRecognition/,上 2 级即 FaceMoudle 目录
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FACE_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _FACE_MOUDLE_DIR)
import modelConfig  # 导入即自动限制 InsightFace 推理线程数


# ====================================================================
# 模块级常量
# ====================================================================
# 默认相似度阈值(严格安全场景 0.85,可根据场景调整)
DEFAULT_THRESHOLD = 0.85

# ArcFace R50 模型输出的特征向量维度
EMBEDDING_DIM = 512

# 人脸检测尺寸(与 faceDataGetter 保持一致)
DET_SIZE = (480, 480)


# ====================================================================
# 路径工具函数
# ====================================================================
def getProjectRoot():
    """
    获取项目根目录
    :return: 项目根目录的绝对路径<str>
    """
    # recognition.py 在 FaceMoudle/facialRecognition/ 下,项目根是上 3 级
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def getModelRoot():
    """
    获取 InsightFace 模型根目录
    InsightFace 会在 <root>/models/buffalo_l/ 下自动查找模型文件
    :return: 模型根目录的绝对路径<str>
    """
    return os.path.join(getProjectRoot(), 'FaceMoudle', 'moudleTrainner')


def getFaceDataDir():
    """
    获取特征数据目录(与 faceDataGetter 的输出目录一致)
    :return: 特征数据目录的绝对路径<str>
    """
    return os.path.join(getProjectRoot(), 'cache', 'faceData')


def imreadUnicode(path):
    """
    读取中文路径下的图片(OpenCV imread 在 Windows 不支持中文路径的 workaround)
    :param path: 图片路径<str>
    :return: BGR 图像矩阵<np.ndarray>,读取失败返回 None
    """
    # np.fromfile 按二进制读取原始字节(支持中文路径),cv2.imdecode 解码为 BGR 矩阵
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


# ====================================================================
# 模型初始化
# ====================================================================
# 全局模型实例(单例,避免重复加载模型)
# 与 faceDataGetter 不同:这里用单例而非多进程,因为识别是单张图实时处理,不需要并行
_APP = None


def getFaceApp():
    """
    获取 FaceAnalysis 单例(懒加载,首次调用时初始化,后续复用)
    加载 detection + recognition 模型,与 faceDataGetter 一致

    :return: 配置好的 FaceAnalysis 实例<FaceAnalysis>
    """
    global _APP
    if _APP is None:
        modelRoot = getModelRoot()
        # allowed_modules=['detection','recognition'] 只加载检测和识别两个模型
        _APP = FaceAnalysis(
            name='buffalo_l',
            root=modelRoot,
            allowed_modules=['detection', 'recognition'],
            providers=['CPUExecutionProvider']
        )
        _APP.prepare(ctx_id=-1, det_size=DET_SIZE)
    return _APP


# ====================================================================
# 核心识别函数
# ====================================================================
def loadRegisteredFeature(npyPath):
    """
    从 .npy 文件加载已注册的人脸特征向量
    文件由 faceDataGetter.saveFeatureNpy 生成,内容是 (512,) 的归一化向量

    :param npyPath: .npy 文件路径<str>
    :return: 特征向量<np.ndarray>,形状 (512,),已 L2 归一化
             文件不存在或格式错误时返回 None
    """
    if not os.path.exists(npyPath):
        print(f"特征文件不存在: {npyPath}")
        return None

    try:
        # np.load 加载 .npy 格式的 numpy 数组
        feature = np.load(npyPath)
        # 校验维度
        if feature.shape != (EMBEDDING_DIM,):
            print(f"特征维度异常: 期望 ({EMBEDDING_DIM},),实际 {feature.shape}")
            return None
        return feature
    except Exception as e:
        print(f"加载特征文件失败: {e}")
        return None


def extractCurrentFeature(img):
    """
    从图像中提取人脸特征向量
    支持两种输入:
    1. 图片文件路径(str)→ 自动用 imreadUnicode 读取(支持中文路径)
    2. numpy 数量(BGR 矩阵)→ 直接处理(如摄像头捕获的帧)

    :param img: 图片路径<str> 或 BGR 图像矩阵<np.ndarray>
    :return: 识别结果字典<dict>,格式:
             {
                 "success": True/False,       # 是否成功提取特征
                 "embedding": np.ndarray,      # 512 维特征向量(success=True 时存在)
                 "msg": "描述信息"
             }
    """
    try:
        # 如果输入是字符串路径,先读取图片(支持中文路径)
        if isinstance(img, str):
            img = imreadUnicode(img)
            if img is None:
                return {"success": False, "msg": "图片读取失败"}

        # 获取 FaceAnalysis 单例(首次调用时初始化,后续复用)
        app = getFaceApp()

        # 人脸检测 + 特征提取
        faces = app.get(img)

        # 无人脸
        if len(faces) == 0:
            return {"success": False, "msg": "未检测到人脸"}

        # 取第一张人脸的 normed_embedding(已 L2 归一化的 512 维向量)
        # 注意: InsightFace 按检测置信度降序排列(faces[0] 是置信度最高的人脸,非面积最大)
        currentEmb = faces[0].normed_embedding

        # 校验特征维度
        if currentEmb is None or currentEmb.shape[0] != EMBEDDING_DIM:
            return {"success": False, "msg": "特征维度异常"}

        return {
            "success": True,
            "embedding": currentEmb,
            "msg": f"提取成功(检测到 {len(faces)} 张脸)"
        }

    except Exception as e:
        return {"success": False, "msg": f"异常: {e}"}


def computeSimilarity(emb1, emb2):
    """
    计算两个已归一化特征向量的余弦相似度
    因为两个向量都已 L2 归一化(模长=1),余弦相似度 = 点积 = np.dot(emb1, emb2)
    结果范围 [-1, 1],越接近 1 表示越相似

    :param emb1: 特征向量 1<np.ndarray>,已 L2 归一化
    :param emb2: 特征向量 2<np.ndarray>,已 L2 归一化
    :return: 余弦相似度<float>,范围 [-1, 1]
    """
    # np.dot 计算点积;对于归一化向量,点积 = 余弦相似度
    similarity = float(np.dot(emb1, emb2))
    return similarity


def recognizeFace(registeredNpyPath, img, threshold=DEFAULT_THRESHOLD):
    """
    完整的人脸识别 API:
    1. 从 .npy 文件加载已注册的特征向量
    2. 从待识别图片提取人脸特征
    3. 计算余弦相似度
    4. 阈值判定

    :param registeredNpyPath: 已注册的 .npy 特征文件路径<str>
    :param img: 待识别图片(路径<str> 或 BGR 矩阵<np.ndarray>)
    :param threshold: 相似度阈值<float>,默认 0.85,大于等于此值判定为匹配
    :return: 识别结果字典<dict>,格式:
             {
                 "success": True/False,       # 是否识别成功(含人脸检测成功)
                 "matched": True/False,       # 是否匹配到已注册人脸
                 "similarity": 0.xxxx,        # 余弦相似度(浮点数)
                 "msg": "识别成功" / "未检测到人脸" / "相似度低于阈值" / ...
             }
    """
    # Step 1: 加载已注册的特征向量
    registeredEmb = loadRegisteredFeature(registeredNpyPath)
    if registeredEmb is None:
        return {
            "success": False,
            "matched": False,
            "similarity": 0.0,
            "msg": "加载注册特征失败"
        }

    # Step 2: 从待识别图片提取人脸特征
    extractResult = extractCurrentFeature(img)
    if not extractResult["success"]:
        # 提取失败(无人脸或读取失败),直接返回
        return {
            "success": False,
            "matched": False,
            "similarity": 0.0,
            "msg": extractResult["msg"]
        }

    currentEmb = extractResult["embedding"]

    # Step 3: 计算余弦相似度(两个向量都已归一化,点积 = 余弦相似度)
    similarity = computeSimilarity(registeredEmb, currentEmb)

    # Step 4: 阈值判定
    isMatched = similarity >= threshold

    if isMatched:
        msg = "识别成功"
    else:
        msg = "相似度低于阈值"

    return {
        "success": True,
        "matched": isMatched,
        "similarity": round(similarity, 4),  # 保留 4 位小数
        "msg": msg
    }


# ====================================================================
# 批量识别 API(可选,用于一次比对多个已注册用户)
# ====================================================================
def recognizeFaceMulti(registeredNpyPaths, img, threshold=DEFAULT_THRESHOLD):
    """
    批量识别:将待识别图片与多个已注册特征文件逐一比对,返回最佳匹配

    :param registeredNpyPaths: 已注册的 .npy 特征文件路径列表<list<str>>
    :param img: 待识别图片(路径<str> 或 BGR 矩阵<np.ndarray>)
    :param threshold: 相似度阈值<float>,默认 0.85
    :return: 识别结果字典<dict>,格式:
             {
                 "success": True/False,
                 "matched": True/False,
                 "bestMatch": 文件名<str> 或 None,    # 最佳匹配的文件名
                 "bestSimilarity": float,              # 最佳相似度
                 "allResults": [                       # 所有比对结果
                     {"file": "xxx.npy", "similarity": 0.xxxx, "matched": True/False},
                     ...
                 ],
                 "msg": "描述信息"
             }
    """
    # Step 1: 从待识别图片提取人脸特征(只提取一次,复用)
    extractResult = extractCurrentFeature(img)
    if not extractResult["success"]:
        return {
            "success": False,
            "matched": False,
            "bestMatch": None,
            "bestSimilarity": 0.0,
            "allResults": [],
            "msg": extractResult["msg"]
        }

    currentEmb = extractResult["embedding"]

    # Step 2: 逐一比对
    allResults = []
    bestSimilarity = -1.0
    bestMatch = None

    for npyPath in registeredNpyPaths:
        registeredEmb = loadRegisteredFeature(npyPath)
        if registeredEmb is None:
            continue

        similarity = computeSimilarity(registeredEmb, currentEmb)
        isMatched = similarity >= threshold

        allResults.append({
            "file": os.path.basename(npyPath),
            "similarity": round(similarity, 4),
            "matched": isMatched
        })

        # 更新最佳匹配
        if similarity > bestSimilarity:
            bestSimilarity = similarity
            bestMatch = os.path.basename(npyPath) if isMatched else None

    # Step 3: 判断是否有匹配
    hasMatch = bestMatch is not None

    return {
        "success": True,
        "matched": hasMatch,
        "bestMatch": bestMatch,
        "bestSimilarity": round(bestSimilarity, 4),
        "allResults": allResults,
        "msg": "识别成功" if hasMatch else "相似度低于阈值"
    }


# ====================================================================
# 活体检测 + 人脸识别集成 API
# ====================================================================
def runLivenessRecognize(registeredNpyPath, threshold=DEFAULT_THRESHOLD):
    """
    摄像头活体检测 + 人脸识别一体化流程
    ==================================
    1. 先通过活体检测(静默检测 + 主动动作检测)证明是真人
    2. 活体通过后采集"正脸帧"(而非动作帧),提取特征做身份识别
    3. 与注册特征(npy)计算余弦相似度,阈值判定

    关键改进: 识别用"正脸帧"而非"动作帧",避免侧脸/表情帧导致相似度极低。

    :param registeredNpyPath: 已注册的 .npy 特征文件路径<str>
    :param threshold: 相似度阈值<float>,默认 0.85
    :return: 综合结果字典<dict>,格式:
             {
                 "success": bool,               # 整体成功与否
                 "livenessPass": bool,          # 活体是否通过
                 "step": str,                   # 活体失败时的失败动作名
                 "msg": str,                    # 描述信息
                 "recognizeResult": {           # 活体通过后的识别结果
                     "success": bool,
                     "matched": bool,
                     "similarity": float,
                     "msg": str
                 }
             }
    """
    import sys
    import cv2
    import numpy as np

    # 动态导入活体检测模块(FaceMoudle/liveness/livenessDetector.py)
    projectRoot = getProjectRoot()
    faceMoudleDir = os.path.join(projectRoot, 'FaceMoudle')
    if faceMoudleDir not in sys.path:
        sys.path.insert(0, faceMoudleDir)
    from liveness.livenessDetector import LivenessDetector

    # Step 1: 初始化活体检测器(轻量模型 + 静默检测)
    detector = LivenessDetector()

    # Step 2: 打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return {
            "success": False,
            "livenessPass": False,
            "step": "",
            "msg": "摄像头无法打开",
            "recognizeResult": {}
        }

    # Step 3: 执行活体检测(静默 + 主动动作),并采集正脸帧
    livenessResult = detector.runLivenessCheck(cap, collectFrontal=True)
    cap.release()
    cv2.destroyAllWindows()

    # 活体未通过 → 直接返回(防照片攻击)
    if not livenessResult["success"]:
        return {
            "success": False,
            "livenessPass": False,
            "step": livenessResult.get("step", ""),
            "msg": livenessResult.get("msg", "活体检测失败"),
            "recognizeResult": {}
        }

    # Step 4: 用正脸帧提取特征(而非动作帧,保证识别准确率)
    frontalFrame = livenessResult.get("frontalFrame")
    if frontalFrame is None:
        return {
            "success": False,
            "livenessPass": True,
            "step": "",
            "msg": "活体检测通过但未采集到正脸帧",
            "recognizeResult": {}
        }

    extractResult = extractCurrentFeature(frontalFrame)
    if not extractResult["success"]:
        return {
            "success": False,
            "livenessPass": True,
            "step": "",
            "msg": f"正脸特征提取失败: {extractResult['msg']}",
            "recognizeResult": {}
        }

    currentEmb = extractResult["embedding"]

    # Step 5: 加载注册特征 + 计算相似度 + 阈值判定
    registeredEmb = loadRegisteredFeature(registeredNpyPath)
    if registeredEmb is None:
        return {
            "success": False,
            "livenessPass": True,
            "step": "",
            "msg": "加载注册特征失败",
            "recognizeResult": {}
        }

    similarity = computeSimilarity(registeredEmb, currentEmb)
    isMatched = similarity >= threshold

    recognizeResult = {
        "success": True,
        "matched": isMatched,
        "similarity": round(similarity, 4),
        "msg": "识别成功" if isMatched else "相似度低于阈值"
    }

    return {
        "success": True,
        "livenessPass": True,
        "step": "",
        "msg": "活体检测通过,识别完成",
        "recognizeResult": recognizeResult
    }
