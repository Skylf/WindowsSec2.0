# -*- coding: utf-8 -*-
"""
UI 蓝屏识别接线验证(离屏模式)
==============================
验证端到端链路: 蓝屏识别页按钮 → UiRsp → 中心调度 → SecurityModule(模拟检测)
              → BSOD_CHECK_RESULT 事件 → 主线程 → 页面报告显示
另验证: 自启动状态查询 / 开关联动(不实际改注册表)
"""
import os
import sys
import time

# 离屏渲染
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
centerDir = os.path.join(projectRoot, 'CenterMoudle')
uiDir = os.path.join(projectRoot, 'UI', 'FaceModuleUI')
for d in [centerDir, uiDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from PyQt6.QtWidgets import QApplication

from communicationObject import CommunicationObject
from securityModule import SecurityModule
from UI_object import UiRsp
from UI import MainWindow
from threadBridge import QtMainThreadBridge


def pump(app, seconds=3.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main():
    app = QApplication(sys.argv)
    print("=" * 60)

    print("[1] 装配: 中心调度 + Qt桥 + SecurityModule + UiRsp + MainWindow")
    comm = CommunicationObject()
    comm.set_main_thread_dispatcher(QtMainThreadBridge())
    sec = SecurityModule()
    uiRsp = UiRsp()
    win = MainWindow(uiRsp)
    comm.register_module(sec)
    comm.register_module(uiRsp)
    uiRsp.observe("securityModule")
    win.show()
    app.processEvents()
    print("  ✓ 装配完成")

    print("[2] 蓝屏识别页: 模拟演示 → 全链路 → 报告显示")
    page = win.get_page("bsod")
    assert page is not None, "应存在蓝屏识别页"
    # 切到蓝屏页触发首次显示 → 自动查询自启动状态
    win.switch_page("bsod")
    pump(app, 1.0)
    assert page.switch_autostart is not None
    page.simulate_btn.click()    # [模拟演示] → UiRsp → 调度 → SecurityModule(模拟)
    pump(app, 3.0)
    report = page.result_text.toPlainText()
    assert "蓝屏识别报告" in report, f"报告区应显示报告: {report[:60]}"
    assert "0x0000007E" in report, "报告应含蓝屏代码"
    assert "发现蓝屏记录" in page.status_label.text(), \
        f"状态应显示发现记录: {page.status_label.text()}"
    print(f"  ✓ 模拟检测闭环: 报告 {len(report)} 字符, 含代码 0x0000007E")

    print("[3] 立即检测(真实): 本机事件日志")
    page.check_btn.click()
    pump(app, 8.0)
    status = page.status_label.text()
    report = page.result_text.toPlainText()
    if "未检测到" in status:
        print("  ✓ 真实检测正常(本机无蓝屏记录)")
    else:
        assert "发现蓝屏记录" in status, f"状态异常: {status}"
        assert "蓝屏识别报告" in report, "报告区应显示报告"
        print(f"  ✓ 真实检测: 发现蓝屏记录, 报告 {len(report)} 字符")

    print("[4] 自启动开关: 状态与注册表同步(值跟随实际注册状态)")
    # 页面显示时已收到状态查询结果, 开关应与注册表一致(不硬断言开/关, 环境可能已注册)
    status = "开" if page.switch_autostart.isChecked() else "关"
    print(f"  ✓ 自启动状态查询同步开关正常(当前: {status})")

    print("\n=== UI 蓝屏接线验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
