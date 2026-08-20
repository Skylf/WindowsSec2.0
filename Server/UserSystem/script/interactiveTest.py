# -*- coding: utf-8 -*-
"""
注册 & 登录 交互式测试脚本（你操作版）
=====================================
终端菜单式交互,手动输入字段,实时反馈数据库结果

用法:
    cd Server/UserSystem/script
    python interactiveTest.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, init_db
from enrollSystem import EnrollSystem
from loginSystem import LoginSystem
from tokenManager import TokenManager


SEP = "─" * 50


# ====================================================================
# 交互测试主类
# ====================================================================
class InteractiveTest:
    """
    交互式测试主控
    ==============
    菜单驱动,用户手动操作每一步
    """

    def __init__(self):
        # 初始化数据库
        dbPath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "DataBase", "users.db"
        )
        # 不删除旧数据库,保留已有数据

        self.conn = get_connection()
        r = init_db("admin", self.conn)
        print(f"[初始化] {r['message']}")

        self.enrollSys = EnrollSystem(self.conn)
        self.loginSys = LoginSystem(self.conn)
        self.tokenMgr = TokenManager(self.conn)

        # 当前登录状态
        self.currentToken = None
        self.currentUser = None

    def __del__(self):
        """析构时关闭连接"""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

    # ==================================================================
    # 主菜单
    # ==================================================================
    def run(self):
        """主循环"""
        while True:
            self.__showMenu()
            choice = input("  请选择: ").strip()

            if choice == "1":
                self.__doRegister()
            elif choice == "2":
                self.__doLogin()
            elif choice == "3":
                self.__doVerifyToken()
            elif choice == "4":
                self.__doLogout()
            elif choice == "5":
                self.__showStatus()
            elif choice == "0":
                print("\n  已退出.")
                break
            else:
                print("  无效选择,请重新输入")

    def __showMenu(self):
        """显示菜单"""
        loggedIn = "已登录" if self.currentToken else "未登录"
        userInfo = f" | {self.currentUser['username']}({self.currentUser['role']})" if self.currentUser else ""

        print("\n" + "=" * 50)
        print(f"  注册 & 登录 交互测试  [{loggedIn}{userInfo}]")
        print("=" * 50)
        print("  [1] 注册新用户")
        print("  [2] 登录")
        print("  [3] 验证当前 Token")
        print("  [4] 退出登录")
        print("  [5] 查看当前状态")
        print("  [0] 退出程序")
        print("=" * 50)

    # ==================================================================
    # 注册
    # ==================================================================
    def __doRegister(self):
        """注册流程"""
        print(f"\n  {SEP}")
        print("  用户注册")
        print(f"  {SEP}")
        print("  提示: 验证码固定为 123456")
        print()

        nickname = input("  昵称: ").strip()
        username = input("  用户名: ").strip()
        password = input("  密码: ").strip()
        confirmPassword = input("  确认密码: ").strip()
        email = input("  邮箱: ").strip()
        emailCode = input("  邮箱验证码: ").strip()

        print(f"\n  {SEP}")
        result = self.enrollSys.enroll(
            nickname=nickname,
            username=username,
            password=password,
            confirm_password=confirmPassword,
            email=email,
            email_code=emailCode
        )

        self.__printResult(result)

        if result["code"] == 200:
            data = result["data"]
            print(f"  user_id : {data['user_id']}")
            print(f"  uuid    : {data['uuid']}")
            print(f"  username: {data['username']}")
            print(f"  nickname: {data['nickname']}")
            print(f"  email   : {data['email']}")

    # ==================================================================
    # 登录
    # ==================================================================
    def __doLogin(self):
        """登录流程"""
        if self.currentToken:
            print("\n  您已登录,请先退出登录再重新登录.")
            return

        print(f"\n  {SEP}")
        print("  用户登录")
        print(f"  {SEP}")
        print("  提示: 验证码固定为 123456")
        print()

        identity = input("  用户名/邮箱: ").strip()
        password = input("  密码: ").strip()
        emailCode = input("  邮箱验证码: ").strip()

        print(f"\n  {SEP}")
        result = self.loginSys.login(
            identity=identity,
            password=password,
            email_code=emailCode
        )

        self.__printResult(result)

        if result["code"] != 200:
            return

        userInfo = result["data"]

        # 签发 Token
        tokenResult = self.tokenMgr.generateToken(
            user_id=userInfo["user_id"],
            username=userInfo["username"],
            role=userInfo["role"]
        )

        self.__printResult(tokenResult)

        if tokenResult["code"] == 200:
            self.currentToken = tokenResult["token"]
            self.currentUser = {
                "user_id": userInfo["user_id"],
                "username": userInfo["username"],
                "nickname": userInfo["nickname"],
                "role": userInfo["role"],
                "email": userInfo["email"]
            }
            print(f"\n  Token 已保存,后续操作将使用此 Token 鉴权.")
            print(f"  Token: {self.currentToken[:20]}...{self.currentToken[-20:]}")
            print(f"  过期时间: {tokenResult['data']['expires_at']}")

    # ==================================================================
    # 验证 Token
    # ==================================================================
    def __doVerifyToken(self):
        """验证当前 Token(含自动刷新检测)"""
        if not self.currentToken:
            print("\n  您尚未登录,没有 Token 可验证.")
            return

        print(f"\n  {SEP}")
        print("  验证 Token")
        print(f"  {SEP}")

        result = self.tokenMgr.verifyToken(self.currentToken)
        self.__printResult(result)

        if result["code"] == 200:
            print(f"  user_id : {result['data']['user_id']}")
            print(f"  username: {result['data']['username']}")
            print(f"  role    : {result['data']['role']}")

            # 检查是否自动刷新了 token
            self.__autoUpdateToken(result)

    # ==================================================================
    # 退出登录
    # ==================================================================
    def __doLogout(self):
        """退出登录(撤销 Token)"""
        if not self.currentToken:
            print("\n  您尚未登录.")
            return

        print(f"\n  {SEP}")
        print("  退出登录")
        print(f"  {SEP}")

        result = self.tokenMgr.revokeToken(self.currentToken)
        self.__printResult(result)

        self.currentToken = None
        self.currentUser = None

    # ==================================================================
    # 查看状态
    # ==================================================================
    def __showStatus(self):
        """查看当前登录状态"""
        print(f"\n  {SEP}")
        print("  当前状态")
        print(f"  {SEP}")

        if not self.currentToken:
            print("  状态: 未登录")
            return

        print(f"  状态   : 已登录")
        print(f"  user_id: {self.currentUser['user_id']}")
        print(f"  username: {self.currentUser['username']}")
        print(f"  nickname: {self.currentUser['nickname']}")
        print(f"  role    : {self.currentUser['role']}")
        print(f"  email   : {self.currentUser['email']}")
        print(f"  Token   : {self.currentToken[:20]}...{self.currentToken[-20:]}")

    # ==================================================================
    # 工具方法
    # ==================================================================
    def __autoUpdateToken(self, result):
        """
        检查结果中是否有 new_token,有则自动更新本地 token
        客户端在每次调用 verifyToken/verifyOp 后都应调用此方法
        :param result: 返回结果<dict>
        """
        newToken = result.get("new_token")
        if newToken:
            oldToken = self.currentToken
            self.currentToken = newToken
            print(f"\n  [AUTO] Token 已自动刷新!")
            print(f"  旧 Token: {oldToken[:20]}...{oldToken[-20:]}")
            print(f"  新 Token: {newToken[:20]}...{newToken[-20:]}")

    def __printResult(self, result):
        """
        打印结果
        :param result: 返回结果<dict>
        """
        code = result["code"]
        msg = result["message"]
        if code == 200:
            print(f"  [OK] {msg}")
        else:
            print(f"  [FAIL] {msg}")


# ====================================================================
# 入口
# ====================================================================
if __name__ == "__main__":
    test = InteractiveTest()
    test.run()