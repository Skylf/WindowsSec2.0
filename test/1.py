# -*- coding: utf-8 -*-
"""
InsightFace 基础功能测试脚本
功能:验证 insightface 安装、模型加载、人脸检测、特征向量提取是否正常
测试流程:import → 加载模型 → 读取测试图 → 检测人脸 → 输出特征向量维度
"""
import os
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis


def imreadUnicode(path):
    """
    读取含中文等非 ASCII 字符路径的图片(OpenCV imread 在 Windows 上不支持中文路径的 workaround)
    参数:
        path <str>: 图片文件路径(支持中文)
    返回值:
        img <numpy.ndarray|None>: 解码后的图像(BGR 格式),失败返回 None
    原理:
        cv2.imread 底层用 C 标准库 fopen,Windows 下 fopen 不支持非 ASCII 路径;
        改用 np.fromfile 二进制读取 + cv2.imdecode 解码可绕过此限制
    """
    # np.fromfile 支持任意 Unicode 路径,将文件内容读为 uint8 数组
    data = np.fromfile(path, dtype=np.uint8)
    # cv2.imdecode 从内存缓冲区解码图像,返回 BGR 格式
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


# 项目根目录(test/ 的父目录)
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 模型根目录:InsightFace 会在 <root>/models/buffalo_l/ 下找模型
# 这里指向 FaceMoudle/moudleTrainner,模型实际在 FaceMoudle/moudleTrainner/models/buffalo_l/
modelRoot = os.path.join(projectRoot, 'FaceMoudle', 'moudleTrainner')
# 强制使用 CPU 推理(CPUExecutionProvider)
# root=modelRoot 让 InsightFace 从项目内 FaceMoudle/moudleTrainner/models/buffalo_l/ 加载模型
# 这样项目打包到其他电脑时模型文件随项目走,不依赖 C 盘缓存
app = FaceAnalysis(name='buffalo_l', root=modelRoot, providers=['CPUExecutionProvider'])
# ctx_id=-1 表示使用 CPU;prepare 加载检测/关键点/识别/年龄性别等子模型
app.prepare(ctx_id=-1)

# 构造测试图路径(insightface 内置的 t1.jpg)
# 注意:不能直接用 insightface.data.get_image,因其内部 cv2.imread 不支持含中文的项目路径
image_path = os.path.join(
    os.path.dirname(insightface.__file__),  # insightface 包安装目录
    'data', 'images', 't1.jpg'
)
img = imreadUnicode(image_path)
assert img is not None, f"测试图读取失败: {image_path}"

# 人脸检测+识别:app.get 一次完成检测、关键点对齐、特征提取、年龄性别估计
faces = app.get(img)
print(f"检测到 {len(faces)} 张人脸")

if len(faces) > 0:
    # 输出第一张人脸的特征向量维度(buffalo_l 的 w600k_r50.onnx 输出 512 维)
    print(f"特征向量维度: {faces[0].embedding.shape}")
    # 顺便输出年龄性别估计(展示 genderage 模型也加载成功)
    print(f"年龄: {faces[0].age}, 性别: {'男' if faces[0].gender == 1 else '女'}")
