"""
coding:utf-8
file: communicationObject.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:202608151008
lateCodedTime:20260815
"""

# 该模块为通信模块的object基类
# 中介者模式(Mediator) + 观察者注册中心: 全局唯一调度枢纽,
# A 与 B 的一切互动(调用/发消息)经本对象转接, 模块间不直接通信。
#
# 两大职责:
# 1. 观察者注册与通知分发(支撑 observerObject 的观察任务)
#    - add_observer(target, observer, event): 登记"observer 观察 target 的 event"
#    - notify_observer(target, event, content): target 动作完成后主动回调,
#      由本调度查表分发通知给所有观察者(含主线程切换)
# 2. 中介通信(模块间请求/消息转接)
#    - communication_to(from, to, content, event): 定向(模块名/实例)或广播(None)
#    - 终点统一调用目标模块的 all_event(event, content) 处理
#
# 线程安全要点:
# - 注册表用 RLock 保护; 分发时"加锁复制快照 → 解锁 → 逐个投递"(回调中再注册不死锁)
# - 目标模块 require_main_thread()=True(UI)且当前非主线程时,
#   经主线程投递器(Qt 信号桥, 由装配层注入)异步切主线程投递
# - 本文件不依赖 PyQt6, 信号桥由 UI 入口/装配层实现并注入

import threading

# 引入观察者基类(类型标注与注册校验用, 单向依赖无循环)
from observerObject import Observer


class CommunicationObject:
    """
    通信基类(中心调度/中介者)
    ========================
    全局唯一实例。持有模块注册表 + 观察者注册表, 提供:
    - 模块注册: register_module / unregister_module / get_module
    - 观察任务: add_observer / remove_observer / notify_observer
    - 中介通信: communication_to(定向/广播)
    业务模块继承 Observer, 只与本对象交互, 互相零直接调用。
    """

    def __init__(self):
        # 模块注册表: name(str) -> Observer 实例
        self._modules = {}

        # 观察者注册表: (被观察者name, event|None) -> set(观察者实例)
        # event=None 表示观察该模块的全部事件
        self._observer_map = {}

        # 保护注册表的锁
        self._lock = threading.RLock()

        # 主线程投递器(由装配层注入, PyQt 场景为信号桥)
        self._main_thread_dispatcher = None

    # ============================================================
    # 模块注册管理
    # ============================================================
    def register_module(self, module: Observer):
        """
        注册模块: 登记到通信枢纽 + 注入本调度引用(模块才能 add/notify)
        :param module: 模块实例<Observer>
        :return: None
        """
        with self._lock:
            self._modules[module.name] = module
        module.set_scheduler(self)

    def unregister_module(self, module: Observer):
        """
        注销模块: 从通信枢纽移除, 并清除其观察者关系
        :param module: 模块实例<Observer>
        :return: None
        """
        with self._lock:
            self._modules.pop(module.name, None)
            # 清除与该模块相关的观察关系(作为被观察者)
            keys = [k for k in self._observer_map if k[0] == module.name]
            for k in keys:
                self._observer_map.pop(k, None)
        module.set_scheduler(None)

    def get_module(self, name: str):
        """
        按模块名查询已注册模块(仅供调度内部/日志使用;
        业务通信请走 communication_to, 保持"不直接通信"约束)
        :param name: 模块名<str>
        :return: Observer 实例, 不存在返回 None
        """
        with self._lock:
            return self._modules.get(name)

    def get_module_names(self) -> list:
        """
        获取全部已注册模块名(日志/调试用)
        :return: 模块名列表<list<str>>
        """
        with self._lock:
            return list(self._modules.keys())

    # ============================================================
    # 观察者注册管理(被 Observer.add_observer/remove_observer 委托调用)
    # ============================================================
    def add_observer(self, target, observer, event=None):
        """
        登记观察关系: observer 观察 target 的 event 事件
        :param target: 被观察者(Observer 实例 或 模块名<str>)
        :param observer: 观察者实例<Observer>
        :param event: 事件名<str>, None=观察 target 的全部事件
        :return: None
        """
        target_name = target.name if isinstance(target, Observer) else str(target)
        with self._lock:
            self._observer_map.setdefault((target_name, event), set()).add(observer)

    def remove_observer(self, target, observer, event=None):
        """
        解除观察关系
        :param target: 被观察者(Observer 实例 或 模块名<str>)
        :param observer: 观察者实例<Observer>
        :param event: 事件名<str>, None=从 target 全部事件中解除
        :return: None
        """
        target_name = target.name if isinstance(target, Observer) else str(target)
        with self._lock:
            if event is None:
                # 解除该观察者对 target 的全部观察关系(含全量订阅)
                keys = [k for k in self._observer_map if k[0] == target_name]
                for k in keys:
                    self._observer_map.get(k, set()).discard(observer)
            else:
                observers = self._observer_map.get((target_name, event))
                if observers:
                    observers.discard(observer)

    # ============================================================
    # 通知分发(被 Observer.notify_observer 委托调用, 核心回调逻辑)
    # ============================================================
    def notify_observer(self, target, event, content=None, *args, **kwargs):
        """
        被观察者动作完成后的主动回调: 查表通知所有观察者(快照分发)
        任意线程可调用, 线程安全; 单个观察者异常不影响其他观察者。

        :param target: 被观察者(Observer 实例 或 模块名<str>)
        :param event: 事件名<str>
        :param content: 事件内容(任意对象, 建议 dict)
        :return: None
        """
        target_name = target.name if isinstance(target, Observer) else str(target)

        # 快照: 加锁复制观察者集合后立即解锁, 再逐个投递
        # (回调中可能再次注册/通知, 持锁会死锁)
        with self._lock:
            observers = set(self._observer_map.get((target_name, event), set()))
            observers |= set(self._observer_map.get((target_name, None), set()))

        for observer in observers:
            try:
                self._deliver(observer, event, content, args, kwargs)
            except Exception as e:
                print(f"[Communication] 通知 {observer.name} 处理事件[{event}] 异常: {e}")

    # ============================================================
    # 中介通信(A 与 B 的一切互动经此转接)
    # ============================================================
    def communication_to(self, from_object: object, to_object: object,
                         content, event=None, *args, **kwargs) -> bool:
        """
        模块间通信(定向或广播), 任意线程可调用, 线程安全
        流程: 解析发送方/接收方 → 加锁快照目标列表 → 解锁 → 逐个投递
        (终点统一调用目标模块的 all_event(event, content))

        :param from_object: 发送方(Observer 实例 或 模块名<str>, 仅日志用)
        :param to_object:   接收方(Observer 实例 / 模块名<str> / None=广播全部)
        :param content:     通信内容(任意对象, 建议 dict 结构化)
        :param event:       事件名<str>, 默认 None(目标按内容自行判断)
        :return: 是否至少有一个目标收到<bool>(目标不存在返回 False)
        """
        # ---- 解析发送方(仅日志用) ----
        from_name = from_object.name if isinstance(from_object, Observer) else str(from_object)

        # ---- 解析接收方快照 ----
        with self._lock:
            if to_object is None:
                targets = list(self._modules.values())          # 广播全部
            elif isinstance(to_object, str):
                target = self._modules.get(to_object)           # 定向(模块名)
                targets = [target] if target is not None else []
            elif isinstance(to_object, Observer):
                targets = [to_object]                           # 定向(实例)
            else:
                targets = []

        if not targets:
            print(f"[Communication:{from_name}] 发送事件[{event}] 失败: "
                  f"目标不存在或不合法: {to_object}")
            return False

        # ---- 逐个投递(锁外执行) ----
        for target in targets:
            try:
                self._deliver(target, event, content, args, kwargs)
            except Exception as e:
                print(f"[Communication:{from_name}] 投递事件[{event}] "
                      f"给 {target.name} 异常: {e}")
        return True

    # ============================================================
    # 投递核心(统一处理主线程切换)
    # ============================================================
    def _deliver(self, target, event, content, args, kwargs):
        """
        投递事件到单个目标模块
        :param target: 目标模块<Observer>
        :param event: 事件名<str>
        :param content: 事件内容
        :return: None
        """
        if target.require_main_thread() and self._main_thread_dispatcher is not None:
            # 目标要求主线程 且 已注入投递器 → 异步切主线程投递
            # (PyQt 场景: 投递器内部 pyqtSignal.emit → QueuedConnection
            #  排队到主线程事件循环 → 槽函数在主线程调 target.all_event)
            self._main_thread_dispatcher(target, event, content, args, kwargs)
        else:
            # 同线程/无投递器(纯逻辑测试) → 同步直接调用
            target.all_event(event, content, *args, **kwargs)

    # ============================================================
    # 主线程投递器注入(PyQt 桥由装配层实现, 本类不依赖 PyQt)
    # ============================================================
    def set_main_thread_dispatcher(self, dispatcher):
        """
        注入主线程投递器(UI 入口/装配层启动时调用一次)
        PyQt 实现示例(由装配层编写):
            class QtDispatcher(QObject):
                deliver = pyqtSignal(object, str, object, tuple, dict)
                def __init__(self):
                    super().__init__()
                    self.deliver.connect(self._on_deliver)
                def _on_deliver(self, observer, event, content, args, kwargs):
                    observer.all_event(event, content, *args, **kwargs)
                def __call__(self, observer, event, content, args, kwargs):
                    self.deliver.emit(observer, event, content, args, kwargs)
            # pyqtSignal 跨线程 emit 自动 QueuedConnection:
            # 非主线程 emit → 排队到主线程事件循环 → 槽函数在主线程执行

        :param dispatcher: 可调用对象,
               签名 dispatcher(observer, event, content, args, kwargs)
        :return: None
        """
        self._main_thread_dispatcher = dispatcher
