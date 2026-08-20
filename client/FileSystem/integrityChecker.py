"""
coding:utf-8
file: FileSystem/integrityChecker.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端文件完整性校验器
# ======================
# 与 Server 端逻辑相同, 校验客户端文件是否被篡改或缺失。

import os
import hashlib
import json
import time
import sys

# 注入 LogSystem 路径(client/LogSystem)
_CLIENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CLIENT_DIR not in sys.path:
    sys.path.insert(0, _CLIENT_DIR)

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "integrity_manifest.json")


class IntegrityChecker:
    """客户端文件完整性校验器"""

    def __init__(self):
        self._manifest = {}

        # 日志管理器(延迟导入)
        self._logger = None

    def _getLogger(self):
        """获取日志管理器(延迟初始化)"""
        if self._logger is None:
            from LogSystem.logManager import getLogger
            from LogSystem.logConfig import CATEGORY_FILE
            self._logger = getLogger()
            self._category = CATEGORY_FILE
        return self._logger, self._category

    def _hashFile(self, filePath: str) -> str or None:
        sha = hashlib.sha256()
        try:
            with open(filePath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    sha.update(chunk)
            return sha.hexdigest()
        except (IOError, OSError):
            return None

    def generateManifest(self, rootDir: str, excludeDirs: list = None,
                         excludeExts: list = None) -> dict:
        if excludeDirs is None:
            excludeDirs = ["__pycache__", ".git", ".venv", "venv", ".idea", "DataBase",
                          "cache", "models", "resources", "bug-logs", "FileSystem", "log"]
        if excludeExts is None:
            excludeExts = [".pyc", ".db", ".db-wal", ".db-shm", ".onnx", ".png", ".jpg"]

        logger, category = self._getLogger()
        logger.info(category, f"开始生成文件基线清单: {rootDir}")

        manifest = {}
        fileCount = 0

        for dirpath, dirnames, filenames in os.walk(rootDir):
            dirnames[:] = [d for d in dirnames if d not in excludeDirs]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in excludeExts:
                    continue
                fullPath = os.path.join(dirpath, filename)
                relPath = os.path.relpath(fullPath, rootDir)
                fileHash = self._hashFile(fullPath)
                if fileHash is None:
                    continue
                stat = os.stat(fullPath)
                manifest[relPath] = {"sha256": fileHash, "size": stat.st_size, "mtime": stat.st_mtime}
                fileCount += 1

        self._manifest = manifest
        logger.info(category, f"清单生成完成, 共 {fileCount} 个文件")
        return {"code": 200, "message": f"清单生成完成, 共 {fileCount} 个文件", "data": manifest}

    def saveManifest(self, outputPath: str = MANIFEST_PATH) -> dict:
        if not self._manifest:
            return {"code": 400, "message": "清单为空, 请先调用 generateManifest()"}
        logger, category = self._getLogger()
        data = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "file_count": len(self._manifest), "files": self._manifest}
        try:
            with open(outputPath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(category, f"清单已保存到 {outputPath}")
            return {"code": 200, "message": f"清单已保存到 {outputPath}"}
        except IOError as e:
            logger.error(category, f"清单保存失败: {str(e)}")
            return {"code": 500, "message": f"保存失败: {str(e)}"}

    def loadManifest(self, inputPath: str = MANIFEST_PATH) -> dict:
        if not os.path.exists(inputPath):
            return {"code": 404, "message": f"清单文件不存在: {inputPath}"}
        logger, category = self._getLogger()
        try:
            with open(inputPath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._manifest = data.get("files", {})
            logger.info(category, f"清单已加载, {len(self._manifest)} 个文件")
            return {"code": 200, "message": f"清单已加载, {len(self._manifest)} 个文件", "data": data}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(category, f"清单加载失败: {str(e)}")
            return {"code": 500, "message": f"加载失败: {str(e)}"}

    def verify(self, rootDir: str) -> dict:
        if not self._manifest:
            return {"code": 400, "message": "清单为空, 请先加载或生成清单"}
        logger, category = self._getLogger()
        logger.info(category, f"开始完整性校验: {rootDir}")

        result = {"added": [], "missing": [], "modified": [], "ok": [],
                  "total_manifest": len(self._manifest), "total_current": 0}
        currentFiles = set()
        for dirpath, dirnames, filenames in os.walk(rootDir):
            dirnames[:] = [d for d in dirnames if d not in
                          ["__pycache__", ".git", ".venv", "venv", ".idea", "DataBase", "cache", "models", "resources", "bug-logs", "FileSystem", "log"]]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in [".pyc", ".db", ".db-wal", ".db-shm", ".onnx", ".png", ".jpg"]:
                    continue
                fullPath = os.path.join(dirpath, filename)
                relPath = os.path.relpath(fullPath, rootDir)
                currentFiles.add(relPath)
                if relPath not in self._manifest:
                    result["added"].append(relPath)
                    continue
                expected = self._manifest[relPath]
                currentHash = self._hashFile(fullPath)
                if currentHash is None:
                    result["missing"].append(relPath)
                elif currentHash != expected["sha256"]:
                    result["modified"].append(relPath)
                else:
                    result["ok"].append(relPath)
        for relPath in self._manifest:
            if relPath not in currentFiles:
                result["missing"].append(relPath)
        result["total_current"] = len(currentFiles)
        issues = len(result["added"]) + len(result["missing"]) + len(result["modified"])
        if issues == 0:
            logger.info(category, f"完整性校验通过, {len(result['ok'])} 个文件正常")
            return {"code": 200, "message": f"完整性校验通过, {len(result['ok'])} 个文件正常", "data": result}
        else:
            logger.warning(category, f"完整性校验未通过: 新增{len(result['added'])} 缺失{len(result['missing'])} 篡改{len(result['modified'])}")
            return {"code": 400, "message": f"完整性校验未通过: 新增{len(result['added'])} 缺失{len(result['missing'])} 篡改{len(result['modified'])}", "data": result}