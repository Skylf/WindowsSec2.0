# -*- coding: utf-8 -*-
"""
CenterMoudle 基类自测(不依赖 PyQt/模型, 纯逻辑验证)
====================================================
按设计思路验证:
【观察者】A 观察 B → B 动作完成主动回调 → 中心调度通知 A
【通信】  A 与 B 的一切互动经中心调度转接, 不直接通信
"""
import os
import sys
import threading

# 注入 CenterMoudle 目录
centerDir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'CenterMoudle')
if centerDir not in sys.path:
    sys.path.insert(0, centerDir)

from observerObject import Observer
from communicationObject import CommunicationObject


class ModuleB(Observer):
    """被观察者: 执行动作, 完成后主动回调"""

    def __init__(self):
        super().__init__(name="moduleB")
        self.received = []

    def do_work(self):
        """模拟耗时动作完成, 主动回调观察者"""
        print("  (B) 动作完成, 主动回调观察者...")
        self.notify_observer("WORK_DONE", {"result": "success"})

    def all_event(self, event, content, *args, **kwargs):
        self.received.append((event, content))


class ModuleA(Observer):
    """观察者: 观察 B, 收到通知后动作"""

    def __init__(self):
        super().__init__(name="moduleA")
        self.received = []

    def all_event(self, event, content, *args, **kwargs):
        self.received.append((event, content))
        print(f"  (A) 收到通知: event={event}, content={content}")


class UiModule(Observer):
    """模拟 UI 模块(要求主线程接收)"""

    def __init__(self):
        super().__init__(name="ui")
        self.received = []

    def require_main_thread(self) -> bool:
        return True

    def all_event(self, event, content, *args, **kwargs):
        self.received.append((event, content))
        print(f"  (UI) 收到通知: event={event} @ {threading.current_thread().name}")


# 假的主线程投递器(模拟 Qt 信号桥: 记录投递)
dispatcher_calls = []


def fake_dispatcher(observer, event, content, args, kwargs):
    dispatcher_calls.append((observer.name, event, threading.current_thread().name))
    observer.all_event(event, content, *args, **kwargs)


def main():
    print("=" * 60)
    print("[场景 1] 观察者模式: A 观察 B, B 动作完成主动回调, 中心调度通知 A")
    comm = CommunicationObject()
    a = ModuleA()
    b = ModuleB()
    comm.register_module(a)
    comm.register_module(b)
    b.add_observer(a, event="WORK_DONE")   # A 观察 B 的 WORK_DONE
    b.do_work()                            # B 动作完成 → 主动回调
    assert len(a.received) == 1 and a.received[0][0] == "WORK_DONE"
    print(f"  ✓ A 收到 1 个通知: {a.received}")

    print("[场景 2] 事件过滤: 未注册的事件不会通知 A")
    b.notify_observer("OTHER_EVENT", {})
    assert len(a.received) == 1, "A 不应收到未订阅事件"
    print("  ✓ 未订阅事件被过滤")

    print("[场景 3] 退订后不再收到")
    b.remove_observer(a, event="WORK_DONE")
    b.do_work()
    assert len(a.received) == 1, "退订后不应再收到"
    print("  ✓ 退订生效")

    print("[场景 4] event=None 全量观察")
    b.add_observer(a)   # 观察 B 的全部事件
    b.notify_observer("EVENT_X", {})
    b.notify_observer("EVENT_Y", {})
    assert len(a.received) == 3
    print(f"  ✓ 全量观察收到全部事件, A 累计 {len(a.received)} 个")

    print("[场景 5] 中介通信: communication_to 定向(模块名)")
    a.received.clear()
    ok = comm.communication_to(a, "moduleB", {"request": "hello"}, "REQ")
    assert ok and len(b.received) == 1
    print(f"  ✓ 定向通信送达: {ok}, B 收到 {b.received}")

    print("[场景 6] 中介通信: 定向到不存在的模块 → False")
    ok = comm.communication_to(a, "notExist", {}, "X")
    assert not ok
    print(f"  ✓ 目标不存在返回 False: {ok}")

    print("[场景 7] 中介通信: 广播(to=None)")
    a.received.clear(); b.received.clear()
    comm.communication_to(a, None, {"broadcast": True}, "STATUS")
    assert len(a.received) == 1 and len(b.received) == 1
    print(f"  ✓ 广播送达全部模块: A={len(a.received)}, B={len(b.received)}")

    print("[场景 7.5] 观察者视角注册: B 只报名字观察 A, 不接触 A 实例(完全解耦)")
    a.received.clear()
    # 新模块 C: 通过 observe("moduleA") 观察 A(不需要 A 的引用)
    c = ModuleA()
    c.name = "moduleC"
    comm.register_module(c)
    c.observe("moduleA", event="WORK_DONE")   # 只传模块名字符串
    a.notify_observer("WORK_DONE", {"from": "A"})
    assert len(c.received) == 1, "C 应收到 A 的通知"
    print(f"  ✓ C 通过 observe() 收到 A 通知(全程未接触 A 实例): {c.received}")
    c.unobserve("moduleA", event="WORK_DONE")
    a.notify_observer("WORK_DONE", {})
    assert len(c.received) == 1, "取消观察后不应再收到"
    print("  ✓ unobserve 生效")

    print("[场景 8] 主线程投递: UI 模块从后台线程收通知 → 走 dispatcher")
    comm.set_main_thread_dispatcher(fake_dispatcher)
    ui = UiModule()
    comm.register_module(ui)
    b.add_observer(ui, event="WORK_DONE")
    dispatcher_calls.clear()

    def work_from_bg():
        b.do_work()   # 后台线程触发回调
    t = threading.Thread(target=work_from_bg, name="worker-thread")
    t.start()
    t.join()
    assert len(dispatcher_calls) == 1, f"UI 应走 dispatcher, 实际 {len(dispatcher_calls)}"
    print(f"  ✓ UI 通知经 dispatcher 投递: {dispatcher_calls}")

    print("[场景 9] 非主线程需求的模块从后台线程收通知 → 同步直达(不走 dispatcher)")
    dispatcher_calls.clear()
    a.received.clear()

    def notify_a_from_bg():
        b.notify_observer("EVENT_X", {"from": "bg"})
    t2 = threading.Thread(target=notify_a_from_bg, name="worker-2")
    t2.start()
    t2.join()
    assert len(dispatcher_calls) == 0, "A 不应走 dispatcher"
    assert len(a.received) == 1
    print(f"  ✓ A 同步收到(不走 dispatcher), 累计 {len(a.received)} 个")

    print("[场景 10] 未注册模块调用 add/notify → 友好警告(不崩溃)")
    orphan = ModuleB()
    orphan.add_observer(a, "X")       # 未注册 → 打印警告
    orphan.notify_observer("X", {})   # 未注册 → 打印警告
    print("  ✓ 未注册模块操作不崩溃")

    print("\n=== 中心调度基类自测全部通过 ✓ ===")


if __name__ == '__main__':
    main()
