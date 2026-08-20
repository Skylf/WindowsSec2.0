"""
coding:utf-8
file: FileSystem/integrityChecker.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 文件完整性校验器
# =================
# 基于 SHA-256 哈希的文件完整性验证。
# 生成文件清单 → 存储基线 → 校验比对 → 报告差异。
# 用途: 检测项目文件是否被篡改或缺失。

import os
import hashlib
import json
import time

# 清单文件默认路径
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "integrity_manifest.json")


class IntegrityChecker:
    """
    文件完整性校验器
    ================
    功能:
    - generateManifest(): 扫描指定目录, 生成所有文件的哈希清单
    - saveManifest(): 保存清单到文件
    - loadManifest(): 加载已有清单
    - verify(): 对比当前文件与清单, 报告新增/缺失/篡改
    """

    def __init__(self):
        self._manifest = {}  # {相对路径: {sha256, size, mtime}}

    # ── 文件哈希计算 ──
    def _hashFile(self, filePath: str) -> str or None:
        """
        计算文件 SHA-256 哈希
        :param filePath: 文件路径<str>
        :return: 哈希值<str> 或 None
        """
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

    # ── 扫描目录生成清单 ──
    def generateManifest(self, rootDir: str, excludeDirs: list = None,
                         excludeExts: list = None) -> dict:
        """
        扫描目录, 生成文件哈希清单
        :param rootDir: 根目录<str>
        :param excludeDirs: 排除的目录名列表<list> (如 __pycache__)
        :param excludeExts: 排除的扩展名列表<list> (如 .pyc)
        :return: {"code": 200, "message": str, "data": {文件清单}}
        """
        if excludeDirs is None:
            excludeDirs = ["__pycache__", ".git", ".venv", "venv", ".idea", "DataBase",
                          "cache", "models", "resources", "bug-logs", "FileSystem"]
        if excludeExts is None:
            excludeExts = [".pyc", ".db", ".db-wal", ".db-shm", ".onnx", ".png", ".jpg"]

        manifest = {}
        fileCount = 0

        for dirpath, dirnames, filenames in os.walk(rootDir):
            # 过滤排除目录
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
                manifest[relPath] = {
                    "sha256": fileHash,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
                fileCount += 1

        self._manifest = manifest
        return {"code": 200, "message": f"清单生成完成, 共 {fileCount} 个文件", "data": manifest}

    # ── 保存/加载清单 ──
    def saveManifest(self, outputPath: str = MANIFEST_PATH) -> dict:
        """
        保存清单到 JSON 文件
        :param outputPath: 输出路径<str>
        :return: {"code": int, "message": str}
        """
        if not self._manifest:
            return {"code": 400, "message": "清单为空, 请先调用 generateManifest()"}

        data = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": len(self._manifest),
            "files": self._manifest,
        }
        try:
            with open(outputPath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"code": 200, "message": f"清单已保存到 {outputPath}"}
        except IOError as e:
            return {"code": 500, "message": f"保存失败: {str(e)}"}

    def loadManifest(self, inputPath: str = MANIFEST_PATH) -> dict:
        """
        加载已有的完整性清单
        :param inputPath: 清单文件路径<str>
        :return: {"code": int, "message": str, "data": dict}
        """
        if not os.path.exists(inputPath):
            return {"code": 404, "message": f"清单文件不存在: {inputPath}"}

        try:
            with open(inputPath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._manifest = data.get("files", {})
            return {"code": 200, "message": f"清单已加载, {len(self._manifest)} 个文件", "data": data}
        except (json.JSONDecodeError, IOError) as e:
            return {"code": 500, "message": f"加载失败: {str(e)}"}

    # ── 校验 ──
    def verify(self, rootDir: str) -> dict:
        """
        对比当前文件与清单, 报告差异
        :param rootDir: 根目录<str>
        :return: {"code": int, "message": str, "data": {新增/缺失/篡改/正常}}
        """
        if not self._manifest:
            return {"code": 400, "message": "清单为空, 请先加载或生成清单"}

        result = {
            "added": [],      # 新增文件(不在清单中)
            "missing": [],    # 缺失文件(清单有但磁盘无)
            "modified": [],   # 篡改文件(哈希不匹配)
            "ok": [],         # 正常文件
            "total_manifest": len(self._manifest),
            "total_current": 0,
        }

        currentFiles = set()

        for dirpath, dirnames, filenames in os.walk(rootDir):
            dirnames[:] = [d for d in dirnames if d not in
                          ["__pycache__", ".git", ".venv", "venv", ".idea", "DataBase",
                           "cache", "models", "resources", "bug-logs", "FileSystem"]]

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

        # 检查缺失文件(清单有但磁盘无)
        for relPath in self._manifest:
            if relPath not in currentFiles:
                result["missing"].append(relPath)

        result["total_current"] = len(currentFiles)

        issues = len(result["added"]) + len(result["missing"]) + len(result["modified"])
        if issues == 0:
            return {"code": 200, "message": f"完整性校验通过, {len(result['ok'])} 个文件正常", "data": result}
        else:
            return {"code": 400, "message": f"完整性校验未通过: 新增{len(result['added'])} 缺失{len(result['missing'])} 篡改{len(result['modified'])}",
                    "data": result}