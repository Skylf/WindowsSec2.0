# -*- coding: utf-8 -*-
"""
人脸特征提取与保存模块(faceDataGetter)
======================================
负责人脸录入的第二步:从采集的图片中提取人脸特征向量,计算平均特征并保存。

本文件为工具函数库,仅提供功能 API,不包含调用流程。
后续由流程脚本组合调用以下 API 完成完整的人脸录入流程:

1. extractBatchFeatures  - 批量提取图片中的人脸特征(512 维 normed_embedding)
2. computeMeanFeature    - 计算所有特征向量的平均值并 L2 归一化
3. generateFaceFeature   - 完整流程 API(提取 → 计算 → 保存)
4. cleanOldModelFiles    - 清理同一用户的旧模型文件(保证同一用户只有一个模型)
5. saveFeatureNpy/Json   - 分别保存 npy(加载用)和 json(可视化用)两种格式

技术要点:
- InsightFace 的 allowed_modules=['detection','recognition'] 同时加载检测和识别模型
- normed_embedding 是 InsightFace 内部已 L2 归一化的 512 维特征向量
- 对多张图的特征取平均后,平均值不再归一化,需要再次 L2 归一化
- OpenCV imread 不支持中文路径,统一用 np.fromfile + cv2.imdecode 替代
"""

# 标准库
import os        # 路径操作
import sys       # sys.path 注入(FaceMoudle 目录)
import json      # JSON 格式保存特征向量
import time      # 生成时间戳
import hashlib   # 生成校验码

# 第三方库
import cv2       # 图像解码
import numpy as np  # 特征向量计算
from insightface.app import FaceAnalysis  # 人脸检测+识别模型
from concurrent.futures import ProcessPoolExecutor, as_completed  # 多进程并行

# 限制 ONNX 推理线程数(必须在创建任何 session 前生效)
# 本文件位于 FaceMoudle/faceDetecter/,上 2 级即 FaceMoudle 目录
# 注意: ProcessPoolExecutor spawn 子进程重新导入本模块时同样会执行此 patch
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FACE_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _FACE_MOUDLE_DIR)
import modelConfig  # 导入即自动限制 InsightFace 推理线程数


# ====================================================================
# 模块级常量
# ====================================================================
# 支持的图片扩展名(小写),与 inputter 保持一致
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}

# 人脸检测尺寸(准确率优先,与 inputter 保持一致)
DET_SIZE = (480, 480)

# 进程池默认工作进程数(对应 CPU 物理核心数)
DEFAULT_MAX_WORKERS = 4

# ArcFace R50 模型输出的特征向量维度
EMBEDDING_DIM = 512

# 采集图片目录(与 inputter 共用,位于项目根/cache/captured_photos/)
# faceDataGetter.py 在 FaceMoudle/faceDetecter/ 下,项目根是上 3 级
CAPTURED_PHOTOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "cache", "captured_photos"
)

# 特征数据输出目录(项目根/cache/faceData,与 captured_photos 同级)
FACE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "cache", "faceData"
)


# ====================================================================
# 路径工具函数
# ====================================================================
def getProjectRoot():
    """
    获取项目根目录
    :return: 项目根目录的绝对路径<str>
    """
    # faceDataGetter.py 在 FaceMoudle/faceDetecter/ 下,项目根是上 3 级
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def getModelRoot():
    """
    获取 InsightFace 模型根目录
    InsightFace 会在 <root>/models/buffalo_l/ 下自动查找模型文件
    :return: 模型根目录的绝对路径<str>
    """
    return os.path.join(getProjectRoot(), 'FaceMoudle', 'moudleTrainner')


def getCapturedPhotosDir():
    """
    获取采集图片目录(与 inputter 共用)
    :return: 采集图片目录的绝对路径<str>
    """
    return CAPTURED_PHOTOS_DIR


def getFaceDataDir():
    """
    获取特征数据输出目录
    :return: 特征数据输出目录的绝对路径<str>
    """
    return FACE_DATA_DIR


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
# 子进程全局变量(每个子进程独立持有自己的 _APP 实例,避免重复加载模型)
_APP = None


def initFeatureApp(modelRoot):
    """
    初始化 FaceAnalysis 实例,加载检测+识别模型(用于特征提取)
    与 inputter 的区别:这里需要加载 recognition 模型(w600k_r50.onnx)来提取 512 维特征

    :param modelRoot: 模型根目录<str>(InsightFace 会在其下找 models/buffalo_l/)
    :return: 配置好的 FaceAnalysis 实例<FaceAnalysis>
    """
    # allowed_modules=['detection','recognition'] 只加载检测和识别两个模型
    # 跳过关键点(1k3d68/2d106det)和年龄性别(genderage),减少加载时间和内存
    app = FaceAnalysis(
        name='buffalo_l',
        root=modelRoot,
        allowed_modules=['detection', 'recognition'],
        providers=['CPUExecutionProvider']
    )
    # ctx_id=-1 表示 CPU 推理;det_size 检测尺寸,与 inputter 保持一致
    app.prepare(ctx_id=-1, det_size=DET_SIZE)
    return app


def initWorkerProcess(modelRoot):
    """
    子进程初始化函数(由 ProcessPoolExecutor 的 initializer 调用)
    在每个子进程启动时加载一次 FaceAnalysis 模型,后续所有任务共享该实例
    避免每个任务都重复加载模型(检测+识别模型共约 180MB,加载耗时 3-5 秒)

    :param modelRoot: 模型根目录<str>(主进程传入)
    :return: None
    """
    global _APP
    _APP = initFeatureApp(modelRoot)


# ====================================================================
# 特征提取
# ====================================================================
def extractSingleImageFeature(imgPath):
    """
    从单张图片提取人脸特征向量(在子进程中执行,使用全局 _APP 实例)
    流程:读取图片 → 检测人脸 → 取第一张脸的 normed_embedding(512 维)

    :param imgPath: 图片路径<str>
    :return: 检测结果字典<dict>,格式:
             {
                 "path": 图片路径,
                 "status": "success"/"fail"/"error",
                 "msg": 描述信息,
                 "embedding": np.ndarray(512,)  # 仅 status=success 时存在
             }
    """
    try:
        # 读取图片(支持中文路径)
        img = imreadUnicode(imgPath)
        if img is None:
            return {"path": imgPath, "status": "error", "msg": "无法读取"}

        # 人脸检测+特征提取(检测模型+识别模型同时执行)
        faces = _APP.get(img)

        # 无人脸:返回 fail(不是 error,fail 表示图片有效但无人脸)
        if len(faces) == 0:
            return {"path": imgPath, "status": "fail", "msg": "无脸"}

        # 取第一张人脸的 normed_embedding(InsightFace 内部已 L2 归一化的 512 维向量)
        # 注意: InsightFace 按检测置信度降序排列(faces[0] 是置信度最高的人脸)
        embedding = faces[0].normed_embedding

        # 校验特征维度(正常应为 512 维)
        if embedding is None or embedding.shape[0] != EMBEDDING_DIM:
            return {"path": imgPath, "status": "error", "msg": f"特征维度异常: {embedding.shape if embedding is not None else 'None'}"}

        return {
            "path": imgPath,
            "status": "success",
            "msg": f"有脸 (检测到 {len(faces)} 张脸)",
            "embedding": embedding
        }

    except Exception as e:
        # 捕获异常避免单个任务失败导致整个进程池崩溃
        return {"path": imgPath, "status": "error", "msg": f"异常: {e}"}


def extractBatchFeatures(imgDir, maxWorkers=DEFAULT_MAX_WORKERS):
    """
    批量提取图片中的人脸特征向量(多进程并行 + 进度打印)
    遍历 imgDir 下所有图片,提取每张图的 512 维 normed_embedding

    :param imgDir: 图片目录<str>(支持单文件路径,自动识别)
    :param maxWorkers: 进程池工作进程数<int>,默认 4
    :return: 特征向量列表<list<np.ndarray>>,每个元素是 (512,) 的 numpy 数组
             无人脸或读取失败的图片会被跳过,不包含在返回列表中
             如果所有图片都无效,返回空列表 []
    """
    # 获取模型根目录(传给子进程用于初始化 FaceAnalysis)
    modelRoot = getModelRoot()

    # 前置检查:路径不存在时友好返回空列表
    if not os.path.exists(imgDir):
        print(f"路径 {imgDir} 不存在")
        return []

    # 收集待检测图片列表(自动识别单文件 / 文件夹两种模式)
    image_files = []
    if os.path.isfile(imgDir):
        # 单文件模式:直接加入待检测列表
        if os.path.splitext(imgDir)[1].lower() in IMAGE_EXTENSIONS:
            image_files.append(os.path.abspath(imgDir))
        else:
            print(f"文件 {imgDir} 不是支持的图片格式")
            return []
    else:
        # 文件夹模式:遍历目录收集所有图片
        for file in os.listdir(imgDir):
            if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                image_files.append(os.path.join(imgDir, file))

    if not image_files:
        print(f"文件夹 {imgDir} 中没有图片")
        return []

    total = len(image_files)
    print(f"开始提取 {total} 张图片的人脸特征(进程数={maxWorkers}, det_size={DET_SIZE})...")

    # 收集所有有效的特征向量
    embeddings = []
    # 多进程执行(绕过 GIL,真正并行)
    # initializer=initWorkerProcess 让每个子进程启动时加载一次模型,后续任务共享
    with ProcessPoolExecutor(
        max_workers=maxWorkers,
        initializer=initWorkerProcess,
        initargs=(modelRoot,)
    ) as executor:
        # 提交所有图片的检测任务
        future_to_path = {
            executor.submit(extractSingleImageFeature, path): path
            for path in image_files
        }

        # 每完成一张图就处理结果(按完成顺序,不是提交顺序)
        completed = 0
        for future in as_completed(future_to_path):
            result = future.result()
            completed += 1
            imgPath = result['path']
            # 进度打印(百分比)
            percent = completed * 100 // total
            print(f"[{completed}/{total} {percent}%] {os.path.basename(imgPath)}: {result['msg']}")

            # 收集成功的特征向量
            if result['status'] == 'success':
                embeddings.append(result['embedding'])

    print(f"提取完成: 共 {total} 张,有效特征 {len(embeddings)} 个,无脸/错误 {total - len(embeddings)} 张")
    return embeddings


# ====================================================================
# 特征计算
# ====================================================================
def l2Normalize(vec):
    """
    对向量进行 L2 归一化(除以 L2 范数,使结果模长为 1)
    L2 归一化后的向量在余弦相似度计算中更稳定

    :param vec: 待归一化的向量<np.ndarray>
    :return: L2 归一化后的向量<np.ndarray>,与输入形状相同
    """
    # 计算 L2 范数(向量的模长)
    norm = np.linalg.norm(vec)
    # 避免除以 0(零向量直接返回)
    if norm == 0:
        return vec
    return vec / norm


def computeMeanFeature(embeddings):
    """
    计算多个特征向量的平均值,并对平均值进行 L2 归一化
    用于将多张图片的特征融合为一个代表性特征

    原理:
    1. 每张图的 normed_embedding 已 L2 归一化(模长=1)
    2. 取平均后,平均值不再归一化(模长 < 1)
    3. 需要再次 L2 归一化,使最终特征模长=1,便于后续余弦相似度比对

    :param embeddings: 特征向量列表<list<np.ndarray>>,每个元素是 (512,) 的 numpy 数组
    :return: 平均特征向量<np.ndarray>,形状 (512,),已 L2 归一化
             如果输入为空,返回 None
    """
    if not embeddings:
        print("特征列表为空,无法计算平均值")
        return None

    # 将列表堆叠为矩阵: shape = (N, 512),N 是图片数
    embeddingMatrix = np.stack(embeddings, axis=0)
    print(f"特征矩阵形状: {embeddingMatrix.shape}")

    # 沿 axis=0(图片维度)取平均,得到 (512,) 的平均特征
    meanEmbedding = np.mean(embeddingMatrix, axis=0)
    print(f"平均特征(归一化前)模长: {np.linalg.norm(meanEmbedding):.6f}")

    # 对平均值进行 L2 归一化(模长变为 1)
    normalizedEmbedding = l2Normalize(meanEmbedding)
    print(f"平均特征(归一化后)模长: {np.linalg.norm(normalizedEmbedding):.6f}")

    return normalizedEmbedding


# ====================================================================
# 文件命名与保存
# ====================================================================
def computeChecksum(data):
    """
    计算数据的校验码(MD5 前 8 位十六进制)
    用于文件命名,确保不同特征生成不同文件名,同时可用于验证文件完整性

    :param data: 待计算的数据<bytes>
    :return: 8 位十六进制校验码<str>
    """
    return hashlib.md5(data).hexdigest()[:8]


def generateFileName(userName, feature):
    """
    生成模型文件的基础名(用户名+时间戳+校验码)
    最终文件名为: {baseName}.npy 和 {baseName}.json

    :param userName: 用户名<str>
    :param feature: 特征向量<np.ndarray>,用于计算校验码
    :return: 基础文件名<str>,如 "张三_20260812_153022_a1b2c3d4"
    """
    # 时间戳格式: YYYYMMDD_HHMMSS(精确到秒)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    # 校验码: 特征向量 bytes 的 MD5 前 8 位
    checksum = computeChecksum(feature.tobytes())
    # 拼接: 用户名_时间戳_校验码
    baseName = f"{userName}_{timestamp}_{checksum}"
    return baseName


def saveFeatureNpy(feature, filePath):
    """
    将特征向量保存为 NumPy 二进制格式(.npy)
    用于后续人脸识别时快速加载(比 JSON 读写更快,且保留数据类型)

    :param feature: 特征向量<np.ndarray>,形状 (512,)
    :param filePath: 保存路径<str>,如 "faceData/张三_xxx.npy"
    :return: None
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(filePath), exist_ok=True)
    # np.save 保存为 .npy 格式(自动添加扩展名,但这里 filePath 已含扩展名)
    np.save(filePath, feature)
    print(f"[保存] npy: {filePath}")


def saveFeatureJson(feature, filePath):
    """
    将特征向量保存为 JSON 格式(.json)
    包含一个 key 为 "embedding" 的列表,用于可视化查看和跨语言调用

    :param feature: 特征向量<np.ndarray>,形状 (512,)
    :param filePath: 保存路径<str>,如 "faceData/张三_xxx.json"
    :return: None
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(filePath), exist_ok=True)
    # numpy 数组转 Python list(JSON 不支持 numpy 类型)
    data = {
        "embedding": feature.tolist(),
        "dim": len(feature),
        "norm": float(np.linalg.norm(feature))
    }
    # ensure_ascii=False 允许中文(如用户名注释)正常显示
    with open(filePath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[保存] json: {filePath}")


def cleanOldModelFiles(faceDataDir, userName):
    """
    清理同一用户的旧模型文件(保证同一用户同时只有一个模型)
    扫描 faceDataDir,删除所有以 "{userName}_" 开头的 .npy 和 .json 文件

    :param faceDataDir: 特征数据目录<str>
    :param userName: 用户名<str>
    :return: 删除的文件数量<int>
    """
    # 用户文件前缀: 用户名_
    prefix = f"{userName}_"
    deletedCount = 0

    # 目录不存在时无需清理
    if not os.path.exists(faceDataDir):
        return 0

    # 遍历目录,删除匹配的旧文件
    for file in os.listdir(faceDataDir):
        if file.startswith(prefix) and (file.endswith('.npy') or file.endswith('.json')):
            filePath = os.path.join(faceDataDir, file)
            try:
                os.remove(filePath)
                deletedCount += 1
                print(f"[清理] 删除旧模型: {file}")
            except OSError as e:
                # 文件被占用/权限不足时跳过,不中断特征生成流程
                print(f"[清理] 警告: 删除 {file} 失败(可能被占用): {e}")

    if deletedCount > 0:
        print(f"共清理 {deletedCount} 个旧模型文件")
    return deletedCount


# ====================================================================
# 主入口 API(完整流程,供流程脚本调用)
# ====================================================================
def generateFaceFeature(userName, imgDir=None, maxWorkers=DEFAULT_MAX_WORKERS):
    """
    完整的人脸特征生成流程 API:
    1. 批量提取图片中的人脸特征(normed_embedding)
    2. 计算所有特征向量的平均值并 L2 归一化
    3. 清理同一用户的旧模型文件
    4. 保存为 npy 和 json 两种格式
    5. 返回最终的 512 维特征向量

    :param userName: 用户名<str>(用于文件命名)
    :param imgDir: 图片目录<str>,默认 None 时使用 CAPTURED_PHOTOS_DIR
    :param maxWorkers: 进程池工作进程数<int>,默认 4
    :return: 最终的 512 维特征向量<np.ndarray>,形状 (512,),已 L2 归一化
             如果提取失败(无有效特征),返回 None
    """
    # 默认使用采集图片目录
    if imgDir is None:
        imgDir = CAPTURED_PHOTOS_DIR

    print(f"=== 开始为人脸 '{userName}' 生成特征向量 ===")
    print(f"图片目录: {imgDir}")

    # Step 1: 批量提取特征
    embeddings = extractBatchFeatures(imgDir, maxWorkers)
    if not embeddings:
        print("未提取到任何有效特征,流程终止")
        return None

    # Step 2: 计算平均特征并 L2 归一化
    finalFeature = computeMeanFeature(embeddings)
    if finalFeature is None:
        print("特征计算失败,流程终止")
        return None

    # Step 3: 准备输出目录
    faceDataDir = getFaceDataDir()
    os.makedirs(faceDataDir, exist_ok=True)

    # Step 4: 清理同一用户的旧模型文件(保证同一用户只有一个模型)
    cleanOldModelFiles(faceDataDir, userName)

    # Step 5: 生成文件名并保存
    baseName = generateFileName(userName, finalFeature)
    npyPath = os.path.join(faceDataDir, f"{baseName}.npy")
    jsonPath = os.path.join(faceDataDir, f"{baseName}.json")

    saveFeatureNpy(finalFeature, npyPath)
    saveFeatureJson(finalFeature, jsonPath)

    print(f"=== 特征生成完成 ===")
    print(f"用户: {userName}")
    print(f"特征维度: {finalFeature.shape}")
    print(f"特征模长: {np.linalg.norm(finalFeature):.6f}")
    print(f"npy 路径: {npyPath}")
    print(f"json 路径: {jsonPath}")

    return finalFeature


# ====================================================================
# 直接运行入口(仅在本文件作为主脚本运行时执行,被 import 时不触发)
# Windows 多进程用 spawn 方式,子进程会 re-import 主模块,
# 如果此处不加 __name__ 保护,子进程会重复调用 generateFaceFeature 导致无限递归
# ====================================================================
if __name__ == '__main__':
    generateFaceFeature("admin")
