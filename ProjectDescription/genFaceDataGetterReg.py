# -*- coding: utf-8 -*-
"""
生成 faceDataGetter.py 的函数注册表 Excel
输出: ProjectDescription/FunctionNameReg_faceDataGetter.xlsx
"""
import os
from datetime import datetime
from openpyxl import Workbook

# 当前时间(年月日时分秒)
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# faceDataGetter.py 的相对路径
fileRelPath = "FaceMoudle/faceDetecter/faceDataGetter.py"

# 创建工作簿
wb = Workbook()
ws = wb.active
ws.title = "faceDataGetter"

# 表头
headers = ["函数名/类名", "类型", "参数", "返回值", "函数意义", "位置", "记录/修改时间", "其他"]
ws.append(headers)

# 数据行
data = [
    # === 常量 ===
    ("IMAGE_EXTENSIONS", "常量", "无", "set<{'.jpg','.jpeg','.png','.bmp'}>",
     "支持的图片扩展名(小写),与 inputter 保持一致",
     f"({fileRelPath})[IMAGE_EXTENSIONS:40]", now, "模块级常量"),

    ("DET_SIZE", "常量", "无", "tuple<(480, 480)>",
     "人脸检测尺寸,准确率优先,与 inputter 保持一致",
     f"({fileRelPath})[DET_SIZE:43]", now, "模块级常量"),

    ("DEFAULT_MAX_WORKERS", "常量", "无", "int<4>",
     "进程池默认工作进程数",
     f"({fileRelPath})[DEFAULT_MAX_WORKERS:46]", now, "模块级常量"),

    ("EMBEDDING_DIM", "常量", "无", "int<512>",
     "ArcFace R50 模型输出的特征向量维度",
     f"({fileRelPath})[EMBEDDING_DIM:49]", now, "模块级常量"),

    ("CAPTURED_PHOTOS_DIR", "常量", "无", "str<项目根/cache/captured_photos 绝对路径>",
     "采集图片目录(与 inputter 共用)",
     f"({fileRelPath})[CAPTURED_PHOTOS_DIR:53]", now, "模块级常量,基于 __file__ 推导"),

    ("FACE_DATA_DIR", "常量", "无", "str<采集目录/faceData 绝对路径>",
     "特征数据输出目录",
     f"({fileRelPath})[FACE_DATA_DIR:59]", now, "模块级常量"),

    # === 路径工具函数 ===
    ("getProjectRoot", "函数", "无", "项目根目录<str>",
     "获取项目根目录",
     f"({fileRelPath})[getProjectRoot:65]", now, ""),

    ("getModelRoot", "函数", "无", "模型根目录<str>",
     "获取 InsightFace 模型根目录",
     f"({fileRelPath})[getModelRoot:74]", now, ""),

    ("getCapturedPhotosDir", "函数", "无", "采集图片目录<str>",
     "获取采集图片目录(与 inputter 共用)",
     f"({fileRelPath})[getCapturedPhotosDir:83]", now, ""),

    ("getFaceDataDir", "函数", "无", "特征数据目录<str>",
     "获取特征数据输出目录",
     f"({fileRelPath})[getFaceDataDir:91]", now, ""),

    ("imreadUnicode", "函数", "path<str>", "BGR图像矩阵<np.ndarray>",
     "读取中文路径下的图片(OpenCV imread 中文路径 workaround)",
     f"({fileRelPath})[imreadUnicode:99]", now, ""),

    # === 模型初始化 ===
    ("_APP", "变量", "无", "FaceAnalysis",
     "子进程全局模型实例,每个子进程独立持有",
     f"({fileRelPath})[_APP:114]", now, "全局变量"),

    ("initFeatureApp", "函数", "modelRoot<str>", "FaceAnalysis",
     "初始化 FaceAnalysis,加载检测+识别模型(用于特征提取)",
     f"({fileRelPath})[initFeatureApp:117]", now, ""),

    ("initWorkerProcess", "函数", "modelRoot<str>", "None",
     "子进程初始化函数,每个子进程启动时加载一次模型",
     f"({fileRelPath})[initWorkerProcess:138]", now, "ProcessPoolExecutor initializer"),

    # === 特征提取 ===
    ("extractSingleImageFeature", "函数", "imgPath<str>", "dict",
     "从单张图片提取人脸特征向量(子进程中执行)",
     f"({fileRelPath})[extractSingleImageFeature:154]", now, "返回含 path/status/msg/embedding"),

    ("extractBatchFeatures", "函数", "imgDir<str>, maxWorkers<int>", "list<np.ndarray>",
     "批量提取图片中的人脸特征向量(多进程并行+进度打印)",
     f"({fileRelPath})[extractBatchFeatures:201]", now, "支持单文件/文件夹两种模式"),

    # === 特征计算 ===
    ("l2Normalize", "函数", "vec<np.ndarray>", "np.ndarray",
     "对向量进行 L2 归一化(模长变为 1)",
     f"({fileRelPath})[l2Normalize:278]", now, ""),

    ("computeMeanFeature", "函数", "embeddings<list<np.ndarray>>", "np.ndarray",
     "计算多个特征向量的平均值并 L2 归一化",
     f"({fileRelPath})[computeMeanFeature:294]", now, "返回 (512,) 归一化向量"),

    # === 文件命名与保存 ===
    ("computeChecksum", "函数", "data<bytes>", "str",
     "计算数据的校验码(MD5 前 8 位十六进制)",
     f"({fileRelPath})[computeChecksum:330]", now, ""),

    ("generateFileName", "函数", "userName<str>, feature<np.ndarray>", "str",
     "生成模型文件基础名(用户名+时间戳+校验码)",
     f"({fileRelPath})[generateFileName:341]", now, ""),

    ("saveFeatureNpy", "函数", "feature<np.ndarray>, filePath<str>", "None",
     "将特征向量保存为 NumPy 二进制格式(.npy)",
     f"({fileRelPath})[saveFeatureNpy:359]", now, ""),

    ("saveFeatureJson", "函数", "feature<np.ndarray>, filePath<str>", "None",
     "将特征向量保存为 JSON 格式(.json),含 embedding/dim/norm",
     f"({fileRelPath})[saveFeatureJson:375]", now, ""),

    ("cleanOldModelFiles", "函数", "faceDataDir<str>, userName<str>", "int",
     "清理同一用户的旧模型文件(保证同一用户只有一个模型)",
     f"({fileRelPath})[cleanOldModelFiles:398]", now, "返回删除的文件数量"),

    # === 主入口 API ===
    ("generateFaceFeature", "函数", "userName<str>, imgDir<str>, maxWorkers<int>", "np.ndarray",
     "完整流程 API:提取特征→计算平均→清理旧文件→保存 npy+json",
     f"({fileRelPath})[generateFaceFeature:431]", now, "返回 (512,) 归一化特征向量"),
]

for row in data:
    ws.append(row)

# 调整列宽
for col_idx, col_letter in enumerate(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 1):
    ws.column_dimensions[col_letter].width = [30, 10, 35, 30, 45, 50, 22, 35][col_idx - 1]

# 保存
outputPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FunctionNameReg_faceDataGetter.xlsx")
wb.save(outputPath)
print(f"函数注册表已生成: {outputPath}")
print(f"共登记 {len(data)} 个条目")
