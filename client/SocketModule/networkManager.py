"""
coding:utf-8
file: SocketModule/networkManager.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 网络管理器
# ==========
# 封装 TcpClient, 管理: 连接/断开/心跳/自动重连/Token 管理。
# 上层业务通过 sendRequest 发送请求, 自动处理 Token 透传。

import threading
import time
import os
import sys

# 注入 LogSystem 路径(client/LogSystem)
_CLIENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CLIENT_DIR not in sys.path:
    sys.path.insert(0, _CLIENT_DIR)

from client import TcpClient, DEFAULT_HOST, DEFAULT_PORT
from protocol import (
    buildRequest, buildHeartbeat,
    HEARTBEAT_INTERVAL,
    CODE_OK,
)


class NetworkManager:
    """
    网络管理器
    ===========
    单例模式, 全局唯一网络连接管理。
    职责:
    1. 维护 TCP 连接
    2. 定时发送心跳
    3. 自动重连
    4. 管理当前 Token(登录后自动透传)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._client = TcpClient()
        self._client.setOnDisconnect(self._onDisconnect)

        self._token = ""
        self._heartbeatThread = None
        self._reconnectThread = None
        self._running = False
        self._autoReconnect = True
        self._host = DEFAULT_HOST
        self._port = DEFAULT_PORT

        # 连接状态回调
        self._onStatusChange = None

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
        return self._client.connected

    @property
    def token(self) -> str:
        return self._token

    def setToken(self, token: str):
        """
        设置当前 Token(登录成功后调用)
        :param token: 令牌<str>
        """
        self._token = token
        logger, _ = self._getLogger()
        logger.debug("NETWORK", f"Token 已更新: {token[:8]}...")

    def clearToken(self):
        """清除 Token(登出后调用)"""
        self._token = ""
        logger, _ = self._getLogger()
        logger.debug("NETWORK", "Token 已清除")

    def setOnStatusChange(self, callback):
        """
        设置连接状态变化回调
        :param callback: callable(connected: bool)
        """
        self._onStatusChange = callback

    # ── 连接管理 ──
    def connect(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
        """
        连接到服务器
        :param host: 服务器地址<str>
        :param port: 端口<int>
        :return: 是否成功<bool>
        """
        self._host = host
        self._port = port
        logger, _ = self._getLogger()
        result = self._client.connect(host, port)
        if result:
            self._startHeartbeat()
            self._notifyStatusChange(True)
            logger.info("NETWORK", f"网络管理器连接成功 → {host}:{port}")
        else:
            logger.warning("NETWORK", f"网络管理器连接失败 → {host}:{port}")
        return result

    def disconnect(self):
        """断开连接"""
        logger, _ = self._getLogger()
        self._autoReconnect = False
        self._stopHeartbeat()
        self._client.disconnect()
        self._notifyStatusChange(False)
        logger.info("NETWORK", "网络管理器已断开连接")

    def isConnected(self) -> bool:
        return self._client.connected

    # ── 消息发送 ──
    def sendRequest(self, action: str, data: dict = None, timeout: float = 10.0) -> dict or None:
        """
        发送请求并等待响应(自动透传 Token)
        :param action: 动作<str>
        :param data: 数据<dict>
        :param timeout: 超时秒数<float>
        :return: 响应消息<dict> 或 None
        """
        msg = buildRequest(action, data, self._token)
        return self._client.sendRequest(msg, timeout)

    # ── 心跳 ──
    def _startHeartbeat(self):
        """启动心跳线程"""
        self._running = True
        self._heartbeatThread = threading.Thread(target=self._heartbeatLoop, daemon=True)
        self._heartbeatThread.start()

    def _stopHeartbeat(self):
        """停止心跳线程"""
        self._running = False

    def _heartbeatLoop(self):
        """心跳循环: 每 HEARTBEAT_INTERVAL 秒发送一次 ping"""
        while self._running and self._client.connected:
            time.sleep(HEARTBEAT_INTERVAL)
            if not self._running or not self._client.connected:
                break
            # 发送心跳
            hb = buildHeartbeat(self._token)
            self._client.sendMessage(hb)

    # ── 断线重连 ──
    def _onDisconnect(self):
        """连接断开回调"""
        logger, _ = self._getLogger()
        self._stopHeartbeat()
        self._notifyStatusChange(False)
        logger.warning("NETWORK", "检测到连接断开, 准备重连...")
        if self._autoReconnect:
            self._startReconnect()

    def _startReconnect(self):
        """启动重连线程"""
        if self._reconnectThread and self._reconnectThread.is_alive():
            return
        self._reconnectThread = threading.Thread(target=self._reconnectLoop, daemon=True)
        self._reconnectThread.start()

    def _reconnectLoop(self):
        """重连循环: 每 5 秒尝试一次, 直到成功"""
        logger, _ = self._getLogger()
        while self._autoReconnect and not self._client.connected:
            time.sleep(5)
            if not self._autoReconnect:
                break
            logger.info("NETWORK", f"尝试重连 → {self._host}:{self._port}")
            result = self._client.connect(self._host, self._port)
            if result:
                self._startHeartbeat()
                self._notifyStatusChange(True)
                logger.info("NETWORK", "重连成功")
            else:
                logger.warning("NETWORK", "重连失败, 5秒后重试...")

    def _notifyStatusChange(self, connected: bool):
        """通知状态变化"""
        if self._onStatusChange:
            try:
                self._onStatusChange(connected)
            except Exception:
                pass