"""
coding:utf-8
file: FileSystem/fileGuard.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端文件守护(访问控制)

import os
import time
import threading
import json


class FileGuard:
    """客户端文件守护"""

    def __init__(self):
        self._lock = threading.Lock()
        self._watchers = {}

    def lockFile(self, filePath: str, lockId: str = None, timeout: float = 0) -> dict:
        lockPath = filePath + ".lock"
        with self._lock:
            if os.path.exists(lockPath):
                existingLock = self._readLockFile(lockPath)
                if existingLock:
                    lockAge = time.time() - existingLock.get("timestamp", 0)
                    if lockAge < 60:
                        if timeout > 0:
                            waited = 0
                            while os.path.exists(lockPath) and waited < timeout:
                                time.sleep(0.1)
                                waited += 0.1
                            if os.path.exists(lockPath):
                                return {"code": 400, "message": f"文件已被锁定", "data": ""}
                        else:
                            return {"code": 400, "message": f"文件已被锁定", "data": ""}
                    else:
                        os.remove(lockPath)
            lockId = lockId or f"pid_{os.getpid()}"
            lockData = {"lock_id": lockId, "pid": os.getpid(), "timestamp": time.time(), "file": filePath}
            try:
                with open(lockPath, "w", encoding="utf-8") as f:
                    json.dump(lockData, f)
                return {"code": 200, "message": "锁定成功", "data": lockId}
            except IOError as e:
                return {"code": 500, "message": f"锁定失败: {str(e)}", "data": ""}

    def unlockFile(self, filePath: str, lockId: str = None) -> dict:
        lockPath = filePath + ".lock"
        if not os.path.exists(lockPath):
            return {"code": 404, "message": "文件未被锁定"}
        if lockId:
            existingLock = self._readLockFile(lockPath)
            if existingLock and existingLock.get("lock_id") != lockId:
                return {"code": 403, "message": "锁主不匹配, 无法解锁"}
        try:
            os.remove(lockPath)
            return {"code": 200, "message": "解锁成功"}
        except OSError as e:
            return {"code": 500, "message": f"解锁失败: {str(e)}"}

    def isLocked(self, filePath: str) -> dict:
        lockPath = filePath + ".lock"
        if not os.path.exists(lockPath):
            return {"code": 200, "message": "未锁定", "data": {"locked": False, "lock_info": None}}
        lockInfo = self._readLockFile(lockPath)
        if lockInfo is None:
            return {"code": 200, "message": "未锁定", "data": {"locked": False, "lock_info": None}}
        lockAge = time.time() - lockInfo.get("timestamp", 0)
        if lockAge >= 60:
            return {"code": 200, "message": "锁已过期", "data": {"locked": False, "lock_info": lockInfo, "expired": True}}
        return {"code": 200, "message": "已锁定", "data": {"locked": True, "lock_info": lockInfo, "age_seconds": round(lockAge, 1)}}

    def _readLockFile(self, lockPath: str) -> dict or None:
        try:
            with open(lockPath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def cleanStaleLocks(self, dirPath: str, maxAge: float = 60) -> dict:
        cleaned = 0
        for fname in os.listdir(dirPath):
            if fname.endswith(".lock"):
                lockPath = os.path.join(dirPath, fname)
                lockInfo = self._readLockFile(lockPath)
                if lockInfo:
                    if time.time() - lockInfo.get("timestamp", 0) >= maxAge:
                        try:
                            os.remove(lockPath)
                            cleaned += 1
                        except OSError:
                            pass
                else:
                    try:
                        os.remove(lockPath)
                        cleaned += 1
                    except OSError:
                        pass
        return {"code": 200, "message": f"清理了 {cleaned} 个过期锁文件", "data": {"cleaned_count": cleaned}}

    def getFilePermissions(self, filePath: str) -> dict:
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": {}}
        info = {"readable": os.access(filePath, os.R_OK), "writable": os.access(filePath, os.W_OK),
                "executable": os.access(filePath, os.X_OK), "exists": True}
        try:
            info["mode"] = oct(os.stat(filePath).st_mode)[-3:]
        except OSError:
            info["mode"] = "???"
        return {"code": 200, "message": "获取成功", "data": info}