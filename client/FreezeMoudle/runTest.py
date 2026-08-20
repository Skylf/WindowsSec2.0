# -*- coding: utf-8 -*-
"""
卡死检测 - 运行测试(交互菜单 + 静默自启动)
============================================
手动运行: 显示功能菜单(立即检测/持续监控/配置/自启动)
开机自启动: --autostart 静默启动持续监控, 检测到卡死风险才弹窗报告

运行方式:
  python FreezeMoudle/runTest.py              # 交互菜单
  python FreezeMoudle/runTest.py --autostart  # 开机自启动静默监控(由注册表调用)
  python FreezeMoudle/runTest.py --once       # 立即检测一次(打印报告, 不弹窗)
  python FreezeMoudle/runTest.py --install    # 注册开机自启动
  python FreezeMoudle/runTest.py --uninstall  # 移除开机自启动
"""
import os
import sys

# 注入本模块目录
_FREEZE_DIR = os.path.dirname(os.path.abspath(__file__))
if _FREEZE_DIR not in sys.path:
    sys.path.insert(0, _FREEZE_DIR)

import freezeConfig
from freezeMonitor import FreezeMonitor
from freezeReporter import buildFreezeReport, showFreezeReport

# 开机自启动注册表(与蓝屏模块独立)
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "WindowsSec2_FreezeMonitor"


# ====================================================================
# 自启动管理
# ====================================================================
def getAutostartCommand():
    """构造开机自启动命令行(--autostart 静默监控, pythonw 无控制台)"""
    python_exe = sys.executable
    pythonw = python_exe.replace('python.exe', 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = python_exe
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runTest.py')
    return f'"{pythonw}" "{script}" --autostart'


def installAutostart():
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY)
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, getAutostartCommand())
        winreg.CloseKey(key)
        return True
    except OSError as e:
        print(f"[freeze] 注册开机自启动失败: {e}")
        return False


def uninstallAutostart():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, _AUTOSTART_NAME)
        finally:
            winreg.CloseKey(key)
        return True
    except OSError:
        return False


def isAutostartInstalled():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _AUTOSTART_NAME)
            return True
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


# ====================================================================
# 检测
# ====================================================================
def run_once(show_popup=False):
    """立即检测一次(单次采样), 打印异常; 可弹窗报告"""
    import time as _time
    monitor = FreezeMonitor()
    issues = monitor.sampleOnce()
    if not issues:
        print("\n[freeze] 单次采样未发现异常(CPU/内存/磁盘/进程/界面均正常)")
        return
    print(f"\n[freeze] 单次采样发现 {len(issues)} 项异常:")
    for issue in issues:
        print(f"  ⚠ {issue['msg']}")
    if show_popup and issues:
        from freezeMonitor import KNOWLEDGE
        alert = dict(issues[0])
        alert["time"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        alert["top_processes"] = monitor._topProcesses(
            int(freezeConfig.get("top_process_count")))
        alert["info"] = KNOWLEDGE.get(alert["type"], {})
        showFreezeReport(buildFreezeReport(alert))


def start_monitoring(show_popup=True):
    """启动持续监控(检测到卡死风险弹窗报告)"""
    monitor = FreezeMonitor()
    if show_popup:
        def on_alert(alert):
            print(buildFreezeReport(alert))
            showFreezeReport(buildFreezeReport(alert))
        monitor.setAlertCallback(on_alert)
    else:
        def on_alert(alert):
            print(buildFreezeReport(alert))
        monitor.setAlertCallback(on_alert)

    if not monitor.start():
        print("[freeze] 监控未启动(总开关关闭, 可在菜单中开启)")
        return None
    return monitor


# ====================================================================
# 配置(交互)
# ====================================================================
def show_config():
    cfg = freezeConfig.load()
    print("\n当前配置:")
    print(f"  总开关: {'开' if cfg['enabled'] else '关'}")
    print(f"  采样间隔: {cfg['sample_interval']}s, "
          f"连续确认: {cfg['confirm_count']} 次, 冷却: {cfg['cooldown_seconds']}s")
    print(f"  CPU阈值: {cfg['cpu_threshold']}%, 内存阈值: {cfg['mem_threshold']}%, "
          f"页面文件阈值: {cfg['swap_threshold']}%")
    print(f"  磁盘IO阈值: {cfg['disk_busy_threshold']} MB/s, "
          f"磁盘剩余阈值: {cfg['disk_free_threshold']}%, "
          f"进程数阈值: {cfg['process_count_threshold']}")
    print(f"  界面无响应超时: {cfg['ui_timeout_ms']}ms, 报告进程数: {cfg['top_process_count']}")


def configure():
    """交互修改配置(回车保持原值)"""
    fields = [
        ("enabled", "总开关(1开/0关)"),
        ("sample_interval", "采样间隔(秒)"),
        ("confirm_count", "连续确认次数(抑制误报)"),
        ("cooldown_seconds", "报警冷却(秒)"),
        ("cpu_threshold", "CPU 阈值(%)"),
        ("mem_threshold", "内存阈值(%)"),
        ("swap_threshold", "页面文件阈值(%)"),
        ("disk_busy_threshold", "磁盘 IO 阈值(MB/s)"),
        ("disk_free_threshold", "磁盘剩余阈值(%)"),
        ("process_count_threshold", "进程数阈值"),
        ("ui_timeout_ms", "界面无响应超时(毫秒)"),
    ]
    print("\n逐项修改配置(直接回车保持原值):")
    for key, label in fields:
        current = freezeConfig.get(key)
        val = input(f"  {label} [{current}]: ").strip()
        if not val:
            continue
        try:
            if key == "enabled":
                freezeConfig.set(key, val in ("1", "true", "开", "y", "Y"))
            else:
                freezeConfig.set(key, float(val))
        except ValueError:
            print(f"    无效输入, 保持原值 {current}")


# ====================================================================
# 主流程
# ====================================================================
def main():
    args = sys.argv[1:]

    # ── 静默模式(开机自启动): 启动持续监控, 检测到卡死风险弹窗 ──
    if "--autostart" in args:
        if not freezeConfig.isEnabled():
            return
        monitor = FreezeMonitor()
        def on_alert(alert):
            showFreezeReport(buildFreezeReport(alert))
        monitor.setAlertCallback(on_alert)
        monitor.start()
        print("[freeze] 开机自启动监控已运行(静默, Ctrl+C 退出)")
        try:
            while True:
                __import__('time').sleep(60)
        except KeyboardInterrupt:
            monitor.stop()
        return

    # ── 命令行直接执行 ──
    if "--install" in args:
        print("注册开机自启动:", "成功 ✓" if installAutostart() else "失败")
        return
    if "--uninstall" in args:
        print("移除开机自启动:", "成功 ✓" if uninstallAutostart() else "失败")
        return
    if "--once" in args:
        run_once(show_popup="--show" in args)
        return

    # ── 交互菜单 ──
    print("=" * 56)
    print("           卡死检测模块")
    print("=" * 56)
    monitor = None
    while True:
        print()
        print("请选择功能:")
        print("  1. 立即检测一次(全方位采样)")
        print("  2. 启动持续监控(检测到卡死风险弹窗报告)")
        print("  3. 停止监控")
        print("  4. 查看监控状态与报警历史")
        print("  5. 查看/修改配置(阈值/开关)")
        print("  6. 注册开机自启动(静默监控)")
        print("  7. 移除开机自启动")
        print("  0. 退出")
        choice = input("请输入数字: ").strip()

        if choice == "0":
            if monitor is not None and monitor.is_running():
                monitor.stop()
            print("已退出")
            return
        elif choice == "1":
            run_once(show_popup=True)
        elif choice == "2":
            if monitor is not None and monitor.is_running():
                print("监控已在运行")
            else:
                monitor = start_monitoring(show_popup=True)
        elif choice == "3":
            if monitor is not None and monitor.is_running():
                monitor.stop()
            else:
                print("监控未在运行")
        elif choice == "4":
            print("监控状态:", "运行中" if monitor is not None and monitor.is_running() else "未运行")
            print("开机自启动:", "已注册 ✓" if isAutostartInstalled() else "未注册")
            if monitor is not None and monitor.alerts:
                print(f"报警历史({len(monitor.alerts)} 条):")
                for a in monitor.alerts[-5:]:
                    print(f"  [{a['time']}] {a['msg']}")
            else:
                print("报警历史: 无")
        elif choice == "5":
            show_config()
            print("\n修改配置? (y/n): ", end="")
            if input().strip().lower() in ("y", "yes", "是"):
                configure()
                show_config()
        elif choice == "6":
            print("注册开机自启动:", "成功 ✓" if installAutostart() else "失败")
        elif choice == "7":
            print("移除开机自启动:", "成功 ✓" if uninstallAutostart() else "失败")
        else:
            print("输入无效, 请重试")


if __name__ == '__main__':
    main()
