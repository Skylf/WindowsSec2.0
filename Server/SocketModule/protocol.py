"""
coding:utf-8
file: SocketModule/protocol.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 网络通信协议(客户端与服务端共用)
# =================================
# 消息格式: JSON 文本, 以 \n 分隔每条消息
# {
#   "type":     "request|response|push|heartbeat",
#   "action":   "login|enroll|logout|token_verify|heartbeat|...",
#   "request_id": "uuid",
#   "token":    "current_token",
#   "code":     200,
#   "message":  "ok",
#   "data":     {...}
# }

import json
import uuid

# 消息类型常量
TYPE_REQUEST = "request"
TYPE_RESPONSE = "response"
TYPE_PUSH = "push"
TYPE_HEARTBEAT = "heartbeat"

# 动作常量
ACTION_LOGIN = "login"
ACTION_ENROLL = "enroll"
ACTION_LOGOUT = "logout"
ACTION_TOKEN_VERIFY = "token_verify"
ACTION_AUTO_LOGIN = "auto_login"
ACTION_HEARTBEAT = "heartbeat"

# 响应码
CODE_OK = 200
CODE_BAD_REQUEST = 400
CODE_UNAUTHORIZED = 401
CODE_FORBIDDEN = 403
CODE_NOT_FOUND = 404
CODE_SERVER_ERROR = 500

# 心跳间隔(秒)
HEARTBEAT_INTERVAL = 30
# 心跳超时(秒), 超过此时间无心跳则断开
HEARTBEAT_TIMEOUT = 90


def buildMessage(messageType: str, action: str, data: dict = None, token: str = None,
                requestId: str = None, code: int = CODE_OK, message: str = "ok") -> dict:
    """
    构建一条协议消息
    :param messageType: 消息类型<str>
    :param action: 动作<str>
    :param data: 数据载荷<dict>
    :param token: 鉴权令牌<str>
    :param requestId: 请求ID<str>, 为空则自动生成
    :param code: 响应码<int>
    :param message: 响应消息<str>
    :return: 消息字典<dict>
    """
    return {
        "type": messageType,
        "action": action,
        "request_id": requestId or str(uuid.uuid4()),
        "token": token or "",
        "code": code,
        "message": message,
        "data": data if data is not None else {}
    }


def buildRequest(action: str, data: dict = None, token: str = None) -> dict:
    """
    构建请求消息
    :param action: 动作<str>
    :param data: 数据<dict>
    :param token: 令牌<str>
    :return: 消息字典<dict>
    """
    return buildMessage(TYPE_REQUEST, action, data, token)


def buildResponse(requestId: str, action: str, data: dict = None, token: str = None,
                  code: int = CODE_OK, message: str = "ok") -> dict:
    """
    构建响应消息
    :param requestId: 对应请求的 request_id<str>
    :param action: 动作<str>
    :param data: 数据<dict>
    :param token: 令牌<str>
    :param code: 响应码<int>
    :param message: 响应消息<str>
    :return: 消息字典<dict>
    """
    return buildMessage(TYPE_RESPONSE, action, data, token, requestId, code, message)


def buildHeartbeat(token: str = None) -> dict:
    """
    构建心跳消息
    :param token: 令牌<str>
    :return: 消息字典<dict>
    """
    return buildMessage(TYPE_HEARTBEAT, ACTION_HEARTBEAT, token=token, message="ping")


def encodeMessage(msg: dict) -> bytes:
    """
    编码消息为字节流(JSON + \n 分隔)
    :param msg: 消息字典<dict>
    :return: 字节流<bytes>
    """
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def decodeMessage(data: bytes) -> dict or None:
    """
    解码字节流为消息字典
    :param data: 字节流<bytes>
    :return: 消息字典或 None(解析失败)
    """
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None