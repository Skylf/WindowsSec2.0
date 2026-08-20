"""
coding:utf-8
file: FileSystem/fileManager.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 文件管理器
# ==========

import os
import shutil
import json
import time
from datetime import datetime


class FileManager:
    """
    文件管理器
    ==========
    功能:
    - readFile(): 安全读取文件(支持中文路径、编码检测)
    - writeFile(): 安全写入文件(原子写入: 先写临时文件再替换)
    - appendFile(): 追加写入
    - deleteFile(): 安全删除文件
    - copyFile(): 复制文件
    - moveFile(): 移动文件
    - listFiles(): 列目录(支持过滤)
    - getFileInfo(): 获取文件元信息
    - searchFiles(): 按名称/内容搜索文件
    - backupFile(): 备份文件(时间戳命名)
    - restoreFile(): 从备份恢复
    - safeRename(): 安全重命名
    """

    def __init__(self):
        pass

    # ── 读文件 ──
    def readFile(self, filePath: str, encoding: str = "utf-8") -> dict:
        """
        安全读取文件内容
        :param filePath: 文件路径<str>
        :param encoding: 编码<str>
        :return: {"code": int, "message": str, "data": str}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": ""}
        if not os.path.isfile(filePath):
            return {"code": 400, "message": f"不是文件: {filePath}", "data": ""}

        try:
            with open(filePath, "r", encoding=encoding) as f:
                content = f.read()
            return {"code": 200, "message": "读取成功", "data": content}
        except UnicodeDecodeError:
            # 尝试其他编码
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
        """
        读取二进制文件
        :param filePath: 文件路径<str>
        :return: {"code": int, "message": str, "data": bytes}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": b""}

        try:
            with open(filePath, "rb") as f:
                content = f.read()
            return {"code": 200, "message": "读取成功", "data": content}
        except IOError as e:
            return {"code": 500, "message": f"读取失败: {str(e)}", "data": b""}

    # ── 写文件 ──
    def writeFile(self, filePath: str, content: str, encoding: str = "utf-8",
                  atomic: bool = True) -> dict:
        """
        安全写入文件(原子写入: 先写临时文件, 再替换)
        :param filePath: 文件路径<str>
        :param content: 内容<str>
        :param encoding: 编码<str>
        :param atomic: 是否原子写入<bool>
        :return: {"code": int, "message": str}
        """
        # 确保父目录存在
        parentDir = os.path.dirname(filePath)
        if parentDir and not os.path.exists(parentDir):
            try:
                os.makedirs(parentDir, exist_ok=True)
            except OSError as e:
                return {"code": 500, "message": f"创建父目录失败: {str(e)}"}

        if atomic:
            tmpPath = filePath + ".tmp"
            try:
                with open(tmpPath, "w", encoding=encoding) as f:
                    f.write(content)
                os.replace(tmpPath, filePath)  # 原子替换
                return {"code": 200, "message": f"写入成功: {filePath}"}
            except IOError as e:
                # 清理临时文件
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

    def writeBinaryFile(self, filePath: str, content: bytes, atomic: bool = True) -> dict:
        """
        写入二进制文件
        :param filePath: 文件路径<str>
        :param content: 内容<bytes>
        :param atomic: 是否原子写入<bool>
        :return: {"code": int, "message": str}
        """
        parentDir = os.path.dirname(filePath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)

        if atomic:
            tmpPath = filePath + ".tmp"
            try:
                with open(tmpPath, "wb") as f:
                    f.write(content)
                os.replace(tmpPath, filePath)
                return {"code": 200, "message": f"写入成功: {filePath}"}
            except IOError as e:
                if os.path.exists(tmpPath):
                    os.remove(tmpPath)
                return {"code": 500, "message": f"写入失败: {str(e)}"}
        else:
            try:
                with open(filePath, "wb") as f:
                    f.write(content)
                return {"code": 200, "message": f"写入成功: {filePath}"}
            except IOError as e:
                return {"code": 500, "message": f"写入失败: {str(e)}"}

    # ── 追加写入 ──
    def appendFile(self, filePath: str, content: str, encoding: str = "utf-8") -> dict:
        """
        追加写入文件
        :param filePath: 文件路径<str>
        :param content: 内容<str>
        :param encoding: 编码<str>
        :return: {"code": int, "message": str}
        """
        parentDir = os.path.dirname(filePath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)

        try:
            with open(filePath, "a", encoding=encoding) as f:
                f.write(content)
            return {"code": 200, "message": f"追加写入成功: {filePath}"}
        except IOError as e:
            return {"code": 500, "message": f"追加写入失败: {str(e)}"}

    # ── 删除文件 ──
    def deleteFile(self, filePath: str, safe: bool = True) -> dict:
        """
        删除文件(安全模式: 先备份再删除)
        :param filePath: 文件路径<str>
        :param safe: 是否安全删除(先备份)<bool>
        :return: {"code": int, "message": str}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}"}

        if safe:
            backupResult = self.backupFile(filePath)
            if backupResult["code"] != 200:
                return {"code": 500, "message": f"备份失败, 取消删除: {backupResult['message']}"}

        try:
            os.remove(filePath)
            return {"code": 200, "message": f"删除成功: {filePath}"}
        except OSError as e:
            return {"code": 500, "message": f"删除失败: {str(e)}"}

    # ── 复制/移动 ──
    def copyFile(self, srcPath: str, dstPath: str, overwrite: bool = False) -> dict:
        """
        复制文件
        :param srcPath: 源路径<str>
        :param dstPath: 目标路径<str>
        :param overwrite: 是否覆盖<bool>
        :return: {"code": int, "message": str}
        """
        if not os.path.exists(srcPath):
            return {"code": 404, "message": f"源文件不存在: {srcPath}"}
        if os.path.exists(dstPath) and not overwrite:
            return {"code": 400, "message": f"目标文件已存在: {dstPath}"}

        parentDir = os.path.dirname(dstPath)
        if parentDir and not os.path.exists(parentDir):
            os.makedirs(parentDir, exist_ok=True)

        try:
            shutil.copy2(srcPath, dstPath)  # copy2 保留元数据
            return {"code": 200, "message": f"复制成功: {srcPath} → {dstPath}"}
        except (IOError, shutil.Error) as e:
            return {"code": 500, "message": f"复制失败: {str(e)}"}

    def moveFile(self, srcPath: str, dstPath: str, overwrite: bool = False) -> dict:
        """
        移动文件
        :param srcPath: 源路径<str>
        :param dstPath: 目标路径<str>
        :param overwrite: 是否覆盖<bool>
        :return: {"code": int, "message": str}
        """
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

    # ── 列目录 ──
    def listFiles(self, dirPath: str, pattern: str = "*", recursive: bool = False,
                  excludeDirs: list = None) -> dict:
        """
        列出目录文件
        :param dirPath: 目录路径<str>
        :param pattern: 文件名匹配模式<str> (如 *.py)
        :param recursive: 是否递归<bool>
        :param excludeDirs: 排除的目录名<list>
        :return: {"code": int, "message": str, "data": [文件信息]}
        """
        if not os.path.exists(dirPath):
            return {"code": 404, "message": f"目录不存在: {dirPath}", "data": []}
        if not os.path.isdir(dirPath):
            return {"code": 400, "message": f"不是目录: {dirPath}", "data": []}

        if excludeDirs is None:
            excludeDirs = ["__pycache__", ".git", ".venv", "venv", ".idea"]

        import fnmatch
        files = []

        if recursive:
            for dirpath, dirnames, filenames in os.walk(dirPath):
                dirnames[:] = [d for d in dirnames if d not in excludeDirs]
                for fname in filenames:
                    if fnmatch.fnmatch(fname, pattern):
                        fullPath = os.path.join(dirpath, fname)
                        files.append(self._getFileStat(fullPath, dirPath))
        else:
            for fname in os.listdir(dirPath):
                fullPath = os.path.join(dirPath, fname)
                if os.path.isfile(fullPath) and fnmatch.fnmatch(fname, pattern):
                    files.append(self._getFileStat(fullPath, dirPath))

        return {"code": 200, "message": f"找到 {len(files)} 个文件", "data": files}

    def _getFileStat(self, filePath: str, baseDir: str) -> dict:
        """获取文件状态信息"""
        stat = os.stat(filePath)
        return {
            "name": os.path.basename(filePath),
            "path": os.path.relpath(filePath, baseDir),
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "ctime": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            "is_dir": False,
        }

    # ── 文件信息 ──
    def getFileInfo(self, filePath: str) -> dict:
        """
        获取文件详细元信息
        :param filePath: 文件路径<str>
        :return: {"code": int, "message": str, "data": dict}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}", "data": {}}

        try:
            stat = os.stat(filePath)
            info = {
                "name": os.path.basename(filePath),
                "path": os.path.abspath(filePath),
                "size": stat.st_size,
                "size_human": self._formatSize(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "ctime": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "atime": datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S"),
                "is_dir": os.path.isdir(filePath),
                "is_file": os.path.isfile(filePath),
                "extension": os.path.splitext(filePath)[1].lower(),
                "exists": True,
            }
            return {"code": 200, "message": "获取成功", "data": info}
        except OSError as e:
            return {"code": 500, "message": f"获取失败: {str(e)}", "data": {}}

    def _formatSize(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    # ── 搜索文件 ──
    def searchFiles(self, rootDir: str, namePattern: str = None,
                    contentPattern: str = None, recursive: bool = True) -> dict:
        """
        搜索文件(按名称或内容)
        :param rootDir: 搜索根目录<str>
        :param namePattern: 文件名匹配<str> (如 "*.py")
        :param contentPattern: 内容匹配<str> (如 "class AddDatabase")
        :param recursive: 是否递归<bool>
        :return: {"code": int, "message": str, "data": [匹配文件]}
        """
        if not os.path.exists(rootDir):
            return {"code": 404, "message": f"目录不存在: {rootDir}", "data": []}

        import fnmatch
        results = []
        excludeDirs = ["__pycache__", ".git", ".venv", "venv", ".idea", "DataBase",
                       "cache", "models", "resources", "bug-logs"]

        def _walk(currentDir):
            for fname in os.listdir(currentDir):
                fullPath = os.path.join(currentDir, fname)
                if os.path.isdir(fullPath):
                    if fname in excludeDirs:
                        continue
                    if recursive:
                        _walk(fullPath)
                elif os.path.isfile(fullPath):
                    # 名称匹配
                    if namePattern and not fnmatch.fnmatch(fname, namePattern):
                        continue
                    # 内容匹配
                    if contentPattern:
                        try:
                            with open(fullPath, "r", encoding="utf-8", errors="ignore") as f:
                                if contentPattern.lower() not in f.read().lower():
                                    continue
                        except IOError:
                            continue
                    results.append(self._getFileStat(fullPath, rootDir))

        _walk(rootDir)
        return {"code": 200, "message": f"找到 {len(results)} 个匹配文件", "data": results}

    # ── 备份/恢复 ──
    def backupFile(self, filePath: str, backupDir: str = None) -> dict:
        """
        备份文件(时间戳命名)
        :param filePath: 文件路径<str>
        :param backupDir: 备份目录<str>, 为空则放在同目录下的 .backup
        :return: {"code": int, "message": str, "data": backup_path}
        """
        if not os.path.exists(filePath):
            return {"code": 404, "message": f"文件不存在: {filePath}"}

        if backupDir is None:
            backupDir = os.path.join(os.path.dirname(filePath), ".backup")

        os.makedirs(backupDir, exist_ok=True)

        baseName = os.path.basename(filePath)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backupName = f"{baseName}.{timestamp}.bak"
        backupPath = os.path.join(backupDir, backupName)

        try:
            shutil.copy2(filePath, backupPath)
            return {"code": 200, "message": f"备份成功: {backupPath}", "data": backupPath}
        except IOError as e:
            return {"code": 500, "message": f"备份失败: {str(e)}", "data": ""}

    def restoreFile(self, backupPath: str, targetPath: str, overwrite: bool = False) -> dict:
        """
        从备份恢复文件
        :param backupPath: 备份文件路径<str>
        :param targetPath: 恢复目标路径<str>
        :param overwrite: 是否覆盖<bool>
        :return: {"code": int, "message": str}
        """
        if not os.path.exists(backupPath):
            return {"code": 404, "message": f"备份文件不存在: {backupPath}"}
        if os.path.exists(targetPath) and not overwrite:
            return {"code": 400, "message": f"目标文件已存在: {targetPath}"}

        try:
            shutil.copy2(backupPath, targetPath)
            return {"code": 200, "message": f"恢复成功: {backupPath} → {targetPath}"}
        except IOError as e:
            return {"code": 500, "message": f"恢复失败: {str(e)}"}

    def listBackups(self, filePath: str) -> dict:
        """
        列出文件的所有备份
        :param filePath: 原文件路径<str>
        :return: {"code": int, "message": str, "data": [备份文件信息]}
        """
        backupDir = os.path.join(os.path.dirname(filePath), ".backup")
        if not os.path.exists(backupDir):
            return {"code": 200, "message": "无备份", "data": []}

        baseName = os.path.basename(filePath)
        backups = []
        for fname in os.listdir(backupDir):
            if fname.startswith(baseName) and fname.endswith(".bak"):
                fullPath = os.path.join(backupDir, fname)
                backups.append(self._getFileStat(fullPath, backupDir))

        backups.sort(key=lambda x: x["mtime"], reverse=True)
        return {"code": 200, "message": f"找到 {len(backups)} 个备份", "data": backups}

    # ── 工具方法 ──
    def safeRename(self, oldPath: str, newPath: str) -> dict:
        """
        安全重命名
        :param oldPath: 旧路径<str>
        :param newPath: 新路径<str>
        :return: {"code": int, "message": str}
        """
        if not os.path.exists(oldPath):
            return {"code": 404, "message": f"文件不存在: {oldPath}"}
        if os.path.exists(newPath):
            return {"code": 400, "message": f"目标路径已存在: {newPath}"}

        try:
            os.rename(oldPath, newPath)
            return {"code": 200, "message": f"重命名成功: {oldPath} → {newPath}"}
        except OSError as e:
            return {"code": 500, "message": f"重命名失败: {str(e)}"}

    def ensureDir(self, dirPath: str) -> dict:
        """
        确保目录存在(不存在则创建)
        :param dirPath: 目录路径<str>
        :return: {"code": int, "message": str}
        """
        try:
            os.makedirs(dirPath, exist_ok=True)
            return {"code": 200, "message": f"目录就绪: {dirPath}"}
        except OSError as e:
            return {"code": 500, "message": f"创建目录失败: {str(e)}"}

    def getDirSize(self, dirPath: str) -> dict:
        """
        计算目录总大小
        :param dirPath: 目录路径<str>
        :return: {"code": int, "message": str, "data": {size, size_human, file_count}}
        """
        if not os.path.exists(dirPath) or not os.path.isdir(dirPath):
            return {"code": 404, "message": f"目录不存在: {dirPath}", "data": {}}

        totalSize = 0
        fileCount = 0
        for dirpath, dirnames, filenames in os.walk(dirPath):
            for fname in filenames:
                try:
                    totalSize += os.path.getsize(os.path.join(dirpath, fname))
                    fileCount += 1
                except OSError:
                    pass

        return {"code": 200, "message": "计算完成",
                "data": {"size": totalSize, "size_human": self._formatSize(totalSize), "file_count": fileCount}}