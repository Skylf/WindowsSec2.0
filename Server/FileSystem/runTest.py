"""
coding:utf-8
file: FileSystem/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端文件系统全流程测试
# ========================
# 测试: 完整性校验 / 文件读写删查 / 备份恢复 / 锁机制 / 权限
# 运行: python Server/FileSystem/runTest.py

import os
import sys
import time
import tempfile

# 路径
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from integrityChecker import IntegrityChecker
from fileManager import FileManager
from fileGuard import FileGuard

PASS = 0
FAIL = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def main():
    global PASS, FAIL
    print("=" * 60)
    print("  服务端文件系统全流程测试")
    print("=" * 60)

    fm = FileManager()
    fg = FileGuard()
    ic = IntegrityChecker()

    # 测试目录
    testDir = os.path.join(tempfile.gettempdir(), "fs_test_server")
    if os.path.exists(testDir):
        import shutil
        shutil.rmtree(testDir)

    # ── 1. 目录操作 ──
    print("\n[1] 目录操作")
    test("创建目录", fm.ensureDir(testDir)["code"] == 200)
    test("目录存在", os.path.exists(testDir))

    # ── 2. 文件写入 ──
    print("\n[2] 文件写入")
    testFile = os.path.join(testDir, "test.txt")
    r = fm.writeFile(testFile, "Hello, FileSystem!\n第二行中文测试")
    test("写入文本文件", r["code"] == 200, r["message"])
    test("文件存在", os.path.exists(testFile))

    # 二进制写入
    binFile = os.path.join(testDir, "test.bin")
    r = fm.writeBinaryFile(binFile, b"\x00\x01\x02\xFF\xFE")
    test("写入二进制文件", r["code"] == 200)

    # 追加写入
    r = fm.appendFile(testFile, "\n追加的一行")
    test("追加写入", r["code"] == 200)

    # ── 3. 文件读取 ──
    print("\n[3] 文件读取")
    r = fm.readFile(testFile)
    test("读取文本文件", r["code"] == 200)
    test("内容包含追加行", "追加的一行" in r["data"], r["data"][:50])

    r = fm.readBinaryFile(binFile)
    test("读取二进制文件", r["code"] == 200 and len(r["data"]) == 5)

    r = fm.readFile("nonexistent.txt")
    test("读取不存在的文件 → 404", r["code"] == 404)

    # ── 4. 文件信息 ──
    print("\n[4] 文件信息")
    r = fm.getFileInfo(testFile)
    test("获取文件信息", r["code"] == 200)
    test("文件名正确", r["data"]["name"] == "test.txt")
    test("大小 > 0", r["data"]["size"] > 0)

    # ── 5. 列目录 ──
    print("\n[5] 列目录")
    r = fm.listFiles(testDir)
    test("列出文件", r["code"] == 200)
    test("2个文件", len(r["data"]) == 2, f"实际: {len(r['data'])}")

    r = fm.listFiles(testDir, "*.txt")
    test("过滤 *.txt", len(r["data"]) == 1)

    # ── 6. 复制/移动 ──
    print("\n[6] 复制/移动")
    copyFile = os.path.join(testDir, "test_copy.txt")
    r = fm.copyFile(testFile, copyFile)
    test("复制文件", r["code"] == 200)
    test("副本存在", os.path.exists(copyFile))

    r = fm.copyFile(testFile, copyFile, overwrite=False)
    test("不覆盖已有文件 → 400", r["code"] == 400)

    moveFile = os.path.join(testDir, "test_moved.txt")
    r = fm.moveFile(copyFile, moveFile)
    test("移动文件", r["code"] == 200)
    test("原文件已移走", not os.path.exists(copyFile))
    test("新位置存在", os.path.exists(moveFile))

    # ── 7. 备份/恢复 ──
    print("\n[7] 备份/恢复")
    r = fm.backupFile(testFile)
    test("备份文件", r["code"] == 200)
    backupPath = r["data"]
    test("备份文件存在", os.path.exists(backupPath))

    restoreFile = os.path.join(testDir, "test_restored.txt")
    r = fm.restoreFile(backupPath, restoreFile)
    test("恢复文件", r["code"] == 200)
    r = fm.readFile(restoreFile)
    test("恢复内容一致", "Hello, FileSystem!" in r["data"])

    # ── 8. 文件锁 ──
    print("\n[8] 文件锁")
    lockFile = os.path.join(testDir, "locked.txt")
    fm.writeFile(lockFile, "locked content")

    r = fg.lockFile(lockFile)
    test("锁定文件", r["code"] == 200)
    lockId = r["data"]

    r = fg.isLocked(lockFile)
    test("检测到锁定", r["data"]["locked"] == True)

    r = fg.lockFile(lockFile)
    test("重复锁定被拒绝", r["code"] == 400)

    r = fg.unlockFile(lockFile, lockId)
    test("解锁文件", r["code"] == 200)

    r = fg.isLocked(lockFile)
    test("解锁后未锁定", r["data"]["locked"] == False)

    # 锁主不匹配
    r = fg.lockFile(lockFile, lockId="owner_A")
    r2 = fg.unlockFile(lockFile, lockId="owner_B")
    test("锁主不匹配 → 403", r2["code"] == 403)
    fg.unlockFile(lockFile, "owner_A")

    # ── 9. 文件权限 ──
    print("\n[9] 文件权限")
    r = fg.getFilePermissions(testFile)
    test("获取权限", r["code"] == 200)
    test("可读", r["data"]["readable"] == True)
    test("可写", r["data"]["writable"] == True)

    # ── 10. 完整性校验 ──
    print("\n[10] 完整性校验")
    r = ic.generateManifest(testDir)
    test("生成清单", r["code"] == 200)
    test("清单有文件", r["data"])

    r = ic.saveManifest(os.path.join(tempfile.gettempdir(), "manifest_server.json"))
    test("保存清单", r["code"] == 200)

    r = ic.verify(testDir)
    test("校验通过", r["code"] == 200, r["message"])

    # 模拟篡改
    fm.appendFile(testFile, "\n篡改内容")
    r = ic.verify(testDir)
    test("检测到篡改", r["code"] == 400)
    test("modified 非空", len(r["data"]["modified"]) > 0)

    # ── 11. 文件搜索 ──
    print("\n[11] 文件搜索")
    r = fm.searchFiles(testDir, "*.txt")
    test("搜索 *.txt", r["code"] == 200 and len(r["data"]) > 0)

    r = fm.searchFiles(testDir, contentPattern="FileSystem")
    test("搜索内容", r["code"] == 200 and len(r["data"]) > 0)

    # ── 12. 安全删除 ──
    print("\n[12] 安全删除")
    r = fm.deleteFile(moveFile, safe=True)
    test("安全删除(备份后删除)", r["code"] == 200)
    test("文件已删除", not os.path.exists(moveFile))

    r = fm.deleteFile("nonexistent.txt")
    test("删除不存在的文件 → 404", r["code"] == 404)

    # ── 13. 重命名 ──
    print("\n[13] 重命名")
    renameFile = os.path.join(testDir, "renamed.txt")
    r = fm.safeRename(testFile, renameFile)
    test("重命名成功", r["code"] == 200)
    test("旧名不存在", not os.path.exists(testFile))
    test("新名存在", os.path.exists(renameFile))

    # 清理
    import shutil
    shutil.rmtree(testDir)

    # 总结
    print("\n" + "=" * 60)
    print(f"  测试结果: {PASS} 通过 / {FAIL} 失败 (共 {PASS + FAIL} 项)")
    if FAIL == 0:
        print("  全部通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()