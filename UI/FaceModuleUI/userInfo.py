"""
coding:utf-8
file: UI/FaceModuleUI/userInfo.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260815
"""

# 当前用户信息(占位数据源)
# =========================
# 用户系统尚未实现, 当前预设 admin 为当前登录用户。
# 账户页(头像悬停信息)、录入页(录入归属)等 UI 统一从本模块读取当前用户,
# 保证"账号信息"与"录入用户名"绑定同一数据源。
# 后续实现用户系统后, 替换本模块的数据来源为真实登录用户即可, UI 无需改动。

# 当前用户(占位: 用户名 / ID / 角色)
CURRENT_USER = {
    "userName": "admin",
    "userId": "1001",
    "role": "管理员",
}


def get_current_user() -> dict:
    """
    获取当前用户信息
    :return: {"userName": str, "userId": str, "role": str}
    """
    return dict(CURRENT_USER)


def get_current_user_name() -> str:
    """
    获取当前用户名(录入/识别等业务归属用)
    :return: 用户名<str>
    """
    return CURRENT_USER.get("userName", "admin")
