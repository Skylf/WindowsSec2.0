# 20260817
# LF
# SqlLite数据库


import sqlite3
import os

# 日志系统导入(Server/ServerLogSystem)
from ServerLogSystem.logManager import getLogger
from ServerLogSystem.logConfig import CATEGORY_DATABASE, ERROR


# 用户表
DATA_BASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DataBase/users.db")

# ====================================================================
# SQLite 字段类型常量(建表/加字段统一引用,避免拼写错误)
# ====================================================================
TYPE_TEXT = "TEXT"          # 字符串
TYPE_INTEGER = "INTEGER"    # 整数
TYPE_REAL = "REAL"          # 浮点数
TYPE_BLOB = "BLOB"          # 二进制(如图片字节)
TYPE_NUMERIC = "NUMERIC"    # 数值(布尔/日期可存为 NUMERIC)

# 返回值通用设定：{"code": 404, "message": f"表 {table} 不存在,跳过添加字段"}


# 初始化数据库
def init_db(op, db_conn):
    """
    :param op: 操作权限
    :param db_conn: 数据库对象
    :return:
    """


    if op == "admin":
        # 获取数据库
        conn = db_conn

        # 日志: 开始初始化数据库(调用 ServerLogSystem.logManager->getLogger )
        logger = getLogger()
        logger.info(CATEGORY_DATABASE, "开始初始化数据库")

        # 初始化数据库
        try:
            cursor = conn.cursor()

            # 用户基础信息表
            # CHECK 约束说明(SQLite 3.3.0+ 支持列级 CHECK,3.25.0+ 支持表级外键 ON DELETE):
            #   - 长度约束: 防止异常大文本撑爆库
            #   - 枚举约束: status/role 只能取固定值,避免脏数据
            #   - 格式约束: email 包含 @,uuid/salt 固定 hex 长度
            # 注意: users 表补回 salt 字段(之前 __add_table_users__ 有此参数,建表漏了)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid          TEXT NOT NULL UNIQUE
                                  CHECK (LENGTH(uuid) = 32),
                    username      TEXT NOT NULL UNIQUE
                                  CHECK (LENGTH(username) BETWEEN 1 AND 10),
                    email         TEXT
                                  CHECK (email IS NULL OR (LENGTH(email) <= 254 AND email LIKE '%@%')),
                    password_hash TEXT NOT NULL
                                  CHECK (LENGTH(password_hash) BETWEEN 40 AND 128),
                    salt          TEXT NOT NULL
                                  CHECK (LENGTH(salt) = 32),
                    nickname      TEXT
                                  CHECK (nickname IS NULL OR LENGTH(nickname) <= 20),
                    avatar_path   TEXT
                                  CHECK (avatar_path IS NULL OR LENGTH(avatar_path) <= 255),
                    status        TEXT NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active', 'banned')),
                    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    last_login_at TEXT,
                    last_login_ip TEXT
                                  CHECK (last_login_ip IS NULL OR LENGTH(last_login_ip) <= 45),
                    device_code   TEXT
                                  CHECK (device_code IS NULL OR LENGTH(device_code) <= 128),
                    role          TEXT NOT NULL DEFAULT 'user'
                                  CHECK (role IN ('user', 'admin'))
                )
            """)

            # 加速登录与查询(username / uuid 是高频查询字段)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_uuid ON users(uuid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")

            # 迁移: 旧库的 users 表没有 device_code 字段,补上(SQLite 的 CREATE TABLE IF NOT EXISTS 不会改已存在的表结构)
            cursor.execute("PRAGMA table_info(users)")
            userColumns = [row[1] for row in cursor.fetchall()]
            if "device_code" not in userColumns:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN device_code TEXT "
                    "CHECK (device_code IS NULL OR LENGTH(device_code) <= 128)"
                )
                logger.info(CATEGORY_DATABASE, "users 表已补充 device_code 字段")


            # 用户人脸特征绑定表
            #   一个用户可绑定多份人脸特征(多场景录入),其中一份为主特征
            #   人脸特征本身存 .npy+.json 文件,本表只做路径映射
            # CHECK 约束: 文件路径长度(Windows 路径上限 260 字符)、is_primary 只能 0/1
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_face_bindings (
                    binding_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id           INTEGER NOT NULL,
                    feature_file_path TEXT NOT NULL
                                      CHECK (LENGTH(feature_file_path) <= 255),
                    meta_file_path    TEXT
                                      CHECK (meta_file_path IS NULL OR LENGTH(meta_file_path) <= 255),
                    is_primary        INTEGER NOT NULL DEFAULT 0
                                      CHECK (is_primary IN (0, 1)),
                    enrolled_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    remark            TEXT
                                      CHECK (remark IS NULL OR LENGTH(remark) <= 100),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_face_bindings_user    ON user_face_bindings(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_face_bindings_primary ON user_face_bindings(user_id, is_primary)")

            # ====================================================================
            # 3. login_logs — 登录日志表
            #    成功/失败全记录,支撑登录失败锁定、异地登录告警、审计
            # CHECK 约束: login_method 枚举、success 布尔值、fail_reason 枚举
            # ====================================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS login_logs (
                    log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id          INTEGER,
                    username_attempt TEXT NOT NULL
                                     CHECK (LENGTH(username_attempt) <= 50),
                    login_method     TEXT NOT NULL
                                     CHECK (login_method IN ('password', 'face')),
                    success          INTEGER NOT NULL
                                     CHECK (success IN (0, 1)),
                    ip               TEXT
                                     CHECK (ip IS NULL OR LENGTH(ip) <= 45),
                    device_info      TEXT
                                     CHECK (device_info IS NULL OR LENGTH(device_info) <= 255),
                    fail_reason      TEXT
                                     CHECK (fail_reason IS NULL OR fail_reason IN (
                                         'wrong_password', 'account_banned',
                                         'face_mismatch', 'liveness_fail'
                                     )),
                    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_user_time  ON login_logs(user_id, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_username   ON login_logs(username_attempt)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_success    ON login_logs(success, created_at)")

            # ====================================================================
            # 4. sessions — 会话表
            #    支持"当前在线查看""强制下线""单点登录限制""会话过期"
            # CHECK 约束: session_uuid 固定 32 字符、token 合理上限、is_active 布尔值
            # ====================================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_uuid TEXT NOT NULL UNIQUE
                                 CHECK (LENGTH(session_uuid) = 32),
                    user_id      INTEGER NOT NULL,
                    token        TEXT NOT NULL
                                 CHECK (LENGTH(token) BETWEEN 16 AND 512),
                    ip           TEXT
                                 CHECK (ip IS NULL OR LENGTH(ip) <= 45),
                    device_info  TEXT
                                 CHECK (device_info IS NULL OR LENGTH(device_info) <= 255),
                    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    expires_at   TEXT NOT NULL,
                    is_active    INTEGER NOT NULL DEFAULT 1
                                 CHECK (is_active IN (0, 1)),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user   ON sessions(user_id, is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_uuid   ON sessions(session_uuid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expire ON sessions(expires_at)")

            # ====================================================================
            # 4.5 auto_login_cookies — 自动登录 Cookie 表
            #    用户勾选"自动登录"后签发 cookie,绑定 IP + 设备识别码,一周有效
            #    CHECK 约束: cookie 固定 64 位 hex、ip/device_code 长度上限、is_valid 布尔
            # ====================================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_login_cookies (
                    cookie_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    cookie        TEXT NOT NULL UNIQUE
                                  CHECK (LENGTH(cookie) = 64),
                    ip_address    TEXT NOT NULL
                                  CHECK (LENGTH(ip_address) <= 45),
                    device_code   TEXT NOT NULL
                                  CHECK (LENGTH(device_code) <= 128),
                    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    expires_at    TEXT NOT NULL,
                    is_valid      INTEGER NOT NULL DEFAULT 1
                                  CHECK (is_valid IN (0, 1)),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cookies_user   ON auto_login_cookies(user_id, is_valid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cookies_cookie ON auto_login_cookies(cookie)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cookies_expire ON auto_login_cookies(expires_at)")

            # ====================================================================
            # 5. operation_logs — 用户操作日志表
            #    记录用户(尤其管理员)的关键操作,审计用
            # CHECK 约束: action 枚举(固定 8 种操作)、detail/display 长度上限
            # ====================================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER,
                    action     TEXT NOT NULL
                               CHECK (action IN (
                                   'CREATE_USER', 'DELETE_USER', 'RESET_PASSWORD',
                                   'BAN_USER', 'UNBAN_USER', 'CHANGE_ROLE',
                                   'DELETE_FACE', 'ENROLL_FACE'
                               )),
                    target_id  INTEGER,
                    target     TEXT
                               CHECK (target IS NULL OR LENGTH(target) <= 100),
                    detail     TEXT
                               CHECK (detail IS NULL OR LENGTH(detail) <= 2000),
                    ip         TEXT
                               CHECK (ip IS NULL OR LENGTH(ip) <= 45),
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_logs_user_time ON operation_logs(user_id, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_logs_action    ON operation_logs(action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_logs_target    ON operation_logs(target_id)")


            conn.commit()

            # 日志: 数据库初始化完成
            logger.info(CATEGORY_DATABASE, "数据库初始化完成")

            return {"code": 200, "message": "操作成功！"}

        # 注意: 不在此关闭连接,由调用方通过 get_connection() 管理连接生命周期
        except Exception as e:
            return {"code": 400, "message": f"错误：{e} "}
    else:
        return {"code": 503, "message": "权限不足！"}


# 连接数据库
def get_connection():
    """
        获取数据库连接
        每次操作新建连接,用完即关(SQLite 连接很轻,无需池化)
        :return: sqlite3.Connection 连接对象
        """
    # 日志: 获取数据库连接(调用 ServerLogSystem.logManager->getLogger )
    logger = getLogger()
    logger.info(CATEGORY_DATABASE, "获取数据库连接")

    # check_same_thread=False 允许跨线程使用同一连接
    # 但更推荐每个线程各开各的连接,避免并发问题
    conn = sqlite3.connect(DATA_BASE_PATH, check_same_thread=False)
    # 让查询结果可以用列名访问(row['username']),默认只能用下标 row[0]
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式:读写可并发,大幅减少 database is locked
    conn.execute("PRAGMA journal_mode=WAL")
    # 开启外键约束(SQLite 默认关闭,这点和 MySQL 不同)
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


# ========= 增加数据 ==========
class AddDatabase:
    """
    数据库添加数据操作类
    =====================
    封装 5 张表的 INSERT 操作,统一管理:
    1. 表存在性检查
    2. 外键关联验证
    3. 字段存在性检查
    4. 动态拼 SQL(防注入)
    5. 事务提交

    用法:
        conn = get_connection()
        addDb = AddDatabase(conn)
        result = addDb.add_table_users(uuid=..., username=..., ...)
    """

    def __init__(self, db_conn):
        """
        初始化添加数据操作对象
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __checkTableExists(self, table):
        """
        检查表是否存在
        :param table: 表名<str>
        :return: True=存在, False=不存在
        """
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return cursor.fetchone() is not None

    def __checkColumnExists(self, table, column):
        """
        检查字段是否存在
        :param table: 表名<str>
        :param column: 字段名<str>
        :return: True=存在, False=不存在
        """
        cursor = self.db_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column in columns

    def __checkForeignKeyExists(self, table, tableId, tableIdValue):
        """
        检查外键关联记录是否存在
        即: 查询表中是否存在指定 id 的记录(用于验证 user_id 等外键)
        :param table: 表名<str>
        :param tableId: 表的主键字段名<str>
        :param tableIdValue: 主键值<int>
        :return: True=存在, False=不存在
        """
        cursor = self.db_conn.cursor()
        cursor.execute(f"SELECT {tableId} FROM {table} WHERE {tableId} = ?", (tableIdValue,))
        return cursor.fetchone() is not None

    def __buildInsertSQL(self, table, argsDict):
        """
        根据字段字典动态拼 INSERT 语句并执行(核心通用方法)
        步骤: 检查表存在→检查字段存在→拼 SQL→执行→提交

        :param table: 表名<str>
        :param argsDict: 字段名→值的字典<dict>
        :return: dict {"code": 200/400/404, "message": "...", "lastrowid": int}
        """
        try:
            # 1. 检查表是否存在
            if not self.__checkTableExists(table):
                return {"code": 404, "message": f"操作失败！表 {table} 不存在"}

            # 2. 检查字段是否存在
            for field in argsDict.keys():
                if not self.__checkColumnExists(table, field):
                    return {"code": 400, "message": f"操作失败！字段 {field} 不存在于 {table} 表！"}

            # 3. 动态拼 INSERT 语句(字段名拼SQL,值走 ? 占位符)
            fieldNames = list(argsDict.keys())
            fieldSql = ", ".join(fieldNames)
            placeholderSql = ", ".join(["?"] * len(fieldNames))
            fieldValues = [argsDict[f] for f in fieldNames]

            cursor = self.db_conn.cursor()
            cursor.execute(
                f"INSERT INTO {table} ({fieldSql}) VALUES ({placeholderSql})",
                tuple(fieldValues)
            )

            # 4. 提交事务
            self.db_conn.commit()

            return {"code": 200, "lastrowid": cursor.lastrowid}

        except Exception as e:
            # 回滚失败事务,释放写锁,避免残留事务导致后续写库(如日志表)失败
            self.db_conn.rollback()
            # 日志: 数据库INSERT失败(调用 ServerLogSystem.logManager->error )
            self._logger.error(CATEGORY_DATABASE, f"数据库INSERT失败: {e}")
            return {"code": 400, "message": f"错误：{e}"}

    # ====================================================================
    # 5 张表的添加方法
    # ====================================================================
    def add_table_users(
        self,
        user_id: int = None,              # 序号(主键,自增) 默认
        uuid: str = None,                 # 用户唯一标识(32位hex) 必须有
        username: str = None,             # 用户名(唯一) 必须有
        email: str = None,                # 邮箱
        password_hash: str = None,        # 密码哈希(PBKDF2/bcrypt) 必须有
        salt: str = None,                 # 密码盐值 必须有
        nickname: str = None,             # 昵称(允许重复)
        avatar_path: str = None,          # 用户头像路径
        status: str = None,               # 账户状态: active(正常) / banned(已封禁) 默认
        created_at: str = None,           # 创建时间(精确到秒) 默认
        last_login_at: str = None,        # 最后登录时间(精确到秒) 注册不需要
        last_login_ip: str = None,        # 最后登录IP 注册不需要
        role: str = None,                 # 角色: user(普通用户) / admin(管理员) 默认
        db_conn = None                    # 数据库连接对象(兼容旧接口,实际使用 self.db_conn)
    ):
        # 接收参数,构造最终字典,去除有默认值的参数
        argsDict = {
            "uuid": uuid,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "salt": salt,
            "nickname": nickname,
            "avatar_path": avatar_path,
        }

        result = self.__buildInsertSQL("users", argsDict)
        if result["code"] == 200:
            result["message"] = "添加用户成功！"
            result["user_id"] = result["lastrowid"]
        return result

    def add_table_user_face_bindings(
        self,
        binding_id: int = None,           # 序号(主键,自增) 默认
        user_id: int = None,              # 关联用户ID(外键→users.user_id) 必须有
        feature_file_path: str = None,    # .npy特征文件路径(相对cache/faceData) 必须有
        meta_file_path: str = None,       # .json元数据文件路径
        is_primary: int = None,           # 是否主特征: 1=主特征(登录优先) / 0=备用 默认
        enrolled_at: str = None,          # 录入时间(精确到秒) 默认
        remark: str = None,               # 录入备注(如"办公室白天录入")
        db_conn = None                    # 数据库连接对象
    ):
        # 外键验证: 关联的 user_id 必须存在于 users 表
        if not self.__checkForeignKeyExists("users", "user_id", user_id):
            return {"code": 400, "message": f"操作失败！关联用户ID={user_id} 不存在于 users 表"}

        # 接收参数,构造最终字典,去除有默认值的参数
        argsDict = {
            "user_id": user_id,
            "feature_file_path": feature_file_path,
            "meta_file_path": meta_file_path,
            "is_primary": is_primary,
            "remark": remark,
        }

        result = self.__buildInsertSQL("user_face_bindings", argsDict)
        if result["code"] == 200:
            result["message"] = f"添加人脸绑定成功！绑定ID={result['lastrowid']}"
        return result

    def add_table_login_logs(
        self,
        log_id: int = None,               # 序号(主键,自增) 默认
        user_id: int = None,              # 登录用户ID(失败且用户名不存在时为NULL)
        username_attempt: str = None,     # 尝试输入的用户名(防穷举) 必须有
        login_method: str = None,         # 登录方式: password(密码) / face(人脸) 必须有
        success: int = None,              # 是否成功: 0=失败 / 1=成功 必须有
        ip: str = None,                   # 登录来源IP
        device_info: str = None,          # 设备信息/标识
        fail_reason: str = None,          # 失败原因: wrong_password/account_banned/face_mismatch/liveness_fail
        created_at: str = None,           # 记录时间(精确到秒) 默认
        db_conn = None                    # 数据库连接对象
    ):
        # 外键验证: user_id 不为空时,检查是否存在于 users 表
        #    login_logs 的 user_id 允许 NULL(登录失败时用户名不存在)
        if user_id is not None:
            if not self.__checkForeignKeyExists("users", "user_id", user_id):
                return {"code": 400, "message": f"操作失败！关联用户ID={user_id} 不存在于 users 表"}

        # 接收参数,构造最终字典,去除有默认值的参数(created_at默认)
        argsDict = {
            "user_id": user_id,
            "username_attempt": username_attempt,
            "login_method": login_method,
            "success": success,
            "ip": ip,
            "device_info": device_info,
            "fail_reason": fail_reason,
        }

        result = self.__buildInsertSQL("login_logs", argsDict)
        if result["code"] == 200:
            result["message"] = f"添加登录日志成功！日志ID={result['lastrowid']}"
        return result

    def add_table_sessions(
        self,
        session_id: int = None,           # 序号(主键,自增) 默认
        session_uuid: str = None,         # 会话唯一标识(令牌用,32位hex) 必须有
        user_id: int = None,              # 会话所属用户ID(外键→users.user_id) 必须有
        token: str = None,                # 会话令牌(已签名字符串) 必须有
        ip: str = None,                   # 登录时IP
        device_info: str = None,          # 设备标识
        created_at: str = None,           # 会话创建时间(精确到秒) 默认
        expires_at: str = None,           # 过期时间(精确到秒) 必须有
        is_active: int = None,            # 是否有效: 1=有效 / 0=已注销或已过期 默认
        db_conn = None                    # 数据库连接对象
    ):
        # 外键验证: sessions.user_id 必须存在于 users 表(NOT NULL,必填)
        if not self.__checkForeignKeyExists("users", "user_id", user_id):
            return {"code": 400, "message": f"操作失败！关联用户ID={user_id} 不存在于 users 表"}

        # 接收参数,构造最终字典,去除有默认值的参数
        argsDict = {
            "session_uuid": session_uuid,
            "user_id": user_id,
            "token": token,
            "ip": ip,
            "device_info": device_info,
            "expires_at": expires_at,
        }

        result = self.__buildInsertSQL("sessions", argsDict)
        if result["code"] == 200:
            result["message"] = f"添加会话成功！会话ID={result['lastrowid']}"
        return result

    def add_table_operation_logs(
        self,
        log_id: int = None,               # 序号(主键,自增) 默认
        user_id: int = None,              # 操作者ID(外键→users.user_id)
        action: str = None,               # 操作类型: CREATE_USER/DELETE_USER/RESET_PASSWORD/BAN_USER/UNBAN_USER/CHANGE_ROLE/DELETE_FACE/ENROLL_FACE 必须有
        target_id: int = None,            # 操作对象ID(被改的user_id/binding_id等)
        target: str = None,               # 操作对象描述(如用户名"test1")
        detail: str = None,               # 详情(JSON字符串,存修改前后对比等)
        ip: str = None,                   # 操作来源IP
        created_at: str = None,           # 操作时间(精确到秒) 默认
        db_conn = None                    # 数据库连接对象
    ):
        # 外键验证: user_id 不为空时,检查是否存在于 users 表
        #    operation_logs 的 user_id 允许 NULL(操作者已删除,但日志保留)
        if user_id is not None:
            if not self.__checkForeignKeyExists("users", "user_id", user_id):
                return {"code": 400, "message": f"操作失败！操作者ID={user_id} 不存在于 users 表"}

        # 接收参数,构造最终字典,去除有默认值的参数(created_at默认)
        argsDict = {
            "user_id": user_id,
            "action": action,
            "target_id": target_id,
            "target": target,
            "detail": detail,
            "ip": ip,
        }

        result = self.__buildInsertSQL("operation_logs", argsDict)
        if result["code"] == 200:
            result["message"] = f"添加操作日志成功！日志ID={result['lastrowid']}"
        return result

    def add_table_auto_login_cookies(
        self,
        cookie_id: int = None,            # 序号(主键,自增) 默认
        user_id: int = None,              # 关联用户ID(外键→users.user_id) 必须有
        cookie: str = None,               # cookie 值(64位hex,唯一) 必须有
        ip_address: str = None,           # 登录时 IP 必须
        device_code: str = None,          # 登录设备识别码 必须
        created_at: str = None,           # 创建时间 默认
        expires_at: str = None,           # 过期时间(一周后) 必须有
        is_valid: int = None,             # 是否有效: 1=有效 / 0=已撤销/过期 默认
        db_conn = None                    # 数据库连接对象
    ):
        """
        添加自动登录 cookie 记录
        外键验证关联的 user_id 必须存在,避免脏数据

        :param cookie_id: 序号<str>
        :param user_id: 关联用户ID<int>
        :param cookie: cookie 值<str>
        :param ip_address: IP 地址<str>
        :param device_code: 设备识别码<str>
        :param created_at: 创建时间<str>
        :param expires_at: 过期时间<str>
        :param is_valid: 是否有效<int>
        :param db_conn: 数据库连接对象
        :return: dict
        """
        # 外键验证: auto_login_cookies.user_id 必须存在于 users 表(NOT NULL,必填)
        if not self.__checkForeignKeyExists("users", "user_id", user_id):
            return {"code": 400, "message": f"操作失败！关联用户ID={user_id} 不存在于 users 表"}

        # 过滤为 None 的字段,构造插入字典(去掉有默认值的参数)
        argsDict = {
            "user_id": user_id,
            "cookie": cookie,
            "ip_address": ip_address,
            "device_code": device_code,
            "expires_at": expires_at,
        }

        result = self.__buildInsertSQL("auto_login_cookies", argsDict)
        if result["code"] == 200:
            result["message"] = f"添加自动登录 cookie 成功！cookie_id={result['lastrowid']}"
        return result

    # ====================================================================
    # 添加数据-映射(兼容旧接口)
    # ====================================================================
    def add_data(self, op, table_name):
        """
        根据操作权限和表名返回对应的添加方法(兼容旧 add_data 接口)
        :param op: 操作权限<str> "admin"
        :param table_name: 表名<str>
        :return: 对应的方法对象 或 错误 dict
        """
        # 映射表(方法名已去掉双下划线前缀)
        tableMethodDict = {
            "users": self.add_table_users,
            "user_face_bindings": self.add_table_user_face_bindings,
            "login_logs": self.add_table_login_logs,
            "sessions": self.add_table_sessions,
            "operation_logs": self.add_table_operation_logs,
            "auto_login_cookies": self.add_table_auto_login_cookies
        }

        if op == "admin" and table_name in tableMethodDict:
            return tableMethodDict[table_name]
        else:
            return {"code": 400, "message": "权限不足或参数错误！"}


# ========= 删除数据 ==========
class DeleteDatabase:
    """
    数据库删除数据操作类
    =====================
    封装 users 和 user_face_bindings 两张表的 DELETE 操作

    用法:
        conn = get_connection()
        deleteDb = DeleteDatabase(conn)
        result = deleteDb.delete_table_users(user_id=1)
    """

    def __init__(self, db_conn):
        """
        初始化删除数据操作对象
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __checkTableExists(self, table):
        """检查表是否存在"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return cursor.fetchone() is not None

    def __checkRecordExists(self, table, tableId, tableIdValue):
        """
        检查记录是否存在(删前验证,避免误删返回成功)
        :param table: 表名<str>
        :param tableId: 主键字段名<str>
        :param tableIdValue: 主键值<int>
        :return: True=存在, False=不存在
        """
        cursor = self.db_conn.cursor()
        cursor.execute(f"SELECT {tableId} FROM {table} WHERE {tableId} = ?", (tableIdValue,))
        return cursor.fetchone() is not None

    def __executeDelete(self, table, whereClause, params):
        """
        执行 DELETE 语句(通用方法)
        :param table: 表名<str>
        :param whereClause: WHERE 子句<str> 如 "user_id = ?"
        :param params: 参数<tuple>
        :return: dict {"code": 200/400/404, "message": "...", "deleted_count": int}
        """
        try:
            if not self.__checkTableExists(table):
                return {"code": 404, "message": f"操作失败！表 {table} 不存在"}

            cursor = self.db_conn.cursor()
            cursor.execute(f"DELETE FROM {table} WHERE {whereClause}", params)
            self.db_conn.commit()

            deletedCount = cursor.rowcount
            if deletedCount == 0:
                return {"code": 400, "message": f"操作失败！未找到匹配的记录"}
            return {"code": 200, "message": f"删除成功！共删除 {deletedCount} 条记录", "deleted_count": deletedCount}

        except Exception as e:
            # 日志: 数据库DELETE失败(调用 ServerLogSystem.logManager->error )
            self._logger.error(CATEGORY_DATABASE, f"数据库DELETE失败: {e}")
            return {"code": 400, "message": f"错误：{e}"}

    # ====================================================================
    # users 表删除
    # ====================================================================
    def delete_table_users(self, user_id: int = None, uuid: str = None, username: str = None):
        """
        删除用户(按 user_id/uuid/username 三选一)
        注意: 外键 ON DELETE CASCADE 会自动删除关联的 user_face_bindings 和 sessions
              外键 ON DELETE SET NULL 会保留 login_logs 和 operation_logs(审计痕迹不丢)

        :param user_id: 用户ID<int>
        :param uuid: 用户UUID<str>
        :param username: 用户名<str>
        :return: dict
        """
        table = "users"

        # 确定删除条件(三选一)
        if user_id is not None:
            # 删前检查记录是否存在
            if not self.__checkRecordExists(table, "user_id", user_id):
                return {"code": 400, "message": f"操作失败！用户ID={user_id} 不存在"}
            return self.__executeDelete(table, "user_id = ?", (user_id,))

        elif uuid is not None:
            if not self.__checkRecordExists(table, "uuid", uuid):
                return {"code": 400, "message": f"操作失败！UUID={uuid} 不存在"}
            return self.__executeDelete(table, "uuid = ?", (uuid,))

        elif username is not None:
            if not self.__checkRecordExists(table, "username", username):
                return {"code": 400, "message": f"操作失败！用户名={username} 不存在"}
            return self.__executeDelete(table, "username = ?", (username,))

        else:
            return {"code": 400, "message": "操作失败！请提供 user_id、uuid 或 username 之一"}

    # ====================================================================
    # user_face_bindings 表删除
    # ====================================================================
    def delete_table_user_face_bindings(self, binding_id: int = None, user_id: int = None):
        """
        删除人脸绑定记录

        :param binding_id: 绑定ID<int>(删单条)
        :param user_id: 用户ID<int>(删该用户的所有人脸绑定)
        :return: dict
        """
        table = "user_face_bindings"

        if binding_id is not None:
            if not self.__checkRecordExists(table, "binding_id", binding_id):
                return {"code": 400, "message": f"操作失败！绑定ID={binding_id} 不存在"}
            return self.__executeDelete(table, "binding_id = ?", (binding_id,))

        elif user_id is not None:
            # 删该用户的所有绑定(不检查记录是否存在,0条也返回成功)
            return self.__executeDelete(table, "user_id = ?", (user_id,))

        else:
            return {"code": 400, "message": "操作失败！请提供 binding_id 或 user_id"}

    # ====================================================================
    # 删除数据-映射(兼容旧接口)
    # ====================================================================
    def delete_data(self, op, table_name):
        """
        根据操作权限和表名返回对应的删除方法
        :param op: 操作权限<str> "admin"
        :param table_name: 表名<str>
        :return: 对应的方法对象 或 错误 dict
        """
        tableMethodDict = {
            "users": self.delete_table_users,
            "user_face_bindings": self.delete_table_user_face_bindings
        }

        if op == "admin" and table_name in tableMethodDict:
            return tableMethodDict[table_name]
        else:
            return {"code": 400, "message": "权限不足或参数错误！"}


# ========= 修改数据 ==========
class UpdateDatabase:
    """
    数据库修改数据操作类
    =====================
    封装 users 和 user_face_bindings 两张表的 UPDATE 操作
    支持动态字段更新: 只更新传入的字段,未传入的保持原值

    用法:
        conn = get_connection()
        updateDb = UpdateDatabase(conn)
        result = updateDb.update_table_users(user_id=1, nickname="新昵称", email="new@email.com")
    """

    def __init__(self, db_conn):
        """
        初始化修改数据操作对象
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __checkTableExists(self, table):
        """检查表是否存在"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return cursor.fetchone() is not None

    def __checkColumnExists(self, table, column):
        """检查字段是否存在"""
        cursor = self.db_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column in columns

    def __checkRecordExists(self, table, tableId, tableIdValue):
        """检查记录是否存在"""
        cursor = self.db_conn.cursor()
        cursor.execute(f"SELECT {tableId} FROM {table} WHERE {tableId} = ?", (tableIdValue,))
        return cursor.fetchone() is not None

    def __buildUpdateSQL(self, table, tableId, tableIdValue, updateDict):
        """
        动态拼 UPDATE 语句并执行(核心通用方法)
        步骤: 检查表存在→检查记录存在→检查字段存在→过滤有效字段→拼 SQL→执行→提交

        :param table: 表名<str>
        :param tableId: 主键字段名<str>(WHERE 条件)
        :param tableIdValue: 主键值<int>
        :param updateDict: 要更新的字段名→值的字典<dict>
        :return: dict {"code": 200/400/404, "message": "...", "updated_count": int}
        """
        try:
            # 1. 检查表是否存在
            if not self.__checkTableExists(table):
                return {"code": 404, "message": f"操作失败！表 {table} 不存在"}

            # 2. 检查记录是否存在
            if not self.__checkRecordExists(table, tableId, tableIdValue):
                return {"code": 400, "message": f"操作失败！{table} 表中 {tableId}={tableIdValue} 的记录不存在"}

            # 3. 过滤出表中实际存在的字段(跳过不存在的字段,不报错)
            validFields = {}
            for fieldName, fieldValue in updateDict.items():
                if self.__checkColumnExists(table, fieldName):
                    validFields[fieldName] = fieldValue

            if not validFields:
                return {"code": 400, "message": "操作失败！没有可更新的字段"}

            # 4. 动态拼 UPDATE 语句
            #    格式: UPDATE 表名 SET 字段1=?, 字段2=? WHERE 主键=?
            setClauses = [f"{f} = ?" for f in validFields.keys()]
            setSql = ", ".join(setClauses)
            setValues = list(validFields.values())
            setValues.append(tableIdValue)  # WHERE 条件的值放最后

            cursor = self.db_conn.cursor()
            cursor.execute(
                f"UPDATE {table} SET {setSql} WHERE {tableId} = ?",
                tuple(setValues)
            )
            self.db_conn.commit()

            return {"code": 200, "message": f"修改成功！影响 {cursor.rowcount} 条记录", "updated_count": cursor.rowcount}

        except Exception as e:
            # 日志: 数据库UPDATE失败(调用 ServerLogSystem.logManager->error )
            self._logger.error(CATEGORY_DATABASE, f"数据库UPDATE失败: {e}")
            return {"code": 400, "message": f"错误：{e}"}

    # ====================================================================
    # users 表修改
    # ====================================================================
    def update_table_users(
        self,
        user_id: int = None,
        email: str = None,
        password_hash: str = None,
        salt: str = None,
        nickname: str = None,
        avatar_path: str = None,
        status: str = None,
        last_login_at: str = None,
        last_login_ip: str = None,
        device_code: str = None,
        role: str = None
    ):
        """
        修改用户信息(动态字段,只更新传入的非 None 字段)
        注意: user_id/uuid/username 不可修改(唯一标识)

        :param user_id: 用户ID<int>(必须,定位要修改的用户)
        :param email: 新邮箱<str>
        :param password_hash: 新密码哈希<str>
        :param salt: 新盐值<str>
        :param nickname: 新昵称<str>
        :param avatar_path: 新头像路径<str>
        :param status: 新状态<str> active/banned
        :param last_login_at: 最后登录时间<str>
        :param last_login_ip: 最后登录IP<str>
        :param device_code: 登录设备识别码<str>
        :param role: 新角色<str> user/admin
        :return: dict
        """
        if user_id is None:
            return {"code": 400, "message": "操作失败！user_id 不能为空"}

        # 收集所有非 None 的字段(只更新传入的)
        updateDict = {}
        localVars = locals()
        skipKeys = {"self", "user_id"}
        for key, value in localVars.items():
            if key not in skipKeys and value is not None:
                updateDict[key] = value

        return self.__buildUpdateSQL("users", "user_id", user_id, updateDict)

    # ====================================================================
    # user_face_bindings 表修改
    # ====================================================================
    def update_table_user_face_bindings(
        self,
        binding_id: int = None,
        feature_file_path: str = None,
        meta_file_path: str = None,
        is_primary: int = None,
        remark: str = None
    ):
        """
        修改人脸绑定记录(动态字段)

        :param binding_id: 绑定ID<int>(必须,定位要修改的记录)
        :param feature_file_path: 新特征文件路径<str>
        :param meta_file_path: 新元数据路径<str>
        :param is_primary: 是否主特征<int> 0/1
        :param remark: 新备注<str>
        :return: dict
        """
        if binding_id is None:
            return {"code": 400, "message": "操作失败！binding_id 不能为空"}

        # 收集所有非 None 的字段
        updateDict = {}
        localVars = locals()
        skipKeys = {"self", "binding_id"}
        for key, value in localVars.items():
            if key not in skipKeys and value is not None:
                updateDict[key] = value

        return self.__buildUpdateSQL("user_face_bindings", "binding_id", binding_id, updateDict)

    # ====================================================================
    # sessions 表修改
    # ====================================================================
    def update_table_sessions(
        self,
        session_id: int = None,
        is_active: int = None,
        expires_at: str = None
    ):
        """
        修改会话记录(动态字段,用于登出撤销/续期)
        后续对接 TokenManager 时调用

        :param session_id: 会话ID<int>(必须,定位要修改的会话)
        :param is_active: 是否有效<int> 0=已撤销 / 1=有效
        :param expires_at: 新过期时间<str>
        :return: dict
        """
        if session_id is None:
            return {"code": 400, "message": "操作失败！session_id 不能为空"}

        # 收集所有非 None 的字段
        updateDict = {}
        localVars = locals()
        skipKeys = {"self", "session_id"}
        for key, value in localVars.items():
            if key not in skipKeys and value is not None:
                updateDict[key] = value

        return self.__buildUpdateSQL("sessions", "session_id", session_id, updateDict)

    # ====================================================================
    # auto_login_cookies 表修改
    # ====================================================================
    def update_table_auto_login_cookies(
        self,
        cookie_id: int = None,
        is_valid: int = None,
        expires_at: str = None
    ):
        """
        修改自动登录 cookie 记录(动态字段)
        用于: 刷新有效期(续期)、撤销 cookie(置 is_valid=0)

        :param cookie_id: cookie记录ID<int>(必须,定位要修改的记录)
        :param is_valid: 是否有效<int> 0=已撤销 / 1=有效
        :param expires_at: 新过期时间<str>
        :return: dict
        """
        if cookie_id is None:
            return {"code": 400, "message": "操作失败！cookie_id 不能为空"}

        # 收集所有非 None 的字段
        updateDict = {}
        localVars = locals()
        skipKeys = {"self", "cookie_id"}
        for key, value in localVars.items():
            if key not in skipKeys and value is not None:
                updateDict[key] = value

        return self.__buildUpdateSQL("auto_login_cookies", "cookie_id", cookie_id, updateDict)

    # ====================================================================
    # 修改数据-映射(兼容旧接口)
    # ====================================================================
    def update_data(self, op, table_name):
        """
        根据操作权限和表名返回对应的修改方法
        :param op: 操作权限<str> "admin"
        :param table_name: 表名<str>
        :return: 对应的方法对象 或 错误 dict
        """
        tableMethodDict = {
            "users": self.update_table_users,
            "user_face_bindings": self.update_table_user_face_bindings,
            "auto_login_cookies": self.update_table_auto_login_cookies
        }

        if op == "admin" and table_name in tableMethodDict:
            return tableMethodDict[table_name]
        else:
            return {"code": 400, "message": "权限不足或参数错误！"}


# ========= 查询数据 ==========
class QueryDatabase:
    """
    数据库查询数据操作类
    =====================
    封装 users 和 user_face_bindings 两张表的 SELECT 操作

    用法:
        conn = get_connection()
        queryDb = QueryDatabase(conn)
        user = queryDb.query_table_users(user_id=1)
        allUsers = queryDb.query_table_users()  # 不传参数查全部
    """

    def __init__(self, db_conn):
        """
        初始化查询数据操作对象
        :param db_conn: 数据库连接对象(sqlite3.Connection)
        """
        self.db_conn = db_conn
        # 日志管理器(调用 ServerLogSystem.logManager->getLogger )
        self._logger = getLogger()

    # ====================================================================
    # 内部工具方法
    # ====================================================================
    def __checkTableExists(self, table):
        """检查表是否存在"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return cursor.fetchone() is not None

    def __executeQuery(self, table, selectFields, whereClause=None, params=None, orderBy=None, limit=None, offset=None):
        """
        执行 SELECT 查询(通用方法)
        :param table: 表名<str>
        :param selectFields: 查询字段列表<list> 或 "*"
        :param whereClause: WHERE 子句<str>
        :param params: 参数<tuple>
        :param orderBy: ORDER BY 子句<str>
        :param limit: LIMIT 数量<int>
        :param offset: OFFSET 偏移量<int>
        :return: dict {"code": 200/404, "data": [...], "count": int}
        """
        try:
            if not self.__checkTableExists(table):
                return {"code": 404, "message": f"操作失败！表 {table} 不存在", "data": [], "count": 0}

            # 拼 SELECT 语句
            if selectFields == "*":
                fieldSql = "*"
            else:
                fieldSql = ", ".join(selectFields)

            sql = f"SELECT {fieldSql} FROM {table}"

            # 拼 WHERE 子句
            if whereClause:
                sql += f" WHERE {whereClause}"

            # 拼 ORDER BY / LIMIT / OFFSET
            if orderBy:
                sql += f" ORDER BY {orderBy}"
            if limit is not None:
                sql += f" LIMIT {limit}"
            if offset is not None:
                sql += f" OFFSET {offset}"

            cursor = self.db_conn.cursor()
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()

            # 结果转字典列表(方便调用方使用)
            data = [dict(row) for row in rows]
            return {"code": 200, "message": "查询成功", "data": data, "count": len(data)}

        except Exception as e:
            # 日志: 数据库SELECT失败(调用 ServerLogSystem.logManager->error )
            self._logger.error(CATEGORY_DATABASE, f"数据库SELECT失败: {e}")
            return {"code": 400, "message": f"错误：{e}", "data": [], "count": 0}

    # ====================================================================
    # users 表查询
    # ====================================================================
    def query_table_users(
        self,
        user_id: int = None,
        uuid: str = None,
        username: str = None,
        status: str = None,
        role: str = None,
        orderBy: str = "user_id",
        limit: int = None,
        offset: int = None
    ):
        """
        查询用户(支持多条件组合,不传参数查全部)

        :param user_id: 按用户ID查<str>
        :param uuid: 按UUID查<str>
        :param username: 按用户名查<str>(精确匹配)
        :param status: 按状态筛选<str> active/banned
        :param role: 按角色筛选<str> user/admin
        :param orderBy: 排序字段<str> 默认 user_id
        :param limit: 返回条数上限<int>
        :param offset: 偏移量<int>(分页用)
        :return: dict {"code": 200, "data": [...], "count": int}
        """
        # 动态拼 WHERE 条件(只拼接非 None 的过滤条件)
        conditions = []
        params = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if uuid is not None:
            conditions.append("uuid = ?")
            params.append(uuid)
        if username is not None:
            conditions.append("username = ?")
            params.append(username)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if role is not None:
            conditions.append("role = ?")
            params.append(role)

        whereClause = " AND ".join(conditions) if conditions else None

        return self.__executeQuery(
            table="users",
            selectFields="*",
            whereClause=whereClause,
            params=tuple(params) if params else None,
            orderBy=orderBy,
            limit=limit,
            offset=offset
        )

    def query_users_by_nickname(self, keyword: str, limit: int = None):
        """
        按昵称模糊查询(登录/注册时查重)

        :param keyword: 关键字<str>
        :param limit: 返回条数上限<int>
        :return: dict
        """
        return self.__executeQuery(
            table="users",
            selectFields="*",
            whereClause="nickname LIKE ?",
            params=(f"%{keyword}%",),
            limit=limit
        )

    def query_users_count(self, status: str = None):
        """
        统计用户数量(仪表盘用)

        :param status: 按状态统计<str> active/banned,不传查全部
        :return: dict {"code": 200, "data": [{"total": N}], "count": 1}
        """
        try:
            if not self.__checkTableExists("users"):
                return {"code": 404, "message": "操作失败！表 users 不存在", "data": [], "count": 0}

            cursor = self.db_conn.cursor()
            if status:
                cursor.execute("SELECT COUNT(*) AS total FROM users WHERE status = ?", (status,))
            else:
                cursor.execute("SELECT COUNT(*) AS total FROM users")
            row = cursor.fetchone()
            return {"code": 200, "message": "查询成功", "data": [dict(row)], "count": 1}
        except Exception as e:
            return {"code": 400, "message": f"错误：{e}", "data": [], "count": 0}

    # ====================================================================
    # user_face_bindings 表查询
    # ====================================================================
    def query_table_user_face_bindings(
        self,
        binding_id: int = None,
        user_id: int = None,
        is_primary: int = None,
        orderBy: str = "binding_id",
        limit: int = None,
        offset: int = None
    ):
        """
        查询人脸绑定记录(支持多条件组合)

        :param binding_id: 按绑定ID查<int>
        :param user_id: 按用户ID查<int>(查某用户的所有人脸)
        :param is_primary: 是否主特征<int> 0/1
        :param orderBy: 排序字段<str>
        :param limit: 返回条数上限<int>
        :param offset: 偏移量<int>
        :return: dict
        """
        conditions = []
        params = []

        if binding_id is not None:
            conditions.append("binding_id = ?")
            params.append(binding_id)
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if is_primary is not None:
            conditions.append("is_primary = ?")
            params.append(is_primary)

        whereClause = " AND ".join(conditions) if conditions else None

        return self.__executeQuery(
            table="user_face_bindings",
            selectFields="*",
            whereClause=whereClause,
            params=tuple(params) if params else None,
            orderBy=orderBy,
            limit=limit,
            offset=offset
        )

    # ====================================================================
    # sessions 表查询
    # ====================================================================
    def query_table_sessions(
        self,
        session_id: int = None,
        session_uuid: str = None,
        user_id: int = None,
        token: str = None,
        is_active: int = None,
        orderBy: str = "session_id",
        limit: int = None,
        offset: int = None
    ):
        """
        查询会话记录(支持多条件组合)

        :param session_id: 按会话ID查<int>
        :param session_uuid: 按会话UUID查<str>
        :param user_id: 按用户ID查<int>
        :param token: 按token查<str>
        :param is_active: 是否有效<int> 0/1
        :param orderBy: 排序字段<str>
        :param limit: 返回条数上限<int>
        :param offset: 偏移量<int>
        :return: dict {"code": 200, "data": [...], "count": int}
        """
        conditions = []
        params = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if session_uuid is not None:
            conditions.append("session_uuid = ?")
            params.append(session_uuid)
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if token is not None:
            conditions.append("token = ?")
            params.append(token)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(is_active)

        whereClause = " AND ".join(conditions) if conditions else None

        return self.__executeQuery(
            table="sessions",
            selectFields="*",
            whereClause=whereClause,
            params=tuple(params) if params else None,
            orderBy=orderBy,
            limit=limit,
            offset=offset
        )

    # ====================================================================
    # auto_login_cookies 表查询
    # ====================================================================
    def query_table_auto_login_cookies(
        self,
        cookie_id: int = None,
        user_id: int = None,
        cookie: str = None,
        ip_address: str = None,
        device_code: str = None,
        is_valid: int = None,
        orderBy: str = "cookie_id",
        limit: int = None,
        offset: int = None
    ):
        """
        查询自动登录 cookie 记录(支持多条件组合)

        :param cookie_id: 按记录ID查<int>
        :param user_id: 按用户ID查<int>
        :param cookie: 按 cookie 值查<str>
        :param ip_address: 按 IP 查<str>
        :param device_code: 按设备识别码查<str>
        :param is_valid: 是否有效<int> 0/1
        :param orderBy: 排序字段<str>
        :param limit: 返回条数上限<int>
        :param offset: 偏移量<int>
        :return: dict {"code": 200, "data": [...], "count": int}
        """
        # 动态拼 WHERE 条件(只拼接非 None 的过滤条件)
        conditions = []
        params = []

        if cookie_id is not None:
            conditions.append("cookie_id = ?")
            params.append(cookie_id)
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if cookie is not None:
            conditions.append("cookie = ?")
            params.append(cookie)
        if ip_address is not None:
            conditions.append("ip_address = ?")
            params.append(ip_address)
        if device_code is not None:
            conditions.append("device_code = ?")
            params.append(device_code)
        if is_valid is not None:
            conditions.append("is_valid = ?")
            params.append(is_valid)

        whereClause = " AND ".join(conditions) if conditions else None

        return self.__executeQuery(
            table="auto_login_cookies",
            selectFields="*",
            whereClause=whereClause,
            params=tuple(params) if params else None,
            orderBy=orderBy,
            limit=limit,
            offset=offset
        )

    # ====================================================================
    # 查询数据-映射(兼容旧接口)
    # ====================================================================
    def query_data(self, op, table_name):
        """
        根据操作权限和表名返回对应的查询方法
        :param op: 操作权限<str> "admin"
        :param table_name: 表名<str>
        :return: 对应的方法对象 或 错误 dict
        """
        tableMethodDict = {
            "users": self.query_table_users,
            "user_face_bindings": self.query_table_user_face_bindings,
            "auto_login_cookies": self.query_table_auto_login_cookies
        }

        if op == "admin" and table_name in tableMethodDict:
            return tableMethodDict[table_name]
        else:
            return {"code": 400, "message": "权限不足或参数错误！"}


