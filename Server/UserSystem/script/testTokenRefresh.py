# -*- coding: utf-8 -*-
"""
Token 自动刷新机制测试
=====================
测试: 注册 → 登录 → 模拟 token 临近过期 → 自动刷新 → 旧 token 失效
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, init_db
from enrollSystem import EnrollSystem
from loginSystem import LoginSystem
from tokenManager import TokenManager

# 清理
dbPath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DataBase", "users.db")
if os.path.exists(dbPath):
    os.remove(dbPath)
for ext in [".db-wal", ".db-shm"]:
    if os.path.exists(dbPath + ext):
        os.remove(dbPath + ext)

conn = get_connection()
r = init_db("admin", conn)
print(f"1. 初始化DB: {r['message']}")

# 注册
enrollSys = EnrollSystem(conn)
r = enrollSys.enroll("测试", "testuser", "Test123!", "Test123!", "test@test.com", "123456")
print(f"2. 注册: {r['message']}")

# 登录
loginSys = LoginSystem(conn)
r = loginSys.login("testuser", "Test123!", "123456")
print(f"3. 登录: {r['message']}")

# 签发 Token
tm = TokenManager(conn)
r = tm.generateToken(1, "testuser", "user")
token = r["token"]
print(f"4. Token: {token[:20]}...")

# ================================================================
# 手动将 token 过期时间设为"5分钟后"(进入刷新窗口)
# ================================================================
from datetime import datetime, timedelta
soonExpire = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
cursor = conn.cursor()
cursor.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (soonExpire, token))
conn.commit()
print(f"5. 模拟: 将过期时间改为 {soonExpire} (剩余5分钟,进入刷新窗口)")

# 验证 Token → 应触发自动刷新
r = tm.verifyToken(token)
print(f"6. 验证Token: {r['message']}")
print(f"   new_token != None: {r.get('new_token') is not None}")

if r.get("new_token"):
    newToken = r["new_token"]
    print(f"   新Token: {newToken[:20]}...")

    # 验证旧 token 已失效
    r = tm.verifyToken(token)
    print(f"7. 旧Token验证: {r['message']}")

    # 验证新 token 有效
    r = tm.verifyToken(newToken)
    print(f"8. 新Token验证: {r['message']}")

    # 测试手动续期 refreshTokenExpiry
    r = tm.refreshTokenExpiry(newToken)
    print(f"9. 手动续期: {r['message']}")
    if r.get("new_token"):
        renewedToken = r["new_token"]
        print(f"   new_token != None: {r.get('new_token') is not None}")
        # 旧 token 应失效
        r = tm.verifyToken(newToken)
        print(f"10. 续期后旧Token: {r['message']}")
        # 新 token 应有效
        r = tm.verifyToken(renewedToken)
        print(f"11. 续期后新Token: {r['message']}")
else:
    print("   ERROR: 未触发自动刷新!")

conn.close()
print("\n=== 测试完成 ===")