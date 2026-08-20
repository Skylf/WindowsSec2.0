"""
coding:utf-8
file: securityModule.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:202608151006
lateCodedTime:20260815
"""

# 该模块为系统安全模块类
# =========================
# 系统级安全能力入口(继承观察者基类, 可注册到中心调度供其他模块调用):
#   - check_bsod:       检查最近蓝屏记录(真实事件日志 或 simulate 模拟生产环境)
#   - run_bsod_report:  检测 + 弹出蓝屏报告窗口(供开机自启动/系统策略调用)
# 蓝屏识别核心逻辑在 BsodMoudle 包, 本类负责系统层面的封装与调度接入。
#
# 事件协议(预留, 后续系统联动用):
#   - 发布 BSOD_DETECTED {time, code, msg}  检测到蓝屏记录时
#   - 发布 MODULE_STATUS {moduleName, online} 由调度器广播

import os
import sys
import threading

# 注入 CenterMoudle / BsodMoudle 目录
_CENTER_DIR = os.path.dirname(os.path.abspath(__file__))
_BSOD_DIR = os.path.join(os.path.dirname(_CENTER_DIR), 'BsodMoudle')
for _d in (_CENTER_DIR, _BSOD_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from observerObject import Observer


class SecurityModule(Observer):
    """
    系统安全模块(蓝屏识别等系统级安全能力)
    ======================================
    使用方式(装配层):
        scheduler.register_module(SecurityModule())
        scheduler.communication_to(调用方, "securityModule", {}, "BSOD_CHECK_REQUEST")
    蓝屏检测在后台线程执行(wevtutil 子进程可能耗时, 不阻塞调用方/主线程)。
    """

    def __init__(self, name="securityModule"):
        super().__init__(name=name)
        self._check_lock = threading.Lock()   # 检测互斥(防并发查询)

    # ============================================================
    # 蓝屏检测
    # ============================================================
    def check_bsod(self, count=1, simulate=False):
        """
        检查最近蓝屏记录(事件日志 BugCheck 1001)
        :param count: 最多返回条数<int>, 默认 1
        :param simulate: 是否使用模拟数据<bool>(模拟生产环境, 便于演示), 默认 False
        :return: 事件列表<list<dict>>, 每条含 time/code/params
        """
        from bsodDetector import checkLatestBugCheck
        return checkLatestBugCheck(count=count, simulate=simulate)

    def run_bsod_report(self, simulate=False):
        """
        蓝屏检测 + 报告弹窗(供开机自启动/系统策略调用)
        :param simulate: 是否使用模拟数据<bool>
        :return: 是否检测到蓝屏并弹窗<bool>
        """
        from bsodReporter import buildReport, showReport
        events = self.check_bsod(count=1, simulate=simulate)
        if not events:
            return False
        report = buildReport(events[0])
        print(report)   # 控制台保留
        showReport(report)
        # 预留: 发布蓝屏检测事件(后续系统联动, 如 AI 分析/通知)
        if self._scheduler is not None:
            event = events[0]
            self.notify_observer("BSOD_DETECTED", {
                "time": event.get("time", ""),
                "code": event.get("code"),
                "msg": "检测到蓝屏记录",
            })
        return True

    # ============================================================
    # 蓝屏检测(后台线程)
    # ============================================================
    def _do_bsod_check(self, simulate):
        """
        后台执行蓝屏检测并发布结果事件(线程安全, 互斥防并发)
        :param simulate: 是否使用模拟数据<bool>
        :return: None
        """
        with self._check_lock:
            events = self.check_bsod(count=1, simulate=simulate)
        if events:
            from bsodReporter import buildReport
            self._publish("BSOD_CHECK_RESULT", {
                "found": True,
                "event": events[0],
                "report": buildReport(events[0]),
            })
        else:
            self._publish("BSOD_CHECK_RESULT", {
                "found": False,
                "event": None,
                "report": "",
            })

    # ============================================================
    # 事件接收(覆写 Observer.all_event)
    # ============================================================
    def all_event(self, event, content, *args, **kwargs):
        """
        收到中心调度事件
        :param event: 事件名<str>
        :param content: 事件内容(dict)
        :return: None
        """
        if event == "BSOD_CHECK_REQUEST":
            # UI/系统请求: 后台线程执行蓝屏检测(wevtutil 可能耗时, 不阻塞调用方)
            simulate = bool(content.get("simulate", False))
            threading.Thread(target=self._do_bsod_check, args=(simulate,),
                             daemon=True).start()

        elif event == "BSOD_AUTOSTART_REQUEST":
            # 开关: 注册/移除开机自启动
            enabled = bool(content.get("enabled", True))
            from bsodDetector import installAutostart, uninstallAutostart
            ok = installAutostart() if enabled else uninstallAutostart()
            self._publish("BSOD_AUTOSTART_RESULT", {"enabled": enabled, "ok": ok})

        elif event == "BSOD_AUTOSTART_STATUS_REQUEST":
            # 查询自启动状态(页面初始化)
            from bsodDetector import isAutostartInstalled
            self._publish("BSOD_AUTOSTART_STATUS_RESULT",
                          {"enabled": isAutostartInstalled()})

        else:
            print(f"[SecurityModule] 未处理事件: {event}: {content}")

    # ============================================================
    # 事件发布(经中心调度通知观察者, 如 UI)
    # ============================================================
    def _publish(self, event, payload):
        """发布事件(未注册调度时静默, 如独立测试)"""
        if self._scheduler is not None:
            self.notify_observer(event, payload)
