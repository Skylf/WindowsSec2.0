"""
coding:utf-8
file: SocketModule/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端启动脚本
# ==============
# 启动 TCP 服务器, 注册业务处理器, 进入监听循环。
# 运行方式: python Server/SocketModule/runTest.py

import os
import sys

# 确保路径
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from handler import startServer

if __name__ == "__main__":
    print("=" * 60)
    print("  Windows 安全系统 2.0 - 服务端")
    print("=" * 60)
    print("  启动 TCP 服务器...")
    print("  监听地址: 127.0.0.1:9527")
    print("=" * 60)
    startServer("127.0.0.1", 9527)