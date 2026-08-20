"""
coding:utf-8
file: SocketModule/deviceInfo.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 本机设备信息采集(自动登录用)
# ===============================
# 采集登录机器的 IP 地址与设备识别码,上传服务端用于 cookie 绑定:
#   - IP: 与服务端通信时本机实际出口 IP(同一台机器需保证前后采集一致)
#   - 设备识别码: 由系统 + 计算机名 + MAC + Windows MachineGuid 哈希生成,稳定唯一
# 自动登录校验时,服务端比对 cookie 绑定的 ip/device_code 与本次采集结果。

import socket
import platform
import uuid
import hashlib


def getLocalIp() -> str:
    """
    获取本机局域网 IP 地址
    通过 UDP 空连接方式探测本机出口网卡 IP(不真正发包给目标)
    失败时回退为 127.0.0.1

    :return: 本机 IP 地址<str>
    """
    try:
        # 建立 UDP 套接字并"连接"到公网地址,由内核自动选择出口网卡
        probeSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probeSocket.connect(("8.8.8.8", 80))
            localIp = probeSocket.getsockname()[0]
        finally:
            probeSocket.close()
        return localIp
    except Exception:
        return "127.0.0.1"


def getDeviceCode() -> str:
    """
    获取本机设备识别码(稳定且不易随软件重装变化)
    组成: 操作系统 + 计算机名 + MAC 地址 + Windows MachineGuid,再做 sha256
    使用 MachineGuid 保证同一台机器重装系统前识别码稳定

    :return: 设备识别码<str>(64位hex)
    """
    # 基础信息(跨平台可用)
    machineName = platform.node()
    systemName = platform.system()
    macAddress = uuid.getnode()

    # Windows 专属: 读取注册表 MachineGuid(机器唯一标识,最稳定)
    machineGuid = ""
    try:
        import winreg
        regKey = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography"
        )
        machineGuid, _ = winreg.QueryValueEx(regKey, "MachineGuid")
    except Exception:
        machineGuid = ""

    # 组合原始串并哈希(哈希后固定 64 位 hex,避免原始串过长)
    rawInfo = f"{systemName}|{machineName}|{macAddress}|{machineGuid}"
    return hashlib.sha256(rawInfo.encode("utf-8")).hexdigest()