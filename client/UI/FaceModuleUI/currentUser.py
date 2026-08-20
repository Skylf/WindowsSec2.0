"""
coding:utf-8
file: UI/FaceModuleUI/currentUser.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 当前登录用户状态管理
# ======================
# 管理登录状态、当前用户信息、头像路径。
# 后续对接用户系统时,替换本模块的数据来源为真实登录即可,UI 无需改动。
#
# 头像路径规则:
#   1. 用户设置了头像 → 使用数据库中 avatar_path 指定的路径
#   2. 用户未设置头像 → 使用默认头像 DEFAULT_AVATAR_PATH
#   3. 未登录 → 使用默认头像

import os

# 默认头像路径(相对 resources 目录)
_UI_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AVATAR_PATH = os.path.join(_UI_DIR, "resources", "default_avatar.png")

# 登录状态
_is_logged_in = False

# 当前用户信息(登录后填充)
# 字段: user_id, username, nickname, email, role, avatar_path, uuid
_current_user = None


def is_logged_in() -> bool:
    """
    是否已登录
    :return: bool
    """
    return _is_logged_in


def get_current_user() -> dict or None:
    """
    获取当前登录用户信息
    :return: dict 或 None(未登录)
    """
    return dict(_current_user) if _current_user else None


def get_current_user_name() -> str:
    """
    获取当前用户名
    :return: 用户名<str>, 未登录返回空字符串
    """
    if _current_user:
        return _current_user.get("username", "")
    return ""


def get_avatar_path() -> str:
    """
    获取当前用户头像路径
    规则: 用户设置了头像 → 用用户路径; 否则 → 默认头像
    :return: 头像文件路径<str>
    """
    if _current_user and _current_user.get("avatar_path"):
        path = _current_user["avatar_path"]
        if os.path.exists(path):
            return path
    return DEFAULT_AVATAR_PATH


def set_current_user(user_dict: dict):
    """
    设置当前登录用户(登录成功后调用)
    :param user_dict: 用户信息字典, 含 user_id/username/nickname/email/role/avatar_path/uuid
    """
    global _is_logged_in, _current_user
    _is_logged_in = True
    _current_user = dict(user_dict)


def logout():
    """
    退出登录(清空用户信息)
    """
    global _is_logged_in, _current_user
    _is_logged_in = False
    _current_user = None