"""
coding:utf-8
file: freezeModule.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260816
lateCodedTime:20260816
"""

# 该模块为卡死检测模块类
# =========================
# 系统级卡死检测能力入口(继承观察者基类, 注册到中心调度供 UI/系统调用):
#   - 启动/停止持续监控(FreezeMonitor 后台采样, 9 维度检测)
#   - 配置读写(freezeConfig, 阈值/总开关)
#   - 报警事件 FREEZE_ALERT 发布(UI 显示/弹窗)
#
# 事件协议:
#   接收: FREEZE_START_REQUEST {} / FREEZE_STOP_REQUEST {}
#         FREEZE_STATUS_REQUEST {} / FREEZE_CONFIG_STATUS_REQUEST {}
#         FREEZE_SET_CONFIG_REQUEST {key, value}
#   发布: FREEZE_STATUS_RESULT {running} / FREEZE_CONFIG_STATUS_RESULT {config}
#         FREEZE_ALERT {alert...}(检测到卡死风险时)

import os
import sys

# 注入 CenterMoudle / FreezeMoudle 目录
_CENTER_DIR = os.path.dirname(os.path.abspath(__file__))
_FREEZE_DIR = os.path.join(os.path.dirname(_CENTER_DIR), 'FreezeMoudle')
for _d in (_CENTER_DIR, _FREEZE_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from observerObject import Observer
import freezeConfig
from freezeMonitor import FreezeMonitor


class FreezeModule(Observer):
    """
    卡死检测模块(系统级资源监控)
    ============================
    使用方式(装配层):
        scheduler.register_module(FreezeModule())
    """

    def __init__(self, name="freezeModule"):
        super().__init__(name=name)
        self._monitor = FreezeMonitor()
        # 报警回调(采样线程) → 发布 FREEZE_ALERT 事件(经调度主线程投递到 UI)
        self._monitor.setAlertCallback(self._on_alert)

    def _on_alert(self, alert):
        """检测到卡死风险 → 发布事件"""
        self._publish("FREEZE_ALERT", alert)

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
        if event == "FREEZE_START_REQUEST":
            # 启动持续监控
            ok = self._monitor.start()
            self._publish("FREEZE_STATUS_RESULT",
                          {"running": self._monitor.is_running(), "ok": ok})

        elif event == "FREEZE_STOP_REQUEST":
            # 停止监控
            self._monitor.stop()
            self._publish("FREEZE_STATUS_RESULT", {"running": False, "ok": True})

        elif event == "FREEZE_STATUS_REQUEST":
            # 查询运行状态
            self._publish("FREEZE_STATUS_RESULT",
                          {"running": self._monitor.is_running(), "ok": True})

        elif event == "FREEZE_CONFIG_STATUS_REQUEST":
            # 查询全部配置(页面初始化加载)
            self._publish("FREEZE_CONFIG_STATUS_RESULT",
                          {"config": freezeConfig.load()})

        elif event == "FREEZE_SET_CONFIG_REQUEST":
            # 修改单项配置(阈值/总开关等)
            key = content.get("key")
            value = content.get("value")
            if key and key in freezeConfig.DEFAULT_CONFIG:
                freezeConfig.set(key, value)

        else:
            print(f"[FreezeModule] 未处理事件: {event}: {content}")

    # ============================================================
    # 事件发布(经中心调度通知观察者, 如 UI)
    # ============================================================
    def _publish(self, event, payload):
        if self._scheduler is not None:
            self.notify_observer(event, payload)
