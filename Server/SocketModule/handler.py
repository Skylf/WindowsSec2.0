"""
coding:utf-8
file: SocketModule/handler.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端业务处理器
# =================
# 将 socket 消息路由到 UserSystem 的各模块:
#   login   → loginSystem.LoginSystem
#   enroll  → enrollSystem.EnrollSystem
#   token_* → tokenManager.TokenManager
#   logout  → tokenManager.TokenManager.revokeToken
#
# 每个处理器函数接收 msg: dict, 返回 response: dict

import os
import sys

# 确保 UserSystem 路径
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USER_SYSTEM_DIR = os.path.join(_SERVER_DIR, "UserSystem")
if _USER_SYSTEM_DIR not in sys.path:
    sys.path.insert(0, _USER_SYSTEM_DIR)

# 确保 ServerLogSystem 路径
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

import database
from protocol import (
    buildResponse,
    CODE_OK, CODE_BAD_REQUEST, CODE_UNAUTHORIZED, CODE_FORBIDDEN, CODE_NOT_FOUND,
    ACTION_LOGIN, ACTION_ENROLL, ACTION_LOGOUT, ACTION_TOKEN_VERIFY, ACTION_AUTO_LOGIN,
)


class HandlerRegister:
    """
    业务处理器注册
    ===============
    初始化数据库连接, 创建 EnrollSystem/LoginSystem/TokenManager 实例,
    并将处理函数注册到服务器的 HandlerRouter 上。
    """

    def __init__(self):
        # 初始化服务端日志管理器(传入数据库路径, 日志写入 system_logs 表)
        # 必须先于 database.get_connection() 调用, 否则早期日志无法入库
        from ServerLogSystem.logManager import getLogger as getLogSystemLogger
        getLogSystemLogger(database.DATA_BASE_PATH)

        # 数据库连接(整个服务端生命周期内保持)
        self.dbConn = database.get_connection()
        database.init_db("admin", self.dbConn)

        # 业务模块实例
        from enrollSystem import EnrollSystem
        from loginSystem import LoginSystem
        from tokenManager import TokenManager
        from cookieManager import CookieManager

        self.enrollSystem = EnrollSystem(self.dbConn)
        self.loginSystem = LoginSystem(self.dbConn)
        self.tokenManager = TokenManager(self.dbConn)
        self.cookieManager = CookieManager(self.dbConn)

        # 日志管理器(延迟导入)
        from ServerLogSystem.logManager import getLogger
        from ServerLogSystem.logConfig import CATEGORY_AUTH
        self._logger = getLogger()
        self._category = CATEGORY_AUTH

    def registerAll(self, router):
        """
        将所有业务处理器注册到路由
        :param router: HandlerRouter 实例
        """
        router.register(ACTION_ENROLL, self.handleEnroll)
        router.register(ACTION_LOGIN, self.handleLogin)
        router.register(ACTION_AUTO_LOGIN, self.handleAutoLogin)
        router.register(ACTION_LOGOUT, self.handleLogout)
        router.register(ACTION_TOKEN_VERIFY, self.handleTokenVerify)

    def handleEnroll(self, msg: dict) -> dict:
        """
        处理注册请求
        请求数据: { nickname, username, password, confirm_password, email, email_code }
        响应数据: { user_id, username }
        """
        data = msg.get("data", {})
        requestId = msg.get("request_id", "")

        username = data.get("username", "")
        self._logger.info(self._category, f"收到注册请求: username={username}")

        result = self.enrollSystem.enroll(
            nickname=data.get("nickname", ""),
            username=username,
            password=data.get("password", ""),
            confirm_password=data.get("confirm_password", ""),
            email=data.get("email", ""),
            email_code=data.get("email_code", "123456"),
            captcha_input=data.get("captcha", "")
        )

        if result["code"] == 200:
            self._logger.info(self._category, f"注册成功: username={username}")
            return buildResponse(requestId, ACTION_ENROLL, result.get("data", {}),
                                 code=CODE_OK, message=result["message"])
        else:
            self._logger.warning(self._category, f"注册失败: username={username}, 原因: {result['message']}")
            return buildResponse(requestId, ACTION_ENROLL,
                                 code=CODE_BAD_REQUEST, message=result["message"])

    def handleLogin(self, msg: dict) -> dict:
        """
        处理登录请求
        请求数据: { identity, password, email_code, auto_login, ip, device_code }
        响应数据: { token, user_id, username, nickname, email, role, avatar_path, cookie }
        """
        data = msg.get("data", {})
        requestId = msg.get("request_id", "")

        identity = data.get("identity", "")
        self._logger.info(self._category, f"收到登录请求: identity={identity}")

        # 登录校验
        result = self.loginSystem.login(
            identity=identity,
            password=data.get("password", ""),
            email_code=data.get("email_code", "123456"),
            captcha_input=data.get("captcha", "")
        )

        if result["code"] != 200:
            self._logger.warning(self._category, f"登录失败: identity={identity}, 原因: {result['message']}")
            return buildResponse(requestId, ACTION_LOGIN,
                                 code=CODE_BAD_REQUEST, message=result["message"])

        # 登录成功 → 签发 Token
        userData = result.get("data", {})
        tokenResult = self.tokenManager.generateToken(
            userData["user_id"],
            userData.get("username", ""),
            userData.get("role", "user")
        )

        if tokenResult["code"] != 200:
            self._logger.error(self._category, f"Token 签发失败: identity={identity}")
            return buildResponse(requestId, ACTION_LOGIN,
                                 code=CODE_BAD_REQUEST, message=tokenResult["message"])

        # 更新用户最后登录信息(记录 IP + 设备识别码,供下次自动登录匹配)
        from datetime import datetime
        nowStr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip = data.get("ip", "")
        deviceCode = data.get("device_code", "")
        updateDb = database.UpdateDatabase(self.dbConn)
        updateDb.update_table_users(
            user_id=userData["user_id"],
            last_login_at=nowStr,
            last_login_ip=ip or None,
            device_code=deviceCode or None
        )

        # 组合返回数据(先放 token 与用户信息,后面按需追加 cookie)
        responseData = {
            "token": tokenResult.get("token", ""),
            "user_id": userData["user_id"],
            "username": userData["username"],
            "nickname": userData.get("nickname", ""),
            "email": userData.get("email", ""),
            "role": userData["role"],
            "avatar_path": userData.get("avatar_path", ""),
        }

        # 勾选"自动登录"且提供了 ip + device_code → 签发 cookie 返回给客户端
        if data.get("auto_login") and ip and deviceCode:
            cookieResult = self.cookieManager.generateCookie(
                userData["user_id"], ip, deviceCode
            )
            if cookieResult["code"] == 200:
                responseData["cookie"] = cookieResult["cookie"]
                responseData["cookie_expires_at"] = cookieResult["data"]["expires_at"]
            else:
                self._logger.warning(self._category, f"自动登录 Cookie 签发失败: {cookieResult['message']}")

        self._logger.info(self._category, f"登录成功: username={userData['username']}, role={userData['role']}")

        return buildResponse(requestId, ACTION_LOGIN, responseData,
                             code=CODE_OK, message="登录成功")

    def handleAutoLogin(self, msg: dict) -> dict:
        """
        处理自动登录请求
        请求数据: { cookie, ip, device_code }
        响应数据: { token, user_id, username, nickname, email, role, avatar_path, cookie_expires_at }
        """
        data = msg.get("data", {})
        requestId = msg.get("request_id", "")

        cookie = data.get("cookie", "")
        ip = data.get("ip", "")
        deviceCode = data.get("device_code", "")

        self._logger.info(self._category, f"收到自动登录请求: ip={ip}")

        # 校验 cookie(IP + 设备识别码 + 有效期,任一不匹配则撤销并返回 401)
        verifyResult = self.cookieManager.verifyCookie(cookie, ip, deviceCode)
        if verifyResult["code"] != 200:
            self._logger.warning(self._category, f"自动登录失败: {verifyResult['message']}")
            return buildResponse(requestId, ACTION_AUTO_LOGIN,
                                 code=CODE_UNAUTHORIZED, message=verifyResult["message"])

        userId = verifyResult["data"]["user_id"]

        # 查询用户信息(确认用户仍存在且未被封禁)
        queryDb = database.QueryDatabase(self.dbConn)
        userResult = queryDb.query_table_users(user_id=userId)
        if userResult["code"] != 200 or userResult["count"] == 0:
            return buildResponse(requestId, ACTION_AUTO_LOGIN,
                                 code=CODE_UNAUTHORIZED, message="用户不存在")
        user = userResult["data"][0]

        if user["status"] == "banned":
            return buildResponse(requestId, ACTION_AUTO_LOGIN,
                                 code=CODE_FORBIDDEN, message="账户已被封禁,请联系管理员")

        # 签发新的会话 token(每次登录都分配新 token,单会话有效)
        tokenResult = self.tokenManager.generateToken(user["user_id"], user["username"], user["role"])
        if tokenResult["code"] != 200:
            self._logger.error(self._category, f"自动登录 Token 签发失败: user_id={userId}")
            return buildResponse(requestId, ACTION_AUTO_LOGIN,
                                 code=CODE_BAD_REQUEST, message=tokenResult["message"])

        # 刷新 cookie 有效期(每次登录成功延期一周)
        refreshResult = self.cookieManager.refreshCookieExpiry(cookie, ip, deviceCode)

        # 更新用户最后登录信息(刷新登录时间 + IP + 设备识别码)
        from datetime import datetime
        nowStr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updateDb = database.UpdateDatabase(self.dbConn)
        updateDb.update_table_users(
            user_id=userId,
            last_login_at=nowStr,
            last_login_ip=ip,
            device_code=deviceCode
        )

        # 组合返回数据(cookie 值不变,仅刷新有效期,客户端本地重复使用)
        responseData = {
            "token": tokenResult.get("token", ""),
            "user_id": user["user_id"],
            "username": user["username"],
            "nickname": user.get("nickname") or "",
            "email": user.get("email") or "",
            "role": user["role"],
            "avatar_path": user.get("avatar_path") or "",
            "cookie_expires_at": refreshResult.get("expires_at", ""),
        }

        self._logger.info(self._category, f"自动登录成功: username={user['username']}")
        return buildResponse(requestId, ACTION_AUTO_LOGIN, responseData,
                             code=CODE_OK, message="自动登录成功")

    def handleLogout(self, msg: dict) -> dict:
        """
        处理登出请求
        请求数据: 通过 token 字段鉴权
        """
        token = msg.get("token", "")
        requestId = msg.get("request_id", "")

        self._logger.info(self._category, "收到登出请求")

        if not token:
            self._logger.warning(self._category, "登出请求未提供 Token")
            return buildResponse(requestId, ACTION_LOGOUT,
                                 code=CODE_UNAUTHORIZED, message="未提供 Token")

        result = self.tokenManager.revokeToken(token)
        if result["code"] == 200:
            self._logger.info(self._category, "登出成功")
            return buildResponse(requestId, ACTION_LOGOUT,
                                 code=CODE_OK, message="已退出登录")
        else:
            self._logger.warning(self._category, f"登出失败: {result['message']}")
            return buildResponse(requestId, ACTION_LOGOUT,
                                 code=CODE_BAD_REQUEST, message=result["message"])

    def handleTokenVerify(self, msg: dict) -> dict:
        """
        处理 Token 验证请求
        请求数据: 通过 token 字段鉴权, 可选 required_role
        响应数据: { valid, user_id, username, role, new_token }
        """
        token = msg.get("token", "")
        data = msg.get("data", {})
        requestId = msg.get("request_id", "")

        requiredRole = data.get("required_role", None)

        result = self.tokenManager.verifyOp(token, requiredRole)

        if result["code"] == 200:
            respData = result.get("data", {})
            newToken = result.get("new_token")
            if newToken:
                self._logger.info(self._category, f"Token 验证通过并自动刷新: user={respData.get('username')}")
            return buildResponse(requestId, ACTION_TOKEN_VERIFY,
                                 {
                                     "valid": True,
                                     "user_id": respData.get("user_id"),
                                     "username": respData.get("username"),
                                     "role": respData.get("role"),
                                     "new_token": newToken,
                                 },
                                 token=newToken or token,
                                 code=CODE_OK, message=result["message"])
        else:
            self._logger.warning(self._category, f"Token 验证失败: {result['message']}")
            return buildResponse(requestId, ACTION_TOKEN_VERIFY,
                                 code=CODE_UNAUTHORIZED, message=result["message"])


def startServer(host: str = "127.0.0.1", port: int = 9527):
    """
    启动服务器(便捷入口)
    :param host: 监听地址<str>
    :param port: 监听端口<int>
    """
    from server import Server
    srv = Server(host, port)

    # 注册业务处理器
    handlers = HandlerRegister()
    handlers.registerAll(srv.getRouter())

    # 启动
    srv.start()