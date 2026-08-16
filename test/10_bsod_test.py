# -*- coding: utf-8 -*-
"""
BsodMoudle 蓝屏识别模块验证
============================
1. 知识库: 常见代码解读 / 未知代码通用解读 / 代码格式化
2. 事件日志: 真实查询 BugCheck(1001)(无记录时容错)
3. 报告组装: 文本内容完整
4. AI 接口: 配置存取 / 未配置 key 时 analyzeReport 返回 None
"""
import os
import sys

# 注入 BsodMoudle 目录
bsodDir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'BsodMoudle')
if bsodDir not in sys.path:
    sys.path.insert(0, bsodDir)

from bsodKnowledge import getBsodInfo, formatCode, BSOD_KNOWLEDGE
from bsodDetector import checkLatestBugCheck
from bsodReporter import buildReport
from aiAnalyzer import setAiConfig, getAiConfig, hasAiKey, analyzeReport


def main():
    print("=" * 60)
    print("[1] 知识库: 常见蓝屏代码解读")
    # 常见代码: 0x7E / 0x50 / 0xD1 / 0x116 / 0x124
    for code in (0x7E, 0x50, 0xD1, 0x116, 0x124):
        info = getBsodInfo(code)
        assert info["name"] != "未知蓝屏代码", f"0x{code:X} 应有内置解读"
        assert info["meaning"] and info["advice"]
        print(f"  ✓ 0x{code:08X} {info['name']}: {info['meaning'][:24]}...")
    # 字符串格式输入(十进制 / 十六进制)
    assert getBsodInfo("0x7E")["name"] == "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED"
    assert getBsodInfo("126")["name"] == "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED"
    print("  ✓ 字符串输入(0x7E / 126)解析正确")

    print("[2] 知识库: 未知代码 → 通用解读")
    unknown = getBsodInfo(0xDEAD)
    assert unknown["name"] == "未知蓝屏代码"
    assert formatCode(0x7E) == "0x0000007E"
    assert formatCode("0x7E") == "0x0000007E"
    assert formatCode(126) == "0x0000007E"
    print(f"  ✓ 未知代码回退通用解读, 格式化: {formatCode(0x7E)}")

    print("[3] 事件日志: 真实查询 BugCheck(1001)")
    events = checkLatestBugCheck(count=3)
    if events:
        print(f"  ✓ 查询到 {len(events)} 条蓝屏记录(当前系统有历史蓝屏)")
        for e in events:
            print(f"     时间={e['time']}, 代码={e['code']}, 参数数={len(e['params'])}")
    else:
        print("  ✓ 查询正常(当前系统无蓝屏记录, 容错返回空)")

    print("[3.5] 事件日志: 模拟 wevtutil XML 解析(覆盖解析路径)")
    from bsodDetector import _parseBugCheckEvents
    fake_xml = (
        '<?xml version="1.0"?><Events>'
        '<Event><System><TimeCreated SystemTime="2026-08-15T18:20:11.000Z"/>'
        '<EventID>1001</EventID></System>'
        '<EventData>'
        '<Data Name="BugcheckCode">126</Data>'
        '<Data Name="BugcheckParameter1">0xffffffff`c0000005</Data>'
        '<Data Name="BugcheckParameter2">0x0</Data>'
        '<Data Name="BugcheckParameter3">0x0</Data>'
        '<Data Name="BugcheckParameter4">0x0</Data>'
        '</EventData></Event>'
        '</Events>'
    )
    parsed = _parseBugCheckEvents(fake_xml)
    assert len(parsed) == 1, f"应解析出 1 条事件: {parsed}"
    assert parsed[0]["code"] == 126, f"BugcheckCode 应为 126(0x7E): {parsed[0]}"
    assert len(parsed[0]["params"]) == 4
    assert parsed[0]["time"].startswith("2026-08-15")
    print(f"  ✓ 模拟 XML 解析正确: code={parsed[0]['code']}(0x{parsed[0]['code']:X}), "
          f"params={len(parsed[0]['params'])} 个, time={parsed[0]['time']}")

    print("[3.6] 模拟生产环境: sample_bsod_events.xml 模拟数据")
    sim_events = checkLatestBugCheck(count=3, simulate=True)
    assert len(sim_events) == 3, f"模拟数据应有 3 条: {len(sim_events)}"
    codes = [e["code"] for e in sim_events]
    assert codes == [126, 278, 292], f"模拟数据代码异常: {codes}"
    # 0x7E / 0x116(278) / 0x124(292) 均应有内置解读
    for e in sim_events:
        info = getBsodInfo(e["code"])
        assert info["name"] != "未知蓝屏代码", f"0x{e['code']:X} 应有解读"
    report_sim = buildReport(sim_events[0])
    assert "0x0000007E" in report_sim
    print(f"  ✓ 模拟数据 3 条({[hex(c) for c in codes]}), 报告组装正常")

    print("[3.7] 系统类集成: SecurityModule.check_bsod(simulate=True)")
    projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(projectRoot, 'CenterMoudle'))
    from securityModule import SecurityModule
    sec = SecurityModule()
    evts = sec.check_bsod(count=2, simulate=True)
    assert len(evts) == 2 and evts[0]["code"] == 126
    print(f"  ✓ SecurityModule 蓝屏检测(模拟)正常: {len(evts)} 条, 首条 code=0x{evts[0]['code']:X}")

    # 报告组装(用模拟事件验证文本)
    fake_event = {"time": "2026-08-15T18:20:11.000Z", "code": 0x7E,
                  "params": ["0xffffffff`c0000005", "0x0", "0x0", "0x0"]}
    report = buildReport(fake_event)
    assert "蓝屏识别报告" in report
    assert "0x0000007E" in report and "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED" in report
    assert "【这是什么问题】" in report and "【你可以这样做】" in report
    print(f"  ✓ 报告组装完整({len(report)} 字符):")
    print("      " + report.splitlines()[3].strip())

    print("[4] AI 接口: 配置存取 + 未配置 key 不调用")
    old = getAiConfig()
    setAiConfig(api_key="sk-test-key-123", model="gpt-4o-mini")
    cfg = getAiConfig()
    assert cfg["api_key"] == "sk-test-key-123" and hasAiKey()
    result = analyzeReport("测试报告")   # 会尝试调用(测试 key 无效 → 返回 None 不崩溃)
    assert result is None or isinstance(result, str)
    print(f"  ✓ 配置存取正常; 无效 key 调用返回: {result}")
    # 还原配置(清空 key, 保留文件)
    setAiConfig(api_key="")
    assert not hasAiKey()
    result2 = analyzeReport("测试报告")
    assert result2 is None, "未配置 key 应返回 None"
    print("  ✓ 未配置 key 时跳过 AI 分析(返回 None)")

    print("\n=== BsodMoudle 验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
