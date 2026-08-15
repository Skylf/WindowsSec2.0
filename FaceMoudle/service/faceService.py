# -*- coding: utf-8 -*-
"""
人脸识别服务(faceService)
=========================
把 FaceMoudle 工具库包装为"事件驱动服务", 供 UI 等模块经中心调度调用。
本模块只与中心调度通信, 不 import 任何 UI 代码。

职责:
- 订阅 FACE_RECOGNIZE_REQUEST / FACE_RECOGNIZE_CANCEL
- 收到请求后在后台线程(Worker)执行 runLivenessRecognize(摄像头+推理, 耗时)
- 执行过程发布 FACE_RECOGNIZE_PROGRESS / FACE_RECOGNIZE_RESULT 事件
- 支持协作式取消: 取消请求置标志, 进度回调处检查并中止

事件协议(与 UI_object.py 约定一致):
- 接收: FACE_RECOGNIZE_REQUEST {featurePath, threshold}
         FACE_RECOGNIZE_CANCEL   {}
- 发布: FACE_RECOGNIZE_PROGRESS {stage, detail}
         FACE_RECOGNIZE_RESULT   {success, livenessPass, matched, similarity,
                                  msg, step, cancelled}
"""

import os
import sys
import threading

# 注入 FaceMoudle 目录(本文件位于 <项目根>/FaceMoudle/service/, 上 2 级为 FaceMoudle)
_FACE_MOUDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FACE_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _FACE_MOUDLE_DIR)

# 注入 CenterMoudle 目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_FACE_MOUDLE_DIR))
_CENTER_MOUDLE_DIR = os.path.join(_PROJECT_ROOT, 'CenterMoudle')
if _CENTER_MOUDLE_DIR not in sys.path:
    sys.path.insert(0, _CENTER_MOUDLE_DIR)

from observerObject import Observer
from worker import Worker


# ====================================================================
# 事件名常量(与 UI_object.py 定义一致; 后续可统一收敛到 CenterMoudle 公共定义)
# ====================================================================
EVENT_FACE_RECOGNIZE_REQUEST = "FACE_RECOGNIZE_REQUEST"
EVENT_FACE_RECOGNIZE_CANCEL = "FACE_RECOGNIZE_CANCEL"
EVENT_FACE_RECOGNIZE_PROGRESS = "FACE_RECOGNIZE_PROGRESS"
EVENT_FACE_RECOGNIZE_RESULT = "FACE_RECOGNIZE_RESULT"
EVENT_FACE_ENROLL_REQUEST = "FACE_ENROLL_REQUEST"
EVENT_FACE_ENROLL_CANCEL = "FACE_ENROLL_CANCEL"
EVENT_FACE_ENROLL_PROGRESS = "FACE_ENROLL_PROGRESS"
EVENT_FACE_ENROLL_RESULT = "FACE_ENROLL_RESULT"

# 识别服务目标模块名(通信寻址用)
MODULE_NAME = "faceService"


class TaskCancelled(Exception):
    """任务被用户取消(内部异常, 用于中止识别流程)"""
    pass


class FaceService(Observer):
    """
    人脸识别服务(事件驱动)
    =====================
    经中心调度注册后(name="faceService")可接收识别请求。
    耗时任务在后台线程执行, 主线程/调用方永不被阻塞。

    使用方式(由流程脚本装配):
        scheduler.register_module(FaceService())
    """

    def __init__(self):
        super().__init__(name=MODULE_NAME)
        self._worker = None          # 当前识别任务 Worker
        self._cancel_event = threading.Event()  # 取消标志(与 Worker 共用)
        self._frame_listener = None  # 帧监听器(UI 内嵌摄像头画面, 请求时注入)

    # ============================================================
    # 事件接收(覆写 Observer.all_event)
    # ============================================================
    def all_event(self, event, content, *args, **kwargs):
        """
        收到中心调度投递的事件, 按事件名分发
        :param event: 事件名<str>
        :param content: 事件内容(dict)
        :return: None
        """
        if event == EVENT_FACE_RECOGNIZE_REQUEST:
            self._on_recognize_request(content)
        elif event == EVENT_FACE_RECOGNIZE_CANCEL:
            self._on_recognize_cancel()
        elif event == EVENT_FACE_ENROLL_REQUEST:
            self._on_enroll_request(content)
        elif event == EVENT_FACE_ENROLL_CANCEL:
            self._on_enroll_cancel()
        else:
            self._log(f"[未处理事件] {event}: {content}")

    # ============================================================
    # 识别请求/取消处理
    # ============================================================
    def _on_recognize_request(self, content):
        """
        收到识别请求: 校验状态 → 启动后台任务
        :param content: {"featurePath": str, "threshold": float}
        :return: None
        """
        # 已有任务在跑 → 拒绝(发布失败结果, 避免并发识别抢摄像头)
        if self._worker is not None and self._worker.is_running():
            self._log("已有识别任务进行中, 拒绝新请求")
            self._publish_result({
                "success": False, "livenessPass": False, "matched": False,
                "similarity": 0.0, "msg": "已有识别任务进行中", "step": "",
                "cancelled": False,
            })
            return

        feature_path = content.get("featurePath", "")
        threshold = float(content.get("threshold", 0.85))
        # 特征路径缺省时: 按用户名自动定位最新特征(供系统级安全策略触发识别)
        if not feature_path:
            user_name = str(content.get("userName", "")).strip()
            if user_name:
                face_detecter_dir = os.path.join(_FACE_MOUDLE_DIR, 'faceDetecter')
                if face_detecter_dir not in sys.path:
                    sys.path.insert(0, face_detecter_dir)
                from faceDataGetter import findLatestFeature
                feature_path = findLatestFeature(user_name) or ""
        if not feature_path or not os.path.exists(feature_path):
            self._log(f"特征文件不存在: {feature_path}")
            self._publish_result({
                "success": False, "livenessPass": False, "matched": False,
                "similarity": 0.0, "msg": f"特征文件不存在: {feature_path}", "step": "",
                "cancelled": False,
            })
            return

        # 启动后台任务(主线程立即返回, 不阻塞)
        self._cancel_event.clear()
        self._worker = Worker(target=self._run_recognize_task,
                              args=(feature_path, threshold))
        self._worker.start()
        self._log(f"识别任务已启动: {os.path.basename(feature_path)} (阈值 {threshold})")

    def _on_recognize_cancel(self):
        """
        收到取消请求: 置取消标志, 任务在进度回调处检查并中止
        :return: None
        """
        if self._worker is not None and self._worker.is_running():
            self._cancel_event.set()
            self._log("已请求取消当前识别任务")
        else:
            self._log("当前无识别任务, 忽略取消请求")

    # ============================================================
    # 录入请求/取消处理
    # ============================================================
    def _on_enroll_request(self, content):
        """
        收到录入请求: 校验状态 → 启动后台任务
        (识别/录入互斥: 同一时刻只有一个任务, 避免抢摄像头)
        :param content: {"userName": str}
        :return: None
        """
        if self._worker is not None and self._worker.is_running():
            self._log("已有任务进行中, 拒绝新请求")
            self._publish_enroll_result({
                "success": False, "msg": "已有任务进行中", "step": "并发校验",
                "featurePath": "", "cancelled": False,
            })
            return

        user_name = str(content.get("userName", "")).strip()
        if not user_name:
            self._log("用户名不能为空")
            self._publish_enroll_result({
                "success": False, "msg": "用户名不能为空", "step": "参数校验",
                "featurePath": "", "cancelled": False,
            })
            return

        self._cancel_event.clear()
        # 帧监听器(UI 内嵌摄像头画面用): 由请求方经 content 传入, 可为 None
        self._frame_listener = content.get("frameListener")
        self._worker = Worker(target=self._run_enroll_task, args=(user_name,))
        self._worker.start()
        self._log(f"录入任务已启动: {user_name}")

    def _on_enroll_cancel(self):
        """
        收到录入取消请求: 置取消标志, 任务在进度回调处检查并中止
        :return: None
        """
        if self._worker is not None and self._worker.is_running():
            self._cancel_event.set()
            self._log("已请求取消当前录入任务")
        else:
            self._log("当前无录入任务, 忽略取消请求")

    def _run_enroll_task(self, user_name):
        """
        后台执行录入全流程(摄像头采集 + 图片清洗 + 特征提取)
        :param user_name: 用户名<str>
        :return: None
        """
        # 进度回调包装: 检查取消标志, 已取消则抛 TaskCancelled 中止流程
        def progress(stage, detail=""):
            if self._cancel_event.is_set():
                raise TaskCancelled()
            self._publish_enroll_progress(stage, detail)

        # 帧回调包装: 检查取消 + 转发给 UI 帧监听器(如已注入)
        def frame_cb(frame, prompt=""):
            if self._cancel_event.is_set():
                raise TaskCancelled()
            if self._frame_listener is not None:
                self._frame_listener(frame, prompt)

        try:
            # 动态导入生产录入流程(faceInputer/faceEnroll.py)
            # 确保 faceInputer 目录在 sys.path(与调用方运行方式无关)
            face_inputer_dir = os.path.join(_FACE_MOUDLE_DIR, 'faceInputer')
            if face_inputer_dir not in sys.path:
                sys.path.insert(0, face_inputer_dir)
            from faceEnroll import runEnroll
            result = runEnroll(user_name, progressCallback=progress,
                               frameCallback=frame_cb)

            self._publish_enroll_result({
                "success": result.get("success", False),
                "msg": result.get("msg", ""),
                "step": result.get("step", ""),
                "featurePath": result.get("featurePath", ""),
                "cancelled": False,
            })

        except TaskCancelled:
            # 用户取消
            self._log("录入任务已取消")
            self._publish_enroll_result({
                "success": False, "msg": "用户取消", "step": "",
                "featurePath": "", "cancelled": True,
            })

        except Exception as e:
            # 未知异常: 发布失败结果(不崩溃)
            self._log(f"录入任务异常: {e}")
            self._publish_enroll_result({
                "success": False, "msg": f"录入异常: {e}", "step": "",
                "featurePath": "", "cancelled": False,
            })

        finally:
            # 任务结束: 清理帧监听器(避免引用残留)
            self._frame_listener = None

    # ============================================================
    # 后台任务(在 Worker 线程执行)
    # ============================================================
    def _run_recognize_task(self, feature_path, threshold):
        """
        后台执行活体识别流程(摄像头+推理, 耗时操作)
        :param feature_path: 特征文件路径<str>
        :param threshold: 相似度阈值<float>
        :return: None
        """
        # 进度回调包装: 检查取消标志, 已取消则抛 TaskCancelled 中止流程
        def progress(stage, detail=""):
            if self._cancel_event.is_set():
                raise TaskCancelled()
            self._publish_progress(stage, detail)

        try:
            # 动态导入识别工具库(确保 facialRecognition 目录在 sys.path, 与调用方运行方式无关)
            facial_recognition_dir = os.path.join(_FACE_MOUDLE_DIR, 'facialRecognition')
            if facial_recognition_dir not in sys.path:
                sys.path.insert(0, facial_recognition_dir)
            from recognition import runLivenessRecognize
            result = runLivenessRecognize(
                feature_path, threshold=threshold, progressCallback=progress
            )

            recognize_result = result.get("recognizeResult", {})
            self._publish_result({
                "success": result.get("success", False),
                "livenessPass": result.get("livenessPass", False),
                "matched": recognize_result.get("matched", False),
                "similarity": recognize_result.get("similarity", 0.0),
                "msg": result.get("msg", ""),
                "step": result.get("step", ""),
                "cancelled": False,
            })

        except TaskCancelled:
            # 用户取消: 发布取消结果, UI 据此回 IDLE
            self._log("识别任务已取消")
            self._publish_result({
                "success": False, "livenessPass": False, "matched": False,
                "similarity": 0.0, "msg": "用户取消", "step": "",
                "cancelled": True,
            })

        except Exception as e:
            # 未知异常: 发布失败结果(不崩溃)
            self._log(f"识别任务异常: {e}")
            self._publish_result({
                "success": False, "livenessPass": False, "matched": False,
                "similarity": 0.0, "msg": f"识别异常: {e}", "step": "",
                "cancelled": False,
            })

    # ============================================================
    # 事件发布(经中心调度通知观察者, 如 UI)
    # ============================================================
    def _publish_progress(self, stage, detail=""):
        """
        发布识别进度事件
        :param stage: 阶段名<str>: "silent"/"action"/"frontal"/"recognize"
        :param detail: 阶段明细<str>
        :return: None
        """
        if self._scheduler is not None:
            self.notify_observer(EVENT_FACE_RECOGNIZE_PROGRESS,
                                 {"stage": stage, "detail": detail})

    def _publish_result(self, payload):
        """
        发布识别结果事件
        :param payload: 结果字典<dict>
        :return: None
        """
        if self._scheduler is not None:
            self.notify_observer(EVENT_FACE_RECOGNIZE_RESULT, payload)

    def _publish_enroll_progress(self, stage, detail=""):
        """
        发布录入进度事件
        :param stage: 阶段名<str>: silent/action/frontal/capture/clean/extract
        :param detail: 阶段明细<str>
        :return: None
        """
        if self._scheduler is not None:
            self.notify_observer(EVENT_FACE_ENROLL_PROGRESS,
                                 {"stage": stage, "detail": detail})

    def _publish_enroll_result(self, payload):
        """
        发布录入结果事件
        :param payload: 结果字典<dict>
        :return: None
        """
        if self._scheduler is not None:
            self.notify_observer(EVENT_FACE_ENROLL_RESULT, payload)

    def _log(self, text):
        """日志输出"""
        print(f"[FaceService] {text}")
