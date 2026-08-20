"""
coding:utf-8
file: ServerLogSystem/logManager.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端日志管理器(数据库 + 控制台)
# =================================
# 日志存储: SQLite system_logs 表
# 控制台输出: 带 ANSI 颜色
# 线程安全: 所有写操作加锁

import sys
import os
import threading
import sqlite3
from datetime import datetime

# 导入配置常量(相对导入, 保证作为 ServerLogSystem 包被引用时也能找到同目录 logConfig)
from .logConfig import (
    DEBUG, INFO, WARNING, ERROR, CRITICAL, LEVEL_NAMES,
    COLOR_RESET, COLOR_LEVEL,
    SERVER_LOG_TABLE, SERVER_LOG_DEFAULT_LEVEL, SERVER_LOG_FORMAT,
    SYSTEM_LOGS_TABLE_SQL,
)


class LogManager:
    """
    服务端日志管理器
    ================
    单例模式, 全局唯一实例。
    日志双写: 数据库 system_logs 表 + 控制台输出。
    用法: logger = LogManager.getInstance(dbPath); logger.info("SYSTEM", "启动成功")
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if LogManager._instance is not None:
            raise RuntimeError("请使用 LogManager.getInstance(dbPath) 获取单例")
        self._writeLock = threading.Lock()
        self._minLevel = SERVER_LOG_DEFAULT_LEVEL
        self._consoleEnabled = True
        self._dbEnabled = True
        self._dbPath = None
        self._dbConn = None
        self._initialized = False

    @classmethod
    def getInstance(cls, dbPath: str = None) -> "LogManager":
        """获取全局唯一日志管理器实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        if dbPath and not cls._instance._initialized:
            cls._instance._initDb(dbPath)
        return cls._instance

    # ── 初始化数据库 ──
    def _initDb(self, dbPath: str):
        """初始化日志数据库连接和表"""
        self._dbPath = dbPath
        dbDir = os.path.dirname(dbPath)
        if dbDir and not os.path.exists(dbDir):
            os.makedirs(dbDir, exist_ok=True)

        self._dbConn = sqlite3.connect(dbPath, check_same_thread=False)
        # 设置行工厂为 sqlite3.Row, 使查询结果可用列名索引(与 database.get_connection 保持一致)
        self._dbConn.row_factory = sqlite3.Row
        self._dbConn.execute("PRAGMA journal_mode=WAL")
        self._dbConn.execute("PRAGMA foreign_keys=ON")

        # 建表 + 索引
        self._dbConn.execute(SYSTEM_LOGS_TABLE_SQL)
        self._dbConn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sys_logs_level ON system_logs(level)"
        )
        self._dbConn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sys_logs_category ON system_logs(category)"
        )
        self._dbConn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sys_logs_time ON system_logs(created_at)"
        )
        self._dbConn.commit()
        self._initialized = True

    # ── 配置 ──
    def setLevel(self, level: int):
        self._minLevel = level

    def setConsoleEnabled(self, enabled: bool):
        self._consoleEnabled = enabled

    def setDbEnabled(self, enabled: bool):
        self._dbEnabled = enabled

    # ── 核心日志方法 ──
    def log(self, level: int, category: str, message: str):
        if level < self._minLevel:
            return

        now = datetime.now()
        levelName = LEVEL_NAMES.get(level, "UNKNOWN")
        line = SERVER_LOG_FORMAT.format(
            datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
            level=levelName,
            category=category,
            message=message,
        )

        with self._writeLock:
            # 控制台输出
            if self._consoleEnabled:
                color = COLOR_LEVEL.get(level, COLOR_RESET)
                print(f"{color}{line}{COLOR_RESET}", flush=True)

            # 数据库写入
            if self._dbEnabled and self._dbConn:
                self._writeToDb(level, levelName, category, message)

    def debug(self, category: str, message: str):
        self.log(DEBUG, category, message)

    def info(self, category: str, message: str):
        self.log(INFO, category, message)

    def warning(self, category: str, message: str):
        self.log(WARNING, category, message)

    def error(self, category: str, message: str):
        self.log(ERROR, category, message)

    def critical(self, category: str, message: str):
        self.log(CRITICAL, category, message)

    # ── 数据库写入 ──
    def _writeToDb(self, level: int, levelName: str, category: str, message: str):
        """写入日志到数据库"""
        try:
            self._dbConn.execute(
                f"INSERT INTO {SERVER_LOG_TABLE} (level, level_name, category, message) "
                "VALUES (?, ?, ?, ?)",
                (level, levelName, category, message),
            )
            self._dbConn.commit()
        except sqlite3.Error:
            # 数据库写入失败时输出到控制台
            if self._consoleEnabled:
                print(
                    f"{COLOR_LEVEL[ERROR]}[LogSystem] 数据库日志写入失败!{COLOR_RESET}",
                    flush=True,
                )

    # ── 查询方法 ──
    def getRecentLogs(self, count: int = 50, level: int = None,
                      category: str = None) -> list:
        """查询最近 N 条日志"""
        if not self._dbConn:
            return []
        sql = "SELECT log_id, level, level_name, category, message, created_at FROM system_logs"
        params = []
        conditions = []
        if level is not None:
            conditions.append("level >= ?")
            params.append(level)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY log_id DESC LIMIT ?"
        params.append(count)
        try:
            cur = self._dbConn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error:
            return []

    def getLogCount(self, level: int = None, category: str = None) -> int:
        """查询日志总数"""
        if not self._dbConn:
            return 0
        sql = "SELECT COUNT(*) FROM system_logs"
        params = []
        conditions = []
        if level is not None:
            conditions.append("level >= ?")
            params.append(level)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        try:
            cur = self._dbConn.execute(sql, params)
            return cur.fetchone()[0]
        except sqlite3.Error:
            return 0

    def clearLogs(self, beforeDays: int = 30) -> int:
        """清理 N 天前的日志, 返回删除条数"""
        if not self._dbConn:
            return 0
        try:
            cur = self._dbConn.execute(
                "DELETE FROM system_logs WHERE created_at < datetime('now', 'localtime', ?)",
                (f"-{beforeDays} days",),
            )
            self._dbConn.commit()
            return cur.rowcount
        except sqlite3.Error:
            return 0

    def close(self):
        """关闭数据库连接"""
        if self._dbConn:
            self._dbConn.close()
            self._dbConn = None


def getLogger(dbPath: str = None) -> LogManager:
    """获取全局日志管理器"""
    return LogManager.getInstance(dbPath)