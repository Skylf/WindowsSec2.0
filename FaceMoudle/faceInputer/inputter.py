# -*- coding: utf-8 -*-
"""
人脸录入模块(inputter)
======================
负责图像的接收、采集与预检:
1. imgInputter  - 从外部文件选择图片(测试用)
2. openCamera   - 摄像头实时批量采集照片(实装方法)
3. faceCheck    - 批量预检:确保文件夹中每张图都包含人脸(只检测,不提取特征)
"""

"""
工作流程：
imgInputter/openCamera函数采集图像，放入cache/captured_photos下，faceCheck识别人脸，确保采集的图像可用
"""

# 标准库
import os
import sys  # sys.path 注入(FaceMoudle 目录)

# 第三方库
import cv2
import numpy as np
from tkinter import filedialog, Tk
from insightface.app import FaceAnalysis
from concurrent.futures import ProcessPoolExecutor, as_completed

# 限制 ONNX 推理线程数(必须在创建任何 session 前生效)
# 本文件位于 FaceMoudle/faceInputer/,上 2 级即 FaceMoudle 目录
# 注意: ProcessPoolExecutor spawn 子进程重新导入本模块时同样会执行此 patch
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FACE_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _FACE_MOUDLE_DIR)
import modelConfig  # 导入即自动限制 InsightFace 推理线程数


# ====================================================================
# 模块级常量
# ====================================================================
# 支持的图片扩展名(小写)
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}

# 摄像头批量采集的目标张数
# 30 张是质量与速度的最佳平衡点:
# - 质量方面:30 张覆盖不同角度/光照/表情,平均特征足够稳定(学术界通常 20-50 张即可)
# - 速度方面:faceCheck 检测约 5 秒,faceDataGetter 特征提取约 12-18 秒
# - 采集方面:摄像头 30fps 下约 1 秒即可采完,用户体验好
TARGET_CAPTURE_COUNT = 30

# 摄像头采集的保存目录(项目根目录下的公共 cache 目录,避免 cwd 依赖)
# 实际路径: <项目根>/cache/captured_photos/
# cache 作为公共缓存目录,后续其他模块也可使用(如人脸特征缓存等)
# inputter.py 位于 FaceMoudle/faceInputer/,项目根是上 3 级
CAPTURE_SAVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "cache", "captured_photos"
)

# 人脸检测尺寸(准确率优先,选 480 而非 640/320,平衡速度与精度)
# 说明:人脸录入场景下人脸占比大,480 足够检出;640 会慢 1.7 倍但无显著精度提升
DET_SIZE = (480, 480)

# 进程池默认工作进程数(对应 CPU 物理核心数,4 是常见值)
DEFAULT_MAX_WORKERS = 4


# ====================================================================
# 工具函数
# ====================================================================
def getProjectRoot():
    """
    获取项目根目录
    :return: 项目根目录的绝对路径<str>
    """
    # inputter.py 在 FaceMoudle/faceInputer/ 下,项目根是上三级
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def getModelRoot():
    """
    获取 InsightFace 模型根目录
    InsightFace 会在 <root>/models/buffalo_l/ 下自动查找模型文件
    :return: 模型根目录的绝对路径<str>
    """
    return os.path.join(getProjectRoot(), 'FaceMoudle', 'moudleTrainner')


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
# 子进程全局模型(进程池 initializer 初始化,每个子进程只加载一次)
# ====================================================================
# 子进程全局变量(每个子进程独立持有自己的 _APP 实例)
_APP = None


def initWorkerProcess(modelRoot):
    """
    子进程初始化函数(由 ProcessPoolExecutor 的 initializer 调用)
    在每个子进程启动时加载一次 FaceAnalysis 模型,后续所有任务共享该实例
    避免每个任务都重复加载模型(模型加载耗时 2-5 秒)

    :param modelRoot: 模型根目录<str>(主进程传入)
    :return: None
    """
    global _APP
    # allowed_modules=['detection'] 只加载人脸检测模型(det_10g.onnx,16MB)
    # 跳过关键点/年龄性别/特征提取模型,大幅减少推理时间
    _APP = FaceAnalysis(
        name='buffalo_l',
        root=modelRoot,
        allowed_modules=['detection'],
        providers=['CPUExecutionProvider']
    )
    _APP.prepare(ctx_id=-1, det_size=DET_SIZE)


def checkSingleImage(imgPath):
    """
    检查单张图片是否包含人脸(在子进程中执行,使用全局 _APP 实例)
    :param imgPath: 图片路径<str>
    :return: 检查结果字典<dict>,格式:
             {"path": 路径, "status": "success"/"fail"/"error", "msg": 描述信息}
    """
    try:
        # 读取图片(支持中文路径)
        img = imreadUnicode(imgPath)
        if img is None:
            return {"path": imgPath, "status": "error", "msg": "无法读取"}

        # 人脸检测(只跑 det_10g.onnx,不跑关键点/年龄性别/特征提取)
        faces = _APP.get(img)

        if len(faces) == 0:
            return {"path": imgPath, "status": "fail", "msg": "无脸"}
        else:
            return {"path": imgPath, "status": "success",
                    "msg": f"有脸 (检测到 {len(faces)} 张脸)"}
    except Exception as e:
        return {"path": imgPath, "status": "error", "msg": str(e)}


# ====================================================================
# 主要功能函数
# ====================================================================
def imgInputter():
    """
    从外部文件系统选择图片(测试用)
    弹出文件选择对话框,返回用户选择的图片路径
    :return: 图片路径<str>,用户取消则返回空字符串
    """
    # 隐藏 Tk 主窗口,只显示文件选择对话框
    root = Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="选择图片",
        filetypes=[("图片文件", "*.jpg *.jpeg *.png")]
    )

    return file_path


def openCamera():
    """
    摄像头引导式采集照片(替换传统的按 O 键盲拍,加入姿态 + 动作引导)
    ==============================================================
    采集 30 张照片,分布如下:
      ① 正面照:    10 张 (要求 Yaw 与 Pitch 接近 0°,姿态摆正)
      ② 左转:       4 张 (Yaw < -15°)
      ③ 右转:       4 张 (Yaw > 15°)
      ④ 抬头:       4 张 (Pitch > 10°)
      ⑤ 眨眼:       4 张 (EAR 下降 > 30%)
      ⑥ 张嘴:       4 张 (MAR > 0.5)
    合计: 10 + 4×5 = 30 张(与 TARGET_CAPTURE_COUNT 一致)

    与原 openCamera 的区别:
      原:用户按 O 键盲拍 30 张(角度/表情随机,质量不可控)
      新:终端+画面引导用户摆出姿态/动作,每满足条件连拍一张,保证每帧质量
    检测阶段复用 LivenessDetector 的轻量模型(detection + landmark_2d_106,21MB)
    只做姿态判定不跑识别模型,速度快(<100ms/帧)

    :return: CAPTURE_SAVE_DIR<str>(即采集图片保存目录,下游 faceCheck 用)
             采集失败或用户 ESC 中断返回 None
    """
    import sys
    import time          # time.time / time.sleep 用于阶段计时、连拍间隔
    import numpy as np   # 眨眼 baseline EAR 平均值计算(np.mean)
    # 动态导入活体检测模块的几何计算工具(FaceMoudle/liveness/livenessDetector.py)
    projectRoot = getProjectRoot()
    faceMoudleDir = os.path.join(projectRoot, 'FaceMoudle')
    if faceMoudleDir not in sys.path:
        sys.path.insert(0, faceMoudleDir)
    from liveness.livenessDetector import LivenessDetector, LEFT_EYE_INDICES, RIGHT_EYE_INDICES

    # 引导采集的绝对姿态阈值(注意: 与活体验证的相对偏移阈值不同,
    # 这里用绝对角度引导用户摆出姿势后拍照)
    BASELINE_DURATION = 1.5          # 眨眼基准采集时长<秒>
    THRESHOLD_YAW_LEFT = -20.0       # 左转拍照: Yaw < -20°
    THRESHOLD_YAW_RIGHT = 20.0       # 右转拍照: Yaw > 20°
    THRESHOLD_PITCH_UP = 15.0        # 抬头拍照: Pitch > 15°
    THRESHOLD_EAR_DROP = 0.2         # 眨眼拍照: EAR 下降 > 20%
    THRESHOLD_MAR_OPEN = 0.4         # 张嘴拍照: MAR > 0.4

    # 30 张照片分配: 正面 10 张 + 5 个动作各 4 张
    # 正面多拍一点,因为识别时正脸占主要比重
    SHOT_COUNT_FRONTAL = 10   # 正面照数量
    SHOT_COUNT_PER_ACTION = 4  # 每个动作(左转/右转/抬头/眨眼/张嘴)各拍几张

    # 正面判定阈值(姿态摆正): Yaw ±10°, Pitch ±5°, Roll ±10°
    FRONTAL_YAW_TOL = 10.0
    FRONTAL_PITCH_TOL = 5.0

    # 连拍间隔(秒):避免两张帧过于相似(每秒 5 张左右)
    SHOT_INTERVAL = 0.2

    # 每个阶段的超时时间(秒): 拉长到 15 秒,给用户充足时间完成动作
    STAGE_TIMEOUT = 15.0

    # 每个阶段定义: (阶段名, 每阶段目标张数, 目标描述字符串)
    # 顺序: 先拍正面,再依次 5 个动作
    stages = [
        ("正面", SHOT_COUNT_FRONTAL, "请正对摄像头,保持不动"),
        ("左转", SHOT_COUNT_PER_ACTION, "请向左转头 (Yaw < -20°)"),
        ("右转", SHOT_COUNT_PER_ACTION, "请向右转头 (Yaw > 20°)"),
        ("抬头", SHOT_COUNT_PER_ACTION, "请抬起下巴 (Pitch > 15°)"),
        ("眨眼", SHOT_COUNT_PER_ACTION, "请眨眼 (EAR 下降 > 20%)"),
        ("张嘴", SHOT_COUNT_PER_ACTION, "请张开嘴 (MAR > 0.4)"),
    ]
    # 校验总张数 = TARGET_CAPTURE_COUNT
    assert sum(s[1] for s in stages) == TARGET_CAPTURE_COUNT, "阶段张数与 TARGET_CAPTURE_COUNT 不匹配"

    # 保存目录
    save_dir = CAPTURE_SAVE_DIR
    os.makedirs(save_dir, exist_ok=True)

    # 先清空旧采集图(避免旧图混进去影响下游 faceCheck)
    for old_file in os.listdir(save_dir):
        if os.path.splitext(old_file)[1].lower() in IMAGE_EXTENSIONS:
            try:
                os.remove(os.path.join(save_dir, old_file))
            except OSError:
                pass

    # 初始化活体检测器(加载轻量模型 det + landmark_2d_106,约 1-2 秒)
    # 引导式采集只用姿态/表情判定,不需要静默活体检测器(useSilent=False 省一次模型加载)
    print("正在初始化检测器(加载模型)...")
    detector = LivenessDetector(useSilent=False)

    # 打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("摄像头无法打开")
        return None

    # 降低采集分辨率(与活体流程一致,减少 USB 带宽/解码开销;部分摄像头不生效由 shrinkFrame 兜底)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\n" + "=" * 60)
    print("  开始引导式采集:正面 10 张 + 5 动作各 4 张 = 30 张")
    print("  每阶段满足条件自动连拍,按 ESC 可中途退出")
    print("=" * 60)

    # 眨眼前需要先采集 baseline EAR(与 livenessDetector 逻辑一致)
    # 这里在"眨眼"阶段开始前采集一次 baseline
    baselineEAR = None

    global_photo_count = 0  # 已保存总张数
    stages_result = {}      # 记录各阶段保存的张数(用于最终确认)

    for stageName, stageTarget, stagePrompt in stages:
        # ── 眨眼阶段前置:采集 baseline EAR ──
        if stageName == "眨眼" and baselineEAR is None:
            # 采集眨眼基准 EAR:最多尝试 3 次,失败逐次延长采集时长
            # 避免直接用固定 0.3(因人而异会导致眨眼判定失效)
            baselineEAR = 0.0
            for attempt in range(3):
                print(f"\n[前置] 请保持正脸,不要眨眼(采集基准 EAR, 第 {attempt + 1} 次)...")
                ears = []
                curDuration = BASELINE_DURATION + attempt  # 第 2/3 次延长采集时间

                def infer(frame):
                    """子线程推理: 检测人脸(复用活体检测器轻量模型)"""
                    return detector.appDetect.get(frame)

                def onResult(faces, frame, state):
                    """主线程处理: 收集 EAR 样本(数值计算快,不阻塞消息泵)"""
                    if len(faces) > 0 and faces[0].landmark_2d_106 is not None:
                        lm = faces[0].landmark_2d_106
                        le = detector.computeEAR(lm, LEFT_EYE_INDICES)
                        re = detector.computeEAR(lm, RIGHT_EYE_INDICES)
                        ears.append((le + re) / 2.0)
                    return False  # 一直采集到超时

                def overlay(display, state):
                    """画面提示: 采集基准中"""
                    cv2.putText(display, "Collecting baseline EAR...", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # 复用 _runDetectLoop 双线程架构(推理在子线程,主线程只显示/收集,不再卡顿)
                baselineState = detector._runDetectLoop(
                    cap, infer, onResult, curDuration, overlayFunc=overlay, windowName="Capture"
                )
                if baselineState.get("interrupted"):
                    print("\n用户 ESC 退出")
                    cap.release()
                    cv2.destroyAllWindows()
                    return None
                if ears:
                    baselineEAR = float(np.mean(ears))
                    break

            # 重试耗尽仍失败,使用保守 fallback
            if baselineEAR == 0.0:
                baselineEAR = 0.25
                print(f"  [警告] 多次采集基准 EAR 失败,使用保守 fallback: {baselineEAR}")
            detector.baselineEAR = baselineEAR
            print(f"  baseline EAR = {baselineEAR:.4f}")

        print(f"\n[{stageName}] {stagePrompt}  (目标 {stageTarget} 张, 阶段超时 {STAGE_TIMEOUT}s)")

        stageShotCount = 0            # 该阶段已拍张数
        lastShotTime = 0.0            # 上次拍时间(用于连拍间隔)
        userEscaped = False

        def infer(frame):
            """子线程推理: 检测人脸(复用活体检测器轻量模型)"""
            return detector.appDetect.get(frame)

        def onResult(faces, frame, state):
            """主线程处理: 条件判定 + 连拍保存(数值计算快,不阻塞消息泵)"""
            nonlocal stageShotCount, lastShotTime, global_photo_count
            if len(faces) == 0:
                return False
            face = faces[0]
            landmarks = face.landmark_2d_106
            if landmarks is None:
                return False

            # ── 条件判定:是否满足该阶段的拍照条件 ──
            conditionPass = False
            curValue = 0.0

            if stageName == "正面":
                # 条件:Yaw 与 Pitch 接近 0°(姿态摆正)
                pitch, yaw, roll = detector._getPose(face)
                curValue = yaw
                conditionPass = (abs(yaw) <= FRONTAL_YAW_TOL) and (abs(pitch) <= FRONTAL_PITCH_TOL)

            elif stageName == "左转":
                # 实测: 用户左转时 face.pose 的 yaw 为正值
                pitch, yaw, roll = detector._getPose(face)
                curValue = yaw
                conditionPass = yaw > THRESHOLD_YAW_RIGHT

            elif stageName == "右转":
                pitch, yaw, roll = detector._getPose(face)
                curValue = yaw
                conditionPass = yaw < THRESHOLD_YAW_LEFT

            elif stageName == "抬头":
                pitch, yaw, roll = detector._getPose(face)
                curValue = pitch
                conditionPass = pitch > THRESHOLD_PITCH_UP

            elif stageName == "眨眼":
                leftEAR = detector.computeEAR(landmarks, LEFT_EYE_INDICES)
                rightEAR = detector.computeEAR(landmarks, RIGHT_EYE_INDICES)
                ear = (leftEAR + rightEAR) / 2.0
                if baselineEAR and baselineEAR > 1e-6:
                    dropRatio = (baselineEAR - ear) / baselineEAR
                    curValue = dropRatio
                    conditionPass = dropRatio > THRESHOLD_EAR_DROP
                else:
                    conditionPass = False

            elif stageName == "张嘴":
                mar = detector.computeMAR(landmarks)
                curValue = mar
                conditionPass = mar > THRESHOLD_MAR_OPEN

            # ── 条件通过 + 距离上次拍照超过间隔 → 保存照片 ──
            if conditionPass and (time.time() - lastShotTime >= SHOT_INTERVAL):
                filename = os.path.join(save_dir, f"photo_{global_photo_count:03d}.jpg")
                # imencode + tofile 替代 cv2.imwrite(支持中文路径)
                is_success, buffer = cv2.imencode('.jpg', frame)
                if is_success:
                    buffer.tofile(filename)
                    stageShotCount += 1
                    global_photo_count += 1
                    lastShotTime = time.time()
                    print(f"  [{stageName}] 已拍 {stageShotCount}/{stageTarget} "
                          f"(共 {global_photo_count}/{TARGET_CAPTURE_COUNT})  val={curValue:.3f}  → {os.path.basename(filename)}")
            return stageShotCount >= stageTarget  # 拍够本阶段张数即结束

        def overlay(display, state):
            """画面提示: 阶段名 + 进度 + 剩余时间 + 进度条"""
            elapsed = time.time() - state["_start"]
            remainTime = max(0.0, STAGE_TIMEOUT - elapsed)
            progress = stageShotCount / stageTarget
            cv2.putText(display,
                        f"{stageName}: {stagePrompt}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display,
                        f"Progress: {stageShotCount}/{stageTarget}  Time: {remainTime:.1f}s",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            # 进度条
            barW = 400
            barX0, barY0 = 10, 80
            cv2.rectangle(display, (barX0, barY0), (barX0 + barW, barY0 + 10), (200, 200, 200), -1)
            cv2.rectangle(display, (barX0, barY0), (barX0 + int(barW * progress), barY0 + 10), (0, 255, 0), -1)

        # 复用 _runDetectLoop 双线程架构(推理在子线程,主线程只显示/判定/保存,不再卡顿)
        stageState = detector._runDetectLoop(
            cap, infer, onResult, STAGE_TIMEOUT, overlayFunc=overlay, windowName="Capture"
        )
        if stageState.get("interrupted"):
            userEscaped = True

        # 阶段超时保护:超时就强行进入下一阶段
        if stageShotCount < stageTarget:
            print(f"  [超时] {stageName} 只拍了 {stageShotCount}/{stageTarget} 张,进入下一阶段")

        if userEscaped:
            print("\n用户 ESC 退出")
            cap.release()
            cv2.destroyAllWindows()
            return None

        stages_result[stageName] = stageShotCount

    # ── 所有阶段结束 ──
    cap.release()
    cv2.destroyAllWindows()

    # 打印最终采集统计
    print("\n" + "=" * 60)
    print(f"  采集完成! 共保存 {global_photo_count}/{TARGET_CAPTURE_COUNT} 张")
    print("  各阶段统计:")
    for sName, sTarget, _ in stages:
        shot = stages_result.get(sName, 0)
        mark = "✓" if shot >= sTarget else "△"
        print(f"    {mark} {sName:>5s}: {shot}/{sTarget}")
    print(f"  保存目录: {save_dir}")
    print("=" * 60)

    # 即使缺一些张(超时没拍够)也返回目录,下游 faceCheck 会自动过滤无脸图
    return CAPTURE_SAVE_DIR


def faceCheck(folderPath, maxWorkers=DEFAULT_MAX_WORKERS):
    """
    预检图片是否包含人脸(支持单文件路径或文件夹路径)
    传入文件夹时:批量检测文件夹内所有图片
    传入单文件时:仅检测该文件(忽略扩展名,交由读取环节判断)
    使用多进程 + 只检测模型 + det_size=480 优化,150 张图约 27 秒完成
    每张图检测完立即记录结果到字典,key 为图片绝对路径,value 为检测结果,
    全部检测完后统一返回结果字典

    :param folderPath: 待检查的图片路径或文件夹路径<str>
    :param maxWorkers: 进程池工作进程数<int>,默认 4
    :return: 检查结果字典<dict>,格式:
             {
                 "图片绝对路径": {"hasFace": True/False, "status": "success"/"fail"/"error", "msg": "描述信息"},
                 "D:\\...\\photo_000.jpg": {"hasFace": True, "status": "success", "msg": "有脸 (检测到 1 张脸)"},
                 ...
             }
             路径不存在或文件夹无图片时返回空字典 {}
    """
    # 获取模型根目录(传给子进程用于初始化 FaceAnalysis)
    modelRoot = getModelRoot()

    # 前置检查:路径不存在时友好返回空字典(避免 os.listdir 抛 FileNotFoundError)
    if not os.path.exists(folderPath):
        print(f"路径 {folderPath} 不存在")
        return {}

    # 收集待检测图片列表(自动识别单文件 / 文件夹两种模式)
    image_files = []
    if os.path.isfile(folderPath):
        # 单文件模式:直接加入待检测列表(扩展名不匹配时由读取环节返回 error)
        if os.path.splitext(folderPath)[1].lower() in IMAGE_EXTENSIONS:
            image_files.append(os.path.abspath(folderPath))
        else:
            print(f"文件 {folderPath} 不是支持的图片格式")
            return {}
    else:
        # 文件夹模式:遍历目录收集所有图片
        for file in os.listdir(folderPath):
            if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                image_files.append(os.path.join(folderPath, file))

    if not image_files:
        print(f"文件夹 {folderPath} 中没有图片")
        return {}

    print(f"开始检查 {len(image_files)} 张图片(进程数={maxWorkers}, det_size={DET_SIZE})...")

    # 多进程执行(绕过 GIL,真正并行)
    # initializer=initWorkerProcess 让每个子进程启动时加载一次模型,后续任务共享
    # key: 图片绝对路径, value: 检测结果字典
    resultsDict = {}
    with ProcessPoolExecutor(
        max_workers=maxWorkers,
        initializer=initWorkerProcess,
        initargs=(modelRoot,)
    ) as executor:
        future_to_path = {
            executor.submit(checkSingleImage, path): path
            for path in image_files
        }

        # 每张图检测完立即以 path 为 key 记录到结果字典(不再 fail-fast 提前终止)
        for future in as_completed(future_to_path):
            result = future.result()
            imgPath = result['path']
            # 组装每个图片的检测结果字典(去掉冗余 path 字段,path 已作为字典 key)
            resultsDict[imgPath] = {
                'hasFace': (result['status'] == 'success'),
                'status': result['status'],
                'msg': result['msg']
            }
            print(f"{os.path.basename(imgPath)}: {result['msg']}")

    # 统计结果
    success_count = sum(1 for v in resultsDict.values() if v['hasFace'])
    fail_count = len(resultsDict) - success_count
    print(f"检查完成: 共 {len(resultsDict)} 张,有脸 {success_count} 张,无脸/错误 {fail_count} 张")

    return resultsDict

def handleNoFace(checkResultsDict):
    """
    处理无人脸的图片:
      1. 不直接修改传入的共用字典(数据安全),先复制一份到临时 dict 操作
      2. 遍历复制的 dict,找到 hasFace=False 的条目
      3. 从磁盘删除对应的图片文件,同时从复制的 dict 中移除该条目
      4. 所有操作成功完成后,返回处理后的新字典(仅包含可用人脸图像)
    (Copy-on-Write 策略:保证任何一步失败都不破坏原始共用字典,外部可安全比较处理前后结果)

    :param checkResultsDict: faceCheck 返回的检测结果字典<dict>,
           格式: {"图片绝对路径": {"hasFace": True/False, "status": "...", "msg": "..."}}
    :return: 处理后的可用人脸数据集字典<dict>(仅保留 hasFace=True 的条目),
             格式与入参相同;如果入参为 None/空字典,直接返回入参
    """
    # 防御性检查
    if not checkResultsDict:
        print("[handleNoFace] 输入字典为空,无需处理")
        return checkResultsDict if isinstance(checkResultsDict, dict) else {}

    # ── Copy-on-Write:先浅复制外层字典,不在原字典上操作 ──
    # 浅复制足够:value 内部字段(hasFace/status/msg)不会被修改,仅增删 key
    workingDict = dict(checkResultsDict)
    totalBefore = len(workingDict)

    # 1. 先收集所有无脸图片的路径(不在遍历时删 key,避免 RuntimeError)
    noFacePaths = [
        imgPath for imgPath, info in workingDict.items()
        if not info.get('hasFace', False)
    ]

    if not noFacePaths:
        print(f"[handleNoFace] 共 {totalBefore} 张,无无脸图片,无需删除")
        return workingDict

    print(f"[handleNoFace] 共 {totalBefore} 张,发现 {len(noFacePaths)} 张无脸图片,开始处理...")

    # 2. 删除磁盘文件 + 从工作字典移除 key
    deletedCount = 0
    failedDeletes = []  # 记录删除失败的条目(不抛出,保证流程继续)
    for imgPath in noFacePaths:
        try:
            # 仅在文件存在时删除(避免重复调用时报错)
            if os.path.exists(imgPath):
                os.remove(imgPath)
            # 从工作字典移除该 key(成功/失败都移除,因为确实是无脸图)
            workingDict.pop(imgPath, None)
            deletedCount += 1
            print(f"  [删除] {os.path.basename(imgPath)}")
        except OSError as e:
            # 磁盘删除失败(权限/文件被占用等),仍从字典移除(因为图片无脸,不可用)
            workingDict.pop(imgPath, None)
            failedDeletes.append((imgPath, str(e)))
            print(f"  [警告] {os.path.basename(imgPath)} 磁盘删除失败: {e}, 已从字典移除")

    # 3. 统计结果
    totalAfter = len(workingDict)
    print(
        f"[handleNoFace] 处理完成: 删除 {deletedCount} 张, "
        f"剩余可用 {totalAfter} 张"
    )
    if failedDeletes:
        print(f"  注意: {len(failedDeletes)} 张磁盘删除失败(文件可能不存在或被占用)")

    # 4. 返回新字典(仅含可用人脸图像),调用方据此决定是否覆盖共用字典
    return workingDict

def coverDict(originalDict, newDict):
    """
    安全覆盖共用字典(配合 handleNoFace 使用)
    流程:
      1. 校验 newDict 合法性(必须是 dict,且所有条目的 hasFace 必须为 True)
      2. 校验 newDict 是 originalDict 的子集(即 newDict 是从 originalDict 派生而来,
         不允许引入原字典中不存在的 key,防止数据被污染)
      3. 校验通过后返回 newDict,由调用方执行 sharedDict = coverDict(...) 完成覆盖
      4. 校验失败时返回 originalDict(保持原状,不破坏数据)

    设计意图:把"覆盖共用字典"的决策点集中到一个函数,所有校验逻辑在这里完成,
    调用方只需一行 sharedDict = coverDict(sharedDict, cleanedDict) 即可,
    避免散落的 if 判断造成遗漏。

    :param originalDict: 原始共用字典<dict>(faceCheck 返回的)
    :param newDict: 待覆盖的新字典<dict>(handleNoFace 返回的清理后字典)
    :return: 校验通过返回 newDict,校验失败返回 originalDict<dict>
    """
    # ── 校验 1:类型检查 ──
    if not isinstance(originalDict, dict) or not isinstance(newDict, dict):
        print("[coverDict] 校验失败: 入参必须为 dict 类型,保持原字典不变")
        return originalDict

    # ── 校验 2:空字典保护 ──
    # newDict 为空通常意味着清理逻辑出错(全部图片被删了),不应覆盖
    if not newDict:
        print("[coverDict] 校验失败: 新字典为空(可能清理逻辑有误),保持原字典不变")
        return originalDict

    # ── 校验 3:newDict 必须是 originalDict 的子集 ──
    # 防止 newDict 引入了 originalDict 中不存在的 key(数据污染)
    extra_keys = set(newDict.keys()) - set(originalDict.keys())
    if extra_keys:
        print(f"[coverDict] 校验失败: 新字典包含 {len(extra_keys)} 个原字典中不存在的 key,保持原字典不变")
        return originalDict

    # ── 校验 4:newDict 中所有条目的 hasFace 必须为 True ──
    # (此函数用于覆盖"可用人脸数据集",所以新字典中不应再有 hasFace=False 的条目)
    invalid_entries = [
        path for path, info in newDict.items()
        if not info.get('hasFace', False)
    ]
    if invalid_entries:
        print(f"[coverDict] 校验失败: 新字典中仍有 {len(invalid_entries)} 条 hasFace=False 的记录,保持原字典不变")
        return originalDict

    # ── 所有校验通过,执行覆盖 ──
    removedCount = len(originalDict) - len(newDict)
    print(f"[coverDict] 校验通过,共用字典已更新: {len(originalDict)} → {len(newDict)} (移除 {removedCount} 条)")

    # 返回新字典,调用方执行 sharedDict = coverDict(sharedDict, cleanedDict) 完成赋值
    # 这里不直接修改 originalDict(它作为入参,本身是引用,外部已持有)
    # 真正的"覆盖"在调用方赋值时发生:sharedDict = ... 这一步让外部变量名指向新字典
    return newDict


# ====================================================================
# 活体检测录入(主动活体检测 + 特征提取 + 保存)
# ====================================================================
def collectFrontalPhotos(cap, detector, count=TARGET_CAPTURE_COUNT, timeout=20.0,
                         frameCallback=None):
    """
    采集正脸照片(活体检测通过后调用,复用已打开的摄像头,不重新打开)
    只拍正脸(姿态摆正),不做动作引导
    :param cap: 已打开的摄像头对象<cv2.VideoCapture>
    :param detector: LivenessDetector 实例(用于姿态判定正脸)
    :param count: 目标张数<int>,默认 30
    :param timeout: 超时时间<秒>,默认 20
    :param frameCallback: 帧回调(供 UI 内嵌显示), 签名 frameCallback(frame, prompt),
                          默认 None;传入后不再弹 OpenCV 窗口
    :return: 保存目录<str>,采集不足时也返回目录(下游 faceCheck 会过滤)
    """
    import time  # time.time 用于拍照间隔和超时

    save_dir = CAPTURE_SAVE_DIR
    os.makedirs(save_dir, exist_ok=True)

    # 清空旧采集图(避免旧图混入下游 faceCheck)
    for old_file in os.listdir(save_dir):
        if os.path.splitext(old_file)[1].lower() in IMAGE_EXTENSIONS:
            try:
                os.remove(os.path.join(save_dir, old_file))
            except OSError:
                pass

    print(f"\n开始采集正脸照片(目标 {count} 张,请正对摄像头保持不动)...")
    shot_count = 0
    last_shot = 0.0

    def infer(frame):
        """子线程推理: 检测人脸(复用活体检测器轻量模型)"""
        return detector.appDetect.get(frame)

    def onResult(faces, frame, state):
        """主线程处理: 正脸判定 + 连拍保存(数值计算快,不阻塞消息泵)"""
        nonlocal shot_count, last_shot
        if len(faces) == 0:
            return False
        face = faces[0]
        if face.landmark_2d_106 is None:
            return False

        pitch, yaw, roll = detector._getPose(face)
        # 正脸判定: yaw/pitch 接近 0(姿态摆正)
        if abs(yaw) <= 10.0 and abs(pitch) <= 8.0:
            if time.time() - last_shot >= 0.2:
                filename = os.path.join(save_dir, f"photo_{shot_count:03d}.jpg")
                is_success, buffer = cv2.imencode('.jpg', frame)
                if is_success:
                    buffer.tofile(filename)
                    shot_count += 1
                    last_shot = time.time()
                    print(f"  已拍 {shot_count}/{count}")
        return shot_count >= count  # 拍够目标张数即结束

    def overlay(display, state):
        """画面提示: 进度 + 剩余时间"""
        cv2.putText(display, f"Frontal: {shot_count}/{count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display, f"Time: {max(0, timeout - (time.time() - state['_start'])):.1f}s", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # 复用 _runDetectLoop 双线程架构(推理在子线程,主线程只显示/判定/保存,不再卡顿)
    collectState = detector._runDetectLoop(
        cap, infer, onResult, timeout, overlayFunc=overlay, windowName="Liveness",
        frameCallback=frameCallback, prompt="请正对摄像头,保持不动",
        showWindow=(frameCallback is None)
    )
    if collectState.get("interrupted"):
        print("用户 ESC 中断采集")

    print(f"正脸采集完成: {shot_count}/{count} 张,目录: {save_dir}")
    return save_dir


def openCameraWithLiveness(userName, progressCallback=None, frameCallback=None):
    """
    摄像头活体检测 + 正脸图像收集录入(实装方法)
    ==========================================
    流程:
    1. 打开摄像头(整个流程只打开一次,中途不关闭)
    2. 活体检测(静默检测 + 主动动作检测,验证是真人而非照片/翻拍)
    3. 活体通过后,复用当前摄像头采集 30 张正脸照片
    4. 采集完成后关闭摄像头,返回图片目录

    :param userName: 用户名<str>(保留用于下游特征文件命名)
    :param progressCallback: 阶段进度回调<Callable>,签名 progressCallback(stage, detail),
                             默认 None(不回调);stage 取值:
                             "silent"/"action"/"frontal"(活体检测阶段, 透传自 runLivenessCheck)
                             "capture"(正脸照片采集中)
    :param frameCallback: 帧回调(供 UI 内嵌显示), 签名 frameCallback(frame, prompt),
                          默认 None;传入后活体检测与照片采集阶段不再弹 OpenCV 窗口
    :return: 结果字典<dict>:
             成功: {"success": True, "imgDir": str, "userName": str, "msg": "..."}
             失败: {"success": False, "step": str, "msg": "..."}
    """
    import sys
    # 动态导入活体检测模块(FaceMoudle/liveness/livenessDetector.py)
    projectRoot = getProjectRoot()
    faceMoudleDir = os.path.join(projectRoot, 'FaceMoudle')
    if faceMoudleDir not in sys.path:
        sys.path.insert(0, faceMoudleDir)
    from liveness.livenessDetector import LivenessDetector

    # Step 1: 初始化活体检测器(轻量模型 + 静默检测)
    print("正在初始化活体检测器(静默 + 主动动作)...")
    detector = LivenessDetector()

    # Step 2: 打开摄像头(整个流程只打开一次)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("摄像头无法打开")
        return {"success": False, "msg": "摄像头无法打开"}

    print("摄像头已打开,开始活体检测...")

    # Step 3: 执行活体检测(静默 + 主动动作),进度/帧透传
    result = detector.runLivenessCheck(
        cap, collectFrontal=False, progressCallback=progressCallback,
        frameCallback=frameCallback
    )

    # 活体检测失败,关闭摄像头后返回
    if not result["success"]:
        cap.release()
        cv2.destroyAllWindows()
        print(f"\n活体检测失败: {result['msg']} (步骤: {result.get('step', '')})")
        return result

    # Step 4: 活体通过 → 复用当前摄像头采集 30 张正脸(不关闭摄像头)
    print("\n活体检测通过!开始采集正脸照片...")
    if progressCallback is not None:
        progressCallback("capture", "正脸照片采集中")
    imgDir = collectFrontalPhotos(cap, detector, count=TARGET_CAPTURE_COUNT,
                                  frameCallback=frameCallback)

    # Step 5: 采集完成后关闭摄像头
    cap.release()
    cv2.destroyAllWindows()

    return {
        "success": True,
        "imgDir": imgDir,
        "userName": userName,
        "msg": "活体检测通过,正脸图像采集完成"
    }


# ====================================================================
# 入口
# ====================================================================
if __name__ == '__main__':
    # ================= 完整示例:人脸数据集维护流程 =================
    # Step 1: 获取数据集目录
    # 直接复用 CAPTURE_SAVE_DIR 常量(已是基于 __file__ 的绝对路径)
    test_dir = CAPTURE_SAVE_DIR

    # Step 2: 批量检测所有人脸(faceCheck 返回路径→结果字典)
    sharedDict = faceCheck(test_dir, maxWorkers=4)
    print(f"\n[Step2 完成] 检测字典: 共 {len(sharedDict)} 张")

    # Step 3: 调用 handleNoFace 清理无脸图片
    # ── 重要:handleNoFace 内部做了 copy-on-write,不修改 sharedDict,返回全新的 cleanedDict ──
    cleanedDict = handleNoFace(sharedDict)

    # Step 4: 用 coverDict 安全覆盖共用字典(校验通过才覆盖,失败保持原状)
    # coverDict 内部会校验:类型/非空/子集关系/所有 hasFace=True
    # 校验通过返回 cleanedDict,失败返回 sharedDict(保持原状)
    # 调用方一行赋值即可完成覆盖,无需散落的 if 判断
    sharedDict = coverDict(sharedDict, cleanedDict)

    # Step 5: 最终的可用人脸数据集
    print(f"\n[最终] 可用人脸数据集大小: {len(sharedDict)}")
    if sharedDict:
        sample_path = next(iter(sharedDict.keys()))
        print(f"  示例条目: {os.path.basename(sample_path)} -> hasFace={sharedDict[sample_path]['hasFace']}")
