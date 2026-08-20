"""
coding:utf-8
file: SocketModule/cookieStore.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 自动登录 Cookie 本地存储
# =========================
# 将服务端签发的自动登录 cookie 保存在 client/cache 目录下的 JSON 文件。
# 下次启动软件时读取该文件,凭 cookie 尝试自动登录。
# cookie 数据格式: { cookie, user_id, username, ip, device_code, expires_at }

import os
import json

# 客户端根目录(client 目录)
_CLIENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# cookie 存储目录与文件(client/cache)
COOKIE_DIR = os.path.join(_CLIENT_DIR, "cache")
COOKIE_FILE = os.path.join(COOKIE_DIR, "auto_login_cookie.json")


def __ensureDir() -> None:
    """确保 cookie 存储目录存在(不存在则创建)"""
    if not os.path.exists(COOKIE_DIR):
        os.makedirs(COOKIE_DIR)


def saveCookie(cookieData: dict) -> bool:
    """
    保存自动登录 cookie 到本地文件(覆盖写入)

    :param cookieData: cookie 数据字典<dict>
    :return: 是否保存成功<bool>
    """
    __ensureDir()
    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as fileObj:
            json.dump(cookieData, fileObj, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def loadCookie() -> dict or None:
    """
    读取本地自动登录 cookie
    文件不存在或解析失败均返回 None

    :return: cookie 数据字典<dict> 或 None
    """
    if not os.path.exists(COOKIE_FILE):
        return None
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as fileObj:
            return json.load(fileObj)
    except (json.JSONDecodeError, OSError):
        return None


def deleteCookie() -> bool:
    """
    删除本地自动登录 cookie
    用于: 校验失败需要手动登录时清除本地失效 cookie

    :return: 是否删除成功<bool>
    """
    if not os.path.exists(COOKIE_FILE):
        return True
    try:
        os.remove(COOKIE_FILE)
        return True
    except OSError:
        return False


def hasCookie() -> bool:
    """
    是否存在本地自动登录 cookie

    :return: True=存在, False=不存在
    """
    return os.path.exists(COOKIE_FILE)