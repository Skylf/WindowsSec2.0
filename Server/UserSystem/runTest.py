# -*- coding: utf-8 -*-
"""
注册 & 登录 全流程交互测试
==========================
测试流程:
  1. 初始化数据库(init_db)
  2. 注册测试(EnrollTest.run)
  3. 登录测试(LoginTest.run)
  4. 连接关闭

用法:
    python runTest.py
"""

import sys
import os

# 确保当前目录在 sys.path 中,以便导入同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_connection, init_db
from enrollSystem import EnrollSystem
from loginSystem import LoginSystem
from tokenManager import TokenManager


# 分隔线
SEP = "─" * 50


# ====================================================================
# 注册测试类
# ====================================================================
class EnrollTest:
    """
    注册全流程交互测试
    ==================
    依次测试:
    1. 正常注册
    2. 用户名重复注册(应失败)
    3. 密码格式错误(应失败)
    4. 两次密码不一致(应失败)
    5. 邮箱格式错误(应失败)
    6. 验证码错误(应失败)
    """

    def __init__(self, db_conn):
        """
        初始化注册测试
        :param db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
        self.enrollSys = EnrollSystem(db_conn)

    def run(self):
        """执行注册测试"""
        print("\n" + "=" * 60)
        print("  注册全流程交互测试")
        print("=" * 60)

        # 1. 正常注册
        self.__testNormalEnroll()

        # 2. 用户名重复注册
        self.__testDuplicateUsername()

        # 3. 密码格式错误
        self.__testInvalidPassword()

        # 4. 两次密码不一致
        self.__testPasswordMismatch()

        # 5. 邮箱格式错误
        self.__testInvalidEmail()

        # 6. 验证码错误
        self.__testWrongCode()

        print("\n" + "=" * 60)
        print("  注册测试全部完成")
        print("=" * 60)

    def __printResult(self, label, result):
        """
        打印测试结果
        :param label: 测试项标签<str>
        :param result: 返回结果<dict>
        """
        status = "OK" if result["code"] == 200 else "FAIL"
        print(f"  [{status}] {label}")
        print(f"         → {result['message']}")

    # ------------------------------------------------------------------
    # 正常注册
    # ------------------------------------------------------------------
    def __testNormalEnroll(self):
        print(f"\n  {SEP}")
        print("  1. 正常注册")
        print(f"  {SEP}")

        result = self.enrollSys.enroll(
            nickname="测试用户",
            username="testadmin",
            password="Admin123!",
            confirm_password="Admin123!",
            email="admin@test.com",
            email_code="123456"
        )
        self.__printResult("注册管理员账号", result)

        result = self.enrollSys.enroll(
            nickname="普通用户",
            username="normal",
            password="Normal1!",
            confirm_password="Normal1!",
            email="normal@test.com",
            email_code="123456"
        )
        self.__printResult("注册普通用户", result)

    # ------------------------------------------------------------------
    # 用户名重复注册
    # ------------------------------------------------------------------
    def __testDuplicateUsername(self):
        print(f"\n  {SEP}")
        print("  2. 用户名重复注册(应失败)")
        print(f"  {SEP}")

        result = self.enrollSys.enroll(
            nickname="重复用户",
            username="testadmin",  # 与第1步重复
            password="Dup1234!",
            confirm_password="Dup1234!",
            email="dup@test.com",
            email_code="123456"
        )
        self.__printResult("重复用户名注册", result)

    # ------------------------------------------------------------------
    # 密码格式错误
    # ------------------------------------------------------------------
    def __testInvalidPassword(self):
        print(f"\n  {SEP}")
        print("  3. 密码格式错误(应失败)")
        print(f"  {SEP}")

        # 3.1 密码过短
        result = self.enrollSys.enroll(
            nickname="短密码",
            username="shortpw",
            password="Ab1!",
            confirm_password="Ab1!",
            email="short@test.com",
            email_code="123456"
        )
        self.__printResult("密码过短(4字符)", result)

        # 3.2 密码含中文
        result = self.enrollSys.enroll(
            nickname="中文密码",
            username="cnpw",
            password="密码123456!",
            confirm_password="密码123456!",
            email="cnpw@test.com",
            email_code="123456"
        )
        self.__printResult("密码含中文", result)

    # ------------------------------------------------------------------
    # 两次密码不一致
    # ------------------------------------------------------------------
    def __testPasswordMismatch(self):
        print(f"\n  {SEP}")
        print("  4. 两次密码不一致(应失败)")
        print(f"  {SEP}")

        result = self.enrollSys.enroll(
            nickname="不一致",
            username="mismatch",
            password="Abc1234!",
            confirm_password="Abc9999!",  # 与上面不同
            email="mm@test.com",
            email_code="123456"
        )
        self.__printResult("两次密码不一致", result)

    # ------------------------------------------------------------------
    # 邮箱格式错误
    # ------------------------------------------------------------------
    def __testInvalidEmail(self):
        print(f"\n  {SEP}")
        print("  5. 邮箱格式错误(应失败)")
        print(f"  {SEP}")

        result = self.enrollSys.enroll(
            nickname="无效邮箱",
            username="noemail",
            password="Abc1234!",
            confirm_password="Abc1234!",
            email="notanemail",  # 不含 @
            email_code="123456"
        )
        self.__printResult("邮箱格式错误", result)

    # ------------------------------------------------------------------
    # 验证码错误
    # ------------------------------------------------------------------
    def __testWrongCode(self):
        print(f"\n  {SEP}")
        print("  6. 验证码错误(应失败)")
        print(f"  {SEP}")

        result = self.enrollSys.enroll(
            nickname="验证码",
            username="wrongcode",
            password="Abc1234!",
            confirm_password="Abc1234!",
            email="code@test.com",
            email_code="999999"  # 错误验证码
        )
        self.__printResult("验证码错误", result)


# ====================================================================
# 登录测试类
# ====================================================================
class LoginTest:
    """
    登录全流程交互测试
    ==================
    依次测试:
    1. 用户名登录成功 → 签发Token → 验证Token → 鉴权 → 撤销Token
    2. 邮箱登录成功 → 签发Token → 重新登录(旧Token失效)
    3. 密码错误
    4. 用户名不存在
    5. 验证码错误
    6. 权限验证(admin操作)
    """

    def __init__(self, db_conn):
        """
        初始化登录测试
        :param db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
        self.loginSys = LoginSystem(db_conn)
        self.tokenMgr = TokenManager(db_conn)

    def run(self):
        """执行登录测试"""
        print("\n" + "=" * 60)
        print("  登录全流程交互测试")
        print("=" * 60)

        # 1. 用户名登录
        self.__testUsernameLogin()

        # 2. 邮箱登录 + Token 重新签发
        self.__testEmailLogin()

        # 3. 密码错误
        self.__testWrongPassword()

        # 4. 用户名不存在
        self.__testUserNotFound()

        # 5. 验证码错误
        self.__testWrongCode()

        # 6. 权限验证
        self.__testPermission()

        print("\n" + "=" * 60)
        print("  登录测试全部完成")
        print("=" * 60)

    def __printResult(self, label, result):
        """
        打印测试结果
        :param label: 测试项标签<str>
        :param result: 返回结果<dict>
        """
        status = "OK" if result["code"] == 200 else "FAIL"
        print(f"  [{status}] {label}")
        print(f"         → {result['message']}")

    # ------------------------------------------------------------------
    # 用户名登录 + Token 全流程
    # ------------------------------------------------------------------
    def __testUsernameLogin(self):
        print(f"\n  {SEP}")
        print("  1. 用户名登录 + Token 全流程")
        print(f"  {SEP}")

        # 1.1 登录
        result = self.loginSys.login("testadmin", "Admin123!", "123456")
        self.__printResult("用户名登录", result)
        if result["code"] != 200:
            return

        userInfo = result["data"]
        print(f"         user_id={userInfo['user_id']}, role={userInfo['role']}")

        # 1.2 签发Token
        result = self.tokenMgr.generateToken(
            user_id=userInfo["user_id"],
            username=userInfo["username"],
            role=userInfo["role"]
        )
        self.__printResult("签发Token(admin)", result)
        token = result.get("token")
        if not token:
            return

        # 1.3 验证Token
        result = self.tokenMgr.verifyToken(token)
        self.__printResult("验证Token", result)

        # 1.4 鉴权(admin操作)
        result = self.tokenMgr.verifyOp(token, requiredRole="admin")
        self.__printResult("鉴权(admin)", result)

        # 1.5 撤销Token
        result = self.tokenMgr.revokeToken(token)
        self.__printResult("撤销Token(登出)", result)

        # 1.6 验证已撤销Token(应失败)
        result = self.tokenMgr.verifyToken(token)
        self.__printResult("验证已撤销Token", result)

    # ------------------------------------------------------------------
    # 邮箱登录 + Token 重新签发
    # ------------------------------------------------------------------
    def __testEmailLogin(self):
        print(f"\n  {SEP}")
        print("  2. 邮箱登录 + 旧Token自动失效")
        print(f"  {SEP}")

        # 2.1 邮箱登录
        result = self.loginSys.login("normal@test.com", "Normal1!", "123456")
        self.__printResult("邮箱登录", result)
        if result["code"] != 200:
            return

        userInfo = result["data"]

        # 2.2 签发第1个Token
        result = self.tokenMgr.generateToken(
            user_id=userInfo["user_id"],
            username=userInfo["username"],
            role=userInfo["role"]
        )
        token1 = result.get("token")
        self.__printResult("签发Token1", result)

        # 2.3 重新登录(签发第2个Token,旧Token应自动失效)
        result = self.tokenMgr.generateToken(
            user_id=userInfo["user_id"],
            username=userInfo["username"],
            role=userInfo["role"]
        )
        token2 = result.get("token")
        self.__printResult("签发Token2(重新登录)", result)

        # 2.4 验证旧Token(应失效)
        result = self.tokenMgr.verifyToken(token1)
        self.__printResult("验证Token1(旧,应失效)", result)

        # 2.5 验证新Token(应有效)
        result = self.tokenMgr.verifyToken(token2)
        self.__printResult("验证Token2(新,应有效)", result)

        # 2.6 清理: 撤销Token2
        self.tokenMgr.revokeToken(token2)

    # ------------------------------------------------------------------
    # 密码错误
    # ------------------------------------------------------------------
    def __testWrongPassword(self):
        print(f"\n  {SEP}")
        print("  3. 密码错误(应失败)")
        print(f"  {SEP}")

        result = self.loginSys.login("testadmin", "WrongPass!", "123456")
        self.__printResult("密码错误", result)

    # ------------------------------------------------------------------
    # 用户名不存在
    # ------------------------------------------------------------------
    def __testUserNotFound(self):
        print(f"\n  {SEP}")
        print("  4. 用户名不存在(应失败)")
        print(f"  {SEP}")

        result = self.loginSys.login("nobody", "Abc1234!", "123456")
        self.__printResult("用户名不存在", result)

    # ------------------------------------------------------------------
    # 验证码错误
    # ------------------------------------------------------------------
    def __testWrongCode(self):
        print(f"\n  {SEP}")
        print("  5. 验证码错误(应失败)")
        print(f"  {SEP}")

        result = self.loginSys.login("testadmin", "Admin123!", "000000")
        self.__printResult("验证码错误", result)

    # ------------------------------------------------------------------
    # 权限验证
    # ------------------------------------------------------------------
    def __testPermission(self):
        print(f"\n  {SEP}")
        print("  6. 权限验证(admin操作)")
        print(f"  {SEP}")

        # 6.1 普通用户登录
        result = self.loginSys.login("normal", "Normal1!", "123456")
        self.__printResult("普通用户登录", result)
        if result["code"] != 200:
            return

        userInfo = result["data"]

        # 6.2 签发普通用户Token
        result = self.tokenMgr.generateToken(
            user_id=userInfo["user_id"],
            username=userInfo["username"],
            role=userInfo["role"]
        )
        token = result.get("token")
        self.__printResult("签发Token(user)", result)

        # 6.3 普通用户尝试admin操作(应被拒绝)
        result = self.tokenMgr.verifyOp(token, requiredRole="admin")
        self.__printResult("user执行admin操作(应拒绝)", result)

        # 6.4 清理
        self.tokenMgr.revokeToken(token)


# ====================================================================
# 主入口
# ====================================================================
if __name__ == "__main__":
    # 清理旧数据库
    dbPath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "DataBase", "users.db"
    )
    if os.path.exists(dbPath):
        os.remove(dbPath)
        print(f"[清理] 已删除旧数据库: {dbPath}")
    for ext in [".db-wal", ".db-shm"]:
        walPath = dbPath + ext
        if os.path.exists(walPath):
            os.remove(walPath)

    # 获取连接 + 初始化数据库
    conn = get_connection()
    r = init_db("admin", conn)
    print(f"[初始化] {r['message']}")

    # 运行注册测试
    enrollTest = EnrollTest(conn)
    enrollTest.run()

    # 运行登录测试
    loginTest = LoginTest(conn)
    loginTest.run()

    # 关闭连接
    conn.close()
    print("\n" + "=" * 60)
    print("  全流程测试结束")
    print("=" * 60)