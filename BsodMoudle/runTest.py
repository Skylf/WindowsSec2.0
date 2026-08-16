# -*- coding: utf-8 -*-
"""
蓝屏识别 - 运行测试(交互菜单 + 静默自启动)
============================================
手动运行: 显示功能菜单(检测/模拟/AI配置/自启动管理)
开机自启动: --autostart 静默模式(真实检测, 有蓝屏记录才弹窗, 无记录静默退出)

运行方式:
  python BsodMoudle/runTest.py              # 交互菜单
  python BsodMoudle/runTest.py --autostart  # 开机自启动静默检测(由注册表调用)
  python BsodMoudle/runTest.py --simulate   # 命令行直接模拟检测+弹窗
  python BsodMoudle/runTest.py --install    # 注册开机自启动
  python BsodMoudle/runTest.py --uninstall  # 移除开机自启动
"""
import sys
import os

# 注入本模块目录
_BSOD_DIR = os.path.dirname(os.path.abspath(__file__))
if _BSOD_DIR not in sys.path:
    sys.path.insert(0, _BSOD_DIR)

from bsodDetector import (checkLatestBugCheck, installAutostart,
                          uninstallAutostart, isAutostartInstalled,
                          getAutostartCommand)
from bsodReporter import buildReport, showReport
from aiAnalyzer import analyzeReport, hasAiKey, getAiConfig, setAiConfig


# ====================================================================
# 检测 + 报告(打印 + 弹窗)
# ====================================================================
def run_detection(simulate=False, force_show=False):
    """
    执行一次蓝屏检测并报告
    :param simulate: 是否使用模拟数据<bool>
    :param force_show: 无记录时也弹窗说明<bool>(调试用)
    :return: 检测到的记录条数<int>
    """
    if simulate:
        print("\n[模拟模式] 使用 sample_bsod_events.xml 模拟生产环境蓝屏记录")
    events = checkLatestBugCheck(count=1, simulate=simulate)

    if not events:
        print("\n[bsod] 未检测到蓝屏记录(本机无蓝屏)")
        if force_show:
            showReport("[bsod] 未检测到蓝屏记录(调试模式强制显示)。")
        return 0

    event = events[0]
    report = buildReport(event)
    print(report)   # 控制台保留

    # AI 解读(已配置 key 时附加)
    if hasAiKey():
        print("\n[AI 解读] 正在调用 AI 分析...")
        ai_result = analyzeReport(report)
        if ai_result:
            report += "\n\n" + "=" * 56 + "\n【AI 解读】\n" + ai_result
            print("[AI 解读] 完成")

    showReport(report)
    return 1


# ====================================================================
# AI Key 配置(交互)
# ====================================================================
def configure_ai_key():
    """交互配置 AI key(回车跳过 = 不修改)"""
    current = getAiConfig()
    print("\n当前配置: " + ("已配置 key" if current.get("api_key") else "未配置 key")
          + f", 接口: {current.get('api_base')}, 模型: {current.get('model')}")
    api_key = input("输入 AI API Key(回车跳过): ").strip()
    if not api_key:
        print("已取消(保持当前配置)")
        return
    api_base = input(f"接口地址(回车默认 {current.get('api_base')}): ").strip() or None
    model = input(f"模型名(回车默认 {current.get('model')}): ").strip() or None
    setAiConfig(api_key=api_key, api_base=api_base, model=model)
    print("AI Key 已保存(ai_config.json, 不会提交到 git)")


# ====================================================================
# 自启动管理(交互)
# ====================================================================
def manage_autostart(install):
    """注册/移除开机自启动"""
    if install:
        ok = installAutostart()
        print("注册开机自启动:", "成功 ✓" if ok else "失败")
        if ok:
            print(f"  启动命令: {getAutostartCommand()}")
    else:
        ok = uninstallAutostart()
        print("移除开机自启动:", "成功 ✓" if ok else "失败(可能未注册)")


# ====================================================================
# 主流程
# ====================================================================
def main():
    args = sys.argv[1:]

    # ── 静默模式(开机自启动调用): 真实检测, 有记录才弹窗 ──
    if "--autostart" in args:
        run_detection(simulate=False)
        return

    # ── 兼容命令行直接执行(不弹菜单) ──
    if "--install" in args:
        manage_autostart(install=True)
        return
    if "--uninstall" in args:
        manage_autostart(install=False)
        return
    if "--simulate" in args:
        run_detection(simulate=True, force_show="--show" in args)
        return

    # ── 交互菜单 ──
    print("=" * 56)
    print("           蓝屏识别模块")
    print("=" * 56)
    while True:
        print()
        print("请选择功能:")
        print("  1. 真实检测(本机蓝屏记录)")
        print("  2. 模拟检测(模拟生产环境演示)")
        print("  3. 配置 AI Key(用于 AI 解读蓝屏)")
        print("  4. 注册开机自启动")
        print("  5. 移除开机自启动")
        print("  6. 查看自启动状态")
        print("  0. 退出")
        choice = input("请输入数字: ").strip()

        if choice == "0":
            print("已退出")
            return
        elif choice == "1":
            run_detection(simulate=False)
        elif choice == "2":
            run_detection(simulate=True)
        elif choice == "3":
            configure_ai_key()
        elif choice == "4":
            manage_autostart(install=True)
        elif choice == "5":
            manage_autostart(install=False)
        elif choice == "6":
            print("开机自启动:", "已注册 ✓" if isAutostartInstalled() else "未注册")
            if isAutostartInstalled():
                print(f"  启动命令: {getAutostartCommand()}")
        else:
            print("输入无效, 请重试")


if __name__ == '__main__':
    main()
