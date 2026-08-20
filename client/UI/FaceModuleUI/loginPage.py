"""
coding:utf-8
file: UI/FaceModuleUI/loginPage.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 登录 & 注册 UI 页面(纯 UI, 不涉及后端交互)
# ============================================
# 目前仅实现 UI 展示与页面跳转, 后续对接用户系统时:
#   - 登录按钮 → 调用 loginSystem.login()
#   - 注册按钮 → 调用 enrollSystem.enroll()
#   - 验证码 → 当前固定 123456, 后续对接邮箱服务

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from texts import get_text

# 确保 SocketModule 路径在 sys.path 中(供 import authService)
import os as _os, sys as _sys
_socketPath = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "SocketModule")
if _socketPath not in _sys.path:
    _sys.path.insert(0, _socketPath)

# 日志管理器(延迟导入)
_logger = None
_category = None


def _getLogger():
    """获取日志管理器(延迟初始化)"""
    global _logger, _category
    if _logger is None:
        _CLIENT_DIR = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        if _CLIENT_DIR not in _sys.path:
            _sys.path.insert(0, _CLIENT_DIR)
        from LogSystem.logManager import getLogger
        from LogSystem.logConfig import CATEGORY_UI
        _logger = getLogger()
        _category = CATEGORY_UI
    return _logger, _category


# 分隔线
SEP = "─" * 50


# ====================================================================
# 登录页
# ====================================================================
class LoginPage(QWidget):
    """
    登录页(纯 UI)
    ==============
    输入: 用户名/邮箱(二选一) + 密码 + 邮箱验证码 + 人机验证(自动通过)
    页面切换: "没有账号? 去注册" → 切换到注册页
    """

    # 信号: 登录成功(暂留接口, 后续对接后端)
    login_success = pyqtSignal(dict)

    def __init__(self, gui):
        """
        初始化登录页
        :param gui: MainWindow 实例(GUI 基类)
        """
        super().__init__()
        self._gui = gui
        self.setObjectName("loginPage")

        # 外层容器(居中卡片)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        # 居中卡片
        card = self.__buildCard()
        cardRow = QHBoxLayout()
        cardRow.addStretch(1)
        cardRow.addWidget(card)
        cardRow.addStretch(1)
        outer.addLayout(cardRow)

        outer.addStretch(1)

    def __buildCard(self) -> QFrame:
        """构建登录卡片"""
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(380)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        # 标题
        title = QLabel(get_text("login.title"))
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel(get_text("login.subtitle"))
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        # 用户名/邮箱输入
        identityLabel = QLabel(get_text("login.identity"))
        identityLabel.setObjectName("loginLabel")
        layout.addWidget(identityLabel)
        self.identityInput = QLineEdit()
        self.identityInput.setObjectName("loginInput")
        self.identityInput.setPlaceholderText(get_text("login.identity_placeholder"))
        layout.addWidget(self.identityInput)

        # 密码输入
        pwdLabel = QLabel(get_text("login.password"))
        pwdLabel.setObjectName("loginLabel")
        layout.addWidget(pwdLabel)
        self.passwordInput = QLineEdit()
        self.passwordInput.setObjectName("loginInput")
        self.passwordInput.setPlaceholderText(get_text("login.password_placeholder"))
        self.passwordInput.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.passwordInput)

        # 自动登录复选框(勾选后登录成功会保存 cookie,下次免密登录)
        self.autoLoginCheck = QCheckBox(get_text("login.auto_login"))
        self.autoLoginCheck.setObjectName("autoLoginCheck")
        layout.addWidget(self.autoLoginCheck)

        # 邮箱验证码
        codeLabel = QLabel(get_text("login.email_code"))
        codeLabel.setObjectName("loginLabel")
        layout.addWidget(codeLabel)
        codeRow = QHBoxLayout()
        codeRow.setSpacing(8)
        self.codeInput = QLineEdit()
        self.codeInput.setObjectName("loginInput")
        self.codeInput.setPlaceholderText(get_text("login.code_placeholder"))
        codeRow.addWidget(self.codeInput)
        # 发送验证码按钮(暂为占位)
        self.sendCodeBtn = QPushButton(get_text("login.send_code"))
        self.sendCodeBtn.setObjectName("sendCodeBtn")
        self.sendCodeBtn.setFixedWidth(80)
        codeRow.addWidget(self.sendCodeBtn)
        layout.addLayout(codeRow)

        layout.addSpacing(6)

        # 错误提示标签(隐藏, 仅在出错时显示)
        self.errorLabel = QLabel("")
        self.errorLabel.setObjectName("loginError")
        self.errorLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.errorLabel.hide()
        layout.addWidget(self.errorLabel)

        # 登录按钮
        self.loginBtn = QPushButton(get_text("login.btn_login"))
        self.loginBtn.setObjectName("primaryBtn")
        self.loginBtn.setFixedHeight(40)
        self.loginBtn.clicked.connect(self.__onLogin)
        layout.addWidget(self.loginBtn)

        # 取消按钮(返回概览页)
        self.cancelBtn = QPushButton(get_text("login.btn_cancel"))
        self.cancelBtn.setObjectName("cancelBtn")
        self.cancelBtn.setFixedHeight(40)
        self.cancelBtn.clicked.connect(lambda: self._gui.switch_page("overview"))
        layout.addWidget(self.cancelBtn)

        layout.addSpacing(8)

        # 切换到注册页
        switchRow = QHBoxLayout()
        switchRow.addStretch(1)
        switchLabel = QLabel(get_text("login.no_account"))
        switchLabel.setObjectName("loginSwitchLabel")
        switchRow.addWidget(switchLabel)
        self.toEnrollBtn = QPushButton(get_text("login.to_enroll"))
        self.toEnrollBtn.setObjectName("linkBtn")
        self.toEnrollBtn.clicked.connect(lambda: self._gui.switch_page("enroll"))
        switchRow.addWidget(self.toEnrollBtn)
        switchRow.addStretch(1)
        layout.addLayout(switchRow)

        return card

    def __onLogin(self):
        """
        登录按钮响应
        调用 authService.login() → 成功后写入 currentUser → 返回概览页
        """
        logger, category = _getLogger()
        identity = self.identityInput.text().strip()
        password = self.passwordInput.text()
        code = self.codeInput.text().strip() or "123456"
        autoLogin = self.autoLoginCheck.isChecked()

        # 简单校验(非空)
        if not identity:
            self.__showError(get_text("login.error_empty_identity"))
            return
        if not password:
            self.__showError(get_text("login.error_empty_password"))
            return

        logger.info(category, f"用户点击登录按钮: identity={identity}, auto_login={autoLogin}")

        # 调用 authService 进行网络登录
        # 导入 authService(SocketModule 路径)
        from authService import login as authLogin
        result = authLogin(identity, password, code, autoLogin)

        if result["code"] == 200:
            # 登录成功 → 写入 currentUser
            data = result["data"]
            from currentUser import set_current_user
            set_current_user({
                "user_id": data.get("user_id"),
                "uuid": data.get("uuid", ""),
                "username": data.get("username", ""),
                "nickname": data.get("nickname", ""),
                "email": data.get("email", ""),
                "role": data.get("role", "user"),
                "avatar_path": data.get("avatar_path", ""),
            })
            self.errorLabel.hide()
            logger.info(category, f"登录成功, 切换到概览页: username={data.get('username', '')}")
            self._gui.switch_page("overview")
        else:
            logger.warning(category, f"登录失败: {result['message']}")
            self.__showError(result["message"])

    def __showError(self, msg: str):
        """
        显示错误提示
        :param msg: 错误信息<str>
        """
        self.errorLabel.setText(msg)
        self.errorLabel.show()


# ====================================================================
# 注册页(三步向导)
# ====================================================================
class EnrollPage(QWidget):
    """
    注册页(三步向导, 每步只显示少量字段, 避免窗口拥挤)
    ===================================================
    步骤1: 用户名 + 密码 + 确认密码
    步骤2: 邮箱 + 邮箱验证码
    步骤3: 昵称 → 完成注册
    """

    enroll_success = pyqtSignal(dict)

    def __init__(self, gui):
        """
        初始化注册页
        :param gui: MainWindow 实例(GUI 基类)
        """
        super().__init__()
        self._gui = gui
        self.setObjectName("enrollPage")

        # 收集所有步骤的数据
        self._stepData = {"username": "", "password": "", "confirm": "",
                          "email": "", "code": "", "nickname": ""}

        # 外层容器(居中卡片)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        # 居中卡片
        self._card = self.__buildCard()
        cardRow = QHBoxLayout()
        cardRow.addStretch(1)
        cardRow.addWidget(self._card)
        cardRow.addStretch(1)
        outer.addLayout(cardRow)

        outer.addStretch(1)

        # 初始显示步骤1
        self._currentStep = 0
        self.__showStep(1)

    def __buildCard(self) -> QFrame:
        """构建注册卡片外框"""
        card = QFrame()
        card.setObjectName("enrollCard")
        card.setFixedWidth(380)

        self._cardLayout = QVBoxLayout(card)
        self._cardLayout.setContentsMargins(32, 28, 32, 28)
        self._cardLayout.setSpacing(12)

        return card

    # ── 清空卡片内容 ──
    def __clearCard(self):
        """清空卡片内所有控件"""
        while self._cardLayout.count():
            item = self._cardLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.__clearLayout(item.layout())

    def __clearLayout(self, layout):
        """递归清空布局"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.__clearLayout(item.layout())

    # ── 构建步骤标题 ──
    def __buildStepTitle(self, step: int, title: str):
        """构建步骤标题行: 进度 + 标题 + 副标题"""
        # 进度文本
        progress = QLabel(f"步骤 {step}/3")
        progress.setObjectName("loginSubtitle")
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cardLayout.addWidget(progress)

        # 标题
        titleLabel = QLabel(title)
        titleLabel.setObjectName("loginTitle")
        titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cardLayout.addWidget(titleLabel)

        self._cardLayout.addSpacing(8)

    # ── 构建输入行 ──
    def __buildInput(self, labelText: str, placeholder: str, isPassword: bool = False,
                     maxLength: int = 0) -> QLineEdit:
        """构建标签+输入框"""
        label = QLabel(labelText)
        label.setObjectName("loginLabel")
        self._cardLayout.addWidget(label)

        inp = QLineEdit()
        inp.setObjectName("loginInput")
        inp.setPlaceholderText(placeholder)
        if isPassword:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        if maxLength:
            inp.setMaxLength(maxLength)
        self._cardLayout.addWidget(inp)
        return inp

    # ── 构建错误标签 ──
    def __buildErrorLabel(self) -> QLabel:
        """构建错误提示标签"""
        err = QLabel("")
        err.setObjectName("loginError")
        err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        err.hide()
        self._cardLayout.addWidget(err)
        return err

    # ── 构建按钮行(上一步 / 下一步 / 取消) ──
    def __buildButtonRow(self, nextText: str, nextCallback, showPrev: bool = True):
        """构建底部按钮行"""
        btnRow = QHBoxLayout()
        btnRow.setSpacing(8)

        if showPrev:
            prevBtn = QPushButton(get_text("enroll.btn_prev"))
            prevBtn.setObjectName("cancelBtn")
            prevBtn.setFixedHeight(40)
            prevBtn.clicked.connect(lambda: self.__showStep(self._currentStep - 1))
            btnRow.addWidget(prevBtn)

        cancelBtn = QPushButton(get_text("enroll.btn_cancel"))
        cancelBtn.setObjectName("cancelBtn")
        cancelBtn.setFixedHeight(40)
        cancelBtn.clicked.connect(lambda: self._gui.switch_page("overview"))
        btnRow.addWidget(cancelBtn)

        nextBtn = QPushButton(nextText)
        nextBtn.setObjectName("primaryBtn")
        nextBtn.setFixedHeight(40)
        nextBtn.clicked.connect(nextCallback)
        btnRow.addWidget(nextBtn)

        self._cardLayout.addLayout(btnRow)

    # ── 构建底部切换链接 ──
    def __buildSwitchRow(self):
        """构建"已有账号? 去登录"链接"""
        switchRow = QHBoxLayout()
        switchRow.addStretch(1)
        switchLabel = QLabel(get_text("enroll.has_account"))
        switchLabel.setObjectName("loginSwitchLabel")
        switchRow.addWidget(switchLabel)
        toLoginBtn = QPushButton(get_text("enroll.to_login"))
        toLoginBtn.setObjectName("linkBtn")
        toLoginBtn.clicked.connect(lambda: self._gui.switch_page("login"))
        switchRow.addWidget(toLoginBtn)
        switchRow.addStretch(1)
        self._cardLayout.addLayout(switchRow)

    # ── 显示步骤 ──
    def __showStep(self, step: int):
        """
        切换到指定步骤
        :param step: 步骤号<int> 1/2/3
        """
        self._currentStep = step
        self.__clearCard()

        if step == 1:
            self.__showStep1()
        elif step == 2:
            self.__showStep2()
        elif step == 3:
            self.__showStep3()

    def __showStep1(self):
        """步骤1: 用户名 + 密码 + 确认密码"""
        self.__buildStepTitle(1, "账号信息")

        # 用户名
        self.usernameInput = self.__buildInput(
            get_text("enroll.username"), "3-10 字符, 中英文/数字/特殊字符(除.*?/\)", maxLength=10)
        self.usernameInput.setText(self._stepData["username"])

        # 密码
        self.passwordInput = self.__buildInput(
            get_text("enroll.password"), "6-18 字符, 不含中文", isPassword=True, maxLength=18)
        self.passwordInput.setText(self._stepData["password"])

        # 确认密码
        self.confirmInput = self.__buildInput(
            get_text("enroll.confirm_password"), "请再次输入密码", isPassword=True, maxLength=18)
        self.confirmInput.setText(self._stepData["confirm"])

        self._cardLayout.addSpacing(4)

        # 错误提示
        self.errorLabel = self.__buildErrorLabel()

        # 按钮
        self.__buildButtonRow(
            get_text("enroll.btn_next"),
            self.__onStep1Next,
            showPrev=False
        )

        self.__buildSwitchRow()

    def __onStep1Next(self):
        """步骤1 → 步骤2: 校验用户名+密码"""
        username = self.usernameInput.text().strip()
        password = self.passwordInput.text()
        confirm = self.confirmInput.text()

        # 校验
        if not username:
            self.__showError(get_text("enroll.error_empty_username"))
            return
        if not password:
            self.__showError(get_text("enroll.error_empty_password"))
            return
        if password != confirm:
            self.__showError(get_text("enroll.error_password_mismatch"))
            return

        # 保存数据
        self._stepData["username"] = username
        self._stepData["password"] = password
        self._stepData["confirm"] = confirm

        self.__showStep(2)

    def __showStep2(self):
        """步骤2: 邮箱 + 邮箱验证码"""
        self.__buildStepTitle(2, "邮箱验证")

        # 邮箱
        self.emailInput = self.__buildInput(
            get_text("enroll.email"), "请输入邮箱地址")
        self.emailInput.setText(self._stepData["email"])

        # 邮箱验证码
        codeLabel = QLabel(get_text("enroll.email_code"))
        codeLabel.setObjectName("loginLabel")
        self._cardLayout.addWidget(codeLabel)

        codeRow = QHBoxLayout()
        codeRow.setSpacing(8)
        self.codeInput = QLineEdit()
        self.codeInput.setObjectName("loginInput")
        self.codeInput.setPlaceholderText("请输入验证码(当前固定 123456)")
        self.codeInput.setText(self._stepData["code"])
        codeRow.addWidget(self.codeInput)
        sendBtn = QPushButton(get_text("enroll.send_code"))
        sendBtn.setObjectName("sendCodeBtn")
        sendBtn.setFixedWidth(80)
        codeRow.addWidget(sendBtn)
        self._cardLayout.addLayout(codeRow)

        self._cardLayout.addSpacing(4)

        # 错误提示
        self.errorLabel = self.__buildErrorLabel()

        # 按钮
        self.__buildButtonRow(
            get_text("enroll.btn_next"),
            self.__onStep2Next,
            showPrev=True
        )

        self.__buildSwitchRow()

    def __onStep2Next(self):
        """步骤2 → 步骤3: 校验邮箱+验证码"""
        email = self.emailInput.text().strip()
        code = self.codeInput.text().strip() or "123456"

        if not email:
            self.__showError(get_text("enroll.error_empty_email"))
            return
        if not code:
            self.__showError(get_text("enroll.error_empty_code"))
            return

        self._stepData["email"] = email
        self._stepData["code"] = code

        self.__showStep(3)

    def __showStep3(self):
        """步骤3: 昵称 → 完成注册"""
        self.__buildStepTitle(3, "设置昵称")

        # 昵称
        self.nicknameInput = self.__buildInput(
            get_text("enroll.nickname"), "1-10 字符, 中英文/数字/特殊字符(除.*?/\)", maxLength=10)
        self.nicknameInput.setText(self._stepData["nickname"])

        self._cardLayout.addSpacing(4)

        # 错误提示
        self.errorLabel = self.__buildErrorLabel()

        # 按钮
        self.__buildButtonRow(
            get_text("enroll.btn_enroll"),
            self.__onStep3Submit,
            showPrev=True
        )

        self.__buildSwitchRow()

    def __onStep3Submit(self):
        """
        步骤3: 提交注册
        调用 authService.enroll() → 成功后切回登录页
        """
        logger, category = _getLogger()
        nickname = self.nicknameInput.text().strip()
        if not nickname:
            self.__showError(get_text("enroll.error_empty_nickname"))
            return

        self._stepData["nickname"] = nickname

        logger.info(category, f"用户点击注册提交按钮: username={self._stepData['username']}")

        # 调用 authService 进行网络注册
        from authService import enroll as authEnroll
        result = authEnroll(
            self._stepData["nickname"],
            self._stepData["username"],
            self._stepData["password"],
            self._stepData["confirm"],
            self._stepData["email"],
            self._stepData["code"]
        )

        if result["code"] == 200:
            logger.info(category, f"注册成功, 切换到登录页: username={self._stepData['username']}")
            self.__showError("")
            self.errorLabel.hide()
            self._gui.switch_page("login")
        else:
            logger.warning(category, f"注册失败: {result['message']}")
            self.__showError(result["message"])

    def __showError(self, msg: str):
        """显示错误提示"""
        self.errorLabel.setText(msg)
        self.errorLabel.show()