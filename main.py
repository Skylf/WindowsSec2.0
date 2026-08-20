"""
coding:utf-8
file: main.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 程序统一入口
# ==============
# 运行 python main.py 即可同时启动:
#   0. 文件完整性校验(校验失败则弹窗阻止进入)
#   1. 后端 TCP 服务器(后台线程, 127.0.0.1:9527)
#   2. 客户端网络连接(authService)
#   3. 前端 UI 控制面板
#
# 启动顺序: 完整性校验 → 校验通过 → 服务端 → 客户端连接 → UI

import sys
import os
import threading
import time

# ── 路径注入 ──
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 服务端路径
_SERVER_DIR = os.path.join(_PROJECT_ROOT, "Server")
_SERVER_SOCKET_DIR = os.path.join(_SERVER_DIR, "SocketModule")
_SERVER_USER_DIR = os.path.join(_SERVER_DIR, "UserSystem")
for _d in (_SERVER_DIR, _SERVER_SOCKET_DIR, _SERVER_USER_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

# 客户端路径
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "client")
_CLIENT_SOCKET_DIR = os.path.join(_CLIENT_DIR, "SocketModule")
_CLIENT_UI_DIR = os.path.join(_CLIENT_DIR, "UI", "FaceModuleUI")
_CLIENT_CENTER_DIR = os.path.join(_CLIENT_DIR, "CenterMoudle")
_CLIENT_FACE_SERVICE_DIR = os.path.join(_CLIENT_DIR, "FaceMoudle", "service")
_CLIENT_FS_DIR = os.path.join(_CLIENT_DIR, "FileSystem")
_CLIENT_LOG_DIR = os.path.join(_CLIENT_DIR, "LogSystem")
for _d in (_CLIENT_DIR, _CLIENT_SOCKET_DIR, _CLIENT_UI_DIR, _CLIENT_CENTER_DIR, _CLIENT_FACE_SERVICE_DIR, _CLIENT_FS_DIR, _CLIENT_LOG_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

# 日志管理器(延迟导入)
_mainLogger = None
_mainCategory = None


def _getMainLogger():
    """获取主进程日志管理器"""
    global _mainLogger, _mainCategory
    if _mainLogger is None:
        from LogSystem.logManager import getLogger
        from LogSystem.logConfig import CATEGORY_SYSTEM
        _mainLogger = getLogger()
        _mainCategory = CATEGORY_SYSTEM
    return _mainLogger, _mainCategory


def startServer():
    """
    在后台线程启动 TCP 服务器
    监听 127.0.0.1:9527, 注册用户系统业务处理器
    """
    logger, category = _getMainLogger()
    from server import Server
    from handler import HandlerRegister

    def _run():
        srv = Server("127.0.0.1", 9527)
        handlers = HandlerRegister()
        handlers.registerAll(srv.getRouter())
        logger.info(category, "TCP 服务器已启动, 监听 127.0.0.1:9527")
        srv.start()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.5)  # 等待服务端就绪
    return thread


def startClientNetwork():
    """
    初始化客户端网络连接
    连接服务端 127.0.0.1:9527, 启用心跳和自动重连
    """
    logger, category = _getMainLogger()
    from authService import initAuthService
    result = initAuthService("127.0.0.1", 9527)
    if result:
        logger.info(category, "客户端已连接到服务端 127.0.0.1:9527")
    else:
        logger.warning(category, "客户端无法连接到服务端, 登录/注册功能不可用")
    return result


def checkIntegrity() -> bool:
    """
    启动前文件完整性校验
    =====================
    校验客户端项目文件是否被篡改或缺失。
    首次运行自动生成基线清单, 后续运行对比基线。
    校验失败时弹出 UI 错误弹窗, 用户可选择退出或强制启动。
    :return: True=校验通过/用户强制启动, False=退出
    """
    from PyQt6.QtWidgets import QApplication

    from integrityChecker import IntegrityChecker
    from integrityDialog import showIntegrityErrorDialog

    logger, category = _getMainLogger()
    ic = IntegrityChecker()
    manifestPath = os.path.join(_CLIENT_DIR, "FileSystem", "integrity_manifest.json")

    logger.info(category, "正在进行文件完整性校验...")

    # 首次运行 → 生成基线清单
    if not os.path.exists(manifestPath):
        logger.info(category, "首次运行, 正在生成文件基线清单...")
        genResult = ic.generateManifest(_CLIENT_DIR)
        if genResult["code"] != 200:
            logger.warning(category, f"清单生成失败: {genResult['message']}")
            return True  # 生成失败不阻止启动
        ic.saveManifest(manifestPath)
        logger.info(category, f"基线清单已生成: {genResult['message']}")
        return True

    # 已有基线 → 加载并校验
    loadResult = ic.loadManifest(manifestPath)
    if loadResult["code"] != 200:
        logger.warning(category, f"清单加载失败: {loadResult['message']}")
        return True  # 加载失败不阻止启动

    verifyResult = ic.verify(_CLIENT_DIR)
    if verifyResult["code"] == 200:
        logger.info(category, verifyResult["message"])
        return True

    # 校验失败 → 弹出错误 UI
    logger.error(category, verifyResult["message"])

    # 创建临时 QApplication(弹窗需要)
    app = QApplication(sys.argv)

    forceStart = showIntegrityErrorDialog(verifyResult)

    app.quit()
    app.processEvents()

    if forceStart:
        logger.warning(category, "用户选择强制启动(不推荐)")
    else:
        logger.critical(category, "完整性校验失败, 用户选择退出, 程序终止")

    return forceStart


def startUI():
    """
    启动前端 UI 控制面板
    装配: 中心调度 + FaceService + SecurityModule + FreezeModule + WatermarkModule + UI
    """
    logger, category = _getMainLogger()
    from PyQt6.QtWidgets import QApplication

    from communicationObject import CommunicationObject
    from faceService import FaceService
    from securityModule import SecurityModule
    from freezeModule import FreezeModule
    from watermarkModule import WatermarkModule
    from UI_object import UiRsp
    from UI import MainWindow
    from threadBridge import QtMainThreadBridge

    app = QApplication(sys.argv)

    # ── 中心调度(中介者): 模块间一切通信经此转接 ──
    scheduler = CommunicationObject()
    scheduler.set_main_thread_dispatcher(QtMainThreadBridge())

    # ── 业务模块 ──
    scheduler.register_module(FaceService())      # 人脸识别/录入服务
    scheduler.register_module(SecurityModule())   # 系统安全(蓝屏识别)
    scheduler.register_module(FreezeModule())     # 卡死检测(资源监控)
    scheduler.register_module(WatermarkModule())  # 视频去水印(本地离线)

    # ── UI 模块: 响应层 + 主窗口 ──
    uiRsp = UiRsp()
    window = MainWindow(uiRsp)
    scheduler.register_module(uiRsp)
    uiRsp.observe("faceService")
    uiRsp.observe("securityModule")
    uiRsp.observe("freezeModule")
    uiRsp.observe("watermarkModule")

    window.show()

    logger.info(category, "控制面板 UI 已启动(中心调度 + FaceService + SecurityModule + FreezeModule + WatermarkModule + UI)")
    logger.info(category, "  - 人脸录入: 人脸识别页 → 人脸录入标签 → [开始录入]")
    logger.info(category, "  - 蓝屏识别: 蓝屏识别页 → [立即检测]/[模拟演示]")
    logger.info(category, "  - 卡死检测: 卡死检测页 → [开始监控]")
    logger.info(category, "  - 视频去水印: 视频去水印页 → 选择视频 → [开始处理]")
    logger.info(category, "  - F11 切换全屏")

    sys.exit(app.exec())


def main():
    """统一入口: 服务端 → 客户端网络 → UI(完整性校验当前已禁用)"""
    logger, category = _getMainLogger()
    logger.info(category, "=" * 60)
    logger.info(category, "  Windows 安全系统 2.0 启动中...")
    logger.info(category, "=" * 60)

    # 0. 文件完整性校验(校验失败则弹窗阻止进入)
    # 当前临时禁用: 避免新增文件每次都要重新生成基线清单, 需要时取消注释即可恢复
    # if not checkIntegrity():
    #     return

    # 1. 启动后端服务
    startServer()

    # 2. 连接客户端网络
    startClientNetwork()

    # 3. 启动 UI(阻塞)
    startUI()


if __name__ == "__main__":
    main()