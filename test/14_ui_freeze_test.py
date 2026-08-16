# -*- coding: utf-8 -*-
"""
UI 卡死检测接线验证(离屏模式)
==============================
验证端到端链路: 卡死检测页按钮 → UiRsp → 中心调度 → FreezeModule
              → 状态/配置/报警事件 → 主线程 → 页面更新
覆盖: 配置加载 / 开始监控 / 模拟报警注入 / 停止监控
"""
import os
import sys
import time

# 离屏渲染
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
centerDir = os.path.join(projectRoot, 'CenterMoudle')
freezeDir = os.path.join(projectRoot, 'FreezeMoudle')
uiDir = os.path.join(projectRoot, 'UI', 'FaceModuleUI')
for d in [centerDir, freezeDir, uiDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from PyQt6.QtWidgets import QApplication

from communicationObject import CommunicationObject
from freezeModule import FreezeModule
from UI_object import UiRsp
from UI import MainWindow
from threadBridge import QtMainThreadBridge
import freezeConfig


def pump(app, seconds=3.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main():
    app = QApplication(sys.argv)
    print("=" * 60)

    # 重置卡死配置为默认(不受先前测试/运行残留影响)
    for k, v in freezeConfig.DEFAULT_CONFIG.items():
        freezeConfig.set(k, v)

    print("[1] 装配: 中心调度 + Qt桥 + FreezeModule + UiRsp + MainWindow")
    comm = CommunicationObject()
    comm.set_main_thread_dispatcher(QtMainThreadBridge())
    freeze_mod = FreezeModule()
    uiRsp = UiRsp()
    win = MainWindow(uiRsp)
    comm.register_module(freeze_mod)
    comm.register_module(uiRsp)
    uiRsp.observe("freezeModule")
    win.show()
    print("  ✓ 装配完成")

    print("[2] 卡死检测页: 配置加载 + 控件同步")
    win.switch_page("freeze")   # 触发首次显示 → 请求配置/状态
    pump(app, 1.5)
    page = win.get_page("freeze")
    assert page is not None, "应存在卡死检测页"
    assert page.switch_enabled is not None
    assert page.start_btn.text() == "开始监控"
    assert page.stop_btn.text() == "停止监控"
    cfg = freezeConfig.load()
    # 下拉应同步配置值(findData)
    assert page._combos["sample_interval"].currentData() == cfg["sample_interval"], \
        "检测间隔下拉应同步配置"
    assert page._combos["cpu_threshold"].currentData() == cfg["cpu_threshold"], \
        "CPU 阈值下拉应同步配置"
    print(f"  ✓ 配置加载正常(间隔 {cfg['sample_interval']}s, "
          f"CPU 阈值 {cfg['cpu_threshold']}%)")

    print("[3] 开始监控 → 状态事件回 UI")
    # 测试用短间隔(监控启动后快速采样)
    old_interval = cfg["sample_interval"]
    page._combos["sample_interval"].setCurrentIndex(
        page._combos["sample_interval"].findData(5.0))
    pump(app, 0.5)
    page.start_btn.click()
    pump(app, 1.5)
    assert "运行中" in page.status_label.text(), \
        f"应显示运行中: {page.status_label.text()}"
    print(f"  ✓ 开始监控 → 状态更新: {page.status_label.text()}")

    print("[4] 报警事件 → 页面报警历史")
    # 注入模拟报警(直接走 FreezeModule 的发布路径, 验证 UI 显示)
    freeze_mod._monitor._fireAlert({
        "type": "cpu_high", "value": 95.0, "threshold": 90.0,
        "msg": "CPU 使用率 95%(测试)", "time": "2026-08-16 12:00:00",
        "top_processes": [{"name": "test.exe", "pid": 1, "cpu": 80.0, "mem": 10.0}],
        "info": {"meaning": "CPU 被大量占用(测试)", "advice": "结束占用进程(测试)"},
    })
    pump(app, 1.5)
    history = page.alerts_text.toPlainText()
    assert "CPU 使用率 95%(测试)" in history, f"报警历史应显示: {history}"
    assert "运行中" in page.status_label.text() or "⚠" in page.status_label.text()
    print(f"  ✓ 报警显示在页面: {history.strip().splitlines()[-1]}")

    print("[5] 停止监控 → 状态回停止")
    page.stop_btn.click()
    pump(app, 1.0)
    assert "已停止" in page.status_label.text(), \
        f"应显示已停止: {page.status_label.text()}"
    print(f"  ✓ 停止监控 → 状态更新: {page.status_label.text()}")

    # 恢复配置
    page._combos["sample_interval"].setCurrentIndex(
        page._combos["sample_interval"].findData(old_interval))
    pump(app, 0.5)

    print("\n=== UI 卡死检测接线验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
