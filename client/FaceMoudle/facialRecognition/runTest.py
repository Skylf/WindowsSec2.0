# -*- coding: utf-8 -*-
"""
人脸识别流程跑通脚本(带活体检测)
=================================
组合调用 recognition 工具库的 API,完成完整的人脸识别流程:
1. 选择已注册的特征文件(.npy)
2. 识别方式:
   A. 图片文件识别(传统方式,用于测试)
   B. 【默认】摄像头活体检测识别(先过活体验证,再比对)
3. 调用 recognizeFace 完成 1:1 比对
4. 输出识别结果(是否匹配 / 相似度)

与旧版区别:
  旧版"摄像头拍照识别"→ 拍一帧直接比对,照片/翻拍可欺骗
  新版"活体检测识别"→ 静默检测 + 自适应动作(随机1~5个),再采集正脸帧比对
"""
import platform
import sys
import time
import os
import glob

# 导入人脸识别工具库(同目录模块)
import recognition


def selectFeatureFile():
    """
    选择已注册的特征文件(.npy)
    选项 1: 自动扫描 cache/faceData 目录,列出所有 .npy 文件供选择
    选项 2: 手动输入 .npy 文件路径
    :return: 特征文件路径<str>
    """
    os.system("cls" if platform.system() == "Windows" else "clear")
    print("=" * 50)
    print("          人脸识别流程(带活体检测)")
    print("=" * 50)
    print("\n选择已注册的特征文件:")
    print("  1. 从已注册列表中选择(扫描 cache/faceData)")
    print("  2. 手动输入特征文件路径")
    print("输入 /exit 退出")
    user_input = str(input("请输入数字: "))

    if user_input == "1":
        face_data_dir = recognition.getFaceDataDir()
        npy_files = glob.glob(os.path.join(face_data_dir, "*.npy"))

        if not npy_files:
            print(f"目录 {face_data_dir} 下没有特征文件,请先进行人脸录入")
            time.sleep(2)
            return selectFeatureFile()

        print(f"\n已注册的特征文件(共 {len(npy_files)} 个):")
        for i, f in enumerate(npy_files):
            print(f"  {i + 1}. {os.path.basename(f)}")

        print("输入 /exit 退出")
        choice = str(input("请输入序号: "))
        if choice == "/exit":
            sys.exit()

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(npy_files):
                return npy_files[idx]
            else:
                print("序号超出范围!")
                time.sleep(1.5)
                return selectFeatureFile()
        except ValueError:
            print("请输入数字!")
            time.sleep(1.5)
            return selectFeatureFile()

    elif user_input == "2":
        file_path = str(input("请输入 .npy 特征文件路径: "))
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            time.sleep(1.5)
            return selectFeatureFile()
        return file_path

    elif user_input == "/exit":
        sys.exit()
    else:
        print("输入错误,请重试!")
        time.sleep(1.5)
        return selectFeatureFile()


def selectRecognizeMode():
    """
    选择识别方式
    选项 1: 图片文件识别(传统方式,用于测试/离线场景)
    选项 2: 【默认/推荐】摄像头活体检测识别(防照片攻击,实装方式)
    :return: 识别模式<str> "image" / "liveness"
    """
    print("\n选择识别方式:")
    print("  1. 指定图片文件(传统方式,用于测试)")
    print("  2. 【推荐】摄像头活体检测识别(静默+随机动作,防照片欺骗)")
    print("输入 /exit 退出")
    user_input = str(input("请输入数字(回车默认=2): "))

    if user_input == "" or user_input == "2":
        return "liveness"
    elif user_input == "1":
        return "image"
    elif user_input == "/exit":
        sys.exit()
    else:
        print("输入错误,使用默认活体检测识别!")
        return "liveness"


def selectTestImage():
    """
    【传统方式】指定图片文件路径识别
    :return: 图片路径<str>
    """
    img_path = str(input("\n请输入图片文件路径: "))
    if not os.path.exists(img_path):
        print(f"文件不存在: {img_path}")
        time.sleep(1.5)
        return selectTestImage()
    return img_path


def setThreshold():
    """
    设置相似度阈值(可选,默认 0.85)
    :return: 阈值<float>
    """
    print(f"\n当前默认阈值: {recognition.DEFAULT_THRESHOLD}")
    print("  - 严格场景(安全门禁): 0.85(默认)")
    print("  - 普通场景(考勤): 0.6-0.8")
    print("  - 宽松场景(体验): 0.4-0.6")
    user_input = str(input("是否使用默认阈值?(回车=默认,或输入数值): "))

    if user_input == "" or user_input == "/exit":
        return recognition.DEFAULT_THRESHOLD

    try:
        threshold = float(user_input)
        if 0.0 <= threshold <= 1.0:
            return threshold
        else:
            print("阈值范围应在 0.0-1.0 之间,使用默认值")
            return recognition.DEFAULT_THRESHOLD
    except ValueError:
        print("输入无效,使用默认值")
        return recognition.DEFAULT_THRESHOLD


def doRecognize(npyPath, img, threshold):
    """
    调用 recognition.recognizeFace 完成 1:1 人脸识别

    :param npyPath: 已注册的 .npy 特征文件路径<str>
    :param img: 待识别图片(路径<str> 或 BGR 矩阵<np.ndarray>)
    :param threshold: 相似度阈值<float>
    :return: 识别结果字典<dict>
    """
    result = recognition.recognizeFace(npyPath, img, threshold=threshold)
    return result


def doLivenessRecognize(npyPath, threshold):
    """
    【推荐】摄像头活体检测 + 人脸识别
    1. 先调用 recognition.runLivenessRecognize 跑活体检测流程(静默+自适应动作)
    2. 活体通过后,从通过动作的帧中提取特征与注册特征比对
    (runLivenessRecognize 内部已封装好:活体检测 → 特征提取 → 相似度比对 → 阈值判定)

    :param npyPath: 已注册的 .npy 特征文件路径<str>
    :param threshold: 相似度阈值<float>
    :return: 综合结果字典<dict>
             {"success": bool, "livenessPass": bool, "recognizeResult": {...原始识别结果...}}
    """
    # 调用 recognition 工具库新增的活体识别 API
    # 该 API 内部:活体检测(静默+自适应动作)→ 通过 → 采集正脸帧 → 与注册特征比对
    print("\n即将开始活体检测识别...")
    print("静默检测通过后,需随机做 1~5 个动作完成验证")
    print("注意:动作累计失败 2 次判定识别失败")
    time.sleep(2)

    result = recognition.runLivenessRecognize(npyPath, threshold=threshold)
    return result


def printLivenessRecognizeResult(result, threshold):
    """
    打印活体检测识别结果
    :param result: runLivenessRecognize 返回的综合结果字典<dict>
    :param threshold: 相似度阈值<float>
    """
    print("\n" + "=" * 50)
    print("          活体检测识别结果")
    print("=" * 50)

    livenessPass = result.get("livenessPass", False)
    recognizeResult = result.get("recognizeResult", {})

    if not livenessPass:
        # 活体未通过
        print(f"✗ 活体检测失败: {result.get('msg', '')}")
        step = result.get('step', '')
        if step:
            print(f"  失败步骤: {step}")
        print("\n识别未完成,请重新开始。")
        print("提示:")
        print("  1. 确保摄像头画面中人脸清晰可见")
        print("  2. 动作幅度足够大,在 15 秒内完成")
        return

    # 活体通过,显示识别结果
    print(f"✓ 活体检测通过")
    matched = recognizeResult.get("matched", False)
    similarity = recognizeResult.get("similarity", 0.0)
    msg = recognizeResult.get("msg", "")

    print(f"识别结果: matched={matched}, similarity={similarity}, msg={msg}")
    print()

    if recognizeResult.get("success", False) and matched:
        print(f"✓ 识别成功!相似度 {similarity:.4f} >= 阈值 {threshold}")
    elif recognizeResult.get("success", False) and not matched:
        print(f"✗ 未匹配!相似度 {similarity:.4f} < 阈值 {threshold}")
        print("  可能原因:非注册用户 / 角度差异过大 / 光照差异")
    else:
        print(f"✗ 识别失败: {msg}")


def printRecognizeResult(result, threshold):
    """
    打印普通图片识别结果
    """
    print("\n=== 识别结果 ===")
    print(f"success  : {result['success']}")
    print(f"matched  : {result['matched']}")
    print(f"similarity: {result['similarity']}")
    print(f"msg      : {result['msg']}")

    if result['success'] and result['matched']:
        print(f"\n✓ 识别成功!相似度 {result['similarity']:.4f} >= 阈值 {threshold}")
    elif result['success'] and not result['matched']:
        print(f"\n✗ 未匹配!相似度 {result['similarity']:.4f} < 阈值 {threshold}")
    else:
        print(f"\n✗ 识别失败: {result['msg']}")


if __name__ == '__main__':
    # Step 1: 选择已注册的特征文件
    npyPath = selectFeatureFile()
    print(f"已选择特征文件: {os.path.basename(npyPath)}")

    # Step 2: 选择识别方式(默认=活体检测)
    mode = selectRecognizeMode()

    # Step 3: 设置阈值
    threshold = setThreshold()

    if mode == "liveness":
        # 方式 2: 活体检测识别(先活体,再识别,防照片攻击)
        result = doLivenessRecognize(npyPath, threshold)
        printLivenessRecognizeResult(result, threshold)

    else:
        # 方式 1: 图片文件识别(传统方式,用于测试)
        img = selectTestImage()
        print("\n正在识别(首次运行需加载模型,请稍候)...")
        result = doRecognize(npyPath, img, threshold)
        printRecognizeResult(result, threshold)
