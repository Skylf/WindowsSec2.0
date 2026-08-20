"""
coding:utf-8
file: SocketModule/client.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端 TCP 通信
# ================
# 建立与服务器的 TCP 连接, 发送消息, 接收响应。
# 消息基于 \n 分隔的 JSON 协议。

import socket
import threading
import time
import queue
import os
import sys

# 注入 LogSystem 路径(client/LogSystem)
_CLIENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CLIENT_DIR not in sys.path:
    sys.path.insert(0, _CLIENT_DIR)

from protocol import (
    encodeMessage, decodeMessage,
    TYPE_HEARTBEAT, TYPE_RESPONSE,
    ACTION_HEARTBEAT,
    buildHeartbeat,
)

# 默认服务器地址
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9527

# 连接超时(秒)
CONNECT_TIMEOUT = 5
# 接收超时(秒)
RECV_TIMEOUT = 1.0


class TcpClient:
    """
    TCP 客户端
    ==========
    管理与服务器的 TCP 连接, 提供 sendMessage / sendRequest 接口。
    """

    def __init__(self):
        self._socket = None
        self._host = None
        self._port = None
        self._connected = False
        self._buffer = b""
        self._recvThread = None
        self._running = False
        # 响应队列: request_id → queue.Queue
        self._responses = {}
        self._lock = threading.Lock()

        # 回调: 连接断开时通知
        self._onDisconnect = None

        # 日志管理器(延迟导入, 避免循环依赖)
        self._logger = None

    def _getLogger(self):
        """获取日志管理器(延迟初始化)"""
        if self._logger is None:
            from LogSystem.logManager import getLogger
            from LogSystem.logConfig import CATEGORY_NETWORK
            self._logger = getLogger()
            self._category = CATEGORY_NETWORK
        return self._logger, self._category

    # ── 属性 ──
    @property
    def connected(self) -> bool:
        return self._connected

    def setOnDisconnect(self, callback):
        """
        设置断开连接回调
        :param callback: callable, 无参数
        """
        self._onDisconnect = callback

    # ── 连接管理 ──
    def connect(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
        """
        连接到服务器
        :param host: 服务器地址<str>
        :param port: 服务器端口<int>
        :return: 是否连接成功<bool>
        """
        self._host = host
        self._port = port

        logger, category = self._getLogger()
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(CONNECT_TIMEOUT)
            self._socket.connect((host, port))
            self._socket.settimeout(RECV_TIMEOUT)
            self._connected = True
            self._running = True

            # 启动接收线程
            self._recvThread = threading.Thread(target=self._recvLoop, daemon=True)
            self._recvThread.start()

            logger.info(category, f"TCP 连接成功 → {host}:{port}")
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self._connected = False
            logger.warning(category, f"TCP 连接失败 → {host}:{port}, 原因: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        logger, category = self._getLogger()
        self._running = False
        self._connected = False
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        logger.info(category, "TCP 连接已断开")

    # ── 消息发送 ──
    def sendMessage(self, msg: dict) -> bool:
        """
        发送消息(不等待响应)
        :param msg: 消息字典<dict>
        :return: 是否发送成功<bool>
        """
        if not self._connected or not self._socket:
            logger, category = self._getLogger()
            logger.warning(category, "发送消息失败: 未连接到服务器")
            return False
        try:
            self._socket.sendall(encodeMessage(msg))
            return True
        except OSError:
            self._connected = False
            logger, category = self._getLogger()
            logger.error(category, "发送消息失败: 连接异常断开")
            return False

    def sendRequest(self, msg: dict, timeout: float = 10.0) -> dict or None:
        """
        发送请求并等待响应(同步)
        :param msg: 请求消息<dict>
        :param timeout: 超时秒数<float>
        :return: 响应消息<dict> 或 None(超时/失败)
        """
        requestId = msg.get("request_id", "")
        if not requestId:
            return None

        # 注册响应队列
        respQueue = queue.Queue()
        with self._lock:
            self._responses[requestId] = respQueue

        # 发送消息
        if not self.sendMessage(msg):
            with self._lock:
                self._responses.pop(requestId, None)
            return None

        # 等待响应
        try:
            response = respQueue.get(timeout=timeout)
            return response
        except queue.Empty:
            return None
        finally:
            with self._lock:
                self._responses.pop(requestId, None)

    # ── 接收循环 ──
    def _recvLoop(self):
        """接收线程: 持续读取数据, 按 \n 分割为 JSON 消息, 分发到响应队列"""
        logger, category = self._getLogger()
        while self._running:
            try:
                if not self._socket:
                    break
                data = self._socket.recv(4096)
                if not data:
                    # 连接断开
                    self._connected = False
                    logger.warning(category, "接收线程: 服务器主动断开连接")
                    self._runDisconnectCallback()
                    break
                self._buffer += data
                self._parseMessages()
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                self._connected = False
                logger.error(category, f"接收线程: 连接异常断开 → {e}")
                self._runDisconnectCallback()
                break

    def _parseMessages(self):
        """解析缓冲区中的完整消息"""
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            msg = decodeMessage(line)
            if msg is None:
                continue

            # 心跳响应不进入队列
            msgType = msg.get("type", "")
            if msgType == TYPE_RESPONSE and msg.get("action") == ACTION_HEARTBEAT:
                continue

            # 将响应投递到对应的请求队列
            requestId = msg.get("request_id", "")
            if requestId:
                with self._lock:
                    respQueue = self._responses.get(requestId)
                if respQueue:
                    respQueue.put(msg)

    def _runDisconnectCallback(self):
        """执行断开连接回调"""
        if self._onDisconnect:
            try:
                self._onDisconnect()
            except Exception:
                pass