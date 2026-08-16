# -*- coding: utf-8 -*-
"""
模拟器端到端业务功能测试
========================
1. 模拟器脚本可运行(CPU 短时)
2. 端到端: CPU 满载模拟 → FreezeMonitor 连续确认 → 触发 cpu_high 报警
3. 配置恢复
"""
import os
import subprocess
import sys
import time

# 注入目录
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
freezeDir = os.path.join(projectRoot, 'FreezeMoudle')
if freezeDir not in sys.path:
    sys.path.insert(0, freezeDir)

import freezeConfig
from freezeMonitor import FreezeMonitor

SIM_CPU = os.path.join(freezeDir, 'simulator', 'sim_cpu.py')


def main():
    print("=" * 60)
    print("[1] CPU 模拟器可运行(1 线程 1 秒)")
    r = subprocess.run([sys.executable, SIM_CPU, "--threads", "1", "--duration", "1"],
                       capture_output=True, encoding="utf-8", errors="replace",
                       timeout=30)
    assert r.returncode == 0, f"模拟器运行失败: {r.stderr}"
    assert "已启动 1 个线程" in r.stdout
    print(f"  ✓ CPU 模拟器运行正常: {r.stdout.strip().splitlines()[0]}")

    print("[2] 端到端: CPU 满载模拟 → 检测器连续确认 → 触发 cpu_high 报警")
    # 测试环境配置: 短采样 + 低阈值 + 少确认次数(16 线程 numpy 约 20-35%)
    freezeConfig.set("sample_interval", 0.5)
    freezeConfig.set("confirm_count", 2)
    freezeConfig.set("cooldown_seconds", 5)
    freezeConfig.set("cpu_threshold", 10.0)

    monitor = FreezeMonitor()
    alerts = []
    monitor.setAlertCallback(lambda a: alerts.append(a))
    assert monitor.start()
    # 启动 16 线程 CPU 模拟(numpy 密集计算, 约占 50% 核)
    sim = subprocess.Popen([sys.executable, SIM_CPU, "--threads", "16",
                            "--duration", "5"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # 等待 cpu_high 报警出现(期间可能有其他真实异常报警, 如磁盘空间不足)
        deadline = time.time() + 15
        while time.time() < deadline:
            if any(a["type"] == "cpu_high" for a in alerts):
                break
            time.sleep(0.2)
    finally:
        monitor.stop()
        sim.terminate()

    alert_types = [a["type"] for a in alerts]
    assert "cpu_high" in alert_types, f"CPU 满载模拟应触发 cpu_high 报警: {alert_types}"
    alert = next(a for a in alerts if a["type"] == "cpu_high")
    assert alert["msg"] and alert["info"] and "time" in alert
    print(f"  ✓ 端到端报警触发: [{alert['time']}] {alert['msg']}")
    if len(alerts) > 1:
        print(f"  ✓ 期间还检测到其他异常: {alert_types}")
    print(f"  ✓ 报警含解读/建议: {alert['info']['meaning'][:20]}...")

    print("[3] 配置恢复默认")
    freezeConfig.set("sample_interval", 5.0)
    freezeConfig.set("confirm_count", 3)
    freezeConfig.set("cooldown_seconds", 60)
    freezeConfig.set("cpu_threshold", 90.0)
    print("  ✓ 配置已恢复")

    print("\n=== 模拟器端到端测试全部通过 ✓ ===")


if __name__ == '__main__':
    main()
