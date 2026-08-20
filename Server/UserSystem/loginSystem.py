# 20260818
# LF
# 登录系统


import re
import hashlib

# 数据库操作类(QueryDatabase 查用户, UpdateDatabase 更新登录信息)
from database import QueryDatabase, UpdateDatabase

# 日志系统导入(Server/ServerLogSystem)
from ServerLogSystem.logManager import getLogger
from ServerLogSystem.logConfig import CATEGORY_AUTH, INFO, WARNING, ERROR


# ====================================================================
# 正则常量(统一引用,避免拼写错误)
# ====================================================================
# 密码: 英文+数字+特殊字符(排除 .*?/\),不含中文
REGEX_PASSWORD = re.compile(
    r"^[a-zA-Z0-9!@#$%^&()_+\-=\[\]{}|;':\",<>~`]+$"
)

# 邮箱格式(宽松校验: 包含 @ 且 . 不出现在首尾)
REGEX_EMAIL = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# 验证码常量(临时,后续接入托管平台后替换)
TEMP_EMAIL_CODE = "123456"

# 长度限制
IDENTITY_MAX_LEN = 254      # 登录标识最大长度(取邮箱上限)
PASSWORD_MIN_LEN = 6        # 密码最小长度
PASSWORD_MAX_LEN = 18       # 密码最大长度


# ====================================================================
# 登录系统
# ====================================================================
class LoginSystem:
    """
    用户登录系统
    ============
    负责登录流程中各字段的合法性校验 + 数据库验证:
    1. 登录标识校验(用户名或邮箱二选一)
    2. 密码格式校验
    3. 邮箱验证码校验(临时固定值 123456)
    4. 人机验证校验(临时留空)
    5. 数据库查询用户 + 密码哈希验证
    6. 更新最后登录时间

    用法:
        conn = get_connection()
        loginSys = LoginSystem(conn)
        result = loginSys.login("test_user", "password", "123456")
        if result["code"] == 200:
            print(f"登录成功 user_id={result['user_id']}")
    """

    def __init__(self, db_conn):
        """
        初始化登录系统
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(CATEGORY_AUTH)(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __verifyPassword(self, password: str, salt: str, stored_hash: str):
        """
        验证密码: 用存储的盐值对输入密码做 sha256,与数据库 hash 比对

        :param password: 用户输入的明文密码<str>
        :param salt: 数据库中存储的盐值<str>
        :param stored_hash: 数据库中存储的密码哈希<str>
        :return: True=匹配, False=不匹配
        """
        inputHash = hashlib.sha256(
            (salt + password).encode("utf-8")
        ).hexdigest()
        return inputHash == stored_hash

    # ====================================================================
    # 登录标识校验(用户名或邮箱二选一)
    # ====================================================================
    def validateLoginIdentity(self, identity: str):
        """
        校验登录标识合法性
        规则: 支持用户名或邮箱二选一
          - 若包含 @ 则按邮箱格式校验
          - 否则按用户名校验
        """
        if not identity:
            return {"code": 400, "message": "用户名/邮箱不能为空"}

        if len(identity) > IDENTITY_MAX_LEN:
            return {"code": 400, "message": f"登录标识长度不能超过 {IDENTITY_MAX_LEN} 字符"}

        if "@" in identity:
            if not REGEX_EMAIL.match(identity):
                return {"code": 400, "message": "邮箱格式不正确"}
            return {"code": 200, "message": "登录标识校验通过", "identity_type": "email"}

        else:
            return {"code": 200, "message": "登录标识校验通过", "identity_type": "username"}

    # ====================================================================
    # 密码校验
    # ====================================================================
    def validatePassword(self, password: str):
        """
        校验密码合法性
        规则: 6-18字符,英文/数字/特殊字符(排除 .*?/\),不含中文
        """
        if not password:
            return {"code": 400, "message": "密码不能为空"}

        password_len = len(password)
        if password_len < PASSWORD_MIN_LEN or password_len > PASSWORD_MAX_LEN:
            return {"code": 400,
                    "message": f"密码长度需在 {PASSWORD_MIN_LEN}-{PASSWORD_MAX_LEN} 字符之间,当前 {password_len} 字符"}

        if not REGEX_PASSWORD.match(password):
            return {"code": 400, "message": "密码包含非法字符(不允许中文和 .*?/\\)"}

        return {"code": 200, "message": "密码校验通过"}

    # ====================================================================
    # 邮箱验证码校验
    # ====================================================================
    def validateEmailCode(self, input_code: str):
        """
        校验邮箱验证码(临时固定为 123456)
        """
        if not input_code:
            return {"code": 400, "message": "验证码不能为空"}

        if input_code != TEMP_EMAIL_CODE:
            return {"code": 400, "message": "验证码错误"}

        return {"code": 200, "message": "邮箱验证码校验通过"}

    # ====================================================================
    # 人机验证校验
    # ====================================================================
    def validateCaptcha(self, captcha_input: str = None):
        """
        人机验证校验(临时留空)
        """
        return {"code": 200, "message": "人机验证通过"}

    # ====================================================================
    # 登录入口(校验 + 数据库验证)
    # ====================================================================
    def login(
        self,
        identity: str,
        password: str,
        email_code: str,
        captcha_input: str = None
    ):
        """
        登录入口,依次校验所有字段,通过后查询数据库验证密码

        :param identity: 登录标识<str> 用户名或邮箱
        :param password: 密码<str>
        :param email_code: 邮箱验证码<str>
        :param captcha_input: 人机验证输入<str> 暂不使用
        :return: dict {"code": 200/400/401/403, "message": "...", "user_id": int, "data": {...}}
        """
        # 日志: 收到登录请求(不暴露密码)(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"收到登录请求: identity={identity}")

        # 1. 校验登录标识(用户名或邮箱)
        result = self.validateLoginIdentity(identity)
        if result["code"] != 200:
            return result

        identity_type = result["identity_type"]

        # 2. 校验密码格式
        result = self.validatePassword(password)
        if result["code"] != 200:
            return result

        # 3. 校验邮箱验证码
        result = self.validateEmailCode(email_code)
        if result["code"] != 200:
            return result

        # 4. 人机验证
        result = self.validateCaptcha(captcha_input)
        if result["code"] != 200:
            return result

        # ================================================================
        # 校验通过,开始查询数据库验证
        # ================================================================

        # 日志: 字段校验通过(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, "字段校验通过，查询数据库")

        # 5. 根据登录标识类型,查询用户(调用 QueryDatabase.query_table_users )
        queryDb = QueryDatabase(self.db_conn)

        if identity_type == "username":
            queryResult = queryDb.query_table_users(username=identity)
        else:
            queryResult = queryDb.query_table_users(username=identity)
            # 如果用户名查不到,尝试按邮箱的反向逻辑: 数据库中 email 字段匹配
            # 注意: QueryDatabase 没有直接按 email 查的方法,改用 username 组合
            # 实际上按邮箱登录时,先在 users 表中遍历查找 email 匹配
            if queryResult["count"] == 0:
                # 邮箱登录: 用 executeQuery 的通用能力,直接 raw SQL
                # 这里复用 QueryDatabase.__executeQuery 不行(私有方法),改用直接查询
                import sqlite3
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "SELECT * FROM users WHERE email = ?",
                    (identity,)
                )
                rows = cursor.fetchall()
                if rows:
                    queryResult = {
                        "code": 200,
                        "data": [dict(r) for r in rows],
                        "count": len(rows)
                    }

        if queryResult["code"] != 200 or queryResult["count"] == 0:
            # 日志: 用户名或邮箱不存在(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"登录失败: 用户名或邮箱不存在, identity={identity}")
            return {"code": 401, "message": "用户名或邮箱不存在"}

        user = queryResult["data"][0]

        # 6. 检查账户状态
        if user["status"] == "banned":
            # 日志: 账户已被封禁(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"登录失败: 账户已被封禁, username={user['username']}")
            return {"code": 403, "message": "账户已被封禁,请联系管理员"}

        # 7. 验证密码哈希
        if not self.__verifyPassword(password, user["salt"], user["password_hash"]):
            # 日志: 密码错误(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"登录失败: 密码错误, username={user['username']}")
            return {"code": 401, "message": "密码错误"}

        # 8. 更新最后登录时间(调用 UpdateDatabase.update_table_users )
        from datetime import datetime
        nowStr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updateDb = UpdateDatabase(self.db_conn)
        updateDb.update_table_users(
            user_id=user["user_id"],
            last_login_at=nowStr
        )

        # 登录成功
        # 日志: 登录成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"登录成功: username={user['username']}")
        return {
            "code": 200,
            "message": "登录成功",
            "user_id": user["user_id"],
            "data": {
                "user_id": user["user_id"],
                "username": user["username"],
                "nickname": user["nickname"],
                "role": user["role"],
                "email": user["email"]
            }
        }