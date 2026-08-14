# -*- coding: utf-8 -*-
"""
主动动作活体检测模块(livenessDetector)
=======================================
第二层防御: 要求用户按顺序完成 5 个动作(左转/右转/抬头/眨眼/张嘴),
通过连续多帧动作判定确认是真人(照片/视频无法完成动作)。

关键改进(相对旧版 faceInputer/livenessDetector.py):
1. 姿态基准校准: 动作检测前先采集正面基准 Yaw/Pitch,动作用"相对基准偏移量"判定
2. 双线程架构: 主线程只读帧+显示,子线程推理,画面不再被推理阻塞
3. 显示节流 + 降分辨率: 缓解摄像头窗口/鼠标卡顿
4. 集成静默活体检测(silentLiveness)作为第一道关卡

技术依据:
- 头部姿态: 直接使用 InsightFace 自带的 face.pose(基于 landmark_3d_68,准确可靠)
- EAR(眨眼): 眼睛纵横比,眨眼时瞬间下降(左眼 35/36/37/39/41/42,右眼 89~96)
- MAR(张嘴): 嘴部纵横比,张嘴时增大(嘴巴外轮廓 52~71)
"""

import os
import time
import cv2
import numpy as np
from insightface.app import FaceAnalysis

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

# 正脸采集: 动作通过后采集正脸时的相对偏移容差(度)
FRONTAL_YAW_TOL = 10.0
FRONTAL_PITCH_TOL = 8.0

# 跳帧间隔: 每 N 帧送一帧给子线程推理(降低 CPU 负担)
SKIP_FRAME_INTERVAL = 3

# 显示节流: 每 N 帧才更新一次 imshow(降低 GUI 压力,缓解鼠标卡顿)
DISPLAY_INTERVAL = 2


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


# ====================================================================
# 活体检测器类
# ====================================================================
class LivenessDetector:
    """
    活体检测器(多层防御)
    =====================
    第一层: 静默活体检测(silentLiveness)拦截照片/屏幕翻拍
    第二层: 主动动作检测(5 个动作)防止注入攻击与高级假体

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
        start = time.time()
        frameCount = 0

        while time.time() - start < BASELINE_DURATION:
            ret, frame = cap.read()
            if not ret:
                continue
            frameCount += 1

            display = frame.copy()
            self._putText(display, "Calibrating frontal baseline...", (10, 30))
            cv2.imshow("Liveness", display)
            if cv2.waitKey(1) & 0xFF == 27:
                return False

            # 跳帧降低 CPU 负担
            if frameCount % SKIP_FRAME_INTERVAL != 0:
                continue

            faces = self.appDetect.get(frame)
            if len(faces) == 0:
                continue

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
        连续采集多帧,每帧做人脸检测 + 静默判定,全部通过才进入动作阶段
        :param cap: cv2.VideoCapture 摄像头对象
        :return: 是否通过静默检测<bool>
        """
        print("\n[静默活体检测] 请正对摄像头,勿做动作(拦截照片/翻拍)...")
        passCount = 0
        frameCount = 0
        start = time.time()
        # 静默阶段最长 8 秒
        while passCount < SILENT_PASS_FRAMES and time.time() - start < 8.0:
            ret, frame = cap.read()
            if not ret:
                continue
            frameCount += 1

            display = frame.copy()
            self._putText(display, f"Silent check: {passCount}/{SILENT_PASS_FRAMES}", (10, 30))
            cv2.imshow("Liveness", display)
            if cv2.waitKey(1) & 0xFF == 27:
                return False

            # 跳帧降低 CPU 负担
            if frameCount % SKIP_FRAME_INTERVAL != 0:
                continue

            faces = self.appDetect.get(frame)
            if len(faces) == 0:
                continue

            # 取第一个人脸的 bbox 做静默判定
            bbox = faces[0].bbox
            result = self.silentDetector.check(frame, bbox)
            if result["isReal"]:
                passCount += 1
            else:
                passCount = 0  # 任一帧疑似假体则重新计数
                print(f"  [静默异常] {result['detail']}")

        if passCount >= SILENT_PASS_FRAMES:
            print(f"  ✓ 静默活体检测通过({passCount} 帧)")
            return True
        else:
            print(f"  ✗ 静默活体检测未通过({passCount}/{SILENT_PASS_FRAMES})")
            return False

    def runLivenessCheck(self, cap, collectFrontal=True):
        """
        执行完整活体检测流程(多层防御: 静默 + 主动动作)
        ==================================================
        1. 降低摄像头分辨率(缓解卡顿)
        2. 静默活体检测(第一层)
        3. 正面姿态基准校准
        4. 主动动作检测(第二层,双线程)
        5. (可选)动作通过后采集正脸帧,供后续识别使用

        :param cap: cv2.VideoCapture 摄像头对象
        :param collectFrontal: 动作通过后是否采集正脸帧<bool>,默认 True
        :return: 结果字典<dict>:
                 成功: {"success": True, "msg": "...", "frontalFrame": np.ndarray 或 None}
                 失败: {"success": False, "step": str, "msg": "..."}
        """
        import threading
        import queue

        # Step 1: 降低摄像头采集分辨率,缓解画面/鼠标卡顿
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Step 2: 静默活体检测(第一层)
        if self.useSilent:
            if not self.runSilentCheck(cap):
                cv2.destroyAllWindows()
                return {"success": False, "step": "静默检测", "msg": "静默活体检测未通过(疑似照片/翻拍)"}

        # Step 3: 正面姿态基准校准
        if not self.calibrateBaseline(cap):
            cv2.destroyAllWindows()
            return {"success": False, "step": "校准", "msg": "用户中断"}

        # Step 4: 主动动作检测(双线程架构)
        frame_queue = queue.Queue(maxsize=1)
        result_queue = queue.Queue(maxsize=1)

        def inferenceWorker():
            """子线程: 从帧队列取帧执行轻量模型推理"""
            while True:
                try:
                    frame = frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if frame is None:
                    break
                faces = self.appDetect.get(frame)
                try:
                    result_queue.put(faces, block=False)
                except queue.Full:
                    try:
                        result_queue.get(block=False)
                    except queue.Empty:
                        pass
                    try:
                        result_queue.put(faces, block=False)
                    except queue.Full:
                        pass

        def clearQueues():
            """清空帧/结果队列残留"""
            for q in (frame_queue, result_queue):
                while True:
                    try:
                        q.get(block=False)
                    except queue.Empty:
                        break

        def stopWorker():
            """终止子线程"""
            while True:
                try:
                    frame_queue.get(block=False)
                except queue.Empty:
                    break
            try:
                frame_queue.put(None, block=False)
            except queue.Full:
                pass
            worker.join(timeout=1.0)

        worker = threading.Thread(target=inferenceWorker, daemon=True)
        worker.start()

        try:
            for action in ACTION_SEQUENCE:
                clearQueues()
                print(f"\n请{action}...")
                actionPassed = False
                start = time.time()
                frameCount = 0

                while time.time() - start < ACTION_TIMEOUT:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    frameCount += 1

                    # 显示节流: 每 DISPLAY_INTERVAL 帧才显示一次,降低 GUI 压力
                    if frameCount % DISPLAY_INTERVAL == 0:
                        display = frame.copy()
                        remaining = ACTION_TIMEOUT - (time.time() - start)
                        self._putText(display, f"Action: {action}", (10, 30))
                        self._putText(display, f"Time: {remaining:.1f}s", (10, 60))
                        cv2.imshow("Liveness", display)
                        if cv2.waitKey(1) & 0xFF == 27:
                            return {"success": False, "step": action, "msg": "用户中断"}

                    # 每 SKIP_FRAME_INTERVAL 帧送一帧给子线程推理
                    if frameCount % SKIP_FRAME_INTERVAL == 0:
                        try:
                            frame_queue.put(frame, block=False)
                        except queue.Full:
                            pass

                    # 非阻塞取推理结果并判定
                    try:
                        faces = result_queue.get(block=False)
                    except queue.Empty:
                        continue

                    passed, value, info = self.checkActionWithFaces(faces, frame, action)
                    # 打印详细调试数值(绝对姿态/基准/相对偏移/阈值),便于定位动作检测不到的问题
                    print(f"  [{action}] {info}  => 值={value:.3f} 通过={passed}", end='\r', flush=True)

                    if passed:
                        actionPassed = True
                        print(f"\n  ✓ {action} 通过 (值: {value:.3f})")
                        break

                if not actionPassed:
                    print(f"\n  [超时] {action} 未完成 | 基准 yaw={self.baselineYaw:.2f} pitch={self.baselinePitch:.2f} EAR={self.baselineEAR}")
                    return {"success": False, "step": action, "msg": "动作未完成"}
        finally:
            stopWorker()

        # Step 5: 动作全部通过后,采集正脸帧(供识别使用)
        frontalFrame = None
        if collectFrontal:
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
        start = time.time()
        frameCount = 0
        while time.time() - start < timeout:
            ret, frame = cap.read()
            if not ret:
                continue
            frameCount += 1

            display = frame.copy()
            self._putText(display, "Keep frontal for recognition...", (10, 30))
            cv2.imshow("Liveness", display)
            if cv2.waitKey(1) & 0xFF == 27:
                return None

            if frameCount % SKIP_FRAME_INTERVAL != 0:
                continue

            faces = self.appDetect.get(frame)
            if len(faces) == 0:
                continue
            lm = faces[0].landmark_2d_106
            if lm is None:
                continue

            pitch, yaw, roll = self._getPose(faces[0])
            relYaw = yaw - self.baselineYaw
            relPitch = pitch - self.baselinePitch
            if abs(relYaw) <= FRONTAL_YAW_TOL and abs(relPitch) <= FRONTAL_PITCH_TOL:
                print("  ✓ 已采集正脸帧")
                return frame

        print("  [警告] 正脸采集超时,返回 None")
        return None
