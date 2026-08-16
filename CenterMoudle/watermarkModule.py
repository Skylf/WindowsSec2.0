"""
coding:utf-8
file: watermarkModule.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0
"""

# 该模块为视频去水印模块类(系统级封装, 供 UI/命令行调用)
# ==========================================================
# 水印去除核心逻辑在 WatermarkMoudle 包(功能接口层):
#   - 定位:    静态水印时域中值自动检测 / 手动指定区域; 动态水印模板匹配跟踪
#   - 修复:    fast(OpenCV) / lama(ONNX 神经网络), 像素级填充, 无痕
#   - 全程本地处理, 不上公网; GPU 开关(auto/on/off)由配置控制
# 本类负责: 后台线程执行 + 中心调度事件协议 + 取消支持 + 配置读写。
#
# 事件协议:
#   - 接收 WATERMARK_PROCESS_REQUEST {input, output, mode, quality, use_gpu,
#                                     manual_bbox, sample_frames, threshold}
#   - 接收 WATERMARK_CANCEL_REQUEST {}        请求取消当前处理
#   - 接收 WATERMARK_CONFIG_REQUEST {}        查询当前配置
#   - 发布 WATERMARK_PROGRESS {percent, info} 处理进度(后台线程)
#   - 发布 WATERMARK_RESULT {success, msg, output_path, watermark_bbox,
#                            frames, avg_ms, mode, note, cancelled}
#   - 发布 WATERMARK_CONFIG_RESULT {config}   配置查询结果
#   - 发布 WATERMARK_BUSY {busy}              处理状态变化

import os
import sys
import threading

# 注入 CenterMoudle / WatermarkMoudle 目录
_CENTER_DIR = os.path.dirname(os.path.abspath(__file__))
_WM_DIR = os.path.join(os.path.dirname(_CENTER_DIR), 'WatermarkMoudle')
for _d in (_CENTER_DIR, _WM_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from observerObject import Observer


class WatermarkModule(Observer):
    """
    视频去水印模块(系统级封装)
    ==========================
    使用方式(装配层):
        scheduler.register_module(WatermarkModule())
        scheduler.communication_to(调用方, "watermarkModule",
                                   {"input": "a.mp4"}, "WATERMARK_PROCESS_REQUEST")
    处理在后台线程执行(视频可能很长, 不阻塞主线程/调用方);
    同一时间只允许一个处理任务(互斥), 支持取消。
    """

    def __init__(self, name="watermarkModule"):
        super().__init__(name=name)
        self._lock = threading.Lock()          # 任务互斥
        self._cancel_event = threading.Event() # 取消信号
        self._worker = None                    # 当前工作线程
        self._busy = False

    # ============================================================
    # 任务执行(后台线程)
    # ============================================================
    def _do_process(self, content):
        """
        后台执行视频去水印并发布进度/结果事件
        :param content: 请求内容<dict>
        :return: None
        """
        from videoProcessor import removeWatermark
        try:
            def on_progress(percent, info):
                self._publish("WATERMARK_PROGRESS",
                              {"percent": percent, "info": info})

            result = removeWatermark(
                content.get("input", ""),
                output_path=content.get("output"),
                mode=content.get("mode", "static"),
                manual_bbox=content.get("manual_bbox"),
                quality=content.get("quality"),
                use_gpu=content.get("use_gpu"),
                progress_callback=on_progress,
                cancel_event=self._cancel_event,
            )
            self._publish("WATERMARK_RESULT", result)
        except Exception as e:   # 兜底: 任何异常都回报, 不吞掉
            import traceback
            traceback.print_exc()
            self._publish("WATERMARK_RESULT", {
                "success": False,
                "msg": f"处理异常: {e}",
                "frames": 0, "avg_ms": 0.0,
                "mode": content.get("quality", "fast"),
                "cancelled": False,
            })
        finally:
            with self._lock:
                self._busy = False
                self._worker = None
            self._publish("WATERMARK_BUSY", {"busy": False})

    def _start_process(self, content):
        """校验并启动后台处理线程(互斥, 忙时拒绝)"""
        with self._lock:
            if self._busy:
                self._publish("WATERMARK_RESULT", {
                    "success": False,
                    "msg": "已有任务在处理中, 请等待完成或取消",
                    "frames": 0, "avg_ms": 0.0,
                    "mode": content.get("quality", "fast"),
                    "cancelled": False,
                })
                return
            input_path = content.get("input", "")
            if not input_path or not os.path.isfile(input_path):
                self._publish("WATERMARK_RESULT", {
                    "success": False,
                    "msg": f"输入文件不存在: {input_path}",
                    "frames": 0, "avg_ms": 0.0,
                    "mode": content.get("quality", "fast"),
                    "cancelled": False,
                })
                return
            self._busy = True
            self._cancel_event.clear()
            self._worker = threading.Thread(target=self._do_process,
                                            args=(content,), daemon=True)
            self._worker.start()
        self._publish("WATERMARK_BUSY", {"busy": True})

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
        if event == "WATERMARK_PROCESS_REQUEST":
            self._start_process(content)

        elif event == "WATERMARK_CANCEL_REQUEST":
            # 取消当前处理(线程内每帧检查取消事件)
            self._cancel_event.set()
            self._publish("WATERMARK_PROGRESS",
                          {"percent": 0, "info": "正在取消..."})

        elif event == "WATERMARK_CONFIG_REQUEST":
            # 查询当前配置(页面初始化加载)
            import watermarkConfig
            self._publish("WATERMARK_CONFIG_RESULT",
                          {"config": watermarkConfig.load()})

        else:
            print(f"[WatermarkModule] 未处理事件: {event}: {content}")

    # ============================================================
    # 事件发布(经中心调度通知观察者, 如 UI)
    # ============================================================
    def _publish(self, event, payload):
        """发布事件(未注册调度时静默, 如独立测试)"""
        if self._scheduler is not None:
            self.notify_observer(event, payload)
