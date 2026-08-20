# 20260819
# LF
# 自动登录 Cookie 签发与验证系统


import secrets
from datetime import datetime, timedelta

# 数据库操作类
# AddDatabase    → add_table_auto_login_cookies    (签发 cookie 时写入 auto_login_cookies 表)
# QueryDatabase  → query_table_auto_login_cookies  (验证 cookie 时查询 auto_login_cookies 表)
# UpdateDatabase → update_table_auto_login_cookies (撤销/续期 cookie 时更新 auto_login_cookies 表)
from database import AddDatabase, QueryDatabase, UpdateDatabase

# 日志系统导入(Server/ServerLogSystem)
from ServerLogSystem.logManager import getLogger
from ServerLogSystem.logConfig import CATEGORY_AUTH, INFO, WARNING, ERROR


# ====================================================================
# 常量
# ====================================================================
COOKIE_BYTE_LEN = 32       # Cookie 随机字节数(32字节→64位hex)
COOKIE_EXPIRE_DAYS = 7     # Cookie 有效期(天): 一周未登录则到期失效


# ====================================================================
# 自动登录 Cookie 管理器
# ====================================================================
class CookieManager:
    """
    自动登录 Cookie 签发与验证管理器
    ==================================
    用户勾选"自动登录"登录成功后签发 cookie,绑定 IP + 设备识别码,一周有效。
    下次进入软件时,凭 cookie + 当前 IP + 设备识别码做匹配,一致则自动登录。

    设计要点:
    1. cookie 为 64 位随机 hex(secrets 保证密码学安全,不可伪造)
    2. cookie 绑定 ip_address + device_code,二者任一变则判定为异地/异设备
    3. 有效期 7 天,每次登录成功后调用 refreshCookieExpiry 刷新有效期
    4. 到期或 ip/设备不匹配 → 撤销 cookie(is_valid=0),要求手动登录并重发新 cookie

    用法:
        conn = get_connection()
        cm = CookieManager(conn)
        result = cm.generateCookie(user_id=1, ip="192.168.1.5", device_code="ABC123")
        cookie = result["cookie"]
    """

    def __init__(self, db_conn):
        """
        初始化 Cookie 管理器
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(CATEGORY_AUTH)(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __generateCookieStr(self):
        """
        生成随机 cookie 字符串(64位hex)
        使用 secrets.token_hex 保证密码学安全

        :return: cookie字符串<str>
        """
        return secrets.token_hex(COOKIE_BYTE_LEN)

    def __getExpireTime(self):
        """
        计算 cookie 过期时间(一周后,datetime 字符串格式)

        :return: 过期时间<str> 格式 "YYYY-MM-DD HH:MM:SS"
        """
        expireDt = datetime.now() + timedelta(days=COOKIE_EXPIRE_DAYS)
        return expireDt.strftime("%Y-%m-%d %H:%M:%S")

    def __isExpired(self, expiresAtStr: str):
        """
        判断 cookie 是否已过期

        :param expiresAtStr: 过期时间字符串<str>
        :return: True=已过期, False=未过期
        """
        try:
            expiresDt = datetime.strptime(expiresAtStr, "%Y-%m-%d %H:%M:%S")
            return datetime.now() > expiresDt
        except ValueError:
            return True  # 格式异常视为已过期

    def __revokeAllUserCookies(self, user_id: int):
        """
        撤销该用户所有有效 cookie(重新勾选自动登录时调用,保证旧 cookie 失效)
        调用 UpdateDatabase.update_table_auto_login_cookies 置 is_valid=0

        :param user_id: 用户ID<int>
        """
        queryDb = QueryDatabase(self.db_conn)
        # 查出该用户所有有效 cookie
        result = queryDb.query_table_auto_login_cookies(user_id=user_id, is_valid=1)
        if result["code"] == 200 and result["count"] > 0:
            updateDb = UpdateDatabase(self.db_conn)
            for cookie in result["data"]:
                updateDb.update_table_auto_login_cookies(
                    cookie_id=cookie["cookie_id"],
                    is_valid=0
                )

    # ====================================================================
    # 签发 Cookie(登录成功且勾选"自动登录"时调用)
    # ====================================================================
    def generateCookie(self, user_id: int, ip: str, device_code: str):
        """
        签发新的自动登录 cookie
        写入 auto_login_cookies 表,同时撤销该用户的所有旧 cookie

        :param user_id: 用户ID<int>
        :param ip: 登录机器 IP<str>
        :param device_code: 登录设备识别码<str>
        :return: dict {"code": 200/400, "message": "...", "cookie": "...", "data": {...}}
        """
        # 参数校验
        if not ip or not device_code:
            return {"code": 400, "message": "IP 与设备识别码不能为空"}

        # 生成 cookie 与过期时间
        cookie = self.__generateCookieStr()
        expiresAt = self.__getExpireTime()

        # 撤销该用户的所有旧 cookie(一个用户同一时间只保留一个有效 cookie)
        self.__revokeAllUserCookies(user_id)

        # 写入 auto_login_cookies 表(调用 AddDatabase.add_table_auto_login_cookies )
        addDb = AddDatabase(self.db_conn)
        result = addDb.add_table_auto_login_cookies(
            user_id=user_id,
            cookie=cookie,
            ip_address=ip,
            device_code=device_code,
            expires_at=expiresAt
        )

        if result["code"] != 200:
            return {"code": 400, "message": f"Cookie 签发失败: {result.get('message', '')}"}

        # 日志: Cookie 签发成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"自动登录 Cookie 签发成功: user_id={user_id}")
        return {
            "code": 200,
            "message": "Cookie 签发成功",
            "cookie": cookie,
            "data": {
                "user_id": user_id,
                "ip_address": ip,
                "device_code": device_code,
                "expires_at": expiresAt
            }
        }

    # ====================================================================
    # 验证 Cookie(自动登录时调用,校验 ip + 设备识别码 + 有效期)
    # ====================================================================
    def verifyCookie(self, cookie: str, ip: str, device_code: str):
        """
        验证自动登录 cookie 是否有效
        校验顺序: 存在性 → 有效性(is_valid) → 有效期(expires_at) → ip 匹配 → 设备识别码匹配
        任一不满足 → 撤销该 cookie(is_valid=0),要求手动登录

        :param cookie: cookie字符串<str>
        :param ip: 当前登录机器 IP<str>
        :param device_code: 当前设备识别码<str>
        :return: dict {
            "code": 200/400/401,
            "message": "...",
            "data": {"cookie_id":..., "user_id":..., "expires_at":...}
        }
        """
        # 空值检查
        if not cookie:
            return {"code": 400, "message": "Cookie 不能为空"}

        # 查询 auto_login_cookies 表(只看有效记录)
        queryDb = QueryDatabase(self.db_conn)
        result = queryDb.query_table_auto_login_cookies(cookie=cookie, is_valid=1)

        if result["code"] != 200 or result["count"] == 0:
            return {"code": 401, "message": "Cookie 不存在或已失效"}

        cookieRow = result["data"][0]
        cookieId = cookieRow["cookie_id"]

        # 校验有效期(过期则撤销)
        if self.__isExpired(cookieRow["expires_at"]):
            self.revokeCookie(cookie)
            self._logger.warning(CATEGORY_AUTH, "自动登录 Cookie 已到期,需手动登录")
            return {"code": 401, "message": "Cookie 已到期,请手动登录"}

        # 校验 ip 匹配(不一致则撤销,防止异地登录)
        if cookieRow["ip_address"] != ip:
            self.revokeCookie(cookie)
            self._logger.warning(CATEGORY_AUTH, "自动登录 Cookie 的 IP 不匹配,已撤销")
            return {"code": 401, "message": "IP 不匹配,请手动登录"}

        # 校验设备识别码匹配(不一致则撤销,防止异设备登录)
        if cookieRow["device_code"] != device_code:
            self.revokeCookie(cookie)
            self._logger.warning(CATEGORY_AUTH, "自动登录 Cookie 的设备识别码不匹配,已撤销")
            return {"code": 401, "message": "设备识别码不匹配,请手动登录"}

        # 校验通过
        self._logger.info(CATEGORY_AUTH, f"自动登录 Cookie 验证通过: user_id={cookieRow['user_id']}")
        return {
            "code": 200,
            "message": "Cookie 验证通过",
            "data": {
                "cookie_id": cookieId,
                "user_id": cookieRow["user_id"],
                "expires_at": cookieRow["expires_at"]
            }
        }

    # ====================================================================
    # 撤销 Cookie(登出/校验失败时调用)
    # ====================================================================
    def revokeCookie(self, cookie: str):
        """
        撤销指定的自动登录 cookie(置 is_valid=0)
        用于: 异地/异设备登录取消权限、cookie 到期失效、用户主动关闭自动登录

        :param cookie: cookie字符串<str>
        :return: dict {"code": 200/400/404, "message": "..."}
        """
        if not cookie:
            return {"code": 400, "message": "Cookie 不能为空"}

        # 查 auto_login_cookies 表确认 cookie 存在
        queryDb = QueryDatabase(self.db_conn)
        result = queryDb.query_table_auto_login_cookies(cookie=cookie)

        if result["code"] != 200 or result["count"] == 0:
            return {"code": 404, "message": "Cookie 不存在"}

        cookieRow = result["data"][0]

        # 置为无效(调用 UpdateDatabase.update_table_auto_login_cookies )
        updateDb = UpdateDatabase(self.db_conn)
        updateDb.update_table_auto_login_cookies(
            cookie_id=cookieRow["cookie_id"],
            is_valid=0
        )

        # 日志: Cookie 撤销成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"自动登录 Cookie 撤销成功: cookie_id={cookieRow['cookie_id']}")
        return {"code": 200, "message": "Cookie 已撤销"}

    # ====================================================================
    # 刷新 Cookie 有效期(每次登录成功后调用)
    # ====================================================================
    def refreshCookieExpiry(self, cookie: str, ip: str, device_code: str):
        """
        刷新 cookie 有效期(登录成功后延期一周)
        先验证有效性,再更新 expires_at 为"当前时间 + 7 天"

        :param cookie: cookie字符串<str>
        :param ip: 当前登录机器 IP<str>
        :param device_code: 当前设备识别码<str>
        :return: dict {"code": 200/401, "message": "...", "expires_at": "..."}
        """
        # 先验证有效性(IP/设备码/有效期一致才可续期)
        verifyResult = self.verifyCookie(cookie, ip, device_code)
        if verifyResult["code"] != 200:
            return verifyResult

        cookieId = verifyResult["data"]["cookie_id"]
        newExpiresAt = self.__getExpireTime()

        # 更新过期时间(调用 UpdateDatabase.update_table_auto_login_cookies )
        updateDb = UpdateDatabase(self.db_conn)
        updateDb.update_table_auto_login_cookies(
            cookie_id=cookieId,
            expires_at=newExpiresAt
        )

        # 日志: Cookie 续期成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"自动登录 Cookie 续期成功: cookie_id={cookieId}")
        return {
            "code": 200,
            "message": "Cookie 续期成功",
            "expires_at": newExpiresAt
        }