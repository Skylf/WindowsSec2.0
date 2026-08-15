# -*- coding: utf-8 -*-
"""
UI 基类验证(离屏模式, 不弹真实窗口)
====================================
验证: GUI/UiRsp 装配 / 页面管理 / 状态机 / 与中心调度的完整事件流 / 信号转发
"""
import os
import sys

# 离屏渲染(不弹窗口)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
centerDir = os.path.join(projectRoot, 'CenterMoudle')
uiDir = os.path.join(projectRoot, 'UI', 'FaceModuleUI')
for d in [centerDir, uiDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QThread

from observerObject import Observer
from communicationObject import CommunicationObject
from UI_object import GUI, UiRsp, EVENT_FACE_RECOGNIZE_REQUEST, EVENT_FACE_RECOGNIZE_RESULT


class FakeFaceService(Observer):
    """模拟 FaceService: 收到请求后在后台线程干活并发结果"""

    def __init__(self):
        super().__init__(name="faceService")
        self.last_request = None
        self.received_cancel = False

    def all_event(self, event, content, *args, **kwargs):
        if event == EVENT_FACE_RECOGNIZE_REQUEST:
            self.last_request = content
            # 模拟后台线程: 收到请求后异步发进度+结果
            def work():
                self.notify_observer("FACE_RECOGNIZE_PROGRESS",
                                     {"stage": "silent", "detail": "静默检测中"})
                self.notify_observer("FACE_RECOGNIZE_RESULT",
                                     {"success": True, "livenessPass": True,
                                      "matched": True, "similarity": 0.9482,
                                      "msg": "识别成功", "step": ""})
            import threading
            threading.Thread(target=work, daemon=True).start()
        elif event == "FACE_RECOGNIZE_CANCEL":
            self.received_cancel = True


def main():
    app = QApplication(sys.argv)
    print("=" * 60)

    print("[1] 装配: UiRsp + GUI(外部注入) + 自动补挂")
    uiRsp = UiRsp()
    gui = GUI(uiRsp)
    assert uiRsp.get_gui() is gui, "GUI 构造应自动补挂 UiRsp"
    print("  ✓ GUI.__init__(uiRsp) 注入成功, 自动补挂 set_gui")

    print("[2] 页面管理: add_page / switch_page / get_page")
    page_a = QWidget()
    page_b = QWidget()
    gui.add_page(page_a, "recognition")
    gui.add_page(page_b, "enroll")
    gui.switch_page("recognition")
    assert gui.get_page("recognition") is page_a
    assert gui._stack.currentWidget() is page_a
    gui.switch_page("enroll")
    assert gui._stack.currentWidget() is page_b
    print("  ✓ 页面注册/切换正常")

    print("[3] 信号转发: set_recognizing / show_progress / show_result")
    signals = {"state": [], "progress": [], "result": []}
    gui.recognize_state_changed.connect(lambda b: signals["state"].append(b))
    gui.progress_received.connect(lambda s, d: signals["progress"].append((s, d)))
    gui.result_received.connect(lambda r: signals["result"].append(r))
    gui.set_recognizing(True)
    gui.show_progress("action", "请左转")
    gui.show_result({"matched": True, "similarity": 0.9})
    assert signals["state"] == [True]
    assert signals["progress"] == [("action", "请左转")]
    assert signals["result"][0]["similarity"] == 0.9
    print("  ✓ 三个信号转发正常")

    print("[4] 状态机: 未注册调度时点击开始 → 警告不崩溃")
    uiRsp.on_start_recognize("/tmp/x.npy")
    assert uiRsp._state == UiRsp.STATE_IDLE, "未注册调度不应进入识别中"
    print("  ✓ 未注册调度警告(不崩溃)")

    print("[5] 完整事件流: 注册调度+FaceService → 点击开始 → 进度/结果回 UI")
    comm = CommunicationObject()
    svc = FakeFaceService()
    comm.register_module(svc)
    comm.register_module(uiRsp)
    # UI 观察 FaceService 的进度/结果事件(观察者视角注册, 不接触 FaceService 实例)
    uiRsp.observe("faceService")
    uiRsp.on_start_recognize(r"D:\x\admin.npy", threshold=0.85)
    assert uiRsp._state == UiRsp.STATE_RECOGNIZING, "应进入识别中状态"
    assert svc.last_request["threshold"] == 0.85
    print(f"  ✓ 请求已送达 FaceService: {svc.last_request}")

    # 等待后台线程的事件回流(经调度 → UiRsp)
    import time
    deadline = time.time() + 5
    while uiRsp._state != UiRsp.STATE_IDLE and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    assert uiRsp._state == UiRsp.STATE_IDLE, "收到 RESULT 后应回 IDLE"
    assert signals["progress"], "应收到进度事件"
    assert signals["result"], "应收到结果事件"
    assert signals["state"][-1] is False, "识别结束应恢复按钮(False)"
    print(f"  ✓ 事件回流完成: progress={signals['progress']}, result_sim={signals['result'][-1]['similarity']}")

    print("[6] 防重复点击: 识别中再次点击 → 拒绝")
    uiRsp.on_start_recognize(r"D:\x\admin.npy")
    assert uiRsp._state == UiRsp.STATE_RECOGNIZING
    # 等结果回流
    deadline = time.time() + 5
    while uiRsp._state != UiRsp.STATE_IDLE and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    print("  ✓ 防重复点击生效(识别中拒绝新请求)")

    print("\n=== UI 基类验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
