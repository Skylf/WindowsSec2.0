"""
coding:utf-8
file: FileSystem/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端文件系统全流程测试
# ========================
# 运行: python client/FileSystem/runTest.py

import os
import sys
import tempfile

_CLIENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CLIENT_DIR not in sys.path:
    sys.path.insert(0, _CLIENT_DIR)

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
    print("  客户端文件系统全流程测试")
    print("=" * 60)

    fm = FileManager()
    fg = FileGuard()
    ic = IntegrityChecker()

    testDir = os.path.join(tempfile.gettempdir(), "fs_test_client")
    if os.path.exists(testDir):
        import shutil
        shutil.rmtree(testDir)

    # ── 1. 目录操作 ──
    print("\n[1] 目录操作")
    test("创建目录", fm.ensureDir(testDir)["code"] == 200)

    # ── 2. 文件写入/读取 ──
    print("\n[2] 文件写入/读取")
    testFile = os.path.join(testDir, "client_test.txt")
    r = fm.writeFile(testFile, "客户端文件系统测试\n读取测试")
    test("写入文件", r["code"] == 200)

    r = fm.readFile(testFile)
    test("读取文件", r["code"] == 200)
    test("内容正确", "客户端文件系统测试" in r["data"])

    # ── 3. 文件信息 ──
    print("\n[3] 文件信息")
    r = fm.getFileInfo(testFile)
    test("获取信息", r["code"] == 200)
    test("扩展名 .txt", r["data"]["extension"] == ".txt")

    # ── 4. 复制/移动 ──
    print("\n[4] 复制/移动")
    copyFile = os.path.join(testDir, "copy.txt")
    r = fm.copyFile(testFile, copyFile)
    test("复制成功", r["code"] == 200)

    moveFile = os.path.join(testDir, "moved.txt")
    r = fm.moveFile(copyFile, moveFile)
    test("移动成功", r["code"] == 200)

    # ── 5. 备份/恢复 ──
    print("\n[5] 备份/恢复")
    r = fm.backupFile(testFile)
    test("备份成功", r["code"] == 200)
    backupPath = r["data"]

    restoreFile = os.path.join(testDir, "restored.txt")
    r = fm.restoreFile(backupPath, restoreFile)
    test("恢复成功", r["code"] == 200)

    # ── 6. 文件锁 ──
    print("\n[6] 文件锁")
    lockFile = os.path.join(testDir, "lock_test.txt")
    fm.writeFile(lockFile, "lock me")

    r = fg.lockFile(lockFile)
    test("锁定成功", r["code"] == 200)
    lockId = r["data"]

    r = fg.isLocked(lockFile)
    test("检测锁定", r["data"]["locked"] == True)

    r = fg.unlockFile(lockFile, lockId)
    test("解锁成功", r["code"] == 200)

    # ── 7. 完整性校验 ──
    print("\n[7] 完整性校验")
    r = ic.generateManifest(testDir)
    test("生成清单", r["code"] == 200)

    r = ic.verify(testDir)
    test("校验通过", r["code"] == 200, r["message"])

    # ── 8. 删除 ──
    print("\n[8] 删除")
    r = fm.deleteFile(moveFile, safe=True)
    test("安全删除", r["code"] == 200)
    test("文件已删除", not os.path.exists(moveFile))

    r = fm.deleteFile("nonexistent.txt")
    test("删除不存在 → 404", r["code"] == 404)

    # 清理
    import shutil
    shutil.rmtree(testDir)

    print("\n" + "=" * 60)
    print(f"  测试结果: {PASS} 通过 / {FAIL} 失败 (共 {PASS + FAIL} 项)")
    if FAIL == 0:
        print("  全部通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()