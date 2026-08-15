# -*- coding: utf-8 -*-
"""
主动动作活体检测模块(livenessDetector)
=======================================
第二层防御: 静默检测通过后,随机做 1~5 个动作(左转/右转/抬头/眨眼/张嘴),
通过连续多帧动作判定确认是真人(照片/视频无法完成动作)。

关键改进(相对旧版 faceInputer/livenessDetector.py):
1. 姿态基准校准: 动作检测前先采集正面基准 Yaw/Pitch,动作用"相对基准偏移量"判定
2. 双线程架构: 主线程只读帧+显示,子线程推理,画面不再被推理阻塞
3. 显示节流 + 降分辨率: 缓解摄像头窗口/鼠标卡顿
4. 集成静默活体检测(silentLiveness)作为第一道关卡

技术依据:
- 头部姿态: 直接使用 InsightFace 自带的 face.pose(基于 landmark_3d_68,准确可靠)
- 眨眼: 眼睛区域灰度标准差法(睁眼有瞳孔+眼白差异大,闭眼均匀差异小)
- MAR(张嘴): 嘴部纵横比,张嘴时增大(嘴巴外轮廓 52~71)
"""

import os
import sys
import time
import random
import cv2
import numpy as np
from insightface.app import FaceAnalysis

# 限制 ONNX 推理线程数(必须在创建任何 session 前生效)
# 本文件位于 FaceMoudle/liveness/,上 2 级即 FaceMoudle 目录
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FACE_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _FACE_MOUDLE_DIR)
import modelConfig  # 导入即自动限制 InsightFace 推理线程数

# 同包静默活体检测模块(第一层防御),相对导入避免依赖 sys.path
from .silentLiveness import SilentLivenessDetector


# ====================================================================
# 关键点索引常量(基于 InsightFace 106 关键点官方定义)
# ====================================================================
# 左眼 EAR 关键点: 左眼角,上眼睑x2,右眼角,下眼睑x2
LEFT_EYE_INDICES = [35, 36, 37, 39, 41, 42]

# 右眼 EAR 关键点
RIGHT_EYE_INDICES = [89, 90, 91, 93, 95, 96]

# 嘴部外轮廓 20 点(52~71)
MOUTH_INDICES = list(range(52, 72))


# ====================================================================
# 动作判定阈值(相对基准的偏移量,可调)
# ====================================================================
# 姿态动作: 相对正面基准的偏移量
THRESHOLD_YAW_LEFT = -15.0    # 左转: (yaw - baselineYaw) < -15°
THRESHOLD_YAW_RIGHT = 15.0    # 右转: (yaw - baselineYaw) > 15°
THRESHOLD_PITCH_UP = 10.0     # 抬头: (pitch - baselinePitch) > 10°

# 表情动作
THRESHOLD_EAR_DROP = 0.2      # 眨眼: EAR 相对 baseline 下降 > 20%
THRESHOLD_MAR_OPEN = 0.4      # 张嘴: MAR > 0.4

# 动作序列(严格按此顺序执行)
ACTION_SEQUENCE = ["左转", "右转", "抬头", "眨眼", "张嘴"]

# 每个动作的超时时间(秒): 拉长到 15 秒,避免用户来不及做动作就被判失败
ACTION_TIMEOUT = 15.0

# 基准校准采集时长(秒): 采集正面基准 Yaw/Pitch/EAR
BASELINE_DURATION = 1.5

# 静默活体检测: 需要连续通过的帧数
SILENT_PASS_FRAMES = 5

# 自适应动作检测: 累计失败次数达到此值判定整体失败
MAX_FAIL_COUNT = 2

# 自适应动作检测: 继续下一个动作的概率(键=连续成功次数)
CONTINUE_PROB_NO_FAIL = {1: 0.45, 2: 0.15}   # 无失败记录时
CONTINUE_PROB_HAS_FAIL = {1: 0.30, 2: 0.10}  # 有失败记录时

# 正脸采集: 动作通过后采集正脸时的相对偏移容差(度)
FRONTAL_YAW_TOL = 10.0
FRONTAL_PITCH_TOL = 8.0

# 跳帧间隔: 每 N 帧送一帧给子线程推理(降低 CPU 负担)
SKIP_FRAME_INTERVAL = 3

# 显示节流: 每 N 帧才更新一次 imshow(降低 GUI 压力,缓解鼠标卡顿)
DISPLAY_INTERVAL = 2

# waitKey 延时(毫秒): 每帧给 Windows 消息泵的处理时间。
# 1ms 太短,前台焦点窗口的 WM_MOUSEMOVE/WM_PAINT 消息处理不完会堆积 → 鼠标卡顿;
# 10ms 足够泵完消息,且显示节流下不影响画面流畅度
WAITKEY_DELAY_MS = 10

# 显示/推理帧最大宽度(像素): 摄像头常返回 1080p/720p 高分辨率,
# 前台窗口需实际重绘 + 每帧 copy + 推理预处理开销大,统一缩小到 640 宽
# (人脸检测 det_size=160/识别 det_size=480,640 宽足够,不影响精度)
DISPLAY_MAX_WIDTH = 640


# ====================================================================
# 路径工具函数
# ====================================================================
def getProjectRoot():
    """
    获取项目根目录
    :return: 项目根目录的绝对路径<str>
    """
    # 本文件在 FaceMoudle/liveness/ 下,项目根是上 3 级
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def getModelRoot():
    """
    获取 InsightFace 模型根目录
    :return: 模型根目录的绝对路径<str>
    """
    return os.path.join(getProjectRoot(), 'FaceMoudle', 'moudleTrainner')


def shrinkFrame(frame, maxWidth=DISPLAY_MAX_WIDTH):
    """
    按宽度等比例缩小摄像头帧(降低前台窗口重绘、帧拷贝与推理预处理开销)
    摄像头常返回 1080p/720p,而人脸检测 det_size 仅 160,显示也不需要那么大,
    统一缩到 DISPLAY_MAX_WIDTH 宽,画面更流畅且不影响检测/识别精度
    :param frame: BGR 图像矩阵<np.ndarray>
    :param maxWidth: 目标最大宽度<int>,默认 DISPLAY_MAX_WIDTH
    :return: 缩小后的 BGR 图像矩阵<np.ndarray>
    """
    h, w = frame.shape[:2]
    if w <= maxWidth:
        return frame
    scale = maxWidth / float(w)
    newH = int(h * scale)
    return cv2.resize(frame, (maxWidth, newH), interpolation=cv2.INTER_AREA)


# ====================================================================
# 活体检测器类
# ====================================================================
class LivenessDetector:
    """
    活体检测器(多层防御)
    =====================
    第一层: 静默活体检测(silentLiveness)拦截照片/屏幕翻拍
    第二层: 自适应动作检测(静默通过后随机 1~5 个动作)防止注入攻击与高级假体

    性能策略:
    - 动作检测阶段用轻量模型(detection + landmark_2d_106, det_size=160)
    - 特征提取阶段懒加载完整模型(recognition),仅动作通过后使用
    - 双线程架构: 主线程显示,子线程推理
    """

    def __init__(self, useSilent=True):
        """
        初始化活体检测器
        :param useSilent: 是否启用静默活体检测第一道关卡<bool>,默认 True
        """
        modelRoot = getModelRoot()

        # 轻量模型: 加载检测 + 106关键点 + 3D68关键点(用于获得 face.pose 头部姿态)
        # det_size=160 进一步提速,动作判定只需幅度不需高精度
        self.appDetect = FaceAnalysis(
            name='buffalo_l',
            root=modelRoot,
            allowed_modules=['detection', 'landmark_2d_106', 'landmark_3d_68'],
            providers=['CPUExecutionProvider']
        )
        self.appDetect.prepare(ctx_id=-1, det_size=(160, 160))

        # 完整模型: 加载检测 + 识别(懒加载,提取特征时才创建)
        self.appFull = None

        # 静默活体检测器(第一道关卡)
        self.useSilent = useSilent
        self.silentDetector = SilentLivenessDetector() if useSilent else None

        # 正面姿态基准(校准后填充,用于动作的相对偏移判定)
        self.baselineYaw = 0.0
        self.baselinePitch = 0.0
        self.baselineEAR = None

    def getFullApp(self):
        """
        懒加载完整 FaceAnalysis(加载 detection + recognition)
        首次调用时初始化(约 3-5 秒),后续复用
        :return: 配置好的 FaceAnalysis 实例<FaceAnalysis>
        """
        if self.appFull is None:
            print("[LivenessDetector] 首次加载识别模型,请稍候...")
            modelRoot = getModelRoot()
            self.appFull = FaceAnalysis(
                name='buffalo_l',
                root=modelRoot,
                allowed_modules=['detection', 'recognition'],
                providers=['CPUExecutionProvider']
            )
            self.appFull.prepare(ctx_id=-1, det_size=(480, 480))
        return self.appFull

    def computeEAR(self, landmarks, eyeIndices):
        """
        计算眼睛纵横比(Eye Aspect Ratio)
        眨眼时上下眼睑距离减小,EAR 下降
        :param landmarks: 106 关键点<np.ndarray (106, 2)>
        :param eyeIndices: 眼睛 6 个关键点索引<list<int>>
        :return: EAR 值<float>
        """
        p1 = landmarks[eyeIndices[0]]
        p2 = landmarks[eyeIndices[1]]
        p3 = landmarks[eyeIndices[2]]
        p4 = landmarks[eyeIndices[3]]
        p5 = landmarks[eyeIndices[4]]
        p6 = landmarks[eyeIndices[5]]
        vertical = (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / 2.0
        horizontal = np.linalg.norm(p1 - p4)
        if horizontal < 1e-6:
            return 0.0
        return vertical / horizontal

    def computeMAR(self, landmarks):
        """
        计算嘴部纵横比(Mouth Aspect Ratio)
        嘴巴外轮廓 20 点(52~71): 上唇 52~61,下唇 62~71
        MAR = 上下唇垂直距离 / 左右嘴角距离
        :param landmarks: 106 关键点<np.ndarray (106, 2)>
        :return: MAR 值<float>
        """
        mouth = landmarks[MOUTH_INDICES]  # (20, 2), 52~71
        # 上唇点 y 均值(52~61),下唇点 y 均值(62~71)
        upper_y = np.mean(mouth[:10, 1])
        lower_y = np.mean(mouth[10:, 1])
        vertical = abs(lower_y - upper_y)
        # 左右嘴角: 52(左) 与 61(右,上唇最右点)
        horizontal = np.linalg.norm(mouth[0] - mouth[9])
        if horizontal < 1e-6:
            return 0.0
        return vertical / horizontal

    def _getPose(self, face):
        """
        获取头部姿态 [pitch, yaw, roll]
        优先用 InsightFace 自带的 face.pose(基于 landmark_3d_68,准确可靠),
        避免自写 solvePnP 因关键点索引错误导致姿态异常
        :param face: Face 对象
        :return: (pitch, yaw, roll) 单位: 度
        """
        pose = getattr(face, 'pose', None)
        if pose is not None and len(pose) >= 3:
            return float(pose[0]), float(pose[1]), float(pose[2])
        return 0.0, 0.0, 0.0

    def _getEyeGrayStd(self, frame, face):
        """
        计算双眼区域的灰度标准差(睁眼大,闭眼小)
        原理: 睁眼时眼睛区域有瞳孔(暗)+眼白(亮),灰度差异大;
              闭眼时眼皮颜色均匀,灰度标准差小。
        用于替代 landmark EAR 做眨眼检测(landmark 在眼睛较小时对闭眼不敏感)。
        :param frame: BGR 图像矩阵<np.ndarray>
        :param face: Face 对象
        :return: 灰度标准差<float>,无法计算返回 None
        """
        kps = getattr(face, 'kps', None)
        if kps is None or len(kps) < 2:
            return None
        # 双眼中心 + 眼间距(用于确定眼睛区域大小)
        eye_center = (kps[0] + kps[1]) / 2.0
        eye_dist = float(np.linalg.norm(kps[0] - kps[1]))
        if eye_dist < 1e-6:
            return None
        # 眼睛区域: 宽约眼间距 0.5 倍,高约眼间距 0.22 倍
        w = max(8, int(eye_dist * 0.5))
        h = max(4, int(eye_dist * 0.22))
        cx, cy = int(eye_center[0]), int(eye_center[1])
        imgH, imgW = frame.shape[:2]
        x1 = max(0, cx - w)
        x2 = min(imgW, cx + w)
        y1 = max(0, cy - h)
        y2 = min(imgH, cy + h)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return float(gray.std())

    def checkActionWithFaces(self, faces, frame, actionName):
        """
        基于已检测到的人脸对象做动作判定(相对基准偏移,不重复推理)
        :param faces: appDetect.get() 返回的人脸对象列表<list>
        :param frame: BGR 图像矩阵<np.ndarray>(仅用 frame.shape 计算相机内参)
        :param actionName: 动作名称<str>
        :return: (是否通过<bool>, 当前数值<float>, 调试明细<str>)
                 调试明细包含绝对姿态/基准/相对偏移/阈值,便于定位检测不到的问题
        """
        if len(faces) == 0:
            return False, 0.0, "无人脸"
        face = faces[0]
        landmarks = face.landmark_2d_106
        if landmarks is None:
            return False, 0.0, "无关键点"

        if actionName == "左转":
            # 实测: 用户左转时 face.pose 的 yaw 为正值(增大),故用 relYaw > 正阈值
            pitch, yaw, roll = self._getPose(face)
            relYaw = yaw - self.baselineYaw
            info = (f"yaw={yaw:.2f} pitch={pitch:.2f} | "
                    f"基准yaw={self.baselineYaw:.2f} 基准pitch={self.baselinePitch:.2f} | "
                    f"relYaw={relYaw:.2f} (需>{THRESHOLD_YAW_RIGHT})")
            return relYaw > THRESHOLD_YAW_RIGHT, relYaw, info

        elif actionName == "右转":
            # 与左转相反: 右转时 yaw 为负值(减小)
            pitch, yaw, roll = self._getPose(face)
            relYaw = yaw - self.baselineYaw
            info = (f"yaw={yaw:.2f} pitch={pitch:.2f} | "
                    f"基准yaw={self.baselineYaw:.2f} 基准pitch={self.baselinePitch:.2f} | "
                    f"relYaw={relYaw:.2f} (需<{THRESHOLD_YAW_LEFT})")
            return relYaw < THRESHOLD_YAW_LEFT, relYaw, info

        elif actionName == "抬头":
            pitch, yaw, roll = self._getPose(face)
            relPitch = pitch - self.baselinePitch
            info = (f"yaw={yaw:.2f} pitch={pitch:.2f} | "
                    f"基准yaw={self.baselineYaw:.2f} 基准pitch={self.baselinePitch:.2f} | "
                    f"relPitch={relPitch:.2f} (需>{THRESHOLD_PITCH_UP})")
            return relPitch > THRESHOLD_PITCH_UP, relPitch, info

        elif actionName == "眨眼":
            # 用眼睛区域灰度标准差检测眨眼(睁眼大,闭眼小),
            # 替代 landmark EAR(landmark 在眼睛较小时对闭眼不敏感)
            eye_std = self._getEyeGrayStd(frame, face)
            if eye_std is None:
                info = "眼睛灰度无法计算"
                return False, 0.0, info
            if self.baselineEAR is None or self.baselineEAR < 1e-6:
                info = f"eyeStd={eye_std:.2f} 基准未采集"
                return False, eye_std, info
            drop_ratio = (self.baselineEAR - eye_std) / self.baselineEAR
            info = (f"eyeStd={eye_std:.2f} 基准eyeStd={self.baselineEAR:.2f} | "
                    f"下降={drop_ratio:.3f} (需>{THRESHOLD_EAR_DROP})")
            return drop_ratio > THRESHOLD_EAR_DROP, drop_ratio, info

        elif actionName == "张嘴":
            mar = self.computeMAR(landmarks)
            info = f"mar={mar:.3f} (需>{THRESHOLD_MAR_OPEN})"
            return mar > THRESHOLD_MAR_OPEN, mar, info

        else:
            return False, 0.0, "未知动作"

    def checkAction(self, frame, actionName):
        """
        单线程动作判定(先检测人脸再复用 checkActionWithFaces)
        :param frame: BGR 图像矩阵<np.ndarray>
        :param actionName: 动作名称<str>
        :return: (是否通过<bool>, 当前数值<float>)
        """
        faces = self.appDetect.get(frame)
        passed, value, info = self.checkActionWithFaces(faces, frame, actionName)
        return passed, value

    def _putText(self, frame, text, org, color=(0, 255, 0)):
        """在画面上叠加文字提示"""
        cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def _runDetectLoop(self, cap, inferFunc, onResult, timeout, overlayFunc=None, windowName="Liveness"):
        """
        通用"子线程推理 + 主线程显示"循环
        =================================
        解决主线程直接做 CPU 密集推理(appDetect.get)阻塞 OpenCV 消息泵(waitKey),
        导致窗口在前台获得焦点时鼠标卡顿、画面一顿一顿的问题(后台无焦点消息压力则不卡)。

        架构:
        - 子线程: 从 frame_queue 取帧,执行 inferFunc(frame) 推理,结果放入 result_queue
        - 主线程: 读帧 -> 节流显示 + waitKey -> 送帧给子线程 -> 取结果 -> onResult 判定

        :param cap: cv2.VideoCapture 摄像头对象
        :param inferFunc: 子线程推理函数,签名 inferFunc(frame) -> result
        :param onResult: 主线程结果判定函数,签名 onResult(result, frame, state) -> bool
                         返回 True 表示流程完成(跳出循环);state 用于记录累计数据
        :param timeout: 超时时间<秒>
        :param overlayFunc: 主线程叠加文字函数,签名 overlayFunc(display, state),默认 None
        :param windowName: OpenCV 窗口名<str>,默认 "Liveness"(录入流程用 "Capture")
        :return: state<dict>,含 "interrupted"(是否 ESC 中断)及 onResult 写入的自定义数据
        """
        import threading
        import queue

        frame_queue = queue.Queue(maxsize=1)   # 待推理帧队列(只保留最新 1 帧)
        result_queue = queue.Queue(maxsize=1)  # 推理结果队列(只保留最新 1 个结果)
        state = {"interrupted": False, "_start": time.time()}

        def worker():
            """子线程: 循环取帧推理,收到 None 哨兵退出"""
            while True:
                try:
                    frame = frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if frame is None:
                    break
                result = inferFunc(frame)
                # 结果队列满时丢弃旧结果,保证主线程拿到的是最新帧的推理结果
                try:
                    result_queue.put_nowait(result)
                except queue.Full:
                    try:
                        result_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        result_queue.put_nowait(result)
                    except queue.Full:
                        pass

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()

        frameCount = 0
        finished = False
        try:
            while not finished and (time.time() - state["_start"]) < timeout:
                ret, frame = cap.read()
                if not ret:
                    continue
                # 缩小高分辨率摄像头帧,降低前台重绘/拷贝/推理预处理开销
                frame = shrinkFrame(frame)
                frameCount += 1

                # 显示节流: 每 DISPLAY_INTERVAL 帧才显示一次,降低 HighGUI 消息泵压力
                if frameCount % DISPLAY_INTERVAL == 0:
                    display = frame.copy()
                    if overlayFunc is not None:
                        overlayFunc(display, state)
                    cv2.imshow(windowName, display)
                    if cv2.waitKey(WAITKEY_DELAY_MS) & 0xFF == 27:
                        state["interrupted"] = True
                        finished = True
                        break
                else:
                    # 非显示帧也要泵 Windows 消息(waitKey 内部处理消息泵),
                    # 否则前台焦点窗口的鼠标/重绘消息堆积 → 鼠标卡顿
                    if cv2.waitKey(WAITKEY_DELAY_MS) & 0xFF == 27:
                        state["interrupted"] = True
                        finished = True
                        break

                # 跳帧: 每 SKIP_FRAME_INTERVAL 帧送一帧给子线程推理
                if frameCount % SKIP_FRAME_INTERVAL == 0:
                    try:
                        frame_queue.put(frame, block=False)
                    except queue.Full:
                        pass

                # 非阻塞取推理结果并判定(判定在主线程,速度快,不阻塞消息泵)
                try:
                    result = result_queue.get(block=False)
                except queue.Empty:
                    continue

                if onResult(result, frame, state):
                    finished = True
                    break
        finally:
            # 终止子线程: 清空待处理帧后放入 None 哨兵
            try:
                while True:
                    frame_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                frame_queue.put(None, block=False)
            except queue.Full:
                pass
            worker_thread.join(timeout=1.0)

        return state

    def calibrateBaseline(self, cap):
        """
        采集正面姿态基准(用于动作的相对偏移判定)
        提示用户正对摄像头,采集 BASELINE_DURATION 秒内的 Yaw/Pitch/EAR 均值,
        消除 solvePnP 系统偏差
        :param cap: cv2.VideoCapture 摄像头对象
        :return: 是否校准成功<bool>
        """
        print("\n[校准] 请正对摄像头,保持不动(采集正面基准)...")
        yaws, pitches, ears = [], [], []

        def infer(frame):
            """子线程推理: 检测人脸"""
            return self.appDetect.get(frame)

        def onResult(faces, frame, state):
            """主线程处理: 收集正面姿态/眼睛灰度基准"""
            if len(faces) == 0:
                return False
            pitch, yaw, roll = self._getPose(faces[0])
            yaws.append(yaw)
            pitches.append(pitch)
            eye_std = self._getEyeGrayStd(frame, faces[0])
            if eye_std is not None:
                ears.append(eye_std)
            eye_disp = ears[-1] if ears else 0.0
            # 实时打印采集到的姿态和眼睛灰度,便于观察基准是否合理
            print(f"  [校准] yaw={yaw:.2f} pitch={pitch:.2f} roll={roll:.2f} eyeStd={eye_disp:.2f}",
                  end='\r', flush=True)
            return False  # 一直采集到超时

        def overlay(display, state):
            self._putText(display, "Calibrating frontal baseline...", (10, 30))

        state = self._runDetectLoop(cap, infer, onResult, BASELINE_DURATION, overlayFunc=overlay)
        if state.get("interrupted"):
            return False  # 用户 ESC 中断

        if len(yaws) < 3 or len(ears) < 3:
            print("\n  [警告] 基准采集样本不足,使用默认基准")
            self.baselineYaw = 0.0
            self.baselinePitch = 0.0
            self.baselineEAR = 20.0  # 眼睛灰度标准差默认基准
        else:
            # 用中位数更稳健(排除极端帧)
            self.baselineYaw = float(np.median(yaws))
            self.baselinePitch = float(np.median(pitches))
            self.baselineEAR = float(np.median(ears))

        print(f"\n  基准: Yaw={self.baselineYaw:.2f}, Pitch={self.baselinePitch:.2f}, eyeStd={self.baselineEAR:.2f} (样本 {len(yaws)} 帧)")
        return True

    def runSilentCheck(self, cap):
        """
        静默活体检测阶段(第一层防御)
        连续采集多帧,每帧做人脸检测 + 静默判定,全部通过才判定为真人(非攻击)
        :param cap: cv2.VideoCapture 摄像头对象
        :return: {"passed": bool, "avgLogitDiff": float}
                 passed=True 表示判定为真人(非攻击)
                 avgLogitDiff 为通过帧的平均 logitDiff(仅作日志参考)
        """
        print("\n[静默活体检测] 请正对摄像头,勿做动作(拦截照片/翻拍)...")
        passCount = 0
        logitDiffs = []  # 通过帧的 logitDiff(real - spoof)

        def infer(frame):
            """子线程推理: 人脸检测 + 静默判定(两者均 CPU 密集)"""
            faces = self.appDetect.get(frame)
            if len(faces) == 0:
                return None
            bbox = faces[0].bbox
            return self.silentDetector.check(frame, bbox)

        def onResult(result, frame, state):
            """主线程处理: 统计连续通过帧数"""
            nonlocal passCount, logitDiffs
            if result is None:
                return False
            if result["isReal"]:
                passCount += 1
                logitDiffs.append(result["detail"].get("logitDiff", 0.0))
            else:
                passCount = 0  # 任一帧疑似假体则重新计数
                logitDiffs = []
                print(f"  [静默异常] {result['detail']}")
            return passCount >= SILENT_PASS_FRAMES

        def overlay(display, state):
            self._putText(display, f"Silent check: {passCount}/{SILENT_PASS_FRAMES}", (10, 30))

        # 静默阶段最长 8 秒
        state = self._runDetectLoop(cap, infer, onResult, 8.0, overlayFunc=overlay)
        if state.get("interrupted"):
            return {"passed": False, "avgLogitDiff": 0.0}

        if passCount >= SILENT_PASS_FRAMES:
            avgLogitDiff = float(np.mean(logitDiffs)) if logitDiffs else 0.0
            print(f"  ✓ 静默活体检测通过({passCount} 帧, 平均logitDiff={avgLogitDiff:.2f})")
            return {"passed": True, "avgLogitDiff": avgLogitDiff}
        else:
            print(f"  ✗ 静默活体检测未通过({passCount}/{SILENT_PASS_FRAMES})")
            return {"passed": False, "avgLogitDiff": 0.0}

    def _detectSingleAction(self, cap, action):
        """
        检测单个动作(复用通用 _runDetectLoop 的子线程推理 + 主线程显示架构)
        :param cap: cv2.VideoCapture 摄像头对象
        :param action: 动作名称<str>
        :return: (是否通过<bool>, 是否用户中断<bool>)
        """
        print(f"\n请{action}...")

        def infer(frame):
            """子线程推理: 检测人脸"""
            return self.appDetect.get(frame)

        def onResult(faces, frame, state):
            """主线程处理: 用已检测到的人脸判定动作(数值计算快,不阻塞消息泵)"""
            passed, value, info = self.checkActionWithFaces(faces, frame, action)
            # 打印节流: 每 5 帧才刷新一次控制台,避免 PyCharm/终端渲染高频输出拖慢系统
            frameCount = state.setdefault("printCount", 0) + 1
            state["printCount"] = frameCount
            if frameCount % 5 == 0:
                print(f"  [{action}] {info}  => 值={value:.3f} 通过={passed}", end='\r', flush=True)
            if passed:
                state["passed"] = True
                print(f"\n  ✓ {action} 通过 (值: {value:.3f})")
                return True
            return False

        def overlay(display, state):
            remaining = ACTION_TIMEOUT - (time.time() - state["_start"])
            self._putText(display, f"Action: {action}", (10, 30))
            self._putText(display, f"Time: {remaining:.1f}s", (10, 60))

        state = self._runDetectLoop(cap, infer, onResult, ACTION_TIMEOUT, overlayFunc=overlay)
        if state.get("interrupted"):
            return False, True

        actionPassed = state.get("passed", False)
        if not actionPassed:
            print(f"\n  [超时] {action} 未完成")
        return actionPassed, False

    def runAdaptiveActions(self, cap):
        """
        自适应主动动作检测(第二层防御)
        =================================
        随机动作 + 概率递推 + 累计失败计数:
        - 动作从 ACTION_SEQUENCE 随机打乱,逐个执行
        - 动作成功: 按连续成功次数查概率表决定是否继续(无失败 45%/15%,有失败 30%/10%)
        - 动作失败: 100% 继续下一个,累计失败达 MAX_FAIL_COUNT 判定整体失败
        每个动作内部由 _runDetectLoop 统一管理"子线程推理 + 主线程显示"。
        :param cap: cv2.VideoCapture 摄像头对象
        :return: (是否通过<bool>, 是否用户中断<bool>)
        """
        # 姿态基准校准(相对偏移判定需要基准)
        if not self.calibrateBaseline(cap):
            return False, True  # 用户中断

        # 动作池随机打乱(随机顺序)
        actionPool = list(ACTION_SEQUENCE)
        random.shuffle(actionPool)
        print(f"  [动作池] {actionPool}")

        failCount = 0      # 累计失败次数
        streak = 0         # 连续成功次数
        hasFailed = False  # 是否失败过

        while actionPool:
            action = actionPool.pop(0)
            passed, interrupted = self._detectSingleAction(cap, action)
            if interrupted:
                return False, True

            if not passed:
                # 动作失败: 累计失败 + 重置连续成功
                failCount += 1
                streak = 0
                hasFailed = True
                print(f"  [失败] {action} 未完成,累计失败 {failCount}/{MAX_FAIL_COUNT}")
                if failCount >= MAX_FAIL_COUNT:
                    return False, False  # 累计失败达到阈值,整体失败
                continue  # 失败 100% 继续下一个动作

            # 动作成功
            streak += 1
            probMap = CONTINUE_PROB_NO_FAIL if not hasFailed else CONTINUE_PROB_HAS_FAIL
            continueProb = probMap.get(streak, 0.0)
            if random.random() >= continueProb:
                print(f"  [通过] 动作验证通过(连续成功 {streak} 次),无需继续")
                break
            print(f"  [继续] 继续概率 {continueProb * 100:.0f}%,进行下一个动作")

        # 动作池耗尽或已通过
        return True, False

    def runLivenessCheck(self, cap, collectFrontal=True, progressCallback=None):
        """
        执行完整活体检测流程(多层防御: 静默 + 自适应动作)
        ==================================================
        1. 降低摄像头分辨率(缓解卡顿)
        2. 静默活体检测(第一层),返回 avgLogitDiff
        3. 无论静默检测置信度高低,都进行自适应动作检测(第二层)
        4. (可选)活体通过后采集正脸帧,供识别使用

        :param cap: cv2.VideoCapture 摄像头对象
        :param collectFrontal: 通过后是否采集正脸帧<bool>,默认 True
        :param progressCallback: 阶段进度回调<Callable>,签名 progressCallback(stage, detail),
                                 默认 None(不回调);stage 取值:
                                 "silent" 静默检测 / "action" 主动动作 / "frontal" 正脸采集
                                 (回调抛异常会沿调用链向上传播, 由调用方处理, 如取消任务)
        :return: 结果字典<dict>:
                 成功: {"success": True, "msg": "...", "frontalFrame": np.ndarray 或 None}
                 失败: {"success": False, "step": str, "msg": "..."}
        """
        def _notify(stage, detail=""):
            """阶段进度回调包装"""
            if progressCallback is not None:
                progressCallback(stage, detail)

        # Step 1: 降低摄像头采集分辨率,缓解画面/鼠标卡顿
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Step 2: 静默活体检测(第一层),未通过(疑似照片/翻拍)直接拒绝
        _notify("silent", "静默活体检测中")
        if self.useSilent:
            silentResult = self.runSilentCheck(cap)
            if not silentResult["passed"]:
                cv2.destroyAllWindows()
                return {"success": False, "step": "静默检测", "msg": "静默活体检测未通过(疑似照片/翻拍)"}

        # Step 3: 无论静默检测置信度高低,都必须进行主动动作检测(第二层)
        _notify("action", "主动动作检测中")
        passed, interrupted = self.runAdaptiveActions(cap)
        cv2.destroyAllWindows()
        if interrupted:
            return {"success": False, "step": "动作检测", "msg": "用户中断"}
        if not passed:
            return {"success": False, "step": "动作检测", "msg": "动作验证失败"}

        # Step 4: 活体通过后采集正脸帧(供识别使用)
        frontalFrame = None
        if collectFrontal:
            _notify("frontal", "正脸采集中")
            frontalFrame = self._collectFrontalFrame(cap)

        cv2.destroyAllWindows()
        return {"success": True, "msg": "活体检测通过", "frontalFrame": frontalFrame}

    def _collectFrontalFrame(self, cap, timeout=5.0):
        """
        采集一帧正面人脸(动作通过后调用,用于身份识别)
        要求相对基准偏移接近 0(姿态摆正),避免用侧脸/表情帧做识别
        :param cap: cv2.VideoCapture 摄像头对象
        :param timeout: 超时时间<秒>
        :return: 正脸 BGR 帧<np.ndarray>,超时返回 None
        """
        print("\n[正脸采集] 请正对摄像头,用于身份识别...")

        def infer(frame):
            """子线程推理: 检测人脸"""
            return self.appDetect.get(frame)

        def onResult(faces, frame, state):
            """主线程处理: 判定是否为正脸(姿态摆正),是则记录该帧"""
            if len(faces) == 0:
                return False
            lm = faces[0].landmark_2d_106
            if lm is None:
                return False
            pitch, yaw, roll = self._getPose(faces[0])
            relYaw = yaw - self.baselineYaw
            relPitch = pitch - self.baselinePitch
            if abs(relYaw) <= FRONTAL_YAW_TOL and abs(relPitch) <= FRONTAL_PITCH_TOL:
                state["frontalFrame"] = frame
                print("  ✓ 已采集正脸帧")
                return True
            return False

        def overlay(display, state):
            self._putText(display, "Keep frontal for recognition...", (10, 30))

        state = self._runDetectLoop(cap, infer, onResult, timeout, overlayFunc=overlay)
        if state.get("frontalFrame") is not None:
            return state["frontalFrame"]

        print("  [警告] 正脸采集超时,返回 None")
        return None
