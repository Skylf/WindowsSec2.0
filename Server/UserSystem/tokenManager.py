# 20260818
# LF
# Token 签发与验证系统


import secrets
import hashlib
from datetime import datetime, timedelta

# 数据库操作类
# AddDatabase    → add_table_sessions   (签发 token 时写入 sessions 表)
# QueryDatabase  → query_table_sessions (验证 token 时查询 sessions 表)
# UpdateDatabase → update_table_sessions(撤销/续期 token 时更新 sessions 表)
from database import AddDatabase, QueryDatabase, UpdateDatabase

# 日志系统导入(Server/ServerLogSystem)
from ServerLogSystem.logManager import getLogger
from ServerLogSystem.logConfig import CATEGORY_AUTH, INFO, WARNING, ERROR


# ====================================================================
# 常量
# ====================================================================
TOKEN_BYTE_LEN = 32               # Token 随机字节数(32字节→64位hex)
TOKEN_EXPIRE_MINUTES = 60         # Token 有效期(分钟) 普通用户 1小时
ADMIN_TOKEN_EXPIRE_MINUTES = 120  # 管理员 Token 有效期(分钟) 2小时
REFRESH_WINDOW_MINUTES = 10       # 自动刷新窗口(分钟): token 剩余 ≤ 此值时自动换发新 token

# 角色常量
ROLE_ADMIN = "admin"
ROLE_USER = "user"


# ====================================================================
# Toke/**
# 会话管理器
# ====================================================================
class TokenManager:
    """
    Token 签发与验证管理器
    ======================
    登录成功后签发 token,存储到 sessions 表,后续所有操作通过 op=token 验证权限

    设计要点:
    1. token 为随机 hex 字符串(不可伪造),session_uuid 为随机 32 位 hex
    2. token 区分 admin/user 两种角色,有效期不同
    3. 一个 token 仅支持本次登录,退出登录(revokeToken)→失效
    4. 重新登录时,旧 token 自动失效
    5. verifyOp 为统一入口,所有需要鉴权的操作都调用此方法
    6. 自动刷新: token 剩余有效期 ≤ 10分钟时,verifyToken 自动换发新 token,旧 token 立即失效
       → 客户端检查返回的 new_token 字段,非空则更新本地 token

    用法:
        conn = get_connection()
        tm = TokenManager(conn)
        result = tm.generateToken(user_id=1, username="admin", role="admin")
        token = result["token"]

        # 后续操作鉴权
        result = tm.verifyOp(token, requiredRole="admin")
        if result["code"] == 200:
            userInfo = result["data"]
            doSomething(...)
    """

    def __init__(self, db_conn):
        """
        初始化 Token 管理器
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(CATEGORY_AUTH)(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __generateTokenStr(self):
        """
        生成随机 token 字符串(64位hex)
        使用 secrets.token_hex 保证密码学安全

        :return: token字符串<str>
        """
        return secrets.token_hex(TOKEN_BYTE_LEN)

    def __generateSessionUuid(self):
        """
        生成 session_uuid(32位hex)
        使用随机生成,不依赖 token 内容

        :return: session_uuid<str>
        """
        return secrets.token_hex(16)

    def __getExpireTime(self, role):
        """
        根据角色计算过期时间(datetime 字符串格式)
        管理员 2小时,普通用户 1小时

        :param role: 角色<str> admin/user
        :return: 过期时间<str> 格式 "YYYY-MM-DD HH:MM:SS"
        """
        expireMinutes = ADMIN_TOKEN_EXPIRE_MINUTES if role == ROLE_ADMIN else TOKEN_EXPIRE_MINUTES
        expireDt = datetime.now() + timedelta(minutes=expireMinutes)
        return expireDt.strftime("%Y-%m-%d %H:%M:%S")

    def __getRemainingMinutes(self, expiresAtStr: str):
        """
        计算 token 剩余有效期(分钟),负数表示已过期

        :param expiresAtStr: 过期时间字符串<str>
        :return: 剩余分钟数<float>
        """
        try:
            expiresDt = datetime.strptime(expiresAtStr, "%Y-%m-%d %H:%M:%S")
            delta = expiresDt - datetime.now()
            return delta.total_seconds() / 60.0
        except ValueError:
            return -1.0  # 格式异常视为已过期

    def __revokeAllUserTokens(self, user_id: int):
        """
        撤销用户的所有有效 token(重新登录时调用,确保旧 token 失效)
        调用 UpdateDatabase.update_table_sessions 置 is_active=0

        :param user_id: 用户ID<int>
        """
        queryDb = QueryDatabase(self.db_conn)
        # 查出该用户所有有效 session
        result = queryDb.query_table_sessions(user_id=user_id, is_active=1)
        if result["code"] == 200 and result["count"] > 0:
            updateDb = UpdateDatabase(self.db_conn)
            for session in result["data"]:
                updateDb.update_table_sessions(
                    session_id=session["session_id"],
                    is_active=0
                )

    # ====================================================================
    # 签发 Token(登录成功后调用)
    # ====================================================================
    def generateToken(self, user_id: int, username: str, role: str):
        """
        签发新 token(登录成功后调用)
        写入 sessions 表,同时撤销该用户的所有旧 token

        :param user_id: 用户ID<int>
        :param username: 用户名<str>
        :param role: 角色<str> admin/user
        :return: dict {"code": 200/400, "message": "...", "token": "...", "data": {...}}
        """
        # 角色校验
        if role not in (ROLE_ADMIN, ROLE_USER):
            return {"code": 400, "message": f"角色 {role} 无效,只能为 admin 或 user"}

        # 生成 token 和 session_uuid
        token = self.__generateTokenStr()
        sessionUuid = self.__generateSessionUuid()
        expiresAt = self.__getExpireTime(role)

        # 撤销该用户的所有旧 token(确保一个 token 只支持本次登录)
        self.__revokeAllUserTokens(user_id)

        # 写入 sessions 表(调用 AddDatabase.add_table_sessions )
        addDb = AddDatabase(self.db_conn)
        result = addDb.add_table_sessions(
            session_uuid=sessionUuid,
            user_id=user_id,
            token=token,
            expires_at=expiresAt
        )

        if result["code"] != 200:
            return {"code": 400, "message": f"Token 签发失败: {result.get('message', '')}"}

        # 日志: Token 签发成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"Token 签发成功: user_id={user_id}")
        return {
            "code": 200,
            "message": "Token 签发成功",
            "token": token,
            "data": {
                "user_id": user_id,
                "username": username,
                "role": role,
                "expires_at": expiresAt
            }
        }

    # ====================================================================
    # 验证 Token(通用,含自动刷新)
    # ====================================================================
    def verifyToken(self, token: str):
        """
        验证 token 是否有效(存在、未过期、未撤销)
        查询 sessions 表: WHERE token = ? AND is_active = 1

        自动刷新机制:
          当 token 剩余有效期 ≤ REFRESH_WINDOW_MINUTES(10分钟)时,
          自动换发新 token,旧 token 立即失效,客户端通过 new_token 字段获取

        :param token: token字符串<str>
        :return: dict {
            "code": 200/400/401,
            "message": "...",
            "data": {"user_id":..., "username":..., "role":...},
            "new_token": "..." 或 None  # 自动刷新时非空,客户端应更新本地 token
        }
        """
        # 空值检查
        if not token:
            return {"code": 400, "message": "Token 不能为空"}

        # 查询 sessions 表,只看有效且未过期的记录
        queryDb = QueryDatabase(self.db_conn)
        result = queryDb.query_table_sessions(token=token, is_active=1)

        if result["code"] != 200 or result["count"] == 0:
            return {"code": 401, "message": "Token 无效或不存在"}

        session = result["data"][0]

        # 检查是否过期(expires_at 格式 "YYYY-MM-DD HH:MM:SS")
        try:
            expiresDt = datetime.strptime(session["expires_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiresDt:
                # 过期: 标记为无效(调用 UpdateDatabase.update_table_sessions )
                updateDb = UpdateDatabase(self.db_conn)
                updateDb.update_table_sessions(
                    session_id=session["session_id"],
                    is_active=0
                )
                # 日志: Token 已过期(调用 ServerLogSystem.logManager->warning )
                self._logger.warning(CATEGORY_AUTH, "Token 已过期")
                return {"code": 401, "message": "Token 已过期,请重新登录"}
        except ValueError:
            return {"code": 401, "message": "Token 过期时间格式异常"}

        # 查询关联用户信息(获取 username/role)
        userQueryDb = QueryDatabase(self.db_conn)
        userResult = userQueryDb.query_table_users(user_id=session["user_id"])
        if userResult["code"] != 200 or userResult["count"] == 0:
            return {"code": 401, "message": "Token 关联的用户不存在"}

        user = userResult["data"][0]

        # 基础响应
        response = {
            "code": 200,
            "message": "Token 验证通过",
            "data": {
                "user_id": session["user_id"],
                "username": user["username"],
                "role": user["role"]
            },
            "new_token": None
        }

        # 日志: Token 验证通过(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"Token 验证通过: user_id={session['user_id']}, username={user['username']}")

        # ================================================================
        # 自动刷新: 剩余有效期 ≤ 刷新窗口时,换发新 token
        # ================================================================
        remaining = self.__getRemainingMinutes(session["expires_at"])
        if 0 < remaining <= REFRESH_WINDOW_MINUTES:
            # 生成新 token
            newToken = self.__generateTokenStr()
            newExpiresAt = self.__getExpireTime(user["role"])

            # 撤销旧 token(调用 UpdateDatabase.update_table_sessions )
            updateDb = UpdateDatabase(self.db_conn)
            updateDb.update_table_sessions(
                session_id=session["session_id"],
                is_active=0
            )

            # 写入新 token(调用 AddDatabase.add_table_sessions )
            addDb = AddDatabase(self.db_conn)
            addResult = addDb.add_table_sessions(
                session_uuid=self.__generateSessionUuid(),  # 新 session_uuid(sessions 表 UNIQUE 约束)
                user_id=session["user_id"],
                token=newToken,
                expires_at=newExpiresAt
            )

            if addResult["code"] == 200:
                response["new_token"] = newToken
                response["message"] = f"Token 验证通过(已自动刷新,剩余 {remaining:.0f} 分钟)"

        return response

    # ====================================================================
    # 验证操作权限(统一入口,op=token,含自动刷新)
    # ====================================================================
    def verifyOp(self, op: str, requiredRole: str = None):
        """
        验证操作权限(所有需要鉴权的操作都调用此方法)
        先验证 token 有效性,再验证角色是否满足要求
        自动刷新时 new_token 字段会透传给调用方

        :param op: 操作凭证<str> 即 token
        :param requiredRole: 要求的角色<str> 可选值: admin / user / None(不限制)
        :return: dict {
            "code": 200/400/401/403,
            "message": "...",
            "data": {...},
            "new_token": "..." 或 None
        }
        """
        # 先验证 token 有效性
        result = self.verifyToken(op)
        if result["code"] != 200:
            return result

        userRole = result["data"]["role"]

        # 如果要求特定角色,检查是否匹配
        if requiredRole is not None:
            # requiredRole=admin 时只有 admin 能通过
            # requiredRole=user 时 admin 和 user 都能通过
            if requiredRole == ROLE_ADMIN and userRole != ROLE_ADMIN:
                return {"code": 403, "message": "权限不足,需要管理员权限"}

        return result

    # ====================================================================
    # 撤销 Token(登出时调用)
    # ====================================================================
    def revokeToken(self, token: str):
        """
        撤销 token(用户登出时调用)
        更新 sessions 表: SET is_active = 0

        :param token: token字符串<str>
        :return: dict {"code": 200/400/404, "message": "..."}
        """
        if not token:
            return {"code": 400, "message": "Token 不能为空"}

        # 查 sessions 表确认 token 存在
        queryDb = QueryDatabase(self.db_conn)
        result = queryDb.query_table_sessions(token=token, is_active=1)

        if result["code"] != 200 or result["count"] == 0:
            return {"code": 404, "message": "Token 不存在或已失效"}

        session = result["data"][0]

        # 置为无效(调用 UpdateDatabase.update_table_sessions )
        updateDb = UpdateDatabase(self.db_conn)
        updateDb.update_table_sessions(
            session_id=session["session_id"],
            is_active=0
        )

        # 日志: Token 撤销成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"Token 撤销成功: session_id={session['session_id']}")
        return {"code": 200, "message": "Token 撤销成功,已退出登录"}

    # ====================================================================
    # 获取 Token 信息(不验证有效性,仅查询)
    # ====================================================================
    def getTokenInfo(self, token: str):
        """
        获取 token 详细信息(不验证有效性,仅查询)
        查询 sessions 表

        :param token: token字符串<str>
        :return: dict {"code": 200/404, "message": "...", "data": {...}}
        """
        if not token:
            return {"code": 400, "message": "Token 不能为空"}

        queryDb = QueryDatabase(self.db_conn)
        result = queryDb.query_table_sessions(token=token)

        if result["code"] != 200 or result["count"] == 0:
            return {"code": 404, "message": "Token 不存在"}

        session = result["data"][0]
        return {
            "code": 200,
            "message": "查询成功",
            "data": {
                "session_id": session["session_id"],
                "session_uuid": session["session_uuid"],
                "user_id": session["user_id"],
                "token": session["token"],
                "created_at": session["created_at"],
                "expires_at": session["expires_at"],
                "is_active": session["is_active"]
            }
        }

    # ====================================================================
    # 刷新 Token(手动续期 → 签发全新 token)
    # ====================================================================
    def refreshTokenExpiry(self, token: str):
        """
        刷新 token(手动续期,活跃操作时按需调用)
        签发全新 token,旧 token 立即失效

        :param token: 当前 token 字符串<str>
        :return: dict {"code": 200/400/401, "message": "...", "new_token": "..."}
        """
        # 先验证有效性
        result = self.verifyToken(token)
        if result["code"] != 200:
            return result

        userInfo = result["data"]
        role = userInfo["role"]

        # 查旧 session 获取 session_id / session_uuid
        queryDb = QueryDatabase(self.db_conn)
        queryResult = queryDb.query_table_sessions(token=token, is_active=1)
        if queryResult["code"] != 200 or queryResult["count"] == 0:
            return {"code": 401, "message": "Token 不存在"}

        oldSession = queryResult["data"][0]

        # 生成新 token
        newToken = self.__generateTokenStr()
        newExpiresAt = self.__getExpireTime(role)

        # 撤销旧 token(调用 UpdateDatabase.update_table_sessions )
        updateDb = UpdateDatabase(self.db_conn)
        updateDb.update_table_sessions(
            session_id=oldSession["session_id"],
            is_active=0
        )

        # 写入新 token(调用 AddDatabase.add_table_sessions )
        addDb = AddDatabase(self.db_conn)
        addResult = addDb.add_table_sessions(
            session_uuid=self.__generateSessionUuid(),  # 新 session_uuid(sessions 表 UNIQUE 约束)
            user_id=userInfo["user_id"],
            token=newToken,
            expires_at=newExpiresAt
        )

        if addResult["code"] != 200:
            return {"code": 400, "message": f"Token 续期失败: {addResult.get('message', '')}"}

        # 日志: Token 续期成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"Token 续期成功: user_id={userInfo['user_id']}, username={userInfo['username']}")
        return {
            "code": 200,
            "message": "Token 续期成功",
            "new_token": newToken,
            "data": {
                "user_id": userInfo["user_id"],
                "username": userInfo["username"],
                "role": role,
                "expires_at": newExpiresAt
            }
        }

    # ====================================================================
    # 清理过期 Token(定期调用)
    # ====================================================================
    def cleanExpiredTokens(self):
        """
        清理所有过期 token(定期调用)
        查询所有 is_active=1 且已过期的 session,置为无效

        :return: dict {"code": 200, "message": "...", "cleaned_count": int}
        """
        queryDb = QueryDatabase(self.db_conn)
        # 查出所有有效 session
        result = queryDb.query_table_sessions(is_active=1)

        if result["code"] != 200:
            return {"code": 400, "message": "查询会话失败"}

        now = datetime.now()
        cleanedCount = 0
        updateDb = UpdateDatabase(self.db_conn)

        for session in result["data"]:
            try:
                expiresDt = datetime.strptime(session["expires_at"], "%Y-%m-%d %H:%M:%S")
                if now > expiresDt:
                    updateDb.update_table_sessions(
                        session_id=session["session_id"],
                        is_active=0
                    )
                    cleanedCount += 1
            except ValueError:
                continue

        return {
            "code": 200,
            "message": f"清理完成,共清理 {cleanedCount} 个过期 token",
            "cleaned_count": cleanedCount
        }