"""
coding:utf-8
file: UI/FaceModuleUI/UI.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:202608151015
lateCodedTime:20260815
"""

# PyQt6
# 该模块为人脸识别的UI模块(主窗口实现)
# ======================================
# 完全复刻 UI 最终效果图(深色科技风):
#   无边框窗口 + 自定义标题栏 + 左侧导航(8 项) + 右侧页面容器
# 页面: 安全概览 / 人脸识别(识别+录入同页) / 密码管理 / 蓝屏识别
#       / 卡死检测 / 安全中心 / 防护日志 / 设置
# 约束:
#   1. 窗口固定 1024x632(黄金分割), F11/标题栏按钮全屏(内部布局等比缩放), 禁止拖动改大小
#   2. 文字内容解耦合: 全部经 texts.get_text() 读取(string.xml 风格)
#   3. 样式解耦合: QSS 集中在 style/main.qss, 经 style.load_stylesheet() 加载
#   4. 代码结构遵循 UI_object.py: MainWindow 继承 GUI 基类, 交互经注入的 UiRsp
#
# 使用方式(由流程脚本装配, 本文件不含流程入口):
#   uiRsp = UiRsp()
#   win = MainWindow(uiRsp)
#   scheduler.register_module(uiRsp)
#   win.show()

import os
import sys

# 注入 UI 目录(本文件位于 <项目根>/UI/FaceModuleUI/)
_UI_DIR = os.path.dirname(os.path.abspath(__file__))
if _UI_DIR not in sys.path:
    sys.path.insert(0, _UI_DIR)
# 注入 CenterMoudle 目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_UI_DIR))
_CENTER_MOUDLE_DIR = os.path.join(_PROJECT_ROOT, 'CenterMoudle')
if _CENTER_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _CENTER_MOUDLE_DIR)

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QListWidget, QHBoxLayout, QVBoxLayout,
    QGridLayout, QFrame, QComboBox, QPushButton, QStackedWidget, QTabBar,
    QLineEdit, QAbstractButton, QToolTip,
)
from PyQt6.QtCore import Qt, pyqtProperty, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QKeySequence, QShortcut, QPainter, QColor, QCursor, QImage, QPixmap, QPen, QFont

import cv2  # 摄像头帧 BGR→RGB 转换

# 基类与资源
from UI_object import GUI
from texts import get_text
from style import load_stylesheet
from userInfo import get_current_user, get_current_user_name
import appConfig

# 窗口固定初始尺寸: 1024x632(黄金分割比 ≈ 0.617)
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 632

# 左侧导航固定宽度(像素)
NAV_WIDTH = 190

# 导航项: (文本空间名, 页面 id, 图标占位)
# 完全复刻设计图 8 个模块; 未实现功能的模块页面为静态视觉/占位
NAV_ITEMS = [
    ("nav.overview", "overview", "🛡"),
    ("nav.recognition", "recognition", "👤"),
    ("nav.password", "password", "🔒"),
    ("nav.bsod", "bsod", "🖥"),
    ("nav.freeze", "freeze", "⏳"),
    ("nav.security_center", "security_center", "🏠"),
    ("nav.protect_log", "protect_log", "📋"),
    ("nav.settings", "settings", "⚙"),
]


# ====================================================================
# SwitchButton: 滑动开关(Android Switch 风格)
# ====================================================================
class SwitchButton(QAbstractButton):
    """
    滑动开关(Android Switch 风格)
    =============================
    圆角轨道 + 可拖动的小圆球滑块, 点击切换并播放滑动动画。
    与 QCheckBox 接口兼容: isChecked() / setChecked() / toggled 信号。
    轨道颜色: 开启亮蓝 #3B82F6, 关闭深灰 #374151; 滑块白色。
    """

    TRACK_W = 46
    TRACK_H = 24
    MARGIN = 3          # 滑块与轨道边缘间距
    ANIM_MS = 120       # 滑动动画时长

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.TRACK_W, self.TRACK_H)
        # 滑块偏移量 0.0(左) ~ 1.0(右), 供动画驱动
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(self.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._sync_offset()

    # ── 滑块偏移属性(动画目标) ──
    def offset(self) -> float:
        return self._offset

    def set_offset(self, value: float):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, offset, set_offset)

    def _sync_offset(self):
        """按当前 checked 状态同步滑块位置(无动画)"""
        self._offset = 1.0 if self.isChecked() else 0.0
        self.update()

    def setChecked(self, checked):
        """覆写: 程序化设置状态时同步滑块位置(无动画)"""
        super().setChecked(checked)
        self._sync_offset()

    def nextCheckState(self):
        """覆写: 点击切换状态后播放滑动动画"""
        super().nextCheckState()   # 切换 checked 并发出 toggled
        target = 1.0 if self.isChecked() else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(target)
        self._anim.start()

    def paintEvent(self, event):
        # 防御: 非法尺寸时跳过绘制(避免 Qt 内部断言闪退)
        if self.width() < 10 or self.height() < 10:
            return
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 轨道(圆角矩形)
        track_color = QColor("#3B82F6") if self.isChecked() else QColor("#374151")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(0, 0, w, h, h / 2.0, h / 2.0)

        # 滑块(白色小圆球, 位置由偏移量驱动)
        diameter = h - 2 * self.MARGIN
        x = self.MARGIN + (w - 2 * self.MARGIN - diameter) * self._offset
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(int(x), self.MARGIN, diameter, diameter)


# ====================================================================
# GaugeWidget: 环形仪表盘(自绘: 圆环/弧线 + 中心文字)
# ====================================================================
class GaugeWidget(QWidget):
    """
    环形仪表盘(自绘)
    ================
    深灰背景环 + 绿色前景弧(角度可配) + 中心文字(标题/状态)。
    用于密码管理页(近整圆环)与卡死检测页(扇形弧线)。
    """

    def __init__(self, arc_start=135, arc_span=270, arc_color="#10B981",
                 track_color="#1F2937", parent=None):
        super().__init__(parent)
        self._arc_start = arc_start    # 起始角(度, 3 点钟方向顺时针)
        self._arc_span = arc_span      # 弧长(度)
        self._arc_color = QColor(arc_color)
        self._track_color = QColor(track_color)
        self.setMinimumSize(180, 180)

        # 中心文字(由外部设置, 叠加在圆环中央)
        self.center_title = QLabel(self)
        self.center_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_title.setObjectName("gaugeValue")
        self.center_value = QLabel(self)
        self.center_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_value.setObjectName("gaugeSub")

    def set_center(self, title, value):
        """设置中心文字: 上(大, 绿色) + 下(小, 灰色)"""
        self.center_title.setText(title)
        self.center_value.setText(value)
        self._recenter()

    def _recenter(self):
        """中心文字随控件尺寸居中(全屏缩放时保持)"""
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        self.center_title.setGeometry(cx - 80, cy - 42, 160, 36)
        self.center_value.setGeometry(cx - 80, cy - 2, 160, 24)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recenter()

    def showEvent(self, event):
        """首次显示时布局尺寸已定, 再居中文字(避免构造期 setGeometry 负值)"""
        super().showEvent(event)
        self._recenter()

    def paintEvent(self, event):
        # 防御: 页面切换/隐藏瞬间尺寸可能为 0 或极小,
        # 负宽高的 drawEllipse/drawArc 会触发 Qt 内部断言(0xC0000409 闪退)
        side = min(self.width(), self.height()) - 20
        if side <= 10:
            return
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # 注意: drawEllipse/drawArc 要求 int 参数, float 会抛 TypeError
        # (paintEvent 内异常穿越 C++ 事件边界会导致 0xC0000409 闪退)
        rect = (int((w - side) / 2.0), int((h - side) / 2.0), int(side), int(side))

        pen_width = max(10, side // 12)
        # 背景环
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._track_color)
        painter.drawEllipse(rect[0], rect[1], rect[2], rect[3])
        # 前景弧(绿色, 从 arc_start 起顺时针 arc_span 度)
        painter.setPen(QColor(self._arc_color))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Qt 角度: 0 在 3 点钟方向, 逆时针为正; 转换为 Qt 坐标系
        qt_start = int(((360 - self._arc_start - self._arc_span) % 360) * 16)
        painter.drawArc(rect[0] + pen_width // 2, rect[1] + pen_width // 2,
                        rect[2] - pen_width, rect[3] - pen_width,
                        qt_start, int(self._arc_span * 16))
        painter.setPen(QColor(self._arc_color))
        painter.setBrush(self._track_color)
        painter.drawEllipse(rect[0] + pen_width, rect[1] + pen_width,
                            rect[2] - 2 * pen_width, rect[3] - 2 * pen_width)


# ====================================================================
# TitleBar: 自定义标题栏(无边框窗口用)
# ====================================================================
class TitleBar(QFrame):
    """
    自定义标题栏(复刻设计图: 盾牌图标 + 标题 + 右侧窗口控制按钮)
    支持鼠标拖动窗口、双击切换全屏。
    """

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._drag_pos = None
        self.setObjectName("titleBar")
        self.setFixedHeight(46)

        # 左侧: 图标 + 标题
        icon_label = QLabel("🛡")
        icon_label.setObjectName("appIcon")
        title_label = QLabel(get_text("window.title"))
        title_label.setObjectName("appTitle")

        # 右侧: 窗口控制按钮
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("winBtn")
        self.btn_min.setToolTip(get_text("window.btn.min"))
        self.btn_min.clicked.connect(lambda: self._window.showMinimized())

        self.btn_fs = QPushButton("⛶")
        self.btn_fs.setObjectName("winBtn")
        self.btn_fs.setToolTip(get_text("window.btn.fullscreen"))
        self.btn_fs.clicked.connect(lambda: self._window.toggle_fullscreen())

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("winBtnClose")
        self.btn_close.setToolTip(get_text("window.btn.close"))
        self.btn_close.clicked.connect(self._window.close)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(8)
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_fs)
        layout.addWidget(self.btn_close)

    # ── 窗口拖动 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (event.globalPosition().toPoint()
                              - self._window.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        """双击标题栏切换全屏"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_fullscreen()


# ====================================================================
# UserAvatar: 用户头像(悬停显示用户信息, 点击进入账户页)
# ====================================================================
class UserAvatar(QFrame):
    """
    用户头像(圆形)
    ==============
    悬停: 在鼠标位置弹出 QToolTip 显示用户基本信息(用户名/ID/角色)
    点击: 发出 clicked 信号(主窗口据此切换进账户页)
    当前为默认人头占位(用户系统尚未实现)。
    """

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("userAvatar")
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTipDuration(0)   # 由 enterEvent/leaveEvent 手动控制

        # 默认人头占位(后续替换为真实头像图片)
        self.icon_label = QLabel("👤", self)
        self.icon_label.setObjectName("userAvatarIcon")
        self.icon_label.setGeometry(4, 4, 32, 32)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # ── 悬停提示: 用户基本信息(数据源: userInfo 当前用户) ──
    def _user_info_html(self) -> str:
        """构造用户信息富文本(悬停显示)"""
        user = get_current_user()
        return (f"<b>{get_text('user.tooltip_title')}</b><br/>"
                f"{user['userName']}<br/>"
                f"ID: {user['userId']}<br/>"
                f"{user['role']}")

    def enterEvent(self, event):
        """鼠标进入: 在光标位置显示用户信息"""
        QToolTip.showText(QCursor.pos(), self._user_info_html(), self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开: 隐藏提示"""
        QToolTip.hideText()
        super().leaveEvent(event)

    # ── 点击: 进入账户页 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ====================================================================
# MainWindow: 主窗口(软件外壳)
# ====================================================================
class MainWindow(GUI):
    """
    主窗口(完全复刻 UI 最终效果图)
    ==============================
    无边框窗口: 自定义标题栏 + 左侧导航(8 项) + 右侧页面容器。
    尺寸固定 1024x632(黄金分割), F11/标题栏按钮全屏(内部布局自动等比缩放)。
    """

    def __init__(self, uiRsp):
        super().__init__(uiRsp)

        # 无边框(自定义标题栏) + 固定尺寸(不可拖动改大小)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowTitle(get_text("window.title"))

        # 应用全局样式(QSS 解耦合)
        self.setStyleSheet(load_stylesheet())

        # 搭建外壳布局(标题栏 + 导航 + 页面容器)
        self._build_layout()

        # 注册页面
        self._recognition_page = RecognitionPage(self)
        self.add_page(OverviewPage(self), "overview")
        self.add_page(self._recognition_page, "recognition")
        self.add_page(PasswordPage(self), "password")
        self.add_page(BsodPage(self), "bsod")
        self.add_page(FreezePage(self), "freeze")
        # 账户页(从头像点击进入, 不加入左侧导航)
        self.add_page(AccountPage(self), "account")
        # 全屏摄像头画面页(录入/识别进行时显示, 不加入左侧导航)
        self._live_page = LivePage(self)
        self.add_page(self._live_page, "live")
        # 摄像头帧信号 → 全屏画面页(跨线程自动切主线程)
        self.frame_received.connect(self._live_page.set_frame)
        for _, page_id, _ in NAV_ITEMS:
            if page_id not in self._pages:
                self.add_page(PlaceholderPage(page_id), page_id)

        # 导航联动 + 默认进入安全概览(设计图主页)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        self.switch_page("overview")

        # F11 切换全屏
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

    # ============================================================
    # 外壳布局
    # ============================================================
    def _build_layout(self):
        """搭建: 自定义标题栏 + 主体(左导航 + 右页面容器)"""
        # ── 标题栏 ──
        self._title_bar = TitleBar(self)

        # ── 左侧导航栏(8 项, emoji 图标占位) ──
        self._nav = QListWidget()
        self._nav.setObjectName("navList")
        self._nav.setFixedWidth(NAV_WIDTH)
        self._nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for text_key, _, icon in NAV_ITEMS:
            self._nav.addItem(f"{icon}  {get_text(text_key)}")

        # ── 主体: 导航 + 页面容器(基类的 _stack) ──
        body = QWidget()
        body.setObjectName("appBody")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._nav)
        body_layout.addWidget(self._stack, 1)   # 右侧内容区伸展(全屏时自动放大)

        # ── 总装 ──
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._title_bar)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

    # ============================================================
    # 页面切换(覆写): 沉浸式页面(账户页/全屏画面页)隐藏标题栏+导航, 其他页恢复外壳
    # ============================================================
    def switch_page(self, page_id, animate=False):
        """
        切换页面; 账户页/全屏画面页为沉浸式: 隐藏标题栏与左侧导航, 内容铺满窗口
        :param page_id: 页面 id<str>
        :param animate: 是否动画(预留)
        :return: None
        """
        super().switch_page(page_id, animate)
        is_immersive = page_id in ("account", "live")
        self._title_bar.setVisible(not is_immersive)
        self._nav.setVisible(not is_immersive)

    # ============================================================
    # 全屏画面页控制(覆写 GUI 基类钩子, 由 UiRsp 调用)
    # ============================================================
    def show_live_page(self):
        """进入全屏摄像头画面页: 重置画面页状态 → 记录来源页 → 切换 → 强制全屏"""
        self._live_page.reset()
        current = self._stack.currentWidget()
        self._live_from_page = next(
            (pid for pid, w in self._pages.items() if w is current), "recognition")
        self.switch_page("live")
        self.showFullScreen()

    def hide_live_page(self):
        """退出全屏画面页: 恢复窗口并回到来源页"""
        self.showNormal()
        back_to = getattr(self, "_live_from_page", "recognition")
        self.switch_page(back_to)
        print(f"[MainWindow] 已退出全屏画面页, 回到: {back_to}")

    def show_enroll_success(self):
        """录入成功反馈: 画面显示绿色对勾 + "录入成功", 1.5 秒后自动退回原窗口"""
        self._live_page.show_success(get_text("live.prompt.success"))
        QTimer.singleShot(1500, self.hide_live_page)

    # ============================================================
    # 导航联动
    # ============================================================
    def _on_nav_changed(self, row):
        """导航行变化 → 切换页面"""
        if 0 <= row < len(NAV_ITEMS):
            self.switch_page(NAV_ITEMS[row][1])

    def set_nav_selected(self, page_id):
        """按页面 id 高亮导航项(供外部程序化切换时同步)"""
        for row, (_, pid, _) in enumerate(NAV_ITEMS):
            if pid == page_id:
                self._nav.setCurrentRow(row)
                break

    # ============================================================
    # 全屏控制
    # ============================================================
    def toggle_fullscreen(self):
        """
        切换全屏/窗口态(F11 或标题栏按钮或双击标题栏)
        全屏时布局管理器自动等比拉伸内部空间; 退出恢复固定尺寸
        """
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()


# ====================================================================
# 页面通用工具
# ====================================================================
def make_page_header(title_key):
    """构造页面顶部: ← 返回占位 + 页面标题"""
    head = QHBoxLayout()
    head.setContentsMargins(24, 16, 24, 0)
    back_label = QLabel("←")            # 返回箭头占位(后续接页面回退)
    back_label.setObjectName("settingLabel")
    page_title = QLabel(get_text(title_key))
    page_title.setObjectName("pageTitle")
    head.addWidget(back_label)
    head.addSpacing(8)
    head.addWidget(page_title)
    head.addStretch(1)
    return head


def make_card(object_name=None):
    """构造通用卡片容器"""
    card = QFrame()
    card.setObjectName(object_name if object_name else "card")
    return card


# ====================================================================
# 安全概览页
# ====================================================================
class OverviewPage(QWidget):
    """安全概览(设计图主页): 评分卡 + 功能状态网格 + 底部统计条(静态数据占位)"""

    def __init__(self, gui):
        super().__init__()
        self._gui = gui
        self.setObjectName("overviewPage")

        # ── 顶部标题 ──
        head = QHBoxLayout()
        head.setContentsMargins(24, 18, 24, 0)
        title_box = QVBoxLayout()
        title = QLabel(get_text("overview.title"))
        title.setObjectName("pageTitle")
        subtitle = QLabel(get_text("overview.subtitle"))
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        head.addLayout(title_box)
        head.addStretch(1)

        # ── 右上角用户头像(悬停显示用户信息, 点击进入账户页) ──
        self.avatar = UserAvatar()
        self.avatar.clicked.connect(lambda: self._gui.switch_page("account"))
        head.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        # ── 主体: 左评分卡 + 右功能网格 ──
        body = QHBoxLayout()
        body.setContentsMargins(24, 16, 24, 12)
        body.setSpacing(16)
        body.addWidget(self._build_score_card(), 3)
        body.addWidget(self._build_grid_card(), 4)

        # ── 底部统计条 ──
        stat_bar = self._build_stat_bar()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(head)
        layout.addLayout(body, 1)
        stat_row = QHBoxLayout()
        stat_row.setContentsMargins(24, 0, 24, 18)
        stat_row.addWidget(stat_bar)
        layout.addLayout(stat_row)

    # ── 左侧评分卡 ──
    def _build_score_card(self) -> QFrame:
        card = make_card("scoreCard")
        icon = QLabel("🛡")
        icon.setObjectName("scoreIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score = QLabel("100")
        score.setObjectName("scoreValue")
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(get_text("overview.score"))
        label.setObjectName("scoreLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        last_scan = QLabel(get_text("overview.last_scan", get_text("overview.scan_time")))
        last_scan.setObjectName("cardText")
        last_scan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scan_btn = QPushButton(get_text("overview.btn.scan"))
        self.scan_btn.setObjectName("blueBtn")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.addWidget(icon)
        layout.addSpacing(4)
        layout.addWidget(score)
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(last_scan)
        layout.addSpacing(10)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.scan_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        return card

    # ── 右侧功能状态网格(2x3) ──
    def _build_grid_card(self) -> QWidget:
        # 网格项: (图标, 文本 key)
        grid_items = [
            ("👤", "overview.grid.login"),
            ("🔒", "overview.grid.password"),
            ("🖥", "overview.grid.bsod"),
            ("⏳", "overview.grid.freeze"),
            ("🛡", "overview.grid.real_time"),
            ("🔄", "overview.grid.auto_update"),
        ]
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for i, (icon, text_key) in enumerate(grid_items):
            grid.addWidget(self._make_grid_item(icon, text_key), i // 3, i % 3)
        return container

    def _make_grid_item(self, icon, text_key) -> QFrame:
        card = make_card("gridCard")
        icon_label = QLabel(icon)
        icon_label.setObjectName("gridIcon")
        title = QLabel(get_text(text_key))
        title.setObjectName("gridTitle")
        dot = QLabel("")
        dot.setObjectName("dotOn")
        status = QLabel(get_text("overview.status.enabled"))
        status.setObjectName("gridStatus")

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_row.addWidget(dot)
        status_row.addWidget(status)
        status_row.addStretch(1)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(icon_label)
        layout.addSpacing(6)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addLayout(status_row)
        return card

    # ── 底部统计条(4 项) ──
    def _build_stat_bar(self) -> QFrame:
        bar = make_card("statBar")
        stats = [
            ("🛡", "overview.stat.today_value", "overview.stat.today"),
            ("🚫", "overview.stat.blocked_value", "overview.stat.blocked"),
            ("✨", "overview.stat.optimized_value", "overview.stat.optimized"),
            ("📅", "overview.stat.days_value", "overview.stat.days"),
        ]
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)
        for i, (icon, value_key, label_key) in enumerate(stats):
            item = QWidget()
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(10)
            icon_label = QLabel(icon)
            icon_label.setObjectName("statIcon")
            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            value = QLabel(get_text(value_key))
            value.setObjectName("statValue")
            label = QLabel(get_text(label_key))
            label.setObjectName("statLabel")
            text_box.addWidget(value)
            text_box.addWidget(label)
            item_layout.addWidget(icon_label)
            item_layout.addLayout(text_box)
            item_layout.addStretch(1)
            layout.addWidget(item)
            if i < len(stats) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.VLine)
                line.setStyleSheet("color: #1E293B;")
                layout.addWidget(line)
        return bar


# ====================================================================
# 人脸识别页(识别 + 录入同页, 标签切换)
# ====================================================================
class RecognitionPage(QWidget):
    """人脸识别页: 顶部标题 + 标签栏[人脸识别|人脸录入] + 内容区(识别子页/录入子页)"""

    def __init__(self, gui):
        super().__init__()
        self._gui = gui
        self.setObjectName("recognitionPage")

        # ── 标签栏 ──
        self._tab_bar = QTabBar()
        self._tab_bar.setObjectName("pageTab")
        self._tab_bar.setExpanding(False)
        self._tab_bar.addTab(get_text("recognition.tab.recognize"))
        self._tab_bar.addTab(get_text("recognition.tab.enroll"))

        # ── 内容区 ──
        self._tab_stack = QStackedWidget()
        self._recognize_sub = RecognitionSubPage(gui)
        self._enroll_sub = EnrollSubPage(gui)
        self._tab_stack.addWidget(self._recognize_sub)
        self._tab_stack.addWidget(self._enroll_sub)
        self._tab_bar.currentChanged.connect(self._tab_stack.setCurrentIndex)
        # 识别子页"重新录人脸" → 切换到录入标签页并提示覆盖当前用户特征
        self._recognize_sub.reenroll_requested.connect(self._on_reenroll_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(make_page_header("recognition.page_title"))
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(24, 8, 24, 0)
        tab_row.addWidget(self._tab_bar)
        tab_row.addStretch(1)
        layout.addLayout(tab_row)
        layout.addWidget(self._tab_stack, 1)

        self._tab_bar.setCurrentIndex(0)

    def _on_reenroll_requested(self):
        """[重新录人脸]: 切到录入标签页并提示将覆盖当前用户特征"""
        self._tab_bar.setCurrentIndex(1)
        self._enroll_sub.notify_reenroll()


class RecognitionSubPage(QWidget):
    """识别子页: 左画面区 + 右设置卡(项目实际功能)"""

    # [重新录人脸] 按钮点击信号(RecognitionPage 连接后切换到录入标签页)
    reenroll_requested = pyqtSignal()

    def __init__(self, gui):
        super().__init__()
        self._gui = gui

        body = QHBoxLayout(self)
        body.setContentsMargins(24, 16, 24, 24)
        body.setSpacing(20)
        body.addWidget(self._build_preview_area(), 2)   # 左: 画面区(占 2/5)
        body.addWidget(self._build_settings_card(), 3)  # 右: 设置卡(占 3/5)

        # 连接主窗口信号(识别流程状态联动)
        gui.recognize_state_changed.connect(self._on_recognizing)
        gui.progress_received.connect(self._on_progress)
        gui.result_received.connect(self._on_result)

    # ── 左侧画面区 ──
    def _build_preview_area(self) -> QFrame:
        area = QFrame()
        area.setObjectName("previewArea")
        corners = []
        for corner_id in ("cornerTL", "cornerTR", "cornerBL", "cornerBR"):
            corner = QFrame()
            corner.setObjectName(corner_id)
            corner.setFixedSize(24, 24)
            corners.append(corner)

        # 中央展示: 静态预览图(不接真实摄像头画面), 随布局等比缩放
        self.preview_placeholder = QLabel()
        self.preview_placeholder.setObjectName("previewPlaceholder")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_pixmap = self._load_preview_pixmap()

        self.preview_status = QLabel(f"✓ {get_text('recognition.status.success')}")
        self.preview_status.setObjectName("previewStatus")
        self.preview_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid = QGridLayout(area)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(0)
        grid.addWidget(corners[0], 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(corners[1], 0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        grid.addWidget(corners[2], 2, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(corners[3], 2, 2, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.preview_placeholder, 1, 1)
        grid.addWidget(self.preview_status, 3, 0, 1, 3)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(1, 1)
        return area

    def _load_preview_pixmap(self):
        """
        加载画面区静态预览图(resources/face_preview.png)
        文件缺失时回退为占位文字
        :return: QPixmap 或 None
        """
        image_path = os.path.join(_UI_DIR, 'resources', 'face_preview.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                return pixmap
        # 兜底: 无图时显示占位文字
        self.preview_placeholder.setText(get_text("recognition.preview_placeholder"))
        return None

    def _update_preview_pixmap(self):
        """按画面区当前尺寸等比缩放预览图"""
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        label = self.preview_placeholder
        if label.width() < 10 or label.height() < 10:
            return
        self.preview_placeholder.setPixmap(self._preview_pixmap.scaled(
            label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        """布局尺寸变化 → 预览图等比缩放跟随"""
        super().resizeEvent(event)
        self._update_preview_pixmap()

    def showEvent(self, event):
        """首次显示时更新预览图(布局尺寸已确定)"""
        super().showEvent(event)
        self._update_preview_pixmap()

    # ── 右侧设置卡 ──
    def _build_settings_card(self) -> QFrame:
        card = make_card("settingsCard")
        title = QLabel(get_text("recognition.settings_title"))
        title.setObjectName("settingsTitle")

        # 开关/阈值与全局配置(appConfig)双向联动: 控件加载配置, 变更写回配置
        self.switch_login = SwitchButton()
        self.switch_login.setChecked(appConfig.is_face_login_enabled())
        self.switch_login.toggled.connect(appConfig.set_face_login_enabled)
        self.switch_liveness = SwitchButton()
        self.switch_liveness.setChecked(appConfig.is_liveness_enabled())
        self.switch_liveness.toggled.connect(appConfig.set_liveness_enabled)

        threshold_label = QLabel(get_text("recognition.threshold"))
        threshold_label.setObjectName("settingLabel")
        self.threshold_combo = QComboBox()
        self.threshold_combo.addItems([
            get_text("recognition.threshold.strict"),
            get_text("recognition.threshold.normal"),
            get_text("recognition.threshold.loose"),
        ])
        # 按配置档位恢复下拉选择(strict/normal/loose ↔ 0/1/2)
        level_order = ("strict", "normal", "loose")
        try:
            self.threshold_combo.setCurrentIndex(
                level_order.index(appConfig.get_threshold_level()))
        except ValueError:
            self.threshold_combo.setCurrentIndex(0)
        self.threshold_combo.currentIndexChanged.connect(
            lambda idx: appConfig.set_threshold_level(level_order[idx]))

        self.reenroll_btn = QPushButton(get_text("recognition.btn.reenroll"))
        self.reenroll_btn.setObjectName("primaryBtn")
        self.reenroll_btn.clicked.connect(self._on_reenroll_click)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addLayout(self._make_switch_row(
            "recognition.switch.login", self.switch_login))
        layout.addLayout(self._make_switch_row(
            "recognition.switch.liveness", self.switch_liveness))
        layout.addSpacing(6)
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(threshold_label)
        threshold_row.addStretch(1)
        threshold_row.addWidget(self.threshold_combo)
        layout.addLayout(threshold_row)
        layout.addStretch(1)
        layout.addWidget(self.reenroll_btn)
        return card

    def _make_switch_row(self, label_key, switch) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(get_text(label_key))
        label.setObjectName("settingLabel")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(switch)
        return row

    def _on_reenroll_click(self):
        """[重新录人脸] 点击 → 切换到录入标签页(提示将覆盖当前用户特征)"""
        # 录入页提示"将覆盖当前用户特征"(由 RecognitionPage 切换标签后触发)
        self.reenroll_requested.emit()

    # ── 识别状态联动 ──
    def _on_recognizing(self, active):
        if active:
            self.preview_status.setText(get_text("recognition.status.progress", "silent"))
        else:
            self.preview_status.setText(f"✓ {get_text('recognition.status.success')}")

    def _on_progress(self, stage, detail):
        self.preview_status.setText(get_text("recognition.status.progress", stage))

    def _on_result(self, result_data):
        if result_data.get("matched"):
            sim = result_data.get("similarity", 0.0)
            self.preview_status.setText(f"✓ {get_text('recognition.status.success')} ({sim:.2f})")
        else:
            self.preview_status.setText(str(result_data.get("msg", "")))


class EnrollSubPage(QWidget):
    """
    录入子页(与识别同页)
    ====================
    用户名与账户绑定: 直接使用当前用户(userInfo 数据源, 预设 admin),
    无需手动输入; 未来用户系统实现后随数据源自动切换。
    业务链路: 按钮 → UiRsp.on_start_enroll(当前用户名) → 中心调度
              → FaceService → faceEnroll.runEnroll
              → 进度/结果事件 → 中心调度(主线程) → UiRsp → gui 信号 → 本页状态显示
    """

    def __init__(self, gui):
        super().__init__()
        self._gui = gui
        self._rsp = gui.get_rsp()   # 响应层(经 GUI 基类获取, 页面不直接碰调度器)

        hint = QLabel(get_text("enroll.hint"))
        hint.setObjectName("settingLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 当前用户显示(与账户页/头像同一数据源) + 特征状态
        self.current_user_label = QLabel()
        self.current_user_label.setObjectName("cardValue")
        self.current_user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_user_status()

        # 录入状态显示(进度/结果)
        self.status_label = QLabel(get_text("enroll.status.idle"))
        self.status_label.setObjectName("settingValue")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 开始录入按钮(以当前用户发起, 经 UiRsp 与中介调度)
        self.start_enroll_btn = QPushButton(get_text("enroll.btn.start"))
        self.start_enroll_btn.setObjectName("primaryBtn")
        self.start_enroll_btn.setFixedWidth(200)
        self.start_enroll_btn.clicked.connect(self._on_start_enroll_click)

        layout = QVBoxLayout(self)
        layout.addStretch(2)
        layout.addWidget(hint)
        layout.addSpacing(12)
        layout.addWidget(self.current_user_label)
        layout.addSpacing(8)
        layout.addWidget(self.status_label)
        layout.addSpacing(16)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.start_enroll_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(3)

        # 连接主窗口录入信号(进度/结果 → 状态显示)
        gui.enroll_progress_received.connect(self._on_enroll_progress)
        gui.enroll_result_received.connect(self._on_enroll_result)

    # ============================================================
    # 交互
    # ============================================================
    def _update_user_status(self):
        """显示当前用户 + 特征状态(已有特征/尚未录入)"""
        user_name = get_current_user_name()
        if self._rsp is not None:
            has_feature, feature_name = self._rsp.check_current_feature(user_name)
            if has_feature:
                text = (f"{get_text('user.current', user_name)}\n"
                        f"{get_text('enroll.feature.have', feature_name)}")
            else:
                text = (f"{get_text('user.current', user_name)}\n"
                        f"{get_text('enroll.feature.none')}")
        else:
            text = get_text("user.current", user_name)
        self.current_user_label.setText(text)

    def notify_reenroll(self):
        """[重新录人脸] 提示: 将覆盖当前用户特征"""
        self.status_label.setText(
            get_text("enroll.status.overwrite", get_current_user_name()))
        self._update_user_status()

    def _on_start_enroll_click(self):
        """[开始录入] → UiRsp.on_start_enroll(当前用户, 经中介调度发请求)"""
        if self._rsp is not None:
            ok = self._rsp.on_start_enroll(get_current_user_name())
            if not ok:
                # 发起失败(未连接业务模块/状态忙): 界面给出友好提示
                self.status_label.setText(get_text("enroll.status.not_connected"))
        else:
            self.status_label.setText(get_text("enroll.status.fail", "未绑定 UiRsp"))

    # ============================================================
    # 录入状态联动(连接主窗口信号, 主线程执行)
    # ============================================================
    def _on_enroll_progress(self, stage, detail):
        """录入进度 → 状态文字(阶段名经文本资源映射)"""
        stage_text = get_text(f"enroll.stage.{stage}", default=stage)
        self.status_label.setText(f"{stage_text}: {detail}" if detail else stage_text)

    def _on_enroll_result(self, result_data):
        """录入结果 → 状态文字(成功/失败/取消)"""
        if result_data.get("cancelled"):
            self.status_label.setText(get_text("enroll.status.cancelled"))
        elif result_data.get("success"):
            path = result_data.get("featurePath", "")
            self.status_label.setText(get_text("enroll.status.success", path))
        else:
            self.status_label.setText(
                get_text("enroll.status.fail", result_data.get("msg", "录入失败")))


# ====================================================================
# 密码管理页
# ====================================================================
class PasswordPage(QWidget):
    """密码管理(复刻设计图): 左环形强度图 + 右密码强度检查"""

    def __init__(self, gui):
        super().__init__()
        self.setObjectName("passwordPage")

        body = QHBoxLayout()
        body.setContentsMargins(24, 16, 24, 24)
        body.setSpacing(20)
        body.addWidget(self._build_gauge_card(), 4)
        body.addWidget(self._build_check_card(), 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(make_page_header("password.title"))
        layout.addLayout(body, 1)

    def _build_gauge_card(self) -> QFrame:
        card = make_card("gaugeCard")
        self.gauge = GaugeWidget(arc_start=90, arc_span=300)
        self.gauge.set_center(get_text("password.strength"),
                              f"{get_text('password.percent')}  {get_text('password.range')}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(self.gauge)
        return card

    def _build_check_card(self) -> QFrame:
        card = make_card("checkCard")
        title = QLabel(get_text("password.check_title"))
        title.setObjectName("cardTitle")

        self.password_input = QLineEdit()
        self.password_input.setObjectName("passwordInput")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(get_text("password.input_placeholder"))

        checks = [get_text("password.check.len"), get_text("password.check.upper"),
                  get_text("password.check.digit"), get_text("password.check.special")]
        check_items = []
        for text in checks:
            item = QFrame()
            item.setObjectName("checkItem")
            mark = QLabel("✓")
            mark.setObjectName("checkMark")
            label = QLabel(text)
            label.setObjectName("checkText")
            row = QHBoxLayout(item)
            row.setContentsMargins(12, 8, 12, 8)
            row.addWidget(mark)
            row.addSpacing(8)
            row.addWidget(label)
            row.addStretch(1)
            check_items.append(item)

        self.update_btn = QPushButton(get_text("password.btn.update"))
        self.update_btn.setObjectName("primaryBtn")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(self.password_input)
        layout.addSpacing(12)
        for item in check_items:
            layout.addWidget(item)
        layout.addStretch(1)
        layout.addWidget(self.update_btn)
        return card


# ====================================================================
# 蓝屏识别页
# ====================================================================
class BsodPage(QWidget):
    """蓝屏识别(复刻设计图): 左模拟蓝屏 + 右智能防护"""

    def __init__(self, gui):
        super().__init__()
        self.setObjectName("bsodPage")

        body = QHBoxLayout()
        body.setContentsMargins(24, 16, 24, 24)
        body.setSpacing(20)
        body.addWidget(self._build_bsod_sim(), 4)
        body.addWidget(self._build_protect_card(), 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(make_page_header("bsod.title"))
        layout.addLayout(body, 1)

    def _build_bsod_sim(self) -> QFrame:
        sim = QFrame()
        sim.setObjectName("bsodSim")
        face = QLabel(":(")
        face.setObjectName("bsodFace")
        face.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(get_text("bsod.sim_title"))
        title.setObjectName("bsodTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(get_text("bsod.sim_text"))
        text.setObjectName("bsodText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)
        progress = QLabel(get_text("bsod.sim_progress"))
        progress.setObjectName("bsodProgress")
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(sim)
        layout.setContentsMargins(30, 40, 30, 40)
        layout.addStretch(1)
        layout.addWidget(face)
        layout.addSpacing(20)
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(text)
        layout.addSpacing(24)
        layout.addWidget(progress)
        layout.addStretch(1)
        return sim

    def _build_protect_card(self) -> QFrame:
        card = make_card("settingsCard")
        title = QLabel(get_text("bsod.protect_title"))
        title.setObjectName("settingsTitle")

        self.switch_repair = SwitchButton()
        self.switch_repair.setChecked(True)
        self.switch_report = SwitchButton()
        self.switch_report.setChecked(True)
        self.switch_backup = SwitchButton()
        self.switch_backup.setChecked(True)

        self.repair_btn = QPushButton(get_text("bsod.btn.repair"))
        self.repair_btn.setObjectName("primaryBtn")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addLayout(self._switch_row("bsod.switch.auto_repair", self.switch_repair))
        layout.addLayout(self._switch_row("bsod.switch.report", self.switch_report))
        layout.addLayout(self._switch_row("bsod.switch.backup", self.switch_backup))
        layout.addStretch(1)
        layout.addWidget(self.repair_btn)
        return card

    def _switch_row(self, label_key, switch) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(get_text(label_key))
        label.setObjectName("settingLabel")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(switch)
        return row


# ====================================================================
# 卡死检测页
# ====================================================================
class FreezePage(QWidget):
    """卡死检测(复刻设计图): 左环形仪表盘 + 右检测设置"""

    def __init__(self, gui):
        super().__init__()
        self.setObjectName("freezePage")

        body = QHBoxLayout()
        body.setContentsMargins(24, 16, 24, 24)
        body.setSpacing(20)
        body.addWidget(self._build_gauge_card(), 4)
        body.addWidget(self._build_settings_card(), 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(make_page_header("freeze.title"))
        layout.addLayout(body, 1)

    def _build_gauge_card(self) -> QFrame:
        card = make_card("gaugeCard")
        self.gauge = GaugeWidget(arc_start=135, arc_span=270)
        self.gauge.set_center(get_text("freeze.gauge_title"),
                              get_text("freeze.gauge_status"))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(self.gauge)
        return card

    def _build_settings_card(self) -> QFrame:
        card = make_card("settingsCard")
        title = QLabel(get_text("freeze.settings_title"))
        title.setObjectName("settingsTitle")

        # 四个下拉行: (标签 key, 选项 keys)
        rows = [
            ("freeze.interval", ["freeze.interval_30s", "freeze.interval_60s", "freeze.interval_120s"]),
            ("freeze.cpu", ["freeze.percent_90", "freeze.percent_80", "freeze.percent_70"]),
            ("freeze.mem", ["freeze.percent_90", "freeze.percent_80", "freeze.percent_70"]),
            ("freeze.timeout", ["freeze.timeout_10s", "freeze.timeout_20s", "freeze.timeout_30s"]),
        ]
        self.combos = []
        self.auto_kill = SwitchButton()
        self.auto_kill.setChecked(True)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addSpacing(6)
        for label_key, option_keys in rows:
            row = QHBoxLayout()
            label = QLabel(get_text(label_key))
            label.setObjectName("settingLabel")
            combo = QComboBox()
            combo.addItems([get_text(k) for k in option_keys])
            combo.setCurrentIndex(0)
            self.combos.append(combo)
            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(combo)
            layout.addLayout(row)
        layout.addSpacing(6)
        auto_row = QHBoxLayout()
        auto_label = QLabel(get_text("freeze.auto_kill"))
        auto_label.setObjectName("settingLabel")
        auto_row.addWidget(auto_label)
        auto_row.addStretch(1)
        auto_row.addWidget(self.auto_kill)
        layout.addLayout(auto_row)
        layout.addStretch(1)
        return card


# ====================================================================
# LoadingOverlay: 半透明遮罩 + 旋转加载圆圈
# ====================================================================
class LoadingOverlay(QWidget):
    """
    加载遮罩(自绘)
    ==============
    覆盖整个父控件: 灰色半透明背景 + 中央旋转加载圆圈(QTimer 驱动) + 说明文字。
    用于"正在加载中..."(摄像头未接入) 与 "正在处理中，请稍等"(拍照完成后的处理阶段)。
    """

    SPINNER_SIZE = 56      # 圆圈直径
    SPINNER_WIDTH = 5      # 圆弧线宽
    ROTATE_STEP = 12       # 每 tick 旋转角度
    TICK_MS = 30           # 旋转刷新间隔

    def __init__(self, parent):
        super().__init__(parent)
        self._angle = 0
        self._text = ""
        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._rotate)
        # 默认隐藏(由 show_overlay 显示)
        self.hide()

    # ============================================================
    # 对外接口
    # ============================================================
    def show_overlay(self, text=None):
        """
        显示遮罩(旋转圆圈开始转动)
        :param text: 说明文字<str>, 如 "正在加载中..."
        """
        if text is not None:
            self._text = text
        # 同步几何到父控件(不在布局中, 必须手动跟随父尺寸)
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())
        self.setVisible(True)
        self.raise_()                 # 置于顶层(退出按钮会在其上层单独 raise)
        self._timer.start()

    def hide_overlay(self):
        """隐藏遮罩(停止旋转, 节省资源)"""
        self._timer.stop()
        self.setVisible(False)

    def set_text(self, text):
        """更新说明文字"""
        self._text = text
        self.update()

    def _rotate(self):
        self._angle = (self._angle + self.ROTATE_STEP) % 360
        self.update()

    # ============================================================
    # 尺寸跟随父控件(全屏缩放时自动覆盖)
    # ============================================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())

    # ============================================================
    # 绘制: 半透明背景 + 旋转弧 + 文字
    # ============================================================
    def paintEvent(self, event):
        # 防御: 非法尺寸跳过(避免 Qt 断言)
        if self.width() < 10 or self.height() < 10:
            return
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 灰色半透明遮罩
        painter.fillRect(self.rect(), QColor(15, 23, 42, 160))

        # 中央旋转圆圈
        cx = self.width() / 2.0
        cy = self.height() / 2.0 - 20
        r = self.SPINNER_SIZE / 2.0
        rect = QRectF(cx - r, cy - r, self.SPINNER_SIZE, self.SPINNER_SIZE)

        # 背景环(暗色)
        pen = QPen(QColor(60, 75, 100, 180), self.SPINNER_WIDTH)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        # 前景旋转弧(亮蓝, 120° 弧段, 圆头)
        pen = QPen(QColor("#3B82F6"), self.SPINNER_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        start_angle = int((self._angle - 60) % 360) * 16
        painter.drawArc(rect, start_angle, 120 * 16)

        # 说明文字(圆圈下方)
        if self._text:
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            text_rect = QRectF(0, cy + r + 14, self.width(), 32)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._text)


# ====================================================================
# SuccessOverlay: 整屏变色覆盖层(录入成功: 绿色 + 白色大对勾 + 文字)
# ====================================================================
class SuccessOverlay(QWidget):
    """
    成功覆盖层(自绘)
    ================
    全屏绿色背景 + 中央白色大对勾 + 说明文字。
    用于"录入成功"反馈(屏幕变色机制的基础, 后期可扩展红/蓝等结果反馈)。
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._bg_color = QColor("#10B981")   # 成功绿
        self.hide()

        # 中央: 大对勾 + 文字(布局自动居中)
        self._check_label = QLabel("✓")
        self._check_label.setObjectName("successCheck")
        self._check_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label = QLabel("")
        self._text_label.setObjectName("successText")
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(2)
        layout.addWidget(self._check_label)
        layout.addWidget(self._text_label)
        layout.addStretch(3)

    # ============================================================
    def show_success(self, text=""):
        """显示成功覆盖层(整屏变色 + 对勾 + 文字)"""
        self._text_label.setText(text)
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())
        self.setVisible(True)
        self.raise_()

    def set_bg_color(self, color):
        """设置整屏变色颜色(预留: 红/蓝等结果反馈)"""
        self._bg_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        if self.width() < 10 or self.height() < 10:
            return
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.fillRect(self.rect(), self._bg_color)


# ====================================================================
# LivePage: 全屏摄像头画面页(录入/识别进行时)
# ====================================================================
class LivePage(QWidget):
    """
    全屏摄像头画面页
    ================
    - 中央: 摄像头实时画面(QLabel 等比缩放显示, 黑底)
    - 左上角: [退出识别] 按钮(点击 → UiRsp.on_cancel_enroll 终止流程)
    - 画面下方: 提示词(请不要动 / 请眨眼 / 请张嘴 ...)
    帧与提示词经 GUI.frame_received 信号(跨线程自动切主线程)更新。
    帧显示节流(~15fps): 避免高帧率 scaled 大图淹没主线程导致界面卡死。
    """

    # 帧显示最小间隔(秒): 约 15fps
    FRAME_INTERVAL = 1.0 / 15.0

    def __init__(self, gui):
        super().__init__()
        self._gui = gui
        self._last_frame_time = 0.0
        self._last_prompt = ""
        self._frame_started = False   # 是否已收到首帧(摄像头已接入)
        self.setObjectName("livePage")

        # ── 中央摄像头画面 ──
        self.video_label = QLabel()
        self.video_label.setObjectName("videoLabel")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000000;")

        # ── 画面下方提示词 ──
        self.prompt_label = QLabel(get_text("live.prompt.ready"))
        self.prompt_label.setObjectName("livePrompt")
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── 左上角退出按钮(纳入布局 + 固定尺寸, 防止被拉伸) ──
        self.exit_btn = QPushButton(get_text("live.btn.exit"))
        self.exit_btn.setObjectName("liveExitBtn")
        self.exit_btn.setFixedSize(110, 38)
        self.exit_btn.clicked.connect(self._on_exit_click)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(12, 12, 12, 0)
        top_row.addWidget(self.exit_btn, 0, Qt.AlignmentFlag.AlignLeft)
        top_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top_row)
        layout.addWidget(self.video_label, 1)
        layout.addWidget(self.prompt_label)

        # ── 加载遮罩(摄像头未接入 / 处理中): 覆盖全页, 退出按钮保持可点 ──
        self._overlay = LoadingOverlay(self)
        self._overlay.show_overlay(get_text("live.prompt.loading"))
        # ── 成功覆盖层(录入成功: 整屏绿色 + 对勾) ──
        self._success_overlay = SuccessOverlay(self)
        self.exit_btn.raise_()   # 遮罩之上, 加载/处理中/成功时仍可退出

        # 录入进度联动: 处理阶段(拍照完成, 摄像头已关闭)显示"正在处理中"遮罩
        gui.enroll_progress_received.connect(self._on_enroll_progress)

    # ============================================================
    # 成功反馈(录入成功 → 整屏绿色 + 对勾; 由 MainWindow 定时退回)
    # ============================================================
    def show_success(self, text=""):
        """显示成功覆盖层(整屏变色 + 白色对勾 + 文字)"""
        self._overlay.hide_overlay()
        self._success_overlay.show_success(text)
        self.exit_btn.raise_()

    def set_screen_color(self, color):
        """预留: 整屏变色接口(红/蓝/绿等结果反馈, 后期联动识别结果)"""
        self._success_overlay.set_bg_color(color)
        self._success_overlay.show_success(self._success_overlay._text_label.text())

    def _on_enroll_progress(self, stage, detail):
        """
        录入进度 → 遮罩状态切换
        - liveness: 模型加载/开摄像头中 → "正在加载中..."遮罩
        - clean/extract: 拍照完成, 摄像头已关闭 → "正在处理中"遮罩
        - 其他(silent/action/frontal/capture): 摄像头画面可用 → 隐藏遮罩
        """
        if stage == "liveness":
            self._overlay.show_overlay(get_text("live.prompt.loading"))
        elif stage in ("clean", "extract"):
            self._overlay.show_overlay(get_text("live.prompt.processing"))
        else:
            self._overlay.hide_overlay()

    def hideEvent(self, event):
        """页面隐藏时停止旋转(节省资源)"""
        self._overlay.hide_overlay()
        self._success_overlay.hide()
        super().hideEvent(event)

    def resizeEvent(self, event):
        """父控件尺寸变化 → 遮罩同步全屏覆盖(不在布局中, 必须手动跟随)"""
        super().resizeEvent(event)
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._success_overlay.setGeometry(0, 0, self.width(), self.height())

    def reset(self):
        """重置画面页状态(下次进入时: 清空画面, 重新显示"正在加载中"遮罩)"""
        self._frame_started = False
        self._last_prompt = ""
        self.video_label.clear()                 # 清空上一轮残留画面
        self.prompt_label.setText(get_text("live.prompt.loading"))
        self._success_overlay.hide()             # 清空上一轮成功覆盖层
        self._overlay.show_overlay(get_text("live.prompt.loading"))

    def _on_exit_click(self):
        """[退出识别] → UiRsp.on_cancel_enroll(终止流程, 结果事件回来时退回原窗口)"""
        rsp = self._gui.get_rsp()
        if rsp is not None:
            rsp.on_cancel_enroll()

    # ============================================================
    # 帧更新(由 GUI.frame_received 信号在主线程调用)
    # ============================================================
    def set_frame(self, frame, prompt=""):
        """
        更新摄像头画面与提示词(主线程执行; 画面节流, 提示词变化即时更新)
        :param frame: BGR 帧<np.ndarray>
        :param prompt: 当前提示词<str>
        :return: None
        """
        # 页面不可见(已退回/未进入): 丢弃残留帧事件, 防止下一轮显示上一轮画面
        if not self.isVisible():
            return

        # 首帧到达: 摄像头已接入, 隐藏"正在加载中"遮罩
        if not self._frame_started and frame is not None and frame.size > 0:
            self._frame_started = True
            self._overlay.hide_overlay()

        # 提示词变化: 立即更新(不受画面节流影响)
        if prompt and prompt != self._last_prompt:
            self._last_prompt = prompt
            self.prompt_label.setText(prompt)

        # 帧为空(如取消瞬间)跳过
        if frame is None or frame.size == 0:
            return
        # 画面节流: 丢弃间隔内的帧, 防止高帧率缩放淹没主线程
        import time
        now = time.time()
        if now - self._last_frame_time < self.FRAME_INTERVAL:
            return
        self._last_frame_time = now

        try:
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # copy(): QImage 不持有 numpy 数据, 必须拷贝(否则帧被回收后花屏/崩溃)
            image = QImage(rgb.data, w, h, 3 * w,
                           QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(image)
            # 等比缩放到画面区(保持宽高比)
            pixmap = pixmap.scaled(self.video_label.size(),
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.video_label.setPixmap(pixmap)
        except Exception as e:
            # 帧格式异常时静默跳过, 不影响流程
            print(f"[LivePage] 帧显示异常: {e}")
            return


# ====================================================================
# 账户页(仅 UI, 用户系统尚未实现)
# ====================================================================
class AccountPage(QWidget):
    """
    账户管理页(仅 UI 展示)
    ======================
    从头像点击进入; 顶部返回按钮回概览。
    展示当前用户基本信息(大头像/用户名/ID/角色), 用户系统尚未实现。
    """

    def __init__(self, gui):
        super().__init__()
        self._gui = gui
        self.setObjectName("accountPage")

        # ── 头部: 返回按钮 + 标题 ──
        head = QHBoxLayout()
        head.setContentsMargins(24, 16, 24, 0)
        self.back_btn = QPushButton(get_text("user.back"))
        self.back_btn.setObjectName("backBtn")
        self.back_btn.clicked.connect(lambda: self._gui.switch_page("overview"))
        page_title = QLabel(get_text("user.page_title"))
        page_title.setObjectName("pageTitle")
        head.addWidget(self.back_btn)
        head.addSpacing(8)
        head.addWidget(page_title)
        head.addStretch(1)

        # ── 中部: 大头像 + 用户信息(数据源: userInfo 当前用户) ──
        user = get_current_user()
        self.big_avatar = QLabel("👤")
        self.big_avatar.setObjectName("bigAvatar")
        self.big_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_avatar.setFixedSize(96, 96)

        user_name = QLabel(user["userName"])
        user_name.setObjectName("cardTitle")
        user_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_id = QLabel(f"ID: {user['userId']}")
        user_id.setObjectName("cardText")
        user_id.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_role = QLabel(user["role"])
        user_role.setObjectName("cardText")
        user_role.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(get_text("user.page_hint"))
        hint.setObjectName("cardText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center = QVBoxLayout()
        center.setSpacing(10)
        center.addStretch(2)
        avatar_row = QHBoxLayout()
        avatar_row.addStretch(1)
        avatar_row.addWidget(self.big_avatar)
        avatar_row.addStretch(1)
        center.addLayout(avatar_row)
        center.addSpacing(8)
        center.addWidget(user_name)
        center.addWidget(user_id)
        center.addWidget(user_role)
        center.addSpacing(16)
        center.addWidget(hint)
        center.addStretch(3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(head)
        layout.addLayout(center, 1)


# ====================================================================
# 占位页
# ====================================================================
class PlaceholderPage(QWidget):
    """占位页: 居中显示"功能开发中"(安全中心/防护日志/设置等未实现模块)"""

    def __init__(self, page_id):
        super().__init__()
        self.setObjectName(f"placeholderPage_{page_id}")

        title = QLabel(get_text("placeholder.title"))
        title.setObjectName("placeholderTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(get_text("placeholder.text"))
        text.setObjectName("placeholderText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(text)
        layout.addStretch(1)
