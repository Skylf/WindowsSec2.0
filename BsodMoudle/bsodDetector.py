# -*- coding: utf-8 -*-
"""
蓝屏检测器(bsodDetector)
========================
1. checkLatestBugCheck: 从 Windows 事件日志查询最近的蓝屏记录
   (System 日志, EventID 1001 BugCheck, 由 Windows 错误报告写入,
    记录 BugcheckCode 及 4 个参数)
2. installAutostart / uninstallAutostart: 开机自启动(注册表 HKCU Run)

数据来源说明: 每次蓝屏后 Windows 都会在系统事件日志写入
"Event ID 1001" (来源: Microsoft-Windows-WER-SystemErrorReporting / BugCheck),
包含 BugcheckCode(十进制) 与 BugcheckParameter1~4, 无需解析 .dmp 转储文件。
"""

import os
import re
import subprocess
import sys
from xml.etree import ElementTree

# 事件日志查询命令: 取最近 N 条 EventID=1001 的事件(XML 格式, 最新优先)
_WEVTUTIL_QUERY = ('wevtutil qe System "/q:*[System[(EventID=1001)]]" '
                   '/c:{count} /f:xml /rd:true')

# 开机自启动注册表
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "WindowsSec2_BSODCheck"

# 模拟蓝屏数据文件(模拟生产环境, 无真实蓝屏时演示用)
SAMPLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "sample_bsod_events.xml")


# ====================================================================
# 蓝屏事件查询与解析
# ====================================================================
def checkLatestBugCheck(count=5, simulate=False):
    """
    查询最近的蓝屏(BugCheck)事件
    :param count: 最多返回条数<int>, 默认 5
    :param simulate: 是否使用模拟数据<bool>, 默认 False;
                      True 时从 sample_bsod_events.xml 读取(模拟生产环境, 便于演示)
    :return: 事件列表<list<dict>>, 每条含:
             {
                 "time": "2026-08-15T18:20:11.000",   # 发生时间
                 "code": 126,                          # BugcheckCode(十进制)
                 "params": ["0xffffffff`c0000005", ...],  # 4 个参数(可能有)
             }
             查询失败或无记录返回 []
    """
    if simulate:
        return _checkFromSampleFile(count)

    try:
        cmd = _WEVTUTIL_QUERY.format(count=count)
        completed = subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
        if completed.returncode != 0:
            return []
        raw = completed.stdout
        # wevtutil XML 输出可能为 UTF-16 或 UTF-8, 自动解码
        text = _decodeOutput(raw)
        if not text:
            return []
        return _parseBugCheckEvents(text)
    except (OSError, subprocess.TimeoutExpired):
        return []


def _checkFromSampleFile(count=5):
    """
    从模拟蓝屏数据文件读取事件(模拟生产环境)
    :param count: 最多返回条数<int>
    :return: 事件列表<list<dict>>, 文件缺失返回 []
    """
    if not os.path.exists(SAMPLE_FILE):
        print(f"[bsodDetector] 模拟数据文件不存在: {SAMPLE_FILE}")
        return []
    try:
        with open(SAMPLE_FILE, 'r', encoding='utf-8') as f:
            events = _parseBugCheckEvents(f.read())
        return events[:count]
    except OSError as e:
        print(f"[bsodDetector] 读取模拟数据失败: {e}")
        return []


def _decodeOutput(raw):
    """自动识别 wevtutil 输出编码(UTF-16 BOM / UTF-8 / ASCII)"""
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        return raw.decode('utf-16', errors='replace')
    for enc in ('utf-8', 'gbk'):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='replace')


def _parseBugCheckEvents(xml_text):
    """
    解析 wevtutil XML, 提取 BugCheck 事件的 时间/代码/参数
    :param xml_text: XML 文本<str>
    :return: 事件列表<list<dict>>
    """
    events = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return events

    # 命名空间容错: wevtutil 输出 Event 元素可能带命名空间
    for event in root.iter():
        tag = event.tag.rsplit('}', 1)[-1]
        if tag != 'Event':
            continue
        item = {"time": "", "code": None, "params": []}
        # 遍历子元素(兼容 System/EventData 任意层级)
        for elem in event.iter():
            etag = elem.tag.rsplit('}', 1)[-1]
            if etag == 'TimeCreated':
                item["time"] = elem.attrib.get('SystemTime', '')
            elif etag == 'Data':
                name = elem.attrib.get('Name', '')
                value = (elem.text or '').strip()
                if name == 'BugcheckCode':
                    # 旧格式: <Data Name='BugcheckCode'>126</Data>(十进制)
                    try:
                        item["code"] = int(value)
                    except ValueError:
                        item["code"] = None
                elif name.startswith('BugcheckParameter'):
                    item["params"].append(value)
                elif name == 'param1' and item["code"] is None:
                    # 新格式(Win10+ WER): param1 = "0x0000009f (0x..., 0x..., 0x..., 0x...)"
                    # 或 "0x0000009f (3, 0xffff..., ...)"
                    m = re.match(r'0x([0-9a-fA-F]{8})\s*\((.*?)\)', value)
                    if m:
                        item["code"] = int(m.group(1), 16)
                        item["params"] = [p.strip() for p in m.group(2).split(',') if p.strip()]
                    else:
                        # 无括号格式(仅代码): "0x0000009f"
                        m2 = re.match(r'0x([0-9a-fA-F]{8})', value)
                        if m2:
                            item["code"] = int(m2.group(1), 16)
                elif not name and item["code"] is None:
                    # 旧版无 Name 属性: 第 1 个 Data 视为 BugcheckCode
                    try:
                        item["code"] = int(value)
                    except ValueError:
                        pass
        if item["code"] is not None or item["time"]:
            events.append(item)
    return events


# ====================================================================
# 开机自启动(注册表 HKCU Run)
# ====================================================================
def getAutostartCommand():
    """
    构造开机自启动命令行(本模块的 runTest.py --autostart, 用 pythonw 无控制台窗口)
    --autostart 为静默模式: 真实检测, 有蓝屏记录才弹窗, 无记录静默退出(不打扰用户)
    :return: 命令行<str>
    """
    python_exe = sys.executable
    pythonw = python_exe.replace('python.exe', 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = python_exe
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runTest.py')
    return f'"{pythonw}" "{script}" --autostart'


def installAutostart():
    """
    注册开机自启动(当前用户注册表 Run 键)
    :return: 是否成功<bool>
    """
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY)
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, getAutostartCommand())
        winreg.CloseKey(key)
        return True
    except OSError as e:
        print(f"[bsodDetector] 注册开机自启动失败: {e}")
        return False


def uninstallAutostart():
    """
    移除开机自启动
    :return: 是否成功<bool>
    """
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
    """开机自启动是否已注册"""
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
