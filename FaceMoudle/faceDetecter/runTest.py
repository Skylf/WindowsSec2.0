# -*- coding: utf-8 -*-
"""
人脸特征提取流程跑通脚本
=======================
组合调用 faceDataGetter 工具库的 API,完成完整的人脸特征提取流程:
1. 输入用户名(用于文件命名)
2. 选择图片来源(已采集目录 / 指定目录 / 指定单文件)
3. 调用 generateFaceFeature 完成特征提取+计算+保存
4. 输出结果
"""
import platform
import sys
import time
import os
import numpy as np

# 导入人脸特征提取工具库(同目录模块)
import faceDataGetter


def inputUserName():
    """
    输入用户名(用于特征文件命名,格式: 用户名_时间戳_校验码)
    :return: 用户名<str>
    """
    os.system("cls" if platform.system() == "Windows" else "clear")
    print("=== 人脸特征提取流程 ===")
    print("输入 /exit 退出")
    user_name = str(input("请输入用户名: "))
    if user_name == "/exit":
        sys.exit()
    if not user_name.strip():
        print("用户名不能为空,请重试!")
        time.sleep(1.5)
        return inputUserName()
    return user_name


def selectImageSource():
    """
    选择图片来源
    选项 1: 使用已采集的图片(默认 cache/captured_photos 目录)
    选项 2: 指定图片目录
    选项 3: 指定单张图片文件
    :return: 图片路径<str>(目录或文件)
    """
    print("\n选择图片来源:")
    print("  1. 使用已采集的图片(cache/captured_photos)")
    print("  2. 指定图片目录")
    print("  3. 指定单张图片文件")
    print("输入 /exit 退出")
    user_input = str(input("请输入数字: "))

    if user_input == "1":
        # 使用默认采集目录(与 inputter 共用)
        img_path = faceDataGetter.getCapturedPhotosDir()
        print(f"使用目录: {img_path}")
        return img_path
    elif user_input == "2":
        # 手动输入图片目录路径
        dir_path = str(input("请输入图片目录路径: "))
        if not os.path.exists(dir_path):
            print(f"目录不存在: {dir_path}")
            time.sleep(1.5)
            return selectImageSource()
        return dir_path
    elif user_input == "3":
        # 手动输入单张图片文件路径
        file_path = str(input("请输入图片文件路径: "))
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            time.sleep(1.5)
            return selectImageSource()
        return file_path
    elif user_input == "/exit":
        sys.exit()
    else:
        print("输入错误,请重试!")
        time.sleep(1.5)
        return selectImageSource()


def extractAndSave(userName, imgPath):
    """
    调用 faceDataGetter.generateFaceFeature 完成特征提取+计算+保存
    该函数内部完成:
    1. 批量提取图片中的人脸特征(normed_embedding)
    2. 计算平均特征并 L2 归一化
    3. 清理同一用户的旧模型文件
    4. 保存为 npy + json 两种格式

    :param userName: 用户名<str>
    :param imgPath: 图片路径<str>(目录或文件)
    :return: 最终的 512 维特征向量<np.ndarray>,失败返回 None
    """
    # 调用 faceDataGetter 的完整流程 API
    feature = faceDataGetter.generateFaceFeature(userName, imgDir=imgPath)
    return feature


if __name__ == '__main__':
    # Step 1: 输入用户名
    userName = inputUserName()

    # Step 2: 选择图片来源
    imgPath = selectImageSource()

    # Step 3: 提取特征并保存
    # 注意:generateFaceFeature 内部使用多进程,必须在 __name__ == '__main__' 保护下调用
    # 否则 Windows spawn 模式下子进程会重复执行导致无限递归
    feature = extractAndSave(userName, imgPath)

    # Step 4: 输出结果
    print("\n=== 结果 ===")
    if feature is not None:
        print(f"特征生成成功!")
        print(f"用户: {userName}")
        print(f"特征维度: {feature.shape}")
        print(f"特征模长: {np.linalg.norm(feature):.6f}")
        print(f"特征文件目录: {faceDataGetter.getFaceDataDir()}")
    else:
        print("特征生成失败!请检查图片中是否包含人脸。")
