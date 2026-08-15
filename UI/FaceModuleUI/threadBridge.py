"""
coding:utf-8
file: UI/FaceModuleUI/threadBridge.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260815
"""

# Qt 主线程桥(跨线程事件投递器)
# =============================
# 中心调度(CommunicationObject)在投递事件时, 若目标模块 require_main_thread()=True(如 UI),
# 会调用注入的"主线程投递器"。本桥用 pyqtSignal 实现:
#   - 任意线程 emit → QueuedConnection 自动排队到主线程事件循环
#   - 槽函数在主线程执行 → 再调用 observer.all_event(...) → UI 控件操作安全
#
# 为什么必须注入: 不注入时调度器在 Worker 线程直接调用 UI 回调,
# 跨线程操作 QWidget 会导致 Qt 硬崩溃(如 0xCFFFFFFF)。
#
# 使用(装配层/流程脚本):
#   from threadBridge import QtMainThreadBridge
#   scheduler.set_main_thread_dispatcher(QtMainThreadBridge())
#   注意: 桥实例必须在主线程创建(QObject 归属主线程)

from PyQt6.QtCore import QObject, pyqtSignal


class QtMainThreadBridge(QObject):
    """
    Qt 主线程桥(调度器的主线程投递器)
    ================================
    签名兼容 CommunicationObject.set_main_thread_dispatcher:
    dispatcher(observer, event, content, args, kwargs)
    """

    deliver = pyqtSignal(object, str, object, tuple, dict)

    def __init__(self):
        super().__init__()
        # 槽在桥对象所在线程(主线程)执行
        self.deliver.connect(self._on_deliver)

    def _on_deliver(self, observer, event, content, args, kwargs):
        """主线程执行: 把事件交给目标模块处理"""
        observer.all_event(event, content, *args, **kwargs)

    def __call__(self, observer, event, content, args, kwargs):
        """
        投递器入口(调度器调用, 任意线程):
        跨线程 emit → QueuedConnection → 主线程 _on_deliver
        """
        self.deliver.emit(observer, event, content, args, kwargs)
