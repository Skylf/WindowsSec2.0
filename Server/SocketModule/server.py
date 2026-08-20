"""
coding:utf-8
file: SocketModule/server.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端 TCP 服务器
# ==================
# 监听指定端口, 接收客户端连接, 为每个客户端创建处理线程。
# 消息路由: 根据 action 分发到对应的业务处理器。
# 心跳: 服务端响应客户端心跳, 超时主动断开。

import socket
import threading
import time
import os
import sys

# 将 UserSystem 目录加入路径(引入 database/enroll/login/token)
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USER_SYSTEM_DIR = os.path.join(_SERVER_DIR, "UserSystem")
if _USER_SYSTEM_DIR not in sys.path:
    sys.path.insert(0, _USER_SYSTEM_DIR)

# 注入 ServerLogSystem 路径(Server/ServerLogSystem)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from protocol import (
    encodeMessage, decodeMessage,
    TYPE_HEARTBEAT, TYPE_REQUEST, TYPE_RESPONSE, TYPE_PUSH,
    ACTION_HEARTBEAT, ACTION_LOGIN, ACTION_ENROLL, ACTION_LOGOUT, ACTION_TOKEN_VERIFY,
    CODE_OK, CODE_BAD_REQUEST, CODE_UNAUTHORIZED, CODE_SERVER_ERROR,
    HEARTBEAT_TIMEOUT,
    buildResponse,
)

# 服务器配置
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9527


class ClientHandler:
    """
    客户端连接处理器
    =================
    每个客户端连接一个实例, 在线程中运行。
    负责: 接收消息 → 路由分发 → 发送响应 → 心跳超时检测
    """

    def __init__(self, clientSocket: socket.socket, addr: tuple, handlerRouter):
        """
        初始化客户端处理器
        :param clientSocket: 客户端 socket<socket.socket>
        :param addr: 客户端地址<tuple>
        :param handlerRouter: 业务路由处理器<HandlerRouter>
        """
        self._socket = clientSocket
        self._addr = addr
        self._router = handlerRouter
        self._buffer = b""
        self._running = False
        self._lastHeartbeat = time.time()

        # 日志管理器(延迟导入)
        from ServerLogSystem.logManager import getLogger
        from ServerLogSystem.logConfig import CATEGORY_NETWORK
        self._logger = getLogger()
        self._category = CATEGORY_NETWORK

    def start(self):
        """启动客户端处理线程"""
        self._running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """停止客户端处理"""
        self._running = False
        self._logger.info(self._category, f"客户端断开连接: {self._addr}")
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._socket.close()
        except OSError:
            pass

    def _run(self):
        """主循环: 接收消息, 处理, 响应"""
        self._socket.settimeout(1.0)

        while self._running:
            try:
                data = self._socket.recv(4096)
                if not data:
                    # 连接断开
                    self._running = False
                    break
                self._buffer += data
                self._processBuffer()
            except socket.timeout:
                # 超时检查心跳
                self._checkHeartbeat()
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                self._running = False
                break

    def _processBuffer(self):
        """处理接收缓冲区: 按 \n 分割, 逐条解析 JSON 消息"""
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            msg = decodeMessage(line)
            if msg is None:
                continue

            msgType = msg.get("type", "")
            action = msg.get("action", "")

            # 心跳消息特殊处理
            if msgType == TYPE_HEARTBEAT:
                self._handleHeartbeat(msg)
                continue

            # 业务消息 → 路由分发
            response = self._router.handle(msg)

            if response is not None:
                try:
                    self._socket.sendall(encodeMessage(response))
                except OSError:
                    self._running = False
                    break

    def _handleHeartbeat(self, msg: dict):
        """
        处理心跳消息
        :param msg: 心跳消息<dict>
        """
        self._lastHeartbeat = time.time()
        # 回复心跳确认
        response = buildResponse(
            msg.get("request_id", ""),
            ACTION_HEARTBEAT,
            message="pong",
            code=CODE_OK
        )
        try:
            self._socket.sendall(encodeMessage(response))
        except OSError:
            self._running = False

    def _checkHeartbeat(self):
        """检查心跳超时, 超时断开连接"""
        if time.time() - self._lastHeartbeat > HEARTBEAT_TIMEOUT:
            self._logger.warning(self._category, f"客户端心跳超时, 断开连接: {self._addr}")
            self._running = False


class HandlerRouter:
    """
    业务处理器路由
    ===============
    根据 action 将消息分发到对应的处理函数。
    处理函数签名: handler(msg: dict) -> dict (响应消息)
    """

    def __init__(self):
        self._handlers = {}

        # 日志管理器(延迟导入)
        from ServerLogSystem.logManager import getLogger
        from ServerLogSystem.logConfig import CATEGORY_SYSTEM
        self._logger = getLogger()
        self._category = CATEGORY_SYSTEM

    def register(self, action: str, handler):
        """
        注册业务处理器
        :param action: 动作<str>
        :param handler: 处理函数
        """
        self._handlers[action] = handler

    def handle(self, msg: dict) -> dict:
        """
        路由分发消息到处理器
        :param msg: 消息<dict>
        :return: 响应消息<dict>
        """
        action = msg.get("action", "")
        requestId = msg.get("request_id", "")

        handler = self._handlers.get(action)
        if handler is None:
            self._logger.warning(self._category, f"收到未知动作: {action}")
            return buildResponse(
                requestId, action,
                code=CODE_BAD_REQUEST,
                message=f"未知动作: {action}"
            )

        try:
            return handler(msg)
        except Exception as e:
            self._logger.error(self._category, f"处理器异常: action={action}, error={e}")
            return buildResponse(
                requestId, action,
                code=CODE_SERVER_ERROR,
                message=f"服务器内部错误: {str(e)}"
            )


class Server:
    """
    TCP 服务器
    ==========
    监听端口, 接受连接, 为每个客户端创建 ClientHandler。
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        """
        初始化服务器
        :param host: 监听地址<str>
        :param port: 监听端口<int>
        """
        self._host = host
        self._port = port
        self._socket = None
        self._running = False
        self._clients = []  # 客户端处理器列表
        self._router = HandlerRouter()

        # 日志管理器(延迟导入)
        from ServerLogSystem.logManager import getLogger
        from ServerLogSystem.logConfig import CATEGORY_SYSTEM
        self._logger = getLogger()
        self._category = CATEGORY_SYSTEM

    def getRouter(self) -> HandlerRouter:
        """
        获取消息路由器(供外部注册业务处理器)
        :return: HandlerRouter
        """
        return self._router

    def start(self):
        """启动服务器"""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self._host, self._port))
        self._socket.listen(10)
        self._socket.settimeout(1.0)
        self._running = True

        self._logger.info(self._category, f"服务器监听 {self._host}:{self._port}")

        while self._running:
            try:
                clientSocket, addr = self._socket.accept()
                self._logger.info(self._category, f"新客户端连接: {addr}")
                handler = ClientHandler(clientSocket, addr, self._router)
                self._clients.append(handler)
                handler.start()
            except socket.timeout:
                continue
            except OSError:
                break

        self._cleanup()

    def stop(self):
        """停止服务器"""
        self._running = False
        self._logger.info(self._category, "服务器正在停止...")
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass

    def _cleanup(self):
        """清理所有客户端连接"""
        for client in self._clients:
            client.stop()
        self._clients.clear()
        self._logger.info(self._category, "服务器已停止")