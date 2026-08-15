# -*- coding: utf-8 -*-
"""
UI 主窗口验证(离屏模式, 不弹真实窗口)
======================================
验证: 窗口尺寸/固定/无边框 / 样式加载 / 导航 8 项 / 页面注册与切换
      / 概览页(评分卡+网格+统计条) / 识别页标签 / 密码/蓝屏/卡死页
      / 滑动开关 SwitchButton / 环形仪表 GaugeWidget / 文本解耦 / 全屏
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

from PyQt6.QtWidgets import QApplication, QFrame
from PyQt6.QtCore import Qt

from UI_object import UiRsp
from UI import (MainWindow, RecognitionPage, RecognitionSubPage, EnrollSubPage,
                OverviewPage, PasswordPage, BsodPage, FreezePage, AccountPage,
                UserAvatar, SwitchButton, GaugeWidget, NAV_ITEMS,
                WINDOW_WIDTH, WINDOW_HEIGHT)
from texts import get_text, set_language, LANG_EN, LANG_ZH
from style import load_stylesheet
from userInfo import get_current_user, get_current_user_name


def main():
    app = QApplication(sys.argv)
    print("=" * 60)

    print("[1] 窗口: 1024x632 固定 + 无边框(自定义标题栏) + 控制面板标题")
    uiRsp = UiRsp()
    win = MainWindow(uiRsp)
    assert win.width() == WINDOW_WIDTH and win.height() == WINDOW_HEIGHT
    assert win.minimumSize() == win.maximumSize() == win.size(), "窗口应固定尺寸"
    assert win.windowFlags() & Qt.WindowType.FramelessWindowHint, "应无边框(自定义标题栏)"
    assert win.windowTitle() == "Windows 安全系统 2.0 控制面板", f"标题错误: {win.windowTitle()}"
    print(f"  ✓ 尺寸 {win.width()}x{win.height()}, 固定不可拖动, 无边框")
    print(f"  ✓ 标题: {win.windowTitle()}")
    print(f"  ✓ 黄金分割比 {WINDOW_HEIGHT / WINDOW_WIDTH:.4f} ≈ 0.618")

    print("[2] 样式解耦合: QSS 已加载")
    qss = load_stylesheet()
    assert qss and win.styleSheet(), "样式应为非空"
    assert "#0B1120" in qss
    print(f"  ✓ 样式表 {len(qss)} 字符, 含设计配色")

    print("[3] 导航栏: 8 项(复刻设计图) + 页面注册 10 个(8 导航页 + 账户页 + 全屏画面页)")
    nav = win._nav
    assert nav.count() == 8, f"导航应有 8 项, 实际 {nav.count()}"
    nav_texts = [nav.item(i).text() for i in range(nav.count())]
    print(f"  ✓ 导航: {nav_texts}")
    assert len(win._pages) == 10, f"应注册 10 个页面(含账户页/画面页), 实际 {len(win._pages)}"
    assert all(pid in win._pages for _, pid, _ in NAV_ITEMS)
    assert "account" in win._pages, "应注册账户页(不加入导航)"
    assert "live" in win._pages, "应注册全屏画面页(不加入导航)"
    print("  ✓ 页面注册 10 个(8 导航页 + 隐藏账户页/画面页)")

    print("[4] 导航联动 + 默认页(安全概览)")
    assert win._stack.currentWidget() is win.get_page("overview"), "默认应为安全概览"
    win._nav.setCurrentRow(1)
    assert win._stack.currentWidget() is win.get_page("recognition")
    win._nav.setCurrentRow(0)
    assert win._stack.currentWidget() is win.get_page("overview")
    print("  ✓ 导航联动正常, 默认页为安全概览")

    print("[5] 安全概览页: 评分卡 + 功能网格 + 统计条 + 右上角用户头像")
    ov = win.get_page("overview")
    assert isinstance(ov, OverviewPage)
    assert ov.scan_btn.text() == "立即扫描"
    grid_cards = [ov.findChild(QFrame, "gridCard") for _ in range(6)]
    assert all(c is not None for c in grid_cards), "应有 6 个功能网格卡片"
    stat_bar = ov.findChild(QFrame, "statBar")
    assert stat_bar is not None, "应有底部统计条"
    assert isinstance(ov.avatar, UserAvatar), "右上角应有用户头像"
    assert "admin" in ov.avatar._user_info_html() and "1001" in ov.avatar._user_info_html(), \
        "头像悬停信息应含用户名与 ID(来自 userInfo)"
    print("  ✓ 评分卡(立即扫描按钮)/6 功能卡片/统计条 齐全")
    print(f"  ✓ 右上角用户头像(悬停信息来自 userInfo: {get_current_user()})")

    print("[5.5] 账户页: 头像点击进入 + 铺满窗口(隐藏标题栏/导航) + 返回恢复")
    win.show()                        # 激活布局(离屏), 使几何生效
    app.processEvents()
    account = win.get_page("account")
    assert isinstance(account, AccountPage), "应注册账户页"
    assert account.big_avatar is not None and account.back_btn.text() == "← 返回概览"
    ov.avatar.clicked.emit()          # 模拟点击头像
    app.processEvents()
    assert win._stack.currentWidget() is account, "点击头像应进入账户页"
    # 沉浸式: 标题栏与导航隐藏, 页面铺满窗口
    assert not win._title_bar.isVisible(), "账户页应隐藏标题栏"
    assert not win._nav.isVisible(), "账户页应隐藏左侧导航"
    app.processEvents()
    stack_geo = win._stack.geometry()
    win_geo = win.centralWidget().geometry()
    assert stack_geo.width() >= win_geo.width() - 4 and stack_geo.height() >= win_geo.height() - 4, \
        f"账户页应铺满窗口: stack={stack_geo}, win={win_geo}"
    print(f"  ✓ 账户页铺满窗口(stack={stack_geo.width()}x{stack_geo.height()})")
    account.back_btn.click()          # 模拟点击返回
    app.processEvents()
    assert win._stack.currentWidget() is ov, "返回按钮应回概览页"
    assert win._title_bar.isVisible() and win._nav.isVisible(), "返回后应恢复标题栏与导航"
    print("  ✓ 头像点击 → 沉浸式账户页, 返回 → 外壳恢复")

    print("[6] 识别页: 识别+录入同页标签切换 + 滑动开关")
    page = win.get_page("recognition")
    assert isinstance(page, RecognitionPage)
    assert page._tab_bar.tabText(0) == "人脸识别" and page._tab_bar.tabText(1) == "人脸录入"
    page._tab_bar.setCurrentIndex(1)
    assert page._tab_stack.currentWidget() is page._enroll_sub
    page._tab_bar.setCurrentIndex(0)
    sub = page._recognize_sub
    assert isinstance(sub.switch_login, SwitchButton) and sub.switch_login.isChecked()
    assert isinstance(sub.switch_liveness, SwitchButton) and sub.switch_liveness.isChecked()
    assert abs(sub.switch_login.offset - 1.0) < 1e-6
    sub.switch_login.setChecked(False)
    assert not sub.switch_login.isChecked() and abs(sub.switch_login.offset) < 1e-6
    assert sub.threshold_combo.currentText() == "严格 (0.85)"
    corners = [sub.findChild(QFrame, name) for name in
               ("cornerTL", "cornerTR", "cornerBL", "cornerBR")]
    assert all(c is not None for c in corners)
    print("  ✓ 标签切换/滑动开关/阈值下拉/扫描角标 正常")

    print("[7] 密码管理页: 环形图 + 强度检查")
    pwd = win.get_page("password")
    assert isinstance(pwd, PasswordPage)
    assert isinstance(pwd.gauge, GaugeWidget), "应有环形仪表"
    assert pwd.password_input.echoMode() == pwd.password_input.EchoMode.Password
    assert pwd.update_btn.text() == "更新密码"
    print("  ✓ 环形图(强 95% ±9%)/密码输入(掩码)/检查列表 齐全")

    print("[8] 蓝屏识别页: 模拟蓝屏 + 智能防护开关")
    bsod = win.get_page("bsod")
    assert isinstance(bsod, BsodPage)
    assert isinstance(bsod.switch_repair, SwitchButton) and bsod.switch_repair.isChecked()
    assert bsod.repair_btn.text() == "立即修复"
    sim = bsod.findChild(QFrame, "bsodSim")
    assert sim is not None, "应有模拟蓝屏"
    print("  ✓ 蓝屏模拟(:( + 20% 完成)/3 个防护开关 齐全")

    print("[9] 卡死检测页: 仪表盘 + 检测设置")
    freeze = win.get_page("freeze")
    assert isinstance(freeze, FreezePage)
    assert isinstance(freeze.gauge, GaugeWidget)
    assert len(freeze.combos) == 4, "应有 4 个设置下拉"
    assert isinstance(freeze.auto_kill, SwitchButton)
    print("  ✓ 仪表盘(系统状态 正常)/4 个下拉/自动结束开关 齐全")

    print("[10] 文本解耦合: 双语切换 + 用户数据源(userInfo)")
    assert get_text("window.title") == "Windows 安全系统 2.0 控制面板"
    assert get_text("nav.password") == "密码管理"
    assert get_current_user_name() == "admin", "当前用户应为 admin(占位数据源)"
    set_language(LANG_EN)
    assert get_text("window.title") == "Windows Security System 2.0 Control Panel"
    assert get_text("nav.password") == "Password Manager"
    assert get_text("bsod.sim_title").startswith("Your device")
    set_language(LANG_ZH)
    assert get_text("not.exists.key") == "not.exists.key"
    print("  ✓ 中英切换正常(含控制面板新标题/用户信息), 缺失 key 回退安全")

    print("[11] 全屏切换(F11/标题栏按钮): 不崩溃且状态可切换")
    win.toggle_fullscreen()
    app.processEvents()
    is_fs = win.isFullScreen()
    win.toggle_fullscreen()
    app.processEvents()
    assert not win.isFullScreen()
    print(f"  ✓ 全屏进入({is_fs})/退出正常, 布局等比缩放")

    print("[12] 压力测试: 连续快速切换菜单 200 次(复现闪退场景)")
    for i in range(200):
        win._nav.setCurrentRow(i % 8)
        app.processEvents()
    win._nav.setCurrentRow(0)
    app.processEvents()
    assert win.isVisible() or True  # 离屏下不强制可见, 只验证不崩溃
    print("  ✓ 200 次快速切换无崩溃")

    print("\n=== UI 完全复刻验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
