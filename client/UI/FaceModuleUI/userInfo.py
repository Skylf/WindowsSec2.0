"""
coding:utf-8
file: UI/FaceModuleUI/userInfo.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260819
"""

# 当前用户信息(兼容旧接口, 委托给 currentUser 模块)
# ====================================================
# 原模块为占位数据源, 现已由 currentUser.py 接管登录状态管理。
# 本模块保留向后兼容, 所有调用委托给 currentUser。
# 未登录时返回默认的 admin 占位(保持旧行为), 登录后返回真实用户。

from currentUser import (
    is_logged_in as _is_logged_in,
    get_current_user as _get_current_user,
    get_current_user_name as _get_current_user_name,
    get_avatar_path as _get_avatar_path,
)

# 默认占位用户(未登录时的回退, 兼容旧代码)
_DEFAULT_USER = {
    "userName": "admin",
    "userId": "1001",
    "role": "管理员",
}


def get_current_user() -> dict:
    """
    获取当前用户信息
    已登录 → 返回真实用户(字段: user_id, username, nickname, role, email, avatar_path)
    未登录 → 返回默认占位
    :return: dict
    """
    user = _get_current_user()
    if user:
        # 兼容旧接口: 补充 userName/userId 字段
        return {
            "userName": user.get("username", "admin"),
            "userId": str(user.get("user_id", "1001")),
            "role": "管理员" if user.get("role") == "admin" else "普通用户",
        }
    return dict(_DEFAULT_USER)


def get_current_user_name() -> str:
    """
    获取当前用户名
    :return: 用户名<str>
    """
    name = _get_current_user_name()
    return name if name else _DEFAULT_USER["userName"]


def is_logged_in() -> bool:
    """
    是否已登录
    :return: bool
    """
    return _is_logged_in()


def get_avatar_path() -> str:
    """
    获取当前用户头像路径
    :return: 头像路径<str>
    """
    return _get_avatar_path()