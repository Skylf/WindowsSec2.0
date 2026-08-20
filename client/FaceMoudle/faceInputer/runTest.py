# -*- coding: utf-8 -*-
"""
人脸录入流程跑通脚本
===================
组合调用 inputter 工具库的 API,提供三种录入模式,并完成"采集 → 清洗 → 特征提取"全流程:
1. 文件选择模式(测试用)
2. 摄像头引导式采集(正面 10 张 + 左转/右转/抬头/眨眼/张嘴 各 4 张 = 30 张)
3. 【推荐】活体检测录入(静默检测 + 主动动作检测 + 图像收集)
"""
import platform
import sys
import time
import os

# 导入人脸录入工具库(同目录模块)
import inputter


def inputUserName():
    """
    输入用户名(用于后续特征文件命名)
    :return: 用户名<str>
    """
    user_name = str(input("请输入用户名(用于特征文件命名): "))
    if user_name == "/exit":
        sys.exit()
    if not user_name.strip():
        print("用户名不能为空")
        time.sleep(1.5)
        return inputUserName()
    return user_name


def collectImage():
    """
    选择录入方式,统一返回 {"path": 图片路径<str>, "userName": 用户名<str>}
    :return: 录入结果字典<dict>
    """
    os.system("cls" if platform.system() == "Windows" else "clear")
    print("=" * 50)
    print("          人脸录入流程")
    print("=" * 50)
    print("选择录入方式:")
    print("  1. 选择文件(测试用)")
    print("  2. 摄像头引导式采集 30 张")
    print("  3. 活体检测录入【推荐】(静默+动作验证 + 图像收集)")
    print("输入 /exit 退出")
    user_input = str(input("请输入数字: "))

    if user_input == "1":
        # 方式 1: 文件选择对话框(测试用)
        img_path = inputter.imgInputter()
        if not img_path:
            print("未选择文件")
            time.sleep(1.5)
            return collectImage()
        userName = inputUserName()
        return {"path": img_path, "userName": userName}

    elif user_input == "2":
        # 方式 2: 摄像头引导式采集(openCamera: 正面 10 + 5 动作各 4 = 30 张)
        userName = inputUserName()
        print("即将开始引导式采集(正面 10 张 + 左转/右转/抬头/眨眼/张嘴 各 4 张 = 30 张)...")
        print("  - 每阶段终端+画面有提示,满足条件自动连拍")
        print("  - 按 ESC 可中途退出")
        time.sleep(2)
        img_dir = inputter.openCamera()
        if not img_dir:
            print("采集失败或用户取消")
            time.sleep(1.5)
            return collectImage()
        return {"path": img_dir, "userName": userName}

    elif user_input == "3":
        # 方式 3: 活体检测录入(静默检测 + 主动动作 + 图像收集)
        userName = inputUserName()
        print("即将开始活体检测录入(静默检测 + 主动动作 + 图像收集)...")
        time.sleep(2)
        result = inputter.openCameraWithLiveness(userName)
        if not result["success"]:
            print(f"活体检测录入失败: {result.get('msg', '')}")
            time.sleep(2)
            return collectImage()
        return {"path": result["imgDir"], "userName": userName}

    elif user_input == "/exit":
        sys.exit()

    else:
        print("输入错误,请重试!")
        time.sleep(1.5)
        return collectImage()


def checkAndClean(imgPath):
    """
    批量检测人脸 + 清理无人脸图片
    调用顺序: faceCheck → handleNoFace → coverDict
    :param imgPath: 图片路径(文件或目录)<str>
    :return: 清理后的可用人脸字典<dict>
    """
    print(f"\n[Step 1] 检测人脸...")
    sharedDict = inputter.faceCheck(imgPath)
    if not sharedDict:
        print("未检测到任何可用人脸图片!")
        return {}
    print(f"检测完成: 共 {len(sharedDict)} 张")

    print(f"\n[Step 2] 清理无脸图片...")
    cleanedDict = inputter.handleNoFace(sharedDict)

    print(f"\n[Step 3] 安全覆盖字典...")
    sharedDict = inputter.coverDict(sharedDict, cleanedDict)

    total = len(sharedDict)
    ok = sum(1 for v in sharedDict.values() if v.get('hasFace', False))
    print(f"\n[最终结果] 可用人脸图片: {ok}/{total} 张")

    return sharedDict


def extractFeature(userName, imgPath):
    """
    调用 faceDetecter/faceDataGetter.generateFaceFeature 提取并保存特征
    :param userName: 用户名<str>
    :param imgPath: 图片路径<str>(目录或文件)
    :return: 最终 512 维特征向量<np.ndarray>,失败返回 None
    """
    import sys
    projectRoot = inputter.getProjectRoot()
    faceDetecterDir = os.path.join(projectRoot, 'FaceMoudle', 'faceDetecter')
    if faceDetecterDir not in sys.path:
        sys.path.insert(0, faceDetecterDir)
    from faceDataGetter import generateFaceFeature
    # generateFaceFeature 内部使用多进程,必须在 __main__ 保护下调用
    return generateFaceFeature(userName, imgDir=imgPath)


if __name__ == '__main__':
    # Step 1: 选择录入方式
    collectResult = collectImage()
    imgPath = collectResult["path"]
    userName = collectResult["userName"]

    print(f"\n使用图片路径: {imgPath}")

    # Step 2: 批量检测 + 清理
    sharedDict = checkAndClean(imgPath)

    # Step 3: 特征提取 + 保存
    if sharedDict:
        print("\n" + "=" * 50)
        print("          开始特征提取")
        print("=" * 50)
        feature = extractFeature(userName, imgPath)
        if feature is not None:
            print("\n录入全流程完成!")
            print(f"  用户: {userName}")
            print(f"  特征维度: {feature.shape}")
            print(f"  特征模长: {__import__('numpy').linalg.norm(feature):.6f}")
        else:
            print("\n特征提取失败!请检查图片中是否包含清晰人脸。")
    else:
        print("\n预检未通过,没有可用的人脸图片!请重新采集。")
