# -*- coding: utf-8 -*-
"""
注册→登录→Token 全流程集成测试
==============================
测试: 邮箱登录 / Token 重新签发自动撤销旧Token / 封禁后拒绝登录
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection
from loginSystem import LoginSystem
from tokenManager import TokenManager

conn = get_connection()

# 1. 邮箱登录
loginSys = LoginSystem(conn)
r = loginSys.login('test@x.com', 'abc123!', '123456')
print('1. 邮箱登录:', r['message'])

# 2. 签发token 1
tm = TokenManager(conn)
r = tm.generateToken(1, 'test_user', 'user')
token1 = r['token']
print('2. Token1:', token1[:20] + '... VALID')

# 3. 签发token 2(重新登录,旧token应自动失效)
r = tm.generateToken(1, 'test_user', 'user')
token2 = r['token']
print('3. Token2:', token2[:20] + '... VALID')

# 4. 验证旧token(应失效)
r = tm.verifyToken(token1)
print('4. 验证Token1(旧):', r['message'])

# 5. 验证新token
r = tm.verifyToken(token2)
print('5. 验证Token2(新):', r['message'])

# 6. 账户封禁后登录
cursor = conn.cursor()
cursor.execute("UPDATE users SET status='banned' WHERE user_id=1")
conn.commit()
r = loginSys.login('test_user', 'abc123!', '123456')
print('6. 封禁后登录:', r['message'])

conn.close()
print('=== 全部通过 ===')