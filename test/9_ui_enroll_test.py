# -*- coding: utf-8 -*-
"""
UI 录入/识别业务接线验证(离屏模式, mock 业务层)
================================================
验证端到端链路: UI 按钮 → UiRsp → 中心调度 → FaceService(后台线程) → 事件回流 → UI 状态显示
覆盖: 录入(EnrollSubPage) 与 识别页"重新录人脸"切标签
"""
import os
import sys
import time
import types

# 离屏渲染
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
centerDir = os.path.join(projectRoot, 'CenterMoudle')
serviceDir = os.path.join(projectRoot, 'FaceMoudle', 'service')
uiDir = os.path.join(projectRoot, 'UI', 'FaceModuleUI')
for d in [centerDir, serviceDir, uiDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

# ---- mock 业务层(避免真实摄像头/模型) ----
fake_enroll = types.ModuleType('faceEnroll')


def fake_run_enroll(user_name, progressCallback=None, frameCallback=None):
    if progressCallback:
        progressCallback("silent", "静默检测")
    if progressCallback:
        progressCallback("capture", "照片采集中")
    if frameCallback:
        import numpy as np
        frameCallback(np.zeros((120, 160, 3), dtype=np.uint8), "请正对摄像头")
    time.sleep(0.2)
    if progressCallback:
        progressCallback("clean", "图片检测与清洗中")   # 拍照完成, 摄像头已关闭
    time.sleep(0.3)   # 留出"处理中"遮罩显示窗口(测试观测)
    if progressCallback:
        progressCallback("extract", "特征提取中")
    return {"success": True, "msg": "录入完成", "step": "",
            "featurePath": rf"D:\fake\{user_name}_feat.npy"}


fake_enroll.runEnroll = fake_run_enroll
sys.modules['faceEnroll'] = fake_enroll

from PyQt6.QtWidgets import QApplication

from communicationObject import CommunicationObject
from faceService import FaceService
from UI_object import UiRsp
from UI import MainWindow
from texts import get_text
from threadBridge import QtMainThreadBridge


def pump(app, seconds=3.0):
    """驱动 Qt 事件循环直到状态回 IDLE 或超时"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main():
    app = QApplication(sys.argv)
    print("=" * 60)

    print("[1] 装配: 中心调度 + Qt主线程桥 + FaceService + UiRsp + MainWindow")
    comm = CommunicationObject()
    comm.set_main_thread_dispatcher(QtMainThreadBridge())   # 与生产环境一致: Worker 线程事件切主线程
    svc = FaceService()
    uiRsp = UiRsp()
    win = MainWindow(uiRsp)
    comm.register_module(svc)
    comm.register_module(uiRsp)
    uiRsp.observe("faceService")     # UI 观察 FaceService 的进度/结果事件
    win.show()
    app.processEvents()
    print("  ✓ 装配完成(UI 不直接 import 业务模块, 全部经中介调度)")

    print("[2] 录入页: 点击开始 → 全屏画面页 → 录入完成 → 退回原窗口")
    win.switch_page("recognition")    # 从识别页进入录入标签(来源页 = recognition)
    app.processEvents()
    enroll = win.get_page("recognition")._enroll_sub
    assert uiRsp._state == UiRsp.STATE_IDLE
    # 用户名与账户绑定: 页面显示当前用户, 无手动输入框
    assert "admin" in enroll.current_user_label.text(), f"应显示当前用户: {enroll.current_user_label.text()}"
    assert not hasattr(enroll, "user_input"), "录入页不应有手动用户名输入框"
    enroll.start_enroll_btn.click()  # 模拟点击(→ UiRsp → 调度 → FaceService, 使用当前用户 admin)
    assert uiRsp._state == UiRsp.STATE_ENROLLING, f"应进入录入中状态: {uiRsp._state}"
    # 摄像头未接入(任务刚启动): "正在加载中..."遮罩可见
    live = win._live_page
    assert live._overlay.isVisible(), "摄像头未接入时应显示加载遮罩"
    assert live._overlay._text == "正在加载中...", f"遮罩文字: {live._overlay._text}"
    app.processEvents()
    # 全屏画面页: 强制全屏 + 沉浸式画面页
    assert win._stack.currentWidget() is win.get_page("live"), "应切换到全屏画面页"
    assert win.isFullScreen(), "应强制全屏"
    # 等首帧到达(帧回调更新提示词, 加载遮罩随之隐藏)
    deadline = time.time() + 3.0
    while live.prompt_label.text() != "请正对摄像头" and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert live.prompt_label.text() == "请正对摄像头", \
        f"帧回调应更新提示词: {live.prompt_label.text()}"
    # 拍照完成进入处理阶段: 实时等待"正在处理中"遮罩出现(摄像头已关闭)
    deadline = time.time() + 3.0
    while not (live._overlay.isVisible()
               and live._overlay._text == "正在处理中，请稍等") and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert live._overlay.isVisible() and live._overlay._text == "正在处理中，请稍等", \
        f"处理阶段应显示处理中遮罩: {live._overlay._text}"
    # 录入成功: 整屏绿色成功覆盖层(对勾 + "录入成功")
    deadline = time.time() + 3.0
    while not live._success_overlay.isVisible() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert live._success_overlay.isVisible(), "录入成功应显示成功覆盖层"
    assert live._success_overlay._text_label.text() == "录入成功", \
        f"成功文字: {live._success_overlay._text_label.text()}"
    # 1.5 秒后自动退回原窗口
    pump(app, 3.0)
    assert uiRsp._state == UiRsp.STATE_IDLE, "收到录入结果后应回 IDLE"
    assert not win.isFullScreen(), "完成后应退出全屏"
    assert win._stack.currentWidget() is win.get_page("recognition"), "应退回原页面"
    assert "录入完成" in enroll.status_label.text(), f"状态显示异常: {enroll.status_label.text()}"
    assert "admin" in enroll.status_label.text(), "录入归属应为当前用户 admin"
    print(f"  ✓ 录入闭环完成(加载遮罩→画面→处理遮罩→成功绿屏→自动退回, 用户 admin)")

    print("[3] 录入中重复点击 → 状态机拦截(不重复发起)")
    enroll.start_enroll_btn.click()
    assert uiRsp._state == UiRsp.STATE_ENROLLING
    enroll.start_enroll_btn.click()   # 录入中再次点击
    assert uiRsp._state == UiRsp.STATE_ENROLLING, "录入中重复点击应被拦截"
    pump(app, 5.0)
    assert uiRsp._state == UiRsp.STATE_IDLE
    print("  ✓ 录入中重复点击被拦截")

    print("[4] 识别页: [重新录人脸] → 切换到录入标签页")
    page = win.get_page("recognition")
    sub = page._recognize_sub
    page._tab_bar.setCurrentIndex(0)   # 先回到识别标签
    sub.reenroll_btn.click()
    app.processEvents()
    assert page._tab_bar.currentIndex() == 1, "重新录人脸应切到录入标签"
    print("  ✓ [重新录人脸] 切换到录入页")

    print("[5] 录入互斥: 录入中拒绝新识别请求(UiRsp 状态机)")
    enroll.start_enroll_btn.click()
    assert uiRsp._state == UiRsp.STATE_ENROLLING
    uiRsp.on_start_recognize(r"D:\x\admin.npy")   # 录入中尝试识别
    assert uiRsp._state == UiRsp.STATE_ENROLLING, "录入中不应接受识别请求"
    pump(app, 5.0)
    assert uiRsp._state == UiRsp.STATE_IDLE
    print("  ✓ 状态机互斥生效(录入中拒绝识别)")

    print("\n=== UI 业务接线验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
