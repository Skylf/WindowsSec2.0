"""
coding:utf-8
file: UI/FaceModuleUI/UI_object.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:202608151041
lateCodedTime:20260815
"""

# 该模块为人脸识别 UI 的功能基类(纯功能模块, 不包含流程入口)
# 两层职责分离:
#   GUI  : 纯 UI 显示层(QMainWindow 软件外壳, 页面容器, 显示接口)
#   UiRsp: 响应+通信层(按钮响应 / 文件操作 / 与中心调度的一切通信)
#
# 架构约定:
#   1. GUI.__init__(uiRsp) 外部注入响应层, GUI 内部不创建 UiRsp
#   2. GUI 按钮回调只转发给 UiRsp 的特定方法, GUI 不直接碰中心调度
#   3. UiRsp 继承 CenterMoudle 的 Observer, 注册到中心调度后与业务模块通信
#   4. UiRsp.require_main_thread()=True: 中心调度自动把事件切主线程投递,
#      保证 UI 控件只在主线程操作(PyQt 硬性要求)
#   5. GUI 是软件全部功能的载体(后续扩展录入页/设置页/安全策略页/动画),
#      本文件只提供外壳与接口, 具体页面由后续子类实现

import os
import sys

# 注入 CenterMoudle 目录(本文件位于 <项目根>/UI/FaceModuleUI/, 上 3 级为项目根)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CENTER_MOUDLE_DIR = os.path.join(_PROJECT_ROOT, 'CenterMoudle')
if _CENTER_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _CENTER_MOUDLE_DIR)

# PyQt6
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QFileDialog
from PyQt6.QtCore import pyqtSignal

# 中心调度观察者基类
from observerObject import Observer


# ====================================================================
# 事件名常量(与 FaceService / 中心调度约定一致的通信协议)
# ====================================================================
EVENT_FACE_RECOGNIZE_REQUEST = "FACE_RECOGNIZE_REQUEST"   # UI → FaceService: 发起识别
EVENT_FACE_RECOGNIZE_CANCEL = "FACE_RECOGNIZE_CANCEL"     # UI → FaceService: 取消识别
EVENT_FACE_RECOGNIZE_PROGRESS = "FACE_RECOGNIZE_PROGRESS" # FaceService → UI: 阶段进度
EVENT_FACE_RECOGNIZE_RESULT = "FACE_RECOGNIZE_RESULT"     # FaceService → UI: 识别结果
EVENT_FACE_ENROLL_REQUEST = "FACE_ENROLL_REQUEST"         # UI → FaceService: 发起录入
EVENT_FACE_ENROLL_CANCEL = "FACE_ENROLL_CANCEL"           # UI → FaceService: 取消录入(预留)
EVENT_FACE_ENROLL_PROGRESS = "FACE_ENROLL_PROGRESS"       # FaceService → UI: 录入进度
EVENT_FACE_ENROLL_RESULT = "FACE_ENROLL_RESULT"           # FaceService → UI: 录入结果
EVENT_MODULE_STATUS = "MODULE_STATUS"                     # 调度 → 全体: 模块上线/下线


# ====================================================================
# GUI: 纯 UI 显示层(软件外壳)
# ====================================================================
class GUI(QMainWindow):
    """
    纯 UI 显示基类(软件外壳)
    =======================
    职责: 窗口外壳 / 页面容器 / 显示接口 / 状态管理。
    不含业务逻辑, 不直接与中心调度通信; 一切交互经注入的 UiRsp 转发。

    使用方式(由流程脚本装配):
        uiRsp = UiRsp()
        gui = GUI(uiRsp)        # 外部注入; 构造时自动补挂 uiRsp.set_gui(gui)
        gui.add_page(识别页, "recognition")
        gui.show()

    扩展: 后续在 add_page 注册的具体页面(QWidget)中实现控件与动画,
    页面通过连接本类信号接收状态变化。
    """

    # ---- 信号(供具体页面连接, 基类不依赖具体控件) ----
    recognize_state_changed = pyqtSignal(bool)   # 识别状态变化(True=识别中), 页面据此使能/禁用按钮
    progress_received = pyqtSignal(str, str)     # 识别进度(stage, detail)
    result_received = pyqtSignal(object)         # 识别结果(dict)
    enroll_progress_received = pyqtSignal(str, str)   # 录入进度(stage, detail)
    enroll_result_received = pyqtSignal(object)       # 录入结果(dict)
    frame_received = pyqtSignal(object, str)          # 摄像头帧(frame, prompt), 供全屏画面页显示
    bsod_result_received = pyqtSignal(object)         # 蓝屏检测结果(dict)
    bsod_autostart_result_received = pyqtSignal(object)   # 蓝屏自启动状态(dict)
    freeze_status_received = pyqtSignal(object)       # 卡死监控状态(dict)
    freeze_config_received = pyqtSignal(object)       # 卡死检测配置(dict)
    freeze_alert_received = pyqtSignal(object)        # 卡死报警(dict)
    watermark_progress_received = pyqtSignal(object)  # 去水印进度(dict: percent/info)
    watermark_result_received = pyqtSignal(object)    # 去水印结果(dict)
    watermark_busy_received = pyqtSignal(object)      # 去水印处理状态(dict: busy)

    def __init__(self, uiRsp):
        """
        初始化 GUI 外壳
        :param uiRsp: 响应层实例<UiRsp>(外部注入, 内部不创建)
        """
        super().__init__()

        # 响应层引用(只转发, 不创建)
        self._rsp = uiRsp
        # 自动补挂: 若注入的 UiRsp 尚未持有 GUI, 在此绑定(装配只需两行)
        if self._rsp is not None and self._rsp.get_gui() is None:
            self._rsp.set_gui(self)

        # 页面容器: page_id(str) -> QWidget
        self._pages = {}
        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        # 全局状态
        self._busy = False
        self._recognizing = False

        # 窗口基础设置(具体外观/尺寸由子类或流程脚本调整)
        self.setWindowTitle("Windows 安全系统 2.0")
        self.resize(900, 640)
        self.statusBar().showMessage("就绪")

    # ============================================================
    # 页面管理
    # ============================================================
    def add_page(self, widget, page_id):
        """
        注册页面到容器
        :param widget: 页面控件<QWidget>
        :param page_id: 页面标识<str>, 如 "recognition" / "enroll"
        :return: None
        """
        self._pages[page_id] = widget
        self._stack.addWidget(widget)

    def switch_page(self, page_id, animate=False):
        """
        切换当前页面(预留动画)
        :param page_id: 页面标识<str>
        :param animate: 是否播放切换动画<bool>, 默认 False(动画后续实现)
        :return: None
        """
        if page_id not in self._pages:
            print(f"[GUI] 页面不存在: {page_id}")
            return
        self._stack.setCurrentWidget(self._pages[page_id])
        if animate:
            self.play_page_animation(page_id)

    def get_page(self, page_id):
        """
        获取已注册页面(供 UiRsp 更新具体控件)
        :param page_id: 页面标识<str>
        :return: QWidget 或 None
        """
        return self._pages.get(page_id)

    # ============================================================
    # 显示接口(UiRsp 在主线程调用)
    # ============================================================
    def update_status(self, text):
        """
        更新状态栏文字
        :param text: 状态文本<str>
        :return: None
        """
        self.statusBar().showMessage(text)

    def append_log(self, text):
        """
        追加日志(基类默认打印到控制台; 具体页面可覆写为显示到日志控件)
        :param text: 日志文本<str>
        :return: None
        """
        print(f"[GUI] {text}")

    def set_busy(self, busy):
        """
        设置全局忙碌态(忙碌时禁用页面容器交互, 防止并发操作)
        :param busy: 是否忙碌<bool>
        :return: None
        """
        self._busy = busy
        self._stack.setEnabled(not busy)

    def set_recognizing(self, active):
        """
        设置识别状态(经信号通知页面更新按钮使能)
        :param active: 是否识别中<bool>
        :return: None
        """
        self._recognizing = active
        self.recognize_state_changed.emit(active)

    def show_progress(self, stage, detail=""):
        """
        显示识别阶段进度(经信号转发给具体页面)
        :param stage: 阶段名<str>, 如 "silent" / "action" / "recognize"
        :param detail: 阶段明细<str>
        :return: None
        """
        self.progress_received.emit(stage, detail)

    def show_result(self, result_data):
        """
        显示识别结果(经信号转发给具体页面)
        :param result_data: 结果字典<dict>, 含 success/livenessPass/matched/similarity/msg 等
        :return: None
        """
        self.result_received.emit(result_data)

    def show_enroll_progress(self, stage, detail=""):
        """
        显示录入阶段进度(经信号转发给具体页面)
        :param stage: 阶段名<str>, 如 "silent" / "capture" / "clean" / "extract"
        :param detail: 阶段明细<str>
        :return: None
        """
        self.enroll_progress_received.emit(stage, detail)

    def show_enroll_result(self, result_data):
        """
        显示录入结果(经信号转发给具体页面)
        :param result_data: 结果字典<dict>, 含 success/msg/step/featurePath/cancelled 等
        :return: None
        """
        self.enroll_result_received.emit(result_data)

    def show_frame(self, frame, prompt=""):
        """
        显示摄像头帧(经信号转发给全屏画面页; 跨线程调用安全,
        pyqtSignal 自动 QueuedConnection 切主线程)
        :param frame: BGR 帧<np.ndarray>
        :param prompt: 当前提示词<str>(如 "请左转")
        :return: None
        """
        self.frame_received.emit(frame, prompt)

    def show_bsod_result(self, result_data):
        """
        显示蓝屏检测结果(经信号转发给蓝屏识别页)
        :param result_data: 结果字典<dict>, 含 found/event/report
        :return: None
        """
        self.bsod_result_received.emit(result_data)

    def show_bsod_autostart_result(self, result_data):
        """
        显示蓝屏自启动状态(经信号转发给蓝屏识别页)
        :param result_data: 结果字典<dict>, 含 enabled/ok
        :return: None
        """
        self.bsod_autostart_result_received.emit(result_data)

    def show_freeze_status(self, result_data):
        """
        显示卡死监控状态(经信号转发给卡死检测页)
        :param result_data: 结果字典<dict>, 含 running/ok
        :return: None
        """
        self.freeze_status_received.emit(result_data)

    def show_freeze_config(self, result_data):
        """
        显示卡死检测配置(经信号转发给卡死检测页)
        :param result_data: 结果字典<dict>, 含 config
        :return: None
        """
        self.freeze_config_received.emit(result_data)

    def show_freeze_alert(self, alert_data):
        """
        显示卡死报警(经信号转发给卡死检测页)
        :param alert_data: 报警字典<dict>, 含 type/msg/time/top_processes/info
        :return: None
        """
        self.freeze_alert_received.emit(alert_data)

    def show_watermark_progress(self, progress_data):
        """
        显示去水印进度(经信号转发给视频去水印页)
        :param progress_data: 进度字典<dict>, 含 percent/info
        :return: None
        """
        self.watermark_progress_received.emit(progress_data)

    def show_watermark_result(self, result_data):
        """
        显示去水印结果(经信号转发给视频去水印页)
        :param result_data: 结果字典<dict>, 含 success/msg/output_path/
                            watermark_bbox/frames/avg_ms/mode/note/cancelled
        :return: None
        """
        self.watermark_result_received.emit(result_data)

    def show_watermark_busy(self, busy_data):
        """
        显示去水印处理状态(经信号转发给视频去水印页, 控制按钮使能)
        :param busy_data: 状态字典<dict>, 含 busy
        :return: None
        """
        self.watermark_busy_received.emit(busy_data)

    # ---- 全屏画面页控制(由 MainWindow 覆写实现) ----
    def show_live_page(self):
        """切换到全屏摄像头画面页(录入/识别进行时调用, 由子类覆写)"""
        pass

    def hide_live_page(self):
        """退出全屏画面页, 恢复原窗口(由子类覆写)"""
        pass

    def show_enroll_success(self):
        """录入成功反馈(画面显示成功标识后自动退回, 由子类覆写)"""
        pass

    def get_rsp(self):
        """
        获取注入的响应层(UiRsp)引用(页面控件据此转发交互)
        :return: UiRsp 或 None
        """
        return self._rsp

    # ============================================================
    # 动画预留(后续用 QPropertyAnimation 实现)
    # ============================================================
    def play_page_animation(self, page_id):
        """
        页面切换动画(预留接口, 后续实现淡入淡出/滑动等)
        :param page_id: 页面标识<str>
        :return: None
        """
        pass


# ====================================================================
# UiRsp: 响应+通信层(GUI 与中心调度之间的唯一桥梁)
# ====================================================================
class UiRsp(Observer):
    """
    响应+通信基类(界面交互与外界联系)
    ================================
    职责:
    - 接收 GUI 按钮回调, 转为事件经中心调度发给业务模块(如 FaceService)
    - 文件操作(选择特征文件等本地交互)
    - 接收中心调度推来的事件(进度/结果/模块状态), 更新 GUI 显示
    - 维护交互状态机(IDLE / RECOGNIZING), 防重复点击

    使用方式(由流程脚本装配):
        uiRsp = UiRsp()
        gui = GUI(uiRsp)                    # GUI 构造自动补挂 uiRsp
        scheduler.register_module(uiRsp)    # 注册后才有通信能力
    """

    # 交互状态常量
    STATE_IDLE = "IDLE"                 # 空闲
    STATE_RECOGNIZING = "RECOGNIZING"   # 识别中
    STATE_ENROLLING = "ENROLLING"       # 录入中

    def __init__(self, gui=None):
        """
        初始化响应层
        :param gui: GUI 显示层实例(可稍后经 set_gui 补挂, 由 GUI 构造自动完成)
        """
        super().__init__(name="uiRsp")
        self._gui = gui
        self._state = self.STATE_IDLE

    # ============================================================
    # GUI 绑定
    # ============================================================
    def get_gui(self):
        """
        获取绑定的 GUI 实例
        :return: GUI 或 None
        """
        return self._gui

    def set_gui(self, gui):
        """
        绑定 GUI 显示层(由 GUI 构造时自动调用)
        :param gui: GUI 实例
        :return: None
        """
        self._gui = gui

    # ============================================================
    # 线程钩子(覆写 Observer): UI 控件必须在主线程操作
    # ============================================================
    def require_main_thread(self) -> bool:
        """
        本模块必须在主线程接收事件(中心调度据此自动切换投递线程)
        :return: True
        """
        return True

    # ============================================================
    # GUI 按钮回调入口(由 GUI 按钮事件转发, 均在主线程执行)
    # ============================================================
    def on_start_recognize(self, feature_path, threshold=0.85):
        """
        [开始识别] 按钮响应: 校验状态 → 发识别请求(经中心调度)
        :param feature_path: 已注册特征文件路径<str>
        :param threshold: 相似度阈值<float>, 默认 0.85
        :return: None
        """
        # 防重复点击: 识别中拒绝新请求
        if self._state != self.STATE_IDLE:
            self._log("已有识别任务进行中, 请等待完成或取消")
            return
        if not feature_path:
            self._log("未选择特征文件, 无法识别")
            return

        # 先发送请求, 发送成功才进入识别中状态(失败则保持 IDLE, 避免状态卡死)
        sent = self._send("faceService", {
            "featurePath": feature_path,
            "threshold": threshold,
        }, EVENT_FACE_RECOGNIZE_REQUEST)
        if not sent:
            self._log("识别请求发送失败(目标模块不存在或未注册调度)")
            return

        self._state = self.STATE_RECOGNIZING
        self._gui.set_recognizing(True)
        self._log(f"发起识别: {os.path.basename(feature_path)} (阈值 {threshold})")

    def on_cancel_recognize(self):
        """
        [取消识别] 按钮响应: 发取消请求; 状态由 RESULT 事件确认后回 IDLE
        :return: None
        """
        if self._state != self.STATE_RECOGNIZING:
            return
        self._log("请求取消识别...")
        self._send("faceService", {}, EVENT_FACE_RECOGNIZE_CANCEL)

    def on_start_enroll(self, user_name) -> bool:
        """
        [开始录入] 按钮响应: 校验状态与用户名 → 发录入请求(经中心调度)
        :param user_name: 用户名<str>
        :return: 是否成功发起<bool>(状态忙/用户名空/发送失败返回 False)
        """
        # 防重复: 识别/录入进行中拒绝新任务
        if self._state != self.STATE_IDLE:
            self._log(f"当前状态 {self._state}, 请等待任务完成后再录入")
            return False
        if not user_name or not user_name.strip():
            self._log("用户名不能为空")
            return False

        # 先发送请求(携带帧监听器, 供 FaceService 回调摄像头画面), 成功才进入录入中状态
        sent = self._send("faceService", {
            "userName": user_name.strip(),
            "frameListener": self._on_frame,
        }, EVENT_FACE_ENROLL_REQUEST)
        if not sent:
            self._log("录入请求发送失败(目标模块不存在或未注册调度)")
            return False

        self._state = self.STATE_ENROLLING
        self._gui.set_recognizing(True)   # 复用忙碌信号(禁用相关按钮)
        self._gui.show_live_page()        # 切换全屏摄像头画面页
        self._log(f"发起录入: {user_name.strip()}")
        return True

    def on_cancel_enroll(self):
        """
        [退出识别/取消录入] 响应: 发取消请求(全屏画面页退出按钮调用)
        状态由 ENROLL_RESULT(cancelled) 事件确认后回 IDLE
        :return: None
        """
        if self._state != self.STATE_ENROLLING:
            return
        self._log("请求取消录入...")
        self._send("faceService", {}, EVENT_FACE_ENROLL_CANCEL)

    # ============================================================
    # 帧监听(摄像头画面 → 全屏画面页)
    # ============================================================
    def _on_frame(self, frame, prompt=""):
        """
        摄像头帧回调(由 FaceService 后台线程调用, 线程安全:
        经 GUI.frame_received 信号自动切主线程更新画面)
        :param frame: BGR 帧<np.ndarray>
        :param prompt: 当前提示词<str>
        :return: None
        """
        if self._gui is not None:
            self._gui.show_frame(frame, prompt)

    # ============================================================
    # 文件操作(本地交互, 不经过中心调度)
    # ============================================================
    def select_feature_file(self) -> str:
        """
        弹出文件选择对话框, 选择已注册特征文件(.npy)
        :return: 文件绝对路径<str>, 用户取消返回 None
        """
        if self._gui is None:
            print("[UiRsp] 未绑定 GUI, 无法弹出文件对话框")
            return None
        path, _ = QFileDialog.getOpenFileName(
            self._gui, "选择已注册特征文件", "", "特征文件 (*.npy)"
        )
        return path if path else None

    # ============================================================
    # 蓝屏识别交互(经中心调度 → SecurityModule)
    # ============================================================
    def on_bsod_check(self, simulate=False):
        """
        [立即检测/模拟演示] 按钮响应: 请求蓝屏检测(经中心调度)
        :param simulate: 是否使用模拟数据<bool>
        :return: None
        """
        self._send("securityModule", {"simulate": simulate}, "BSOD_CHECK_REQUEST")

    def on_bsod_autostart(self, enabled):
        """
        开机自启动开关响应: 注册/移除自启动(经中心调度)
        :param enabled: 是否开启<bool>
        :return: None
        """
        self._send("securityModule", {"enabled": enabled}, "BSOD_AUTOSTART_REQUEST")

    def on_bsod_autostart_status(self):
        """查询开机自启动状态(页面初始化调用)"""
        self._send("securityModule", {}, "BSOD_AUTOSTART_STATUS_REQUEST")

    # ============================================================
    # 卡死检测交互(经中心调度 → FreezeModule)
    # ============================================================
    def on_freeze_start(self):
        """[开始监控] → FreezeModule 启动持续监控"""
        self._send("freezeModule", {}, "FREEZE_START_REQUEST")

    def on_freeze_stop(self):
        """[停止监控] → FreezeModule 停止持续监控"""
        self._send("freezeModule", {}, "FREEZE_STOP_REQUEST")

    def on_freeze_status(self):
        """查询监控运行状态(页面初始化)"""
        self._send("freezeModule", {}, "FREEZE_STATUS_REQUEST")

    def on_freeze_config_status(self):
        """查询卡死检测配置(页面初始化加载)"""
        self._send("freezeModule", {}, "FREEZE_CONFIG_STATUS_REQUEST")

    # ============================================================
    # 视频去水印交互(经中心调度 → WatermarkModule)
    # ============================================================
    def on_watermark_start(self, params):
        """
        [开始处理] 按钮响应: 请求后台处理视频(经中心调度)
        :param params: 处理参数<dict>, 含 input/output/mode/quality/use_gpu
        :return: None
        """
        self._send("watermarkModule", params, "WATERMARK_PROCESS_REQUEST")

    def on_watermark_cancel(self):
        """[取消] 按钮响应: 请求取消当前处理(经中心调度)"""
        self._send("watermarkModule", {}, "WATERMARK_CANCEL_REQUEST")

    def on_freeze_set_config(self, key, value):
        """修改卡死检测配置项(阈值/总开关等)"""
        self._send("freezeModule", {"key": key, "value": value},
                   "FREEZE_SET_CONFIG_REQUEST")

    def check_current_feature(self, user_name):
        """
        检查指定用户是否已有特征(文件操作类, 供录入页显示特征状态)
        :param user_name: 用户名<str>
        :return: (是否存在<bool>, 特征文件名<str> 或 None)
        """
        try:
            import os as _os
            project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
            face_detecter_dir = _os.path.join(project_root, 'FaceMoudle', 'faceDetecter')
            if face_detecter_dir not in sys.path:
                sys.path.insert(0, face_detecter_dir)
            from faceDataGetter import findLatestFeature
            feature_path = findLatestFeature(user_name)
            if feature_path:
                return True, _os.path.basename(feature_path)
        except Exception as e:
            print(f"[UiRsp] 检查特征状态失败: {e}")
        return False, None

    # ============================================================
    # 事件接收(覆写 Observer.all_event, 由中心调度在主线程投递)
    # ============================================================
    def all_event(self, event, content, *args, **kwargs):
        """
        收到中心调度投递的事件, 按事件名分发更新 GUI
        :param event: 事件名<str>
        :param content: 事件内容(dict)
        :return: None
        """
        if event == EVENT_FACE_RECOGNIZE_PROGRESS:
            # 识别阶段进度: {stage: str, detail: str}
            stage = content.get("stage", "")
            detail = content.get("detail", "")
            self._gui.show_progress(stage, detail)
            self._log(f"[进度] {stage}: {detail}")

        elif event == EVENT_FACE_RECOGNIZE_RESULT:
            # 识别结果: {success, livenessPass, matched, similarity, msg, step}
            # 收到结果 → 状态机回 IDLE, 恢复按钮
            self._state = self.STATE_IDLE
            self._gui.set_recognizing(False)
            self._gui.show_result(content)
            self._log(f"[结果] {content}")

        elif event == EVENT_FACE_ENROLL_PROGRESS:
            # 录入进度: {stage: str, detail: str}
            stage = content.get("stage", "")
            detail = content.get("detail", "")
            self._gui.show_enroll_progress(stage, detail)
            self._log(f"[录入进度] {stage}: {detail}")

        elif event == EVENT_FACE_ENROLL_RESULT:
            # 录入结果: {success, msg, step, featurePath, cancelled}
            # 收到结果 → 状态机回 IDLE, 恢复按钮
            self._state = self.STATE_IDLE
            self._gui.set_recognizing(False)
            if content.get("success"):
                # 成功: 画面显示绿色对勾 + "录入成功", 1.5s 后自动退回
                print(f"[UiRsp] 录入成功, 显示成功反馈后自动退回: {content.get('featurePath')}")
                self._gui.show_enroll_success()
            else:
                # 失败/取消: 立即退回原窗口
                print(f"[UiRsp] 收到录入结果(非成功), 立即退回: success={content.get('success')} "
                      f"cancelled={content.get('cancelled')}")
                self._gui.hide_live_page()
            self._gui.show_enroll_result(content)
            self._log(f"[录入结果] {content}")

        elif event == EVENT_MODULE_STATUS:
            # 模块上线/下线: {moduleName: str, online: bool}
            module_name = content.get("moduleName", "?")
            online = content.get("online", False)
            self._gui.update_status(f"模块 {module_name} {'上线' if online else '下线'}")

        elif event == "BSOD_CHECK_RESULT":
            # 蓝屏检测结果: {found, event, report}
            self._gui.show_bsod_result(content)
            self._log(f"[蓝屏检测] {'发现蓝屏记录' if content.get('found') else '未发现蓝屏记录'}")

        elif event == "BSOD_AUTOSTART_RESULT":
            # 自启动操作结果: {enabled, ok}
            self._gui.show_bsod_autostart_result(content)

        elif event == "BSOD_AUTOSTART_STATUS_RESULT":
            # 自启动状态查询结果: {enabled}
            self._gui.show_bsod_autostart_result(content)

        elif event == "FREEZE_STATUS_RESULT":
            # 卡死监控状态: {running, ok}
            self._gui.show_freeze_status(content)

        elif event == "FREEZE_CONFIG_STATUS_RESULT":
            # 卡死检测配置: {config}
            self._gui.show_freeze_config(content)

        elif event == "FREEZE_ALERT":
            # 卡死报警: {type, msg, time, top_processes, info}
            self._gui.show_freeze_alert(content)
            self._log(f"[卡死报警] {content.get('msg', '')}")

        elif event == "WATERMARK_PROGRESS":
            # 去水印进度: {percent, info}
            self._gui.show_watermark_progress(content)

        elif event == "WATERMARK_RESULT":
            # 去水印结果: {success, msg, output_path, watermark_bbox, ...}
            self._gui.show_watermark_result(content)
            self._log(f"[去水印] {'完成' if content.get('success') else '失败'}: "
                      f"{content.get('msg', '')}")

        elif event == "WATERMARK_BUSY":
            # 去水印处理状态: {busy}
            self._gui.show_watermark_busy(content)

        else:
            # 未知事件: 记录但不崩溃
            self._log(f"[未处理事件] {event}: {content}")

    # ============================================================
    # 内部工具
    # ============================================================
    def _send(self, to_module, content, event) -> bool:
        """
        经中心调度发送事件(模块间不直接通信)
        :param to_module: 目标模块名<str>
        :param content: 事件内容<dict>
        :param event: 事件名<str>
        :return: 是否发送成功<bool>(未注册调度或目标不存在返回 False)
        """
        if self._scheduler is not None:
            return self._scheduler.communication_to(self, to_module, content, event)
        self._log(f"通信失败: 未注册到中心调度(事件 {event})")
        return False

    def _log(self, text):
        """
        输出日志: 优先追加到 GUI 日志区, 无 GUI 时打印控制台
        :param text: 日志文本<str>
        :return: None
        """
        if self._gui is not None:
            self._gui.append_log(text)
        else:
            print(f"[UiRsp] {text}")
