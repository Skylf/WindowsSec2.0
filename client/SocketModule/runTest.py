"""
coding:utf-8
file: SocketModule/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 全链路测试脚本
# ==============
# 测试流程:
# 1. 启动服务端(线程)
# 2. 客户端连接服务端
# 3. 注册新用户
# 4. 登录(用户名 + 邮箱)
# 5. Token 验证
# 6. 登出
# 7. 登出后 Token 失效
# 8. 重复注册 → 拒绝
# 9. 错误密码 → 拒绝
# 10. 心跳验证
#
# 运行方式: python client/SocketModule/runTest.py

import os
import sys
import time
import threading

# 添加路径
_CLIENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CLIENT_DIR not in sys.path:
    sys.path.insert(0, _CLIENT_DIR)

# 服务端路径(Server/SocketModule)
_SERVER_SOCKET_DIR = os.path.join(os.path.dirname(_CLIENT_DIR), "Server", "SocketModule")
if _SERVER_SOCKET_DIR not in sys.path:
    sys.path.insert(0, _SERVER_SOCKET_DIR)

# 服务端 UserSystem 路径(handler 依赖)
_SERVER_USER_DIR = os.path.join(os.path.dirname(_CLIENT_DIR), "Server", "UserSystem")
if _SERVER_USER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_USER_DIR)

from authService import (
    initAuthService, shutdownAuthService, isConnected,
    enroll, login, logout, verifyToken,
)
from protocol import CODE_OK, CODE_BAD_REQUEST, CODE_UNAUTHORIZED

# 测试计数
PASS = 0
FAIL = 0


def test(name: str, condition: bool, detail: str = ""):
    """测试断言"""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def startServerThread():
    """在后台线程启动服务端"""
    from server import Server
    from server import HandlerRouter
    from handler import HandlerRegister

    def _run():
        srv = Server("127.0.0.1", 9527)
        handlers = HandlerRegister()
        handlers.registerAll(srv.getRouter())
        srv.start()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.5)  # 等待服务端就绪
    return thread


def main():
    global PASS, FAIL

    print("=" * 60)
    print("  全链路通信测试")
    print("=" * 60)

    # 0. 清理旧数据库
    dbPath = os.path.join(os.path.dirname(_CLIENT_DIR), "Server", "UserSystem", "DataBase", "users.db")
    if os.path.exists(dbPath):
        os.remove(dbPath)
        print("\n[0] 已清理旧数据库")

    # 1. 启动服务端
    print("\n[1] 启动服务端...")
    startServerThread()
    print("  服务端已启动(后台线程)")

    # 2. 客户端连接
    print("\n[2] 客户端连接...")
    test("连接服务器", initAuthService("127.0.0.1", 9527), "")

    if not isConnected():
        print("  无法连接服务器, 测试终止")
        return

    # 3. 注册新用户
    print("\n[3] 注册新用户")
    result = enroll("测试用户", "testuser", "Test123456", "Test123456", "test@test.com")
    test("注册成功", result["code"] == 200, result["message"])

    # 注册管理员
    result = enroll("管理员", "testadmin", "Admin123456", "Admin123456", "admin@test.com")
    test("注册管理员", result["code"] == 200, result["message"])

    # 4. 重复注册 → 拒绝
    print("\n[4] 重复注册 → 应被拒绝")
    result = enroll("测试用户", "testuser", "Test123456", "Test123456", "test2@test.com")
    test("重复注册被拒绝", result["code"] == CODE_BAD_REQUEST, result["message"])

    # 5. 用户名登录
    print("\n[5] 用户名登录")
    result = login("testuser", "Test123456")
    test("用户名登录成功", result["code"] == 200, result["message"])
    test("返回 Token 非空", bool(result["data"].get("token")), "")
    test("返回 user_id=1", result["data"].get("user_id") is not None, str(result["data"]))

    # 登出
    logout()

    # 6. 邮箱登录
    print("\n[6] 邮箱登录")
    result = login("test@test.com", "Test123456")
    test("邮箱登录成功", result["code"] == 200, result["message"])

    # 7. Token 验证
    print("\n[7] Token 验证")
    result = verifyToken()
    test("Token 验证通过", result["code"] == 200, result["message"])
    test("返回 user_id", result["data"].get("user_id") is not None, "")
    test("返回 username", result["data"].get("username") == "testuser", str(result["data"]))

    # 8. 登出
    print("\n[8] 登出")
    result = logout()
    test("登出成功", result["code"] == 200, result["message"])

    # 9. 登出后 Token 验证 → 失败
    print("\n[9] 登出后 Token 验证 → 应失败")
    result = verifyToken()
    test("登出后 Token 无效", result["code"] == CODE_UNAUTHORIZED, result["message"])

    # 10. 错误密码 → 拒绝
    print("\n[10] 错误密码登录 → 应被拒绝")
    result = login("testuser", "wrongpassword")
    test("错误密码被拒绝", result["code"] == CODE_BAD_REQUEST, result["message"])

    # 11. 管理员登录 + 角色验证
    print("\n[11] 管理员登录")
    result = login("testadmin", "Admin123456")
    test("管理员登录成功", result["code"] == 200, result["message"])
    test("role=user(注册默认为 user, admin 需管理系统设置)", result["data"].get("role") == "user", str(result["data"]))

    # 12. 心跳测试(等待一次心跳周期)
    print("\n[12] 心跳测试(等待 2 秒)...")
    time.sleep(2)
    test("心跳后连接仍有效", isConnected(), "")

    # 登出管理员
    logout()

    # 13. 清理
    print("\n[13] 清理")
    shutdownAuthService()
    test("断开连接", not isConnected(), "")

    # 总结
    print("\n" + "=" * 60)
    print(f"  测试结果: {PASS} 通过 / {FAIL} 失败 (共 {PASS + FAIL} 项)")
    if FAIL == 0:
        print("  全部通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()