"""
coding:utf-8
file: SocketModule/authService.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 认证服务(UI 调用的封装层)
# ===========================
# 将网络通信封装为简单的业务接口, UI 层无需关心 socket 细节。
# 返回格式统一: {"code": 200/400/..., "message": "...", "data": {...}}
#
# 使用前需调用 initAuthService() 初始化连接。

from networkManager import NetworkManager
from protocol import (
    ACTION_LOGIN, ACTION_ENROLL, ACTION_LOGOUT, ACTION_TOKEN_VERIFY, ACTION_AUTO_LOGIN,
    CODE_OK, CODE_BAD_REQUEST, CODE_UNAUTHORIZED,
)

# 设备信息采集(自动登录上传 ip + device_code)
from deviceInfo import getLocalIp, getDeviceCode

# cookie 本地存储(读写 client/cache 下的 cookie 文件)
from cookieStore import saveCookie, loadCookie, deleteCookie, hasCookie

# 全局网络管理器单例
_network = None

# 日志管理器(延迟导入)
_logger = None
_category = None


def _getLogger():
    """获取日志管理器(延迟初始化)"""
    global _logger, _category
    if _logger is None:
        import os as _os, sys as _sys
        _CLIENT_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _CLIENT_DIR not in _sys.path:
            _sys.path.insert(0, _CLIENT_DIR)
        from LogSystem.logManager import getLogger
        from LogSystem.logConfig import CATEGORY_AUTH
        _logger = getLogger()
        _category = CATEGORY_AUTH
    return _logger, _category


def initAuthService(host: str = "127.0.0.1", port: int = 9527) -> bool:
    """
    初始化认证服务(连接服务器)
    :param host: 服务器地址<str>
    :param port: 端口<int>
    :return: 是否连接成功<bool>
    """
    global _network
    logger, category = _getLogger()
    _network = NetworkManager()
    result = _network.connect(host, port)
    if result:
        logger.info(category, f"认证服务初始化成功 → {host}:{port}")
    else:
        logger.warning(category, f"认证服务初始化失败 → {host}:{port}")
    return result


def isConnected() -> bool:
    """
    检查是否已连接服务器
    :return: bool
    """
    return _network is not None and _network.isConnected()


def shutdownAuthService():
    """关闭认证服务(断开连接)"""
    global _network
    logger, category = _getLogger()
    if _network:
        _network.disconnect()
        _network = None
    logger.info(category, "认证服务已关闭")


def enroll(nickname: str, username: str, password: str, confirmPassword: str,
           email: str, emailCode: str = "123456") -> dict:
    """
    注册新用户
    :param nickname: 昵称<str>
    :param username: 用户名<str>
    :param password: 密码<str>
    :param confirmPassword: 确认密码<str>
    :param email: 邮箱<str>
    :param emailCode: 邮箱验证码<str>, 默认 123456
    :return: {"code": int, "message": str, "data": dict}
    """
    logger, category = _getLogger()
    if not _network or not _network.connected:
        logger.warning(category, "注册请求失败: 未连接到服务器")
        return {"code": CODE_BAD_REQUEST, "message": "未连接到服务器", "data": {}}

    logger.info(category, f"发起注册请求: username={username}, email={email}")
    response = _network.sendRequest(ACTION_ENROLL, {
        "nickname": nickname,
        "username": username,
        "password": password,
        "confirm_password": confirmPassword,
        "email": email,
        "email_code": emailCode,
    })

    if response is None:
        logger.error(category, f"注册请求超时: username={username}")
        return {"code": CODE_BAD_REQUEST, "message": "请求超时", "data": {}}

    code = response.get("code", 400)
    msg = response.get("message", "")
    if code == CODE_OK:
        logger.info(category, f"注册成功: username={username}")
    else:
        logger.warning(category, f"注册失败: username={username}, 原因: {msg}")
    return {"code": code, "message": msg, "data": response.get("data", {})}


def login(identity: str, password: str, emailCode: str = "123456", autoLogin: bool = False) -> dict:
    """
    登录
    :param identity: 用户名或邮箱<str>
    :param password: 密码<str>
    :param emailCode: 邮箱验证码<str>, 默认 123456
    :param autoLogin: 是否勾选自动登录<bool>, 勾选则上传 ip+device_code 并保存服务端签发的 cookie
    :return: {"code": int, "message": str, "data": {token, user_id, username, ..., cookie?}}
    """
    logger, category = _getLogger()
    if not _network or not _network.connected:
        logger.warning(category, "登录请求失败: 未连接到服务器")
        return {"code": CODE_BAD_REQUEST, "message": "未连接到服务器", "data": {}}

    logger.info(category, f"发起登录请求: identity={identity}, auto_login={autoLogin}")

    # 构造请求数据; 勾选自动登录时附带本机 ip + 设备识别码供服务端绑定 cookie
    requestData = {
        "identity": identity,
        "password": password,
        "email_code": emailCode,
    }
    if autoLogin:
        requestData["auto_login"] = True
        requestData["ip"] = getLocalIp()
        requestData["device_code"] = getDeviceCode()

    response = _network.sendRequest(ACTION_LOGIN, requestData)

    if response is None:
        logger.error(category, f"登录请求超时: identity={identity}")
        return {"code": CODE_BAD_REQUEST, "message": "请求超时", "data": {}}

    code = response.get("code", 400)
    data = response.get("data", {})

    # 登录成功 → 保存 Token
    if code == 200 and data.get("token"):
        _network.setToken(data["token"])
        logger.info(category, f"登录成功: identity={identity}, role={data.get('role', 'user')}")

        # 勾选自动登录且服务端返回 cookie → 写入本地 cache
        if autoLogin and data.get("cookie"):
            saveCookie({
                "cookie": data["cookie"],
                "user_id": data.get("user_id"),
                "username": data.get("username", ""),
                "ip": requestData["ip"],
                "device_code": requestData["device_code"],
                "expires_at": data.get("cookie_expires_at", ""),
            })
            logger.info(category, f"自动登录 cookie 已保存: identity={identity}")

    return {"code": code, "message": response.get("message", ""), "data": data}


def hasStoredCookie() -> bool:
    """
    检查本地是否存在自动登录 cookie

    :return: True=存在, False=不存在
    """
    return hasCookie()


def autoLogin() -> dict:
    """
    自动登录: 读取本地 cookie,与服务端比对 ip + 设备识别码后自动登录
    成功 → 保存新 token 并刷新本地 cookie 有效期
    失败(ip/设备码不匹配或已到期) → 删除本地失效 cookie,要求手动登录

    :return: {"code": int, "message": str, "data": {token, user_id, username, ...}}
    """
    logger, category = _getLogger()
    if not _network or not _network.connected:
        logger.warning(category, "自动登录失败: 未连接到服务器")
        return {"code": CODE_BAD_REQUEST, "message": "未连接到服务器", "data": {}}

    # 读取本地 cookie,不存在则直接返回(需手动登录)
    cookieData = loadCookie()
    if not cookieData:
        logger.info(category, "本地无自动登录 cookie,跳过自动登录")
        return {"code": CODE_UNAUTHORIZED, "message": "本地无自动登录 cookie", "data": {}}

    cookie = cookieData.get("cookie", "")
    ip = getLocalIp()
    deviceCode = getDeviceCode()

    logger.info(category, f"发起自动登录请求: ip={ip}")
    response = _network.sendRequest(ACTION_AUTO_LOGIN, {
        "cookie": cookie,
        "ip": ip,
        "device_code": deviceCode,
    })

    if response is None:
        logger.error(category, "自动登录请求超时")
        return {"code": CODE_BAD_REQUEST, "message": "请求超时", "data": {}}

    code = response.get("code", 400)
    data = response.get("data", {})
    message = response.get("message", "")

    if code == CODE_OK and data.get("token"):
        _network.setToken(data["token"])
        # 服务端已刷新 cookie 有效期,同步更新本地 expires_at
        cookieData["expires_at"] = data.get("cookie_expires_at", cookieData.get("expires_at", ""))
        cookieData["ip"] = ip
        cookieData["device_code"] = deviceCode
        saveCookie(cookieData)
        logger.info(category, f"自动登录成功: username={data.get('username', '')}")
    else:
        # 校验失败 → 删除本地 cookie(服务端已在数据库中撤销该 cookie)
        deleteCookie()
        logger.warning(category, f"自动登录失败,已清除本地 cookie: {message}")

    return {"code": code, "message": message, "data": data}


def logout() -> dict:
    """
    退出登录
    :return: {"code": int, "message": str, "data": {}}
    """
    logger, category = _getLogger()
    if not _network or not _network.connected:
        logger.warning(category, "登出请求失败: 未连接到服务器")
        return {"code": CODE_BAD_REQUEST, "message": "未连接到服务器", "data": {}}

    logger.info(category, "发起登出请求")
    response = _network.sendRequest(ACTION_LOGOUT)

    if response is None:
        logger.error(category, "登出请求超时")
        return {"code": CODE_BAD_REQUEST, "message": "请求超时", "data": {}}

    # 无论成功与否, 清除本地 Token
    _network.clearToken()
    logger.info(category, "已登出")

    return {"code": response.get("code", 400), "message": response.get("message", ""),
            "data": response.get("data", {})}


def verifyToken(requiredRole: str = None) -> dict:
    """
    验证当前 Token
    :param requiredRole: 要求的角色<str>, 可选 "admin"/"user"/None
    :return: {"code": int, "message": str, "data": {valid, user_id, username, ...}}
    """
    logger, category = _getLogger()
    if not _network or not _network.connected:
        logger.warning(category, "Token 验证失败: 未连接到服务器")
        return {"code": CODE_BAD_REQUEST, "message": "未连接到服务器", "data": {}}

    data = {}
    if requiredRole:
        data["required_role"] = requiredRole

    response = _network.sendRequest(ACTION_TOKEN_VERIFY, data)

    if response is None:
        logger.error(category, "Token 验证请求超时")
        return {"code": CODE_BAD_REQUEST, "message": "请求超时", "data": {}}

    code = response.get("code", 400)
    respData = response.get("data", {})

    # Token 自动刷新
    if respData.get("new_token"):
        _network.setToken(respData["new_token"])
        logger.info(category, "Token 已自动刷新")

    return {"code": code, "message": response.get("message", ""), "data": respData}