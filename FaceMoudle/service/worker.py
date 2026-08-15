# -*- coding: utf-8 -*-
"""
后台任务执行器(worker)
======================
通用"线程 + 取消标志"任务载体:
- 把耗时任务(摄像头采集/模型推理)放入后台线程执行, 主线程不被阻塞
- 支持取消标志(threading.Event): 任务函数内部在关键节点检查 is_cancelled 实现协作式取消
- 同一 Worker 只能同时跑一个任务(重复 start 返回 False)

典型用法(FaceService 内部):
    worker = Worker(target=task_func, args=(...))
    worker.start()          # 启动后台线程
    worker.cancel()         # 请求取消(任务内轮询 is_cancelled 退出)
    worker.is_running()     # 是否仍在运行
"""

import threading


class Worker:
    """
    后台任务执行器
    =============
    target 在后台 daemon 线程执行; 任务函数内通过 is_cancelled() 检查取消请求。
    """

    def __init__(self, target, args=(), kwargs=None):
        """
        初始化任务
        :param target: 任务函数<Callable>
        :param args: 位置参数<tuple>
        :param kwargs: 关键字参数<dict>
        """
        self._target = target
        self._args = args
        self._kwargs = kwargs if kwargs is not None else {}
        self._cancel_event = threading.Event()
        self._thread = None

    def start(self) -> bool:
        """
        启动任务(后台线程)
        :return: 是否成功启动<bool>(已有任务在运行返回 False)
        """
        if self.is_running():
            return False
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self):
        """线程入口: 执行任务函数, 异常打印不崩溃"""
        try:
            self._target(*self._args, **self._kwargs)
        except Exception as e:
            print(f"[Worker] 任务异常: {e}")

    def cancel(self):
        """
        请求取消任务(协作式: 任务函数需轮询 is_cancelled 主动退出)
        :return: None
        """
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        """
        任务是否被请求取消(任务函数内部轮询此标志)
        :return: bool
        """
        return self._cancel_event.is_set()

    def is_running(self) -> bool:
        """
        任务是否仍在运行
        :return: bool
        """
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout=None):
        """
        等待任务结束(退出流程收尾用)
        :param timeout: 超时秒数<float>, None=无限等待
        :return: None
        """
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout)
