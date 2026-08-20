"""
coding:utf-8
file: FileSystem/fileGuard.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 文件守护(访问控制)
# ===================
# 功能:
# - lockFile(): 锁定文件(创建 .lock 锁文件, 防止并发写入)
# - unlockFile(): 解锁文件
# - isLocked(): 检查文件是否被锁定
# - acquireLock(): 阻塞式获取锁(带超时)
# - cleanStaleLocks(): 清理过期锁文件
# - watchFile(): 监控文件变化(基于轮询 mtime)
# - getFilePermissions(): 获取文件权限信息
# - setFileReadOnly(): 设置文件只读/可写

import os
import time
import threading
import json


class FileGuard:
    """
    文件守护(访问控制)
    ===================
    基于锁文件的并发控制, 防止多进程/多线程同时写入同一文件。
    锁文件格式: {原文件名}.lock
    锁文件内容: {pid, timestamp, lock_id}
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._watchers = {}  # 文件监控任务

    # ── 锁/解锁 ──
    def lockFile(self, filePath: str, lockId: str = None, timeout: float = 0) -> dict:
        """
        锁定文件(非阻塞)
        :param filePath: 文件路径<str>
        :param lockId: 锁标识<str>, 为空则用进程ID
        :param timeout: 超时秒数<float>, 0=非阻塞
        :return: {"code": int, "message": str, "data": lock_id}
        """
        lockPath = filePath + ".lock"

        with self._lock:
            # 检查是否已有锁
            if os.path.exists(lockPath):
                existingLock = self._readLockFile(lockPath)
                if existingLock:
                    # 检查锁是否过期(超过 60 秒视为过期)
                    lockAge = time.time() - existingLock.get("timestamp", 0)
                    if lockAge < 60:
                        if timeout > 0:
                            # 阻塞等待
                            waited = 0
                            while os.path.exists(lockPath) and waited < timeout:
                                time.sleep(0.1)
                                waited += 0.1
                            if os.path.exists(lockPath):
                                return {"code": 400, "message": f"文件已被锁定(锁主: {existingLock.get('lock_id')})", "data": ""}
                        else:
                            return {"code": 400, "message": f"文件已被锁定(锁主: {existingLock.get('lock_id')})", "data": ""}
                    else:
                        # 锁过期, 清理
                        os.remove(lockPath)

            # 创建锁文件
            lockId = lockId or f"pid_{os.getpid()}"
            lockData = {
                "lock_id": lockId,
                "pid": os.getpid(),
                "timestamp": time.time(),
                "file": filePath,
            }
            try:
                with open(lockPath, "w", encoding="utf-8") as f:
                    json.dump(lockData, f)
                return {"code": 200, "message": "锁定成功", "data": lockId}
            except IOError as e:
                return {"code": 500, "message": f"锁定失败: {str(e)}", "data": ""}

    def unlockFile(self, filePath: str, lockId: str = None) -> dict:
        """
        解锁文件
        :param filePath: 文件路径<str>
        :param lockId: 锁标识<str>, 为空则不验证锁主
        :return: {"code": int, "message": str}
        """
        lockPath = filePath + ".lock"

        if not os.path.exists(lockPath):
            return {"code": 404, "message": "文件未被锁定"}

        # 验证锁主
        if lockId:
            existingLock = self._readLockFile(lockPath)
            if existingLock and existingLock.get("lock_id") != lockId:
                return {"code": 403, "message": f"锁主不匹配, 无法解锁"}

        try:
            os.remove(lockPath)
            return {"code": 200, "message": "解锁成功"}
        except OSError as e:
            return {"code": 500, "message": f"解锁失败: {str(e)}"}

    def isLocked(self, filePath: str) -> dict:
        """
        检查文件是否被锁定
        :param filePath: 文件路径<str>
        :return: {"code": int, "message": str, "data": {locked, lock_info}}
        """
        lockPath = filePath + ".lock"
        if not os.path.exists(lockPath):
            return {"code": 200, "message": "未锁定", "data": {"locked": False, "lock_info": None}}

        lockInfo = self._readLockFile(lockPath)
        if lockInfo is None:
            return {"code": 200, "message": "未锁定", "data": {"locked": False, "lock_info": None}}

        # 检查过期
        lockAge = time.time() - lockInfo.get("timestamp", 0)
        if lockAge >= 60:
            return {"code": 200, "message": "锁已过期",
                    "data": {"locked": False, "lock_info": lockInfo, "expired": True}}

        return {"code": 200, "message": "已锁定",
                "data": {"locked": True, "lock_info": lockInfo, "age_seconds": round(lockAge, 1)}}

    def _readLockFile(self, lockPath: str) -> dict or None:
        """读取锁文件内容"""
        try:
            with open(lockPath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    # ── 清理过期锁 ──
    def cleanStaleLocks(self, dirPath: str, maxAge: float = 60) -> dict:
        """
        清理目录中的过期锁文件
        :param dirPath: 目录路径<str>
        :param maxAge: 最大锁年龄(秒)<float>
        :return: {"code": int, "message": str, "data": {cleaned_count}}
        """
        cleaned = 0
        for fname in os.listdir(dirPath):
            if fname.endswith(".lock"):
                lockPath = os.path.join(dirPath, fname)
                lockInfo = self._readLockFile(lockPath)
                if lockInfo:
                    lockAge = time.time() - lockInfo.get("timestamp", 0)
                    if lockAge >= maxAge:
                        try:
                            os.remove(lockPath)
                            cleaned += 1
                        except OSError:
                            pass
                else:
                    # 无法解析的锁文件直接删除
                    try:
                        os.remove(lockPath)
                        cleaned += 1
                    except OSError:
                        pass

        return {"code": 200, "message": f"清理了 {cleaned} 个过期锁文件", "data": {"cleaned_count": cleaned}}

    # ── 文件监控(轮询) ──
    def watchFile(self, filePath: str, callback, interval: float = 1.0) -> dict:
        """
        监控文件变化(基于 mtime 轮询)
        :param filePath: 文件路径<str>
        :param callback: 回调函数 callable(filePath, oldMtime, newMtime)
        :param interval: 轮询间隔<秒>
        :return: {"code": int, "message": str, "data": watch_id}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": ""}

        watchId = f"watch_{filePath}_{time.time()}"
        lastMtime = os.path.getmtime(filePath)
        running = {"active": True}

        def _poll():
            nonlocal lastMtime
            while running["active"]:
                time.sleep(interval)
                if not running["active"]:
                    break
                try:
                    if not os.path.exists(filePath):
                        running["active"] = False
                        callback(filePath, lastMtime, None)
                        break
                    currentMtime = os.path.getmtime(filePath)
                    if currentMtime != lastMtime:
                        callback(filePath, lastMtime, currentMtime)
                        lastMtime = currentMtime
                except OSError:
                    break

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()

        self._watchers[watchId] = {"thread": thread, "running": running}
        return {"code": 200, "message": f"监控已启动: {filePath}", "data": watchId}

    def stopWatch(self, watchId: str) -> dict:
        """
        停止文件监控
        :param watchId: 监控ID<str>
        :return: {"code": int, "message": str}
        """
        watcher = self._watchers.pop(watchId, None)
        if watcher is None:
            return {"code": 404, "message": "监控任务不存在"}

        watcher["running"]["active"] = False
        return {"code": 200, "message": "监控已停止"}

    # ── 权限操作 ──
    def getFilePermissions(self, filePath: str) -> dict:
        """
        获取文件权限信息
        :param filePath: 文件路径<str>
        :return: {"code": int, "message": str, "data": {readable, writable, executable, mode}}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": {}}

        info = {
            "readable": os.access(filePath, os.R_OK),
            "writable": os.access(filePath, os.W_OK),
            "executable": os.access(filePath, os.X_OK),
            "exists": True,
        }
        try:
            info["mode"] = oct(os.stat(filePath).st_mode)[-3:]
        except OSError:
            info["mode"] = "???"

        return {"code": 200, "message": "获取成功", "data": info}

    def setFileReadOnly(self, filePath: str, readOnly: bool = True) -> dict:
        """
        设置文件只读/可写
        :param filePath: 文件路径<str>
        :param readOnly: 是否只读<bool>
        :return: {"code": int, "message": str}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}"}

        try:
            import stat
            currentMode = os.stat(filePath).st_mode
            if readOnly:
                # 去除写权限
                newMode = currentMode & ~stat.S_IWRITE
            else:
                # 添加写权限
                newMode = currentMode | stat.S_IWRITE
            os.chmod(filePath, newMode)
            return {"code": 200, "message": f"已设置为{'只读' if readOnly else '可写'}"}
        except OSError as e:
            return {"code": 500, "message": f"设置失败: {str(e)}"}