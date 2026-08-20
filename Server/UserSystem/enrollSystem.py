# 20260818
# LF
# 注册系统


import re
import hashlib
import secrets

# 数据库操作类(AddDatabase 写 users 表, QueryDatabase 查用户名重复)
from database import AddDatabase, QueryDatabase

# 日志系统导入(Server/ServerLogSystem)
from ServerLogSystem.logManager import getLogger
from ServerLogSystem.logConfig import CATEGORY_AUTH, INFO, WARNING, ERROR


# ====================================================================
# 正则常量(统一引用,避免拼写错误)
# ====================================================================
# 昵称/用户名: 中英文+数字+特殊字符(排除 .*?/\)
REGEX_NICKNAME_USERNAME = re.compile(
    r"^[\u4e00-\u9fa5a-zA-Z0-9!@#$%^&()_+\-=\[\]{}|;':\",<>~`]+$"
)

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
NICKNAME_MIN_LEN = 1      # 昵称最小长度
NICKNAME_MAX_LEN = 10     # 昵称最大长度
USERNAME_MIN_LEN = 1      # 用户名最小长度
USERNAME_MAX_LEN = 10     # 用户名最大长度
PASSWORD_MIN_LEN = 6      # 密码最小长度
PASSWORD_MAX_LEN = 18     # 密码最大长度
EMAIL_MAX_LEN = 254       # 邮箱最大长度(RFC 5321)

# 密码学常量
SALT_BYTE_LEN = 16        # 盐值字节数(16字节→32位hex)
UUID_BYTE_LEN = 16        # UUID字节数(16字节→32位hex)


# ====================================================================
# 注册系统
# ====================================================================
class EnrollSystem:
    """
    用户注册系统
    ============
    负责注册流程中各字段的合法性校验 + 数据库写入:
    1. 昵称/用户名/密码/邮箱格式校验
    2. 用户名重复检查(查数据库)
    3. 密码哈希(sha256(salt+password))
    4. 写入 users 表

    用法:
        conn = get_connection()
        enrollSys = EnrollSystem(conn)
        result = enrollSys.enroll("昵称", "用户名", "密码", "确认密码", "email@x.com", "123456")
        if result["code"] == 200:
            print(f"注册成功 user_id={result['user_id']}")
    """

    def __init__(self, db_conn):
        """
        初始化注册系统
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(CATEGORY_AUTH)(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __hashPassword(self, password: str):
        """
        对密码进行哈希处理
        算法: sha256(salt + password)
        盐值: 随机 32 位 hex

        :param password: 明文密码<str>
        :return: (password_hash<str>, salt<str>)
        """
        salt = secrets.token_hex(SALT_BYTE_LEN)  # 32位hex
        hashVal = hashlib.sha256(
            (salt + password).encode("utf-8")
        ).hexdigest()  # 64位hex
        return hashVal, salt

    def __generateUuid(self):
        """
        生成用户唯一标识 UUID(32位hex)

        :return: uuid<str>
        """
        return secrets.token_hex(UUID_BYTE_LEN)

    # ====================================================================
    # 昵称校验
    # ====================================================================
    def validateNickname(self, nickname: str):
        """
        校验昵称合法性
        规则: 1-10字符,中英文/数字/特殊字符(排除 .*?/\)
        """
        if not nickname:
            return {"code": 400, "message": "昵称不能为空"}

        nickname_len = len(nickname)
        if nickname_len < NICKNAME_MIN_LEN or nickname_len > NICKNAME_MAX_LEN:
            return {"code": 400,
                    "message": f"昵称长度需在 {NICKNAME_MIN_LEN}-{NICKNAME_MAX_LEN} 字符之间,当前 {nickname_len} 字符"}

        if not REGEX_NICKNAME_USERNAME.match(nickname):
            return {"code": 400, "message": "昵称包含非法字符(不允许 .*?/\\)"}

        return {"code": 200, "message": "昵称校验通过"}

    # ====================================================================
    # 用户名校验
    # ====================================================================
    def validateUsername(self, username: str):
        """
        校验用户名合法性
        规则: 1-10字符,中英文/数字/特殊字符(排除 .*?/\)
        """
        if not username:
            return {"code": 400, "message": "用户名不能为空"}

        username_len = len(username)
        if username_len < USERNAME_MIN_LEN or username_len > USERNAME_MAX_LEN:
            return {"code": 400,
                    "message": f"用户名长度需在 {USERNAME_MIN_LEN}-{USERNAME_MAX_LEN} 字符之间,当前 {username_len} 字符"}

        if not REGEX_NICKNAME_USERNAME.match(username):
            return {"code": 400, "message": "用户名包含非法字符(不允许 .*?/\\)"}

        return {"code": 200, "message": "用户名校验通过"}

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
    # 密码确认校验
    # ====================================================================
    def validatePasswordConfirm(self, password: str, confirm_password: str):
        """
        校验两次密码是否一致
        """
        if password != confirm_password:
            return {"code": 400, "message": "两次输入的密码不一致"}

        return {"code": 200, "message": "密码确认通过"}

    # ====================================================================
    # 邮箱格式校验
    # ====================================================================
    def validateEmail(self, email: str):
        """
        校验邮箱格式合法性
        """
        if not email:
            return {"code": 400, "message": "邮箱不能为空"}

        if len(email) > EMAIL_MAX_LEN:
            return {"code": 400, "message": f"邮箱长度不能超过 {EMAIL_MAX_LEN} 字符"}

        if not REGEX_EMAIL.match(email):
            return {"code": 400, "message": "邮箱格式不正确"}

        return {"code": 200, "message": "邮箱格式校验通过"}

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
    # 注册入口(校验 + 写库)
    # ====================================================================
    def enroll(
        self,
        nickname: str,
        username: str,
        password: str,
        confirm_password: str,
        email: str,
        email_code: str,
        captcha_input: str = None
    ):
        """
        注册入口,依次校验所有字段,通过后写入 users 表

        :param nickname: 昵称<str>
        :param username: 用户名<str>
        :param password: 密码<str>
        :param confirm_password: 确认密码<str>
        :param email: 邮箱<str>
        :param email_code: 邮箱验证码<str>
        :param captcha_input: 人机验证输入<str> 暂不使用
        :return: dict {"code": 200/400, "message": "...", "user_id": int, "data": {...}}
        """
        # 日志: 收到注册请求(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"收到注册请求: username={username}")

        # 1. 校验昵称
        result = self.validateNickname(nickname)
        if result["code"] != 200:
            # 日志: 昵称校验失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 昵称校验失败, username={username}, reason={result['message']}")
            return result

        # 2. 校验用户名
        result = self.validateUsername(username)
        if result["code"] != 200:
            # 日志: 用户名校验失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 用户名校验失败, username={username}, reason={result['message']}")
            return result

        # 3. 校验密码
        result = self.validatePassword(password)
        if result["code"] != 200:
            # 日志: 密码校验失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 密码校验失败, username={username}, reason={result['message']}")
            return result

        # 4. 校验两次密码一致
        result = self.validatePasswordConfirm(password, confirm_password)
        if result["code"] != 200:
            # 日志: 密码确认失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 密码确认失败, username={username}, reason={result['message']}")
            return result

        # 5. 校验邮箱格式
        result = self.validateEmail(email)
        if result["code"] != 200:
            # 日志: 邮箱校验失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 邮箱校验失败, username={username}, reason={result['message']}")
            return result

        # 6. 校验邮箱验证码
        result = self.validateEmailCode(email_code)
        if result["code"] != 200:
            # 日志: 邮箱验证码校验失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 邮箱验证码校验失败, username={username}, reason={result['message']}")
            return result

        # 7. 人机验证
        result = self.validateCaptcha(captcha_input)
        if result["code"] != 200:
            # 日志: 人机验证失败(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 人机验证失败, username={username}, reason={result['message']}")
            return result

        # ================================================================
        # 校验通过,开始写入数据库
        # ================================================================

        # 8. 检查用户名是否已被占用(调用 QueryDatabase.query_table_users )
        queryDb = QueryDatabase(self.db_conn)
        queryResult = queryDb.query_table_users(username=username)
        if queryResult["code"] == 200 and queryResult["count"] > 0:
            # 日志: 用户名已被注册(调用 ServerLogSystem.logManager->warning )
            self._logger.warning(CATEGORY_AUTH, f"注册失败: 用户名已被注册, username={username}")
            return {"code": 400, "message": f"用户名 {username} 已被注册"}

        # 9. 生成 UUID 和密码哈希
        uuid = self.__generateUuid()
        password_hash, salt = self.__hashPassword(password)

        # 10. 写入 users 表(调用 AddDatabase.add_table_users )
        addDb = AddDatabase(self.db_conn)
        result = addDb.add_table_users(
            uuid=uuid,
            username=username,
            email=email,
            password_hash=password_hash,
            salt=salt,
            nickname=nickname
        )

        if result["code"] != 200:
            # 日志: 数据库写入失败(调用 ServerLogSystem.logManager->error )
            self._logger.error(CATEGORY_AUTH, f"注册失败: 数据库写入失败, username={username}, reason={result.get('message', '')}")
            return result

        # 注册成功
        # 日志: 注册成功(调用 ServerLogSystem.logManager->info )
        self._logger.info(CATEGORY_AUTH, f"注册成功: username={username}")
        return {
            "code": 200,
            "message": "注册成功",
            "user_id": result["user_id"],
            "data": {
                "user_id": result["user_id"],
                "uuid": uuid,
                "username": username,
                "nickname": nickname,
                "email": email
            }
        }