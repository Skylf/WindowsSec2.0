# -*- coding: utf-8 -*-
"""
FreezeMoudle 卡死检测模块验证
==============================
1. 配置: 默认值 / 读写 / 总开关
2. 单次采样: 真实系统全方位采样(结构验证, 不断言具体异常)
3. 误报抑制: 连续确认 / 冷却期 / 恢复清零(注入假采样)
4. 报告组装: 文本完整
5. 监控生命周期: 启动/停止(短采样间隔)
"""
import os
import sys
import time

# 注入 FreezeMoudle 目录
freezeDir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'FreezeMoudle')
if freezeDir not in sys.path:
    sys.path.insert(0, freezeDir)

import freezeConfig
from freezeMonitor import FreezeMonitor, KNOWLEDGE
from freezeReporter import buildFreezeReport


def main():
    print("=" * 60)
    print("[1] 配置: 默认值 / 总开关 / 持久化")
    cfg = freezeConfig.load()
    assert cfg["enabled"] is True, "默认总开关应开启"
    assert cfg["confirm_count"] >= 2, "默认连续确认次数应 >= 2"
    assert freezeConfig.isEnabled()
    freezeConfig.setEnabled(False)
    assert not freezeConfig.isEnabled()
    freezeConfig.setEnabled(True)
    freezeConfig.set("sample_interval", 5.0)   # 恢复默认(避免影响后续)
    print(f"  ✓ 配置读写正常(默认: 间隔{cfg['sample_interval']}s, "
          f"确认{cfg['confirm_count']}次, 冷却{cfg['cooldown_seconds']}s)")

    print("[2] 单次采样: 真实系统全方位检测(9 维度)")
    monitor = FreezeMonitor()
    issues = monitor.sampleOnce()
    valid_types = {"cpu_high", "proc_cpu_high", "mem_high", "swap_high",
                   "disk_busy", "disk_full", "process_storm", "ui_freeze",
                   "sys_slow"}
    for issue in issues:
        assert issue["type"] in valid_types, f"未知异常类型: {issue}"
        assert "msg" in issue and "value" in issue
    print(f"  ✓ 单次采样正常, 当前异常 {len(issues)} 项: "
          f"{[i['type'] for i in issues] or '无(系统正常)'}")
    # top 进程采集
    top = monitor._topProcesses(3)
    assert isinstance(top, list) and len(top) <= 3
    if top:
        assert "name" in top[0] and "cpu" in top[0]
        print(f"  ✓ 占用 TOP3 采集正常: {[p['name'] for p in top]}")

    print("[3] 误报抑制: 连续确认 / 冷却期 / 恢复清零(注入假采样)")
    fake = FreezeMonitor()
    fake_alerts = []
    fake.setAlertCallback(lambda a: fake_alerts.append(a))

    # 模拟 CPU 异常: 连续 2 次(未达 3 次) → 不报警
    fake_cpu_issue = {"type": "cpu_high", "value": 95.0, "threshold": 90.0,
                      "msg": "CPU 使用率 95%(测试)"}
    fake._accumulate([fake_cpu_issue])
    fake._accumulate([fake_cpu_issue])
    assert len(fake_alerts) == 0, "连续 2 次未达确认阈值不应报警"
    # 第 3 次 → 报警
    fake._accumulate([fake_cpu_issue])
    assert len(fake_alerts) == 1, "连续 3 次应报警"
    assert fake_alerts[0]["type"] == "cpu_high" and fake_alerts[0]["info"]
    print(f"  ✓ 连续确认: 3 次触发报警(前 2 次抑制), 报警含解读: "
          f"{fake_alerts[0]['info']['meaning'][:16]}...")
    # 冷却期内同类型不再报警
    fake._accumulate([fake_cpu_issue])
    fake._accumulate([fake_cpu_issue])
    fake._accumulate([fake_cpu_issue])
    assert len(fake_alerts) == 1, "冷却期内不应重复报警"
    print("  ✓ 冷却期: 60s 内同类型不重复报警")
    # 异常消失 → 计数清零; 冷却过后再触发需重新累计
    fake._accumulate([])
    assert fake._pending.get("cpu_high", 0) == 0, "异常消失应清零"
    print("  ✓ 恢复清零: 异常消失后计数复位")

    print("[3.5] 持续去重: 持续存在的异常(如磁盘空间不足)只报警一次")
    dedup = FreezeMonitor()
    dedup_alerts = []
    dedup.setAlertCallback(lambda a: dedup_alerts.append(a))
    disk_issue = {"type": "disk_full", "value": 2.0, "threshold": 5.0,
                  "msg": "系统盘剩余空间仅 2%(测试)"}
    # 持续存在 10 轮(远超确认阈值)
    for _ in range(10):
        dedup._accumulate([disk_issue])
    assert len(dedup_alerts) == 1, f"持续异常应只报警 1 次: {len(dedup_alerts)}"
    # 恢复后再现 → 允许再次报警
    dedup._accumulate([])              # 恢复正常
    for _ in range(3):
        dedup._accumulate([disk_issue])
    assert len(dedup_alerts) == 2, f"恢复后再现应再次报警: {len(dedup_alerts)}"
    print("  ✓ 持续去重: 磁盘空间不足只报 1 次, 恢复后再现才重报")

    print("[4] 报告组装")
    alert = {
        "time": "2026-08-15 15:00:00",
        "type": "cpu_high",
        "msg": "CPU 使用率 95%(阈值 90%)",
        "info": KNOWLEDGE["cpu_high"],
        "top_processes": [{"name": "test.exe", "pid": 1234, "cpu": 85.0, "mem": 12.5}],
    }
    report = buildFreezeReport(alert)
    assert "卡死检测报告" in report
    assert "【这是什么问题】" in report and "【谁在占用】" in report
    assert "test.exe" in report and "85" in report
    print(f"  ✓ 报告组装完整({len(report)} 字符), 含进程占用")

    print("[5] 监控生命周期: 启动/停止(短间隔快速验证)")
    freezeConfig.set("sample_interval", 0.5)
    monitor2 = FreezeMonitor()
    assert monitor2.start(), "监控应能启动"
    assert monitor2.is_running()
    time.sleep(1.2)   # 跑 2 轮采样
    monitor2.stop()
    assert not monitor2.is_running()
    freezeConfig.set("sample_interval", 5.0)   # 恢复默认
    print("  ✓ 持续监控启动/停止正常(0.5s 间隔跑 2 轮)")

    print("\n=== FreezeMoudle 验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
