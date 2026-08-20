"""
coding:utf-8
file:observerObject.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:202608151010
lateCodedTime:20260815
"""

# 该模块为观察者模块的object基类
# 观察者模式(Observer Pattern): 解决"A 需要 B 响应后动作, 但不能 while True 轮询"的问题。
#
# 标准运行逻辑(4 步), 以 Subject(被观察者)=A, Observer(观察者)=B 拆解:
#   1. 注册(绑定关系): B 主动调用 A 的注册方法, 把 B 登记到观察列表
#      → 实现: b.observe(a, event) 或 a.add_observer(b, event)(两者等价)
#      → A 知道 B 存在, 但 A 不关心 B 具体是谁
#   2. 触发(状态变更): A 执行特定动作/状态改变时, 自动触发 notify
#      → 实现: A 动作完成后调用 self.notify_observer(event, content)
#   3. 遍历(广播通知): notify 遍历观察列表, 逐一调用 B 的约定接口(update)
#      → 实现: 中心调度查表遍历, 逐一调用 observer.all_event(event, content)
#      → A 只负责"喊"一声, B 收到后做什么 A 完全不管
#   4. 响应(各自执行): 每个 B 在 all_event 中执行自己的逻辑
#
# 核心硬性逻辑: 数据流向单向(A→B), 调用关系反向(A 主动推送, B 不轮询),
# A 面向公共接口(all_event)编程, 不引用任何具体 B 类。
#
# 与标准模式的区别(本项目变体):
# 观察列表与广播分发统一交给中心调度(CommunicationObject)管理,
# 被观察者 A 连"列表里有哪些 B"都不需要维护, 模块间解耦更彻底,
# 且通知是否切主线程(PyQt UI)由中心调度统一处理。
#
# 本文件不 import 调度器(避免循环依赖), 调度器由 register_module 时注入。


class Observer(object):
    """
    观察者基类(所有业务模块的父类)
    ==============================
    子类必须覆写 all_event(event, content, ...) 处理收到的事件;
    UI 模块覆写 require_main_thread() 返回 True(UI 控件只能在主线程操作)。
    """

    def __init__(self, name: str = None):
        """
        初始化观察者
        :param name: 模块名<str>, 默认取类名(通信寻址/日志用)
        """
        self.name = name if name else self.__class__.__name__

        # 中心调度引用(register_module 时由调度器注入, 注册/通知都委托给它)
        self._scheduler = None

    # ============================================================
    # 注册观察关系(本模块作为"被观察者")
    # ============================================================
    def add_observer(self, observer, event=None):
        """
        注册观察者: 让 observer 观察本模块的 event 事件
        (登记到中心调度, 本模块不需要维护任何列表)
        :param observer: 观察者实例<Observer>
        :param event: 事件名<str>, None=观察本模块的全部事件
        :return: None
        """
        if self._scheduler is not None:
            self._scheduler.add_observer(self, observer, event)
        else:
            print(f"[Observer:{self.name}] add_observer 失败: 未注入中心调度(模块未注册)")

    def remove_observer(self, observer, event=None):
        """
        移除观察者(取消观察关系)
        :param observer: 观察者实例<Observer>
        :param event: 事件名<str>, None=从本模块全部事件中移除
        :return: None
        """
        if self._scheduler is not None:
            self._scheduler.remove_observer(self, observer, event)

    # ============================================================
    # 观察者视角注册(本模块作为"观察者"主动观察其他模块)
    # ============================================================
    def observe(self, target, event=None):
        """
        观察目标模块: 订阅其 event 事件(经中心调度登记, 不需要目标模块的引用)
        对应标准观察者模式的注册步骤: B 主动绑定 A, 但 A 无需知道 B 的存在。
        :param target: 被观察模块(模块名<str> 或 Observer 实例)
        :param event: 事件名<str>, None=观察其全部事件
        :return: None
        """
        if self._scheduler is not None:
            self._scheduler.add_observer(target, self, event)
        else:
            print(f"[Observer:{self.name}] observe 失败: 未注入中心调度(模块未注册)")

    def unobserve(self, target, event=None):
        """
        取消观察目标模块
        :param target: 被观察模块(模块名<str> 或 Observer 实例)
        :param event: 事件名<str>, None=取消其全部事件
        :return: None
        """
        if self._scheduler is not None:
            self._scheduler.remove_observer(target, self, event)

    # ============================================================
    # 主动回调(本模块动作完成, 通知观察者)
    # ============================================================
    def notify_observer(self, event, content=None, *args, **kwargs):
        """
        动作完成后主动回调: 通知所有观察本模块该事件的模块
        (经中心调度查表分发, 本模块不知道也不关心观察者是谁)
        :param event: 事件名<str>
        :param content: 事件内容(任意对象, 建议 dict 结构化)
        :return: None
        """
        if self._scheduler is not None:
            self._scheduler.notify_observer(self, event, content, *args, **kwargs)
        else:
            print(f"[Observer:{self.name}] notify_observer 失败: 未注入中心调度(模块未注册)")

    # ============================================================
    # 观察者入口(本模块作为"观察者"收到他人通知)
    # ============================================================
    def all_event(self, event, content, *args, **kwargs):
        """
        收到通知的统一入口(子类必须覆写, 内部按 event 分发处理)
        :param event: 事件名<str>
        :param content: 事件内容(任意对象)
        :return: None
        """
        pass

    # ============================================================
    # 线程相关钩子(由中心调度在投递时判断)
    # ============================================================
    def require_main_thread(self) -> bool:
        """
        是否必须在主线程接收通知
        默认 False(普通模块在任意线程处理);
        PyQt UI 模块覆写返回 True(UI 控件只能在主线程操作)。
        :return: bool
        """
        return False

    # ============================================================
    # 调度器注入(由 CommunicationObject.register_module 调用)
    # ============================================================
    def set_scheduler(self, scheduler):
        """
        注入中心调度引用(注册时由调度器调用, 注销时传 None)
        :param scheduler: CommunicationObject 实例 或 None
        :return: None
        """
        self._scheduler = scheduler
