"""
coding:utf-8
file: LogSystem/logManager.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端日志管理器(文件 + 控制台)
# ===============================
# 日志存储: client/log/ 目录, 按文件大小自动轮转
# 控制台输出: 带 ANSI 颜色, 区分等级和类别
# 线程安全: 所有写操作加锁

import os
import sys
import threading
import time
from datetime import datetime

# 导入配置常量(相对导入, 保证作为 LogSystem 包被引用时也能找到同目录 logConfig)
from .logConfig import (
    DEBUG, INFO, WARNING, ERROR, CRITICAL, LEVEL_NAMES,
    COLOR_RESET, COLOR_LEVEL,
    CLIENT_LOG_DIR, CLIENT_LOG_FILE, CLIENT_LOG_MAX_SIZE,
    CLIENT_LOG_BACKUP_COUNT, CLIENT_LOG_DEFAULT_LEVEL, CLIENT_LOG_FORMAT,
)


class LogManager:
    """
    客户端日志管理器
    ================
    单例模式, 全局唯一实例。
    用法: logger = LogManager.getInstance(); logger.info("SYSTEM", "启动成功")
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if LogManager._instance is not None:
            raise RuntimeError("请使用 LogManager.getInstance() 获取单例")
        self._writeLock = threading.Lock()
        self._minLevel = CLIENT_LOG_DEFAULT_LEVEL
        self._consoleEnabled = True
        self._fileEnabled = True
        self._logDir = None
        self._logFile = None
        self._initLogDir()

    # ── 单例 ──
    @classmethod
    def getInstance(cls) -> "LogManager":
        """获取全局唯一日志管理器实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 初始化日志目录 ──
    def _initLogDir(self):
        """解析日志目录(基于项目根目录的相对路径)"""
        # 从当前文件推导项目根目录: client/LogSystem/logManager.py
        curFile = os.path.abspath(__file__)
        # 向上: logManager.py → LogSystem/ → client/ → 项目根/
        projectRoot = os.path.dirname(os.path.dirname(os.path.dirname(curFile)))
        self._logDir = os.path.join(projectRoot, CLIENT_LOG_DIR)
        os.makedirs(self._logDir, exist_ok=True)
        self._logFile = os.path.join(self._logDir, CLIENT_LOG_FILE)

    # ── 配置 ──
    def setLevel(self, level: int):
        """设置最低输出等级, 低于此等级的日志不输出"""
        self._minLevel = level

    def setConsoleEnabled(self, enabled: bool):
        """启用/禁用控制台输出"""
        self._consoleEnabled = enabled

    def setFileEnabled(self, enabled: bool):
        """启用/禁用文件输出"""
        self._fileEnabled = enabled

    # ── 核心日志方法 ──
    def log(self, level: int, category: str, message: str):
        """
        写入日志(核心方法)
        :param level: 日志等级<int> (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        :param category: 日志类别<str> (SYSTEM/NETWORK/DATABASE/...)
        :param message: 日志内容<str>
        """
        if level < self._minLevel:
            return

        now = datetime.now()
        levelName = LEVEL_NAMES.get(level, "UNKNOWN")
        line = CLIENT_LOG_FORMAT.format(
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

            # 文件输出
            if self._fileEnabled:
                self._writeToFile(line)

    def debug(self, category: str, message: str):
        """调试日志"""
        self.log(DEBUG, category, message)

    def info(self, category: str, message: str):
        """信息日志"""
        self.log(INFO, category, message)

    def warning(self, category: str, message: str):
        """警告日志"""
        self.log(WARNING, category, message)

    def error(self, category: str, message: str):
        """错误日志"""
        self.log(ERROR, category, message)

    def critical(self, category: str, message: str):
        """严重错误日志"""
        self.log(CRITICAL, category, message)

    # ── 文件写入与轮转 ──
    def _writeToFile(self, line: str):
        """写入日志文件, 超过大小上限时自动轮转"""
        try:
            # 检查是否需要轮转
            if os.path.exists(self._logFile) and os.path.getsize(self._logFile) >= CLIENT_LOG_MAX_SIZE:
                self._rotateLogs()

            with open(self._logFile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except IOError:
            # 写入失败时至少输出到控制台
            if self._consoleEnabled:
                print(f"{COLOR_LEVEL[ERROR]}[LogSystem] 日志文件写入失败!{COLOR_RESET}", flush=True)

    def _rotateLogs(self):
        """轮转日志文件(保留最近 N 个备份)"""
        # 删除最旧的备份
        oldestBackup = os.path.join(self._logDir, f"{CLIENT_LOG_FILE}.{CLIENT_LOG_BACKUP_COUNT}")
        if os.path.exists(oldestBackup):
            os.remove(oldestBackup)

        # 重命名: client.log.N → client.log.(N+1)
        for i in range(CLIENT_LOG_BACKUP_COUNT - 1, 0, -1):
            oldPath = os.path.join(self._logDir, f"{CLIENT_LOG_FILE}.{i}")
            newPath = os.path.join(self._logDir, f"{CLIENT_LOG_FILE}.{i + 1}")
            if os.path.exists(oldPath):
                if os.path.exists(newPath):
                    os.remove(newPath)
                os.rename(oldPath, newPath)

        # 重命名当前文件: client.log → client.log.1
        if os.path.exists(self._logFile):
            backup1 = os.path.join(self._logDir, f"{CLIENT_LOG_FILE}.1")
            if os.path.exists(backup1):
                os.remove(backup1)
            os.rename(self._logFile, backup1)

    # ── 工具方法 ──
    def getLogFilePath(self) -> str:
        """获取当前日志文件路径"""
        return self._logFile

    def getLogDir(self) -> str:
        """获取日志目录路径"""
        return self._logDir

    def getRecentLogs(self, count: int = 50) -> list:
        """获取最近 N 条日志(从文件尾部读取)"""
        if not os.path.exists(self._logFile):
            return []
        with self._writeLock:
            with open(self._logFile, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        return lines[-count:]

    def clearLogs(self) -> bool:
        """清空日志文件"""
        try:
            with self._writeLock:
                with open(self._logFile, "w", encoding="utf-8") as f:
                    f.write("")
            return True
        except IOError:
            return False


# ── 模块级快捷函数 ──
def getLogger() -> LogManager:
    """获取全局日志管理器"""
    return LogManager.getInstance()