# -*- coding: utf-8 -*-
"""
注册 & 登录系统流程测试脚本
===========================
测试流程:
1. 注册-正常流程(全部字段合法)
2. 注册-异常流程(各字段非法逐一验证)
3. 登录-正常流程(用户名登录 / 邮箱登录)
4. 登录-异常流程(各字段非法逐一验证)
"""

import sys
import os

# 将上级目录加入 sys.path,以便导入 enrollSystem 和 loginSystem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrollSystem import EnrollSystem
from loginSystem import LoginSystem


# 创建实例
enrollSys = EnrollSystem()
loginSys = LoginSystem()

# 测试通过/失败计数器
passCount = 0
failCount = 0


def checkResult(testName, result, expectCode):
    """
    检查测试结果,打印并统计
    :param testName: 测试名称<str>
    :param result: 返回结果<dict>
    :param expectCode: 期望的 code<int> 200=通过 / 400=拒绝
    """
    global passCount, failCount
    actualCode = result["code"]
    status = "PASS" if actualCode == expectCode else "FAIL"
    if status == "PASS":
        passCount += 1
    else:
        failCount += 1

    msg = result.get("message", "")
    extra = ""
    if "identity_type" in result:
        extra = f" [type={result['identity_type']}]"
    if "data" in result:
        extra += f" [data={result['data']}]"

    print(f"  [{status}] {testName}: code={actualCode} {msg}{extra}")


# ====================================================================
# 1. 注册 - 正常流程
# ====================================================================
print("=" * 60)
print("1. 注册 - 正常流程")
print("=" * 60)

result = enrollSys.enroll(
    nickname="测试昵称",
    username="test_user",
    password="abc123",
    confirm_password="abc123",
    email="test@example.com",
    email_code="123456"
)
checkResult("全部字段合法", result, 200)

# 带特殊字符的昵称和用户名
result = enrollSys.enroll(
    nickname="nick!@#$%",
    username="user~`&()",
    password="Pass@123",
    confirm_password="Pass@123",
    email="admin@test.org",
    email_code="123456"
)
checkResult("特殊字符昵称/用户名", result, 200)

# 中文昵称+中文用户名
result = enrollSys.enroll(
    nickname="张三",
    username="李四王五",
    password="mypassword",
    confirm_password="mypassword",
    email="zhangsan@qq.com",
    email_code="123456"
)
checkResult("中文昵称+中文用户名", result, 200)

# ====================================================================
# 2. 注册 - 异常流程
# ====================================================================
print("\n" + "=" * 60)
print("2. 注册 - 异常流程(期望 code=400)")
print("=" * 60)

# 2.1 昵称异常
result = enrollSys.validateNickname("")
checkResult("昵称-空值", result, 400)

result = enrollSys.validateNickname("12345678901")
checkResult("昵称-超长(11字符)", result, 400)

result = enrollSys.validateNickname("test.user")
checkResult("昵称-含非法字符'.'", result, 400)

result = enrollSys.validateNickname("test*name")
checkResult("昵称-含非法字符'*'", result, 400)

result = enrollSys.validateNickname("test?name")
checkResult("昵称-含非法字符'?'", result, 400)

result = enrollSys.validateNickname("test/name")
checkResult("昵称-含非法字符'/'", result, 400)

result = enrollSys.validateNickname("test\\name")
checkResult("昵称-含非法字符'\\'", result, 400)

# 2.2 用户名异常
result = enrollSys.validateUsername("")
checkResult("用户名-空值", result, 400)

result = enrollSys.validateUsername("a" * 11)
checkResult("用户名-超长(11字符)", result, 400)

result = enrollSys.validateUsername("bad.user")
checkResult("用户名-含非法字符'.'", result, 400)

# 2.3 密码异常
result = enrollSys.validatePassword("")
checkResult("密码-空值", result, 400)

result = enrollSys.validatePassword("12345")
checkResult("密码-过短(5字符)", result, 400)

result = enrollSys.validatePassword("a" * 19)
checkResult("密码-超长(19字符)", result, 400)

result = enrollSys.validatePassword("密码123456")
checkResult("密码-含中文", result, 400)

result = enrollSys.validatePassword("pass.word")
checkResult("密码-含非法字符'.'", result, 400)

# 2.4 密码确认异常
result = enrollSys.validatePasswordConfirm("abc123", "abc456")
checkResult("密码确认-不一致", result, 400)

# 2.5 邮箱异常
result = enrollSys.validateEmail("")
checkResult("邮箱-空值", result, 400)

result = enrollSys.validateEmail("notanemail")
checkResult("邮箱-无@符号", result, 400)

result = enrollSys.validateEmail("@nodomain.com")
checkResult("邮箱-无用户名", result, 400)

result = enrollSys.validateEmail("user@")
checkResult("邮箱-无域名", result, 400)

# 2.6 验证码异常
result = enrollSys.validateEmailCode("")
checkResult("验证码-空值", result, 400)

result = enrollSys.validateEmailCode("000000")
checkResult("验证码-错误", result, 400)

result = enrollSys.validateEmailCode("654321")
checkResult("验证码-错误(其他)", result, 400)

# 2.7 聚合校验-中途失败
result = enrollSys.enroll(
    nickname="bad.nick",
    username="test",
    password="123456",
    confirm_password="123456",
    email="test@qq.com",
    email_code="123456"
)
checkResult("聚合注册-昵称非法(中途失败)", result, 400)

result = enrollSys.enroll(
    nickname="昵称",
    username="test",
    password="123456",
    confirm_password="wrong",
    email="test@qq.com",
    email_code="123456"
)
checkResult("聚合注册-密码不一致(中途失败)", result, 400)

# ====================================================================
# 3. 登录 - 正常流程
# ====================================================================
print("\n" + "=" * 60)
print("3. 登录 - 正常流程")
print("=" * 60)

# 用户名登录
result = loginSys.login(
    identity="test_user",
    password="abc123",
    email_code="123456"
)
checkResult("用户名登录", result, 200)

# 邮箱登录
result = loginSys.login(
    identity="test@example.com",
    password="abc123",
    email_code="123456"
)
checkResult("邮箱登录", result, 200)

# 带特殊字符的密码登录
result = loginSys.login(
    identity="admin@test.org",
    password="Pass@123",
    email_code="123456"
)
checkResult("特殊字符密码登录", result, 200)

# ====================================================================
# 4. 登录 - 异常流程
# ====================================================================
print("\n" + "=" * 60)
print("4. 登录 - 异常流程(期望 code=400)")
print("=" * 60)

# 4.1 登录标识异常
result = loginSys.validateLoginIdentity("")
checkResult("登录标识-空值", result, 400)

result = loginSys.validateLoginIdentity("bad@email")
checkResult("登录标识-邮箱格式错误(无TLD)", result, 400)

result = loginSys.validateLoginIdentity("@test.com")
checkResult("登录标识-邮箱格式错误(无用户名)", result, 400)

# 4.2 密码异常
result = loginSys.validatePassword("")
checkResult("密码-空值", result, 400)

result = loginSys.validatePassword("123")
checkResult("密码-过短(3字符)", result, 400)

result = loginSys.validatePassword("a" * 20)
checkResult("密码-超长(20字符)", result, 400)

result = loginSys.validatePassword("中文密码123")
checkResult("密码-含中文", result, 400)

# 4.3 验证码异常
result = loginSys.validateEmailCode("")
checkResult("验证码-空值", result, 400)

result = loginSys.validateEmailCode("111111")
checkResult("验证码-错误", result, 400)

# 4.4 聚合校验-中途失败
result = loginSys.login(
    identity="bad@email",
    password="abc123",
    email_code="123456"
)
checkResult("聚合登录-邮箱格式错误(中途失败)", result, 400)

result = loginSys.login(
    identity="test_user",
    password="短",
    email_code="123456"
)
checkResult("聚合登录-密码过短(中途失败)", result, 400)

result = loginSys.login(
    identity="test_user",
    password="abc123",
    email_code="wrong"
)
checkResult("聚合登录-验证码错误(中途失败)", result, 400)

# ====================================================================
# 5. 人机验证(临时直接通过)
# ====================================================================
print("\n" + "=" * 60)
print("5. 人机验证(临时)")
print("=" * 60)

result = enrollSys.validateCaptcha()
checkResult("注册-人机验证", result, 200)

result = loginSys.validateCaptcha()
checkResult("登录-人机验证", result, 200)

# ====================================================================
# 6. 统计
# ====================================================================
total = passCount + failCount
print("\n" + "=" * 60)
print(f"测试完成: 通过 {passCount}/{total}, 失败 {failCount}/{total}")
print("=" * 60)

if failCount > 0:
    sys.exit(1)