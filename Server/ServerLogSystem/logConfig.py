"""
coding:utf-8
file: ServerLogSystem/logConfig.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端日志系统配置常量

# ── 日志等级 ──
DEBUG = 0
INFO = 1
WARNING = 2
ERROR = 3
CRITICAL = 4

LEVEL_NAMES = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL",
}

# ── 日志类别 ──
CATEGORY_SYSTEM = "SYSTEM"
CATEGORY_NETWORK = "NETWORK"
CATEGORY_DATABASE = "DATABASE"
CATEGORY_AUTH = "AUTH"
CATEGORY_FILE = "FILE"
CATEGORY_SECURITY = "SECURITY"
CATEGORY_PERFORMANCE = "PERFORMANCE"

# ── 控制台颜色 ──
COLOR_RESET = "\033[0m"
COLOR_LEVEL = {
    DEBUG: "\033[36m",
    INFO: "\033[32m",
    WARNING: "\033[33m",
    ERROR: "\033[31m",
    CRITICAL: "\033[35m",
}

# ── 服务端数据库配置 ──
SERVER_LOG_TABLE = "system_logs"
SERVER_LOG_DEFAULT_LEVEL = DEBUG
SERVER_LOG_FORMAT = "[{datetime}] [{level}] [{category}] {message}"

# 建表 SQL
SYSTEM_LOGS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS system_logs (
        log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        level       INTEGER NOT NULL DEFAULT 0,
        level_name  TEXT NOT NULL
                    CHECK (level_name IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
        category    TEXT NOT NULL
                    CHECK (category IN (
                        'SYSTEM', 'NETWORK', 'DATABASE', 'AUTH',
                        'FILE', 'SECURITY', 'PERFORMANCE'
                    )),
        message     TEXT NOT NULL
                    CHECK (LENGTH(message) <= 4000),
        created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
"""