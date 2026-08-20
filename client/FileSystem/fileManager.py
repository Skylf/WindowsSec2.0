"""
coding:utf-8
file: FileSystem/fileManager.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端文件管理器
# 与 Server 端逻辑一致: 读/写/删/查/备份/恢复

import os
import shutil
import time
from datetime import datetime


class FileManager:
    """客户端文件管理器"""

    def readFile(self, filePath: str, encoding: str = "utf-8") -> dict:
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": ""}
        if not os.path.isfile(filePath):
            return {"code": 400, "message": f"不是文件: {filePath}", "data": ""}
        try:
            with open(filePath, "r", encoding=encoding) as f:
                content = f.read()
            return {"code": 200, "message": "读取成功", "data": content}
        except UnicodeDecodeError:
            for enc in ["gbk", "gb2312", "latin-1"]:
                try:
                    with open(filePath, "r", encoding=enc) as f:
                        content = f.read()
                    return {"code": 200, "message": f"读取成功(编码: {enc})", "data": content}
                except UnicodeDecodeError:
                    continue
            return {"code": 500, "message": "无法解码文件", "data": ""}
        except IOError as e:
            return {"code": 500, "message": f"读取失败: {str(e)}", "data": ""}

    def readBinaryFile(self, filePath: str) -> dict:
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": b""}
        try:
            with open(filePath, "rb") as f:
                return {"code": 200, "message": "读取成功", "data": f.read()}
        except IOError as e:
            return {"code": 500, "message": f"读取失败: {str(e)}", "data": b""}

    def writeFile(self, filePath: str, content: str, encoding: str = "utf-8", atomic: bool = True) -> dict:
        parentDir = os.path.dirname(filePath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)
        if atomic:
            tmpPath = filePath + ".tmp"
            try:
                with open(tmpPath, "w", encoding=encoding) as f:
                    f.write(content)
                os.replace(tmpPath, filePath)
                return {"code": 200, "message": f"写入成功: {filePath}"}
            except IOError as e:
                if os.path.exists(tmpPath):
                    os.remove(tmpPath)
                return {"code": 500, "message": f"写入失败: {str(e)}"}
        else:
            try:
                with open(filePath, "w", encoding=encoding) as f:
                    f.write(content)
                return {"code": 200, "message": f"写入成功: {filePath}"}
            except IOError as e:
                return {"code": 500, "message": f"写入失败: {str(e)}"}

    def appendFile(self, filePath: str, content: str, encoding: str = "utf-8") -> dict:
        parentDir = os.path.dirname(filePath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)
        try:
            with open(filePath, "a", encoding=encoding) as f:
                f.write(content)
            return {"code": 200, "message": f"追加写入成功: {filePath}"}
        except IOError as e:
            return {"code": 500, "message": f"追加写入失败: {str(e)}"}

    def deleteFile(self, filePath: str, safe: bool = True) -> dict:
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}"}
        if safe:
            self.backupFile(filePath)
        try:
            os.remove(filePath)
            return {"code": 200, "message": f"删除成功: {filePath}"}
        except OSError as e:
            return {"code": 500, "message": f"删除失败: {str(e)}"}

    def copyFile(self, srcPath: str, dstPath: str, overwrite: bool = False) -> dict:
        if not os.path.exists(srcPath):
            return {"code": 404, "message": f"源文件不存在: {srcPath}"}
        if os.path.exists(dstPath) and not overwrite:
            return {"code": 400, "message": f"目标文件已存在: {dstPath}"}
        parentDir = os.path.dirname(dstPath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)
        try:
            shutil.copy2(srcPath, dstPath)
            return {"code": 200, "message": f"复制成功: {srcPath} → {dstPath}"}
        except (IOError, shutil.Error) as e:
            return {"code": 500, "message": f"复制失败: {str(e)}"}

    def moveFile(self, srcPath: str, dstPath: str, overwrite: bool = False) -> dict:
        if not os.path.exists(srcPath):
            return {"code": 404, "message": f"源文件不存在: {srcPath}"}
        if os.path.exists(dstPath) and not overwrite:
            return {"code": 400, "message": f"目标文件已存在: {dstPath}"}
        parentDir = os.path.dirname(dstPath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)
        try:
            shutil.move(srcPath, dstPath)
            return {"code": 200, "message": f"移动成功: {srcPath} → {dstPath}"}
        except (IOError, shutil.Error) as e:
            return {"code": 500, "message": f"移动失败: {str(e)}"}

    def listFiles(self, dirPath: str, pattern: str = "*", recursive: bool = False,
                  excludeDirs: list = None) -> dict:
        if not os.path.exists(dirPath) or not os.path.isdir(dirPath):
            return {"code": 404, "message": f"目录不存在: {dirPath}", "data": []}
        if excludeDirs is None:
            excludeDirs = ["__pycache__", ".git", ".venv", "venv", ".idea"]
        import fnmatch
        files = []
        if recursive:
            for dirpath, dirnames, filenames in os.walk(dirPath):
                dirnames[:] = [d for d in dirnames if d not in excludeDirs]
                for fname in filenames:
                    if fnmatch.fnmatch(fname, pattern):
                        files.append(self._getFileStat(os.path.join(dirpath, fname), dirPath))
        else:
            for fname in os.listdir(dirPath):
                fullPath = os.path.join(dirPath, fname)
                if os.path.isfile(fullPath) and fnmatch.fnmatch(fname, pattern):
                    files.append(self._getFileStat(fullPath, dirPath))
        return {"code": 200, "message": f"找到 {len(files)} 个文件", "data": files}

    def _getFileStat(self, filePath: str, baseDir: str) -> dict:
        stat = os.stat(filePath)
        return {"name": os.path.basename(filePath), "path": os.path.relpath(filePath, baseDir),
                "size": stat.st_size, "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "ctime": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")}

    def _formatSize(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def getFileInfo(self, filePath: str) -> dict:
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": {}}
        stat = os.stat(filePath)
        info = {"name": os.path.basename(filePath), "path": os.path.abspath(filePath),
                "size": stat.st_size, "size_human": self._formatSize(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "extension": os.path.splitext(filePath)[1].lower(), "exists": True}
        return {"code": 200, "message": "获取成功", "data": info}

    def backupFile(self, filePath: str, backupDir: str = None) -> dict:
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}"}
        if backupDir is None:
            backupDir = os.path.join(os.path.dirname(filePath), ".backup")
        os.makedirs(backupDir, exist_ok=True)
        baseName = os.path.basename(filePath)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backupPath = os.path.join(backupDir, f"{baseName}.{timestamp}.bak")
        try:
            shutil.copy2(filePath, backupPath)
            return {"code": 200, "message": f"备份成功: {backupPath}", "data": backupPath}
        except IOError as e:
            return {"code": 500, "message": f"备份失败: {str(e)}", "data": ""}

    def restoreFile(self, backupPath: str, targetPath: str, overwrite: bool = False) -> dict:
        if not os.path.exists(backupPath):
            return {"code": 404, "message": f"备份文件不存在: {backupPath}"}
        if os.path.exists(targetPath) and not overwrite:
            return {"code": 400, "message": f"目标文件已存在: {targetPath}"}
        try:
            shutil.copy2(backupPath, targetPath)
            return {"code": 200, "message": f"恢复成功: {backupPath} → {targetPath}"}
        except IOError as e:
            return {"code": 500, "message": f"恢复失败: {str(e)}"}

    def ensureDir(self, dirPath: str) -> dict:
        try:
            os.makedirs(dirPath, exist_ok=True)
            return {"code": 200, "message": f"目录就绪: {dirPath}"}
        except OSError as e:
            return {"code": 500, "message": f"创建目录失败: {str(e)}"}