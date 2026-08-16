"""
coding:utf-8
file: UI/FaceModuleUI/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260815
"""

# 人脸识别 UI 运行测试(完整装配: 中心调度 + FaceService + UI)
# ============================================================
# 用途: 运行完整控制面板 UI, 识别/录入按钮真实可用(需摄像头)
# 装配链路:
#   MainWindow(UiRsp) + FaceService 都注册到中心调度(中介),
#   UiRsp 观察 FaceService 的进度/结果事件 → 界面实时显示。
#
# 运行方式: python UI/FaceModuleUI/runTest.py

import sys
import os

# 注入项目路径(UI 目录 / CenterMoudle / FaceMoudle service)
_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_UI_DIR))
for _d in (_UI_DIR,
           os.path.join(_PROJECT_ROOT, 'CenterMoudle'),
           os.path.join(_PROJECT_ROOT, 'FaceMoudle', 'service')):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from PyQt6.QtWidgets import QApplication

from communicationObject import CommunicationObject
from faceService import FaceService
from securityModule import SecurityModule
from freezeModule import FreezeModule
from watermarkModule import WatermarkModule
from UI_object import UiRsp
from UI import MainWindow
from threadBridge import QtMainThreadBridge


def main():
    """创建中心调度 + 业务服务 + UI 并启动(完整链路)"""
    app = QApplication(sys.argv)

    # ── 中心调度(中介者): 模块间一切通信经此转接 ──
    scheduler = CommunicationObject()
    # 注入 Qt 主线程桥: UI 模块的事件统一切主线程投递(跨线程操作 QWidget 会硬崩溃)
    scheduler.set_main_thread_dispatcher(QtMainThreadBridge())

    # ── 业务模块 ──
    scheduler.register_module(FaceService())      # 人脸识别/录入服务
    scheduler.register_module(SecurityModule())   # 系统安全(蓝屏识别)
    scheduler.register_module(FreezeModule())     # 卡死检测(资源监控)
    scheduler.register_module(WatermarkModule())  # 视频去水印(本地离线)

    # ── UI 模块: 响应层 + 主窗口 ──
    ui_rsp = UiRsp()
    window = MainWindow(ui_rsp)
    scheduler.register_module(ui_rsp)
    # UI 观察业务模块的进度/结果事件(经调度主线程投递)
    ui_rsp.observe("faceService")
    ui_rsp.observe("securityModule")
    ui_rsp.observe("freezeModule")
    ui_rsp.observe("watermarkModule")

    window.show()

    print("控制面板 UI 已启动(中心调度 + FaceService + SecurityModule + FreezeModule + WatermarkModule + UI)")
    print("  - 人脸录入: 人脸识别页 → 人脸录入标签 → [开始录入](需摄像头, 活体检测录入)")
    print("  - 蓝屏识别: 蓝屏识别页 → [立即检测]/[模拟演示]")
    print("  - 卡死检测: 卡死检测页 → [开始监控](9 维度, 报警显示在页面)")
    print("  - 视频去水印: 视频去水印页 → 选择视频 → [开始处理](本地离线, 无痕修复)")
    print("  - F11 切换全屏")
    print("  - 关闭窗口退出")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
