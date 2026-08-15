# -*- coding: utf-8 -*-
"""
FaceService 验证(不依赖摄像头/模型, mock 识别函数)
==================================================
验证: 请求→后台任务→进度/结果事件流 / 取消 / 重复请求拒绝 / 特征文件校验
"""
import glob
import os
import sys
import time
import types

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
centerDir = os.path.join(projectRoot, 'CenterMoudle')
serviceDir = os.path.join(projectRoot, 'FaceMoudle', 'service')
for d in [centerDir, serviceDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

# ---- mock recognition.runLivenessRecognize(避免真实摄像头/模型) ----
fake_recognition = types.ModuleType('recognition')


def fake_run_liveness(feature_path, threshold=0.85, progressCallback=None):
    """模拟活体识别流程: 发进度 → 耗时 → 返回成功"""
    if progressCallback:
        progressCallback("silent", "静默检测中")
    if progressCallback:
        progressCallback("action", "主动动作检测中")
    time.sleep(0.3)  # 模拟耗时操作(取消测试窗口)
    if progressCallback:
        progressCallback("recognize", "特征比对中")
    return {
        "success": True, "livenessPass": True, "step": "", "msg": "活体检测通过,识别完成",
        "recognizeResult": {"success": True, "matched": True,
                            "similarity": 0.9482, "msg": "识别成功"},
    }


fake_recognition.runLivenessRecognize = fake_run_liveness
sys.modules['recognition'] = fake_recognition

from observerObject import Observer
from communicationObject import CommunicationObject
from faceService import FaceService, EVENT_FACE_RECOGNIZE_REQUEST, EVENT_FACE_RECOGNIZE_CANCEL


class Collector(Observer):
    """模拟 UI: 观察 faceService, 收集进度/结果事件"""

    def __init__(self):
        super().__init__(name="collector")
        self.progress = []
        self.results = []

    def all_event(self, event, content, *args, **kwargs):
        if event == "FACE_RECOGNIZE_PROGRESS":
            self.progress.append(content)
        elif event == "FACE_RECOGNIZE_RESULT":
            self.results.append(content)


def find_real_npy():
    """找一个真实存在的特征文件(供路径校验通过)"""
    files = glob.glob(os.path.join(projectRoot, 'cache', 'faceData', '*.npy'))
    return files[0] if files else None


def wait_result(collector, timeout=5.0):
    """等待结果事件"""
    deadline = time.time() + timeout
    while len(collector.results) == 0 and time.time() < deadline:
        time.sleep(0.02)
    return len(collector.results) > 0


def main():
    print("=" * 60)
    comm = CommunicationObject()
    svc = FaceService()
    col = Collector()
    comm.register_module(svc)
    comm.register_module(col)
    col.observe("faceService")  # 观察服务事件

    npy_path = find_real_npy()
    assert npy_path, "cache/faceData 下应有特征文件"
    print(f"[准备] 使用真实特征文件: {os.path.basename(npy_path)}")

    print("[1] 识别请求 → 后台任务 → 进度/结果事件回流")
    comm.communication_to(col, "faceService",
                          {"featurePath": npy_path, "threshold": 0.85},
                          EVENT_FACE_RECOGNIZE_REQUEST)
    assert wait_result(col), "应收到结果事件"
    assert len(col.progress) >= 3, f"应收到至少 3 个进度, 实际 {len(col.progress)}"
    stages = [p["stage"] for p in col.progress]
    assert stages == ["silent", "action", "recognize"], f"进度阶段异常: {stages}"
    r = col.results[-1]
    assert r["success"] and r["matched"] and r["similarity"] == 0.9482 and not r["cancelled"]
    print(f"  ✓ 进度: {stages}")
    print(f"  ✓ 结果: {r}")

    print("[2] 重复请求拒绝: 任务运行中再发请求 → 收到拒绝结果")
    col.results.clear()
    comm.communication_to(col, "faceService",
                          {"featurePath": npy_path}, EVENT_FACE_RECOGNIZE_REQUEST)
    time.sleep(0.05)  # 确保任务已启动(进入 sleep 窗口)
    comm.communication_to(col, "faceService",
                          {"featurePath": npy_path}, EVENT_FACE_RECOGNIZE_REQUEST)
    assert wait_result(col), "应收到拒绝结果"
    assert col.results[-1]["msg"] == "已有识别任务进行中", f"拒绝消息异常: {col.results[-1]}"
    print(f"  ✓ 重复请求被拒绝: {col.results[-1]['msg']}")
    # 等第一个任务自然结束
    deadline = time.time() + 5
    while svc._worker is not None and svc._worker.is_running() and time.time() < deadline:
        time.sleep(0.02)

    print("[3] 取消: 任务运行中发 CANCEL → 结果 cancelled=True")
    col.results.clear()
    comm.communication_to(col, "faceService",
                          {"featurePath": npy_path}, EVENT_FACE_RECOGNIZE_REQUEST)
    time.sleep(0.05)  # 进入 sleep 窗口后取消
    comm.communication_to(col, "faceService",
                          {}, EVENT_FACE_RECOGNIZE_CANCEL)
    assert wait_result(col), "应收到取消结果"
    assert col.results[-1]["cancelled"], f"应为取消结果: {col.results[-1]}"
    print(f"  ✓ 取消生效: {col.results[-1]['msg']}")
    deadline = time.time() + 5
    while svc._worker is not None and svc._worker.is_running() and time.time() < deadline:
        time.sleep(0.02)

    print("[4] 特征文件不存在 → 失败结果")
    col.results.clear()
    comm.communication_to(col, "faceService",
                          {"featurePath": r"D:\not_exist\xx.npy"}, EVENT_FACE_RECOGNIZE_REQUEST)
    assert wait_result(col), "应收到失败结果"
    assert not col.results[-1]["success"] and "不存在" in col.results[-1]["msg"]
    print(f"  ✓ 文件校验生效: {col.results[-1]['msg']}")

    print("[5] 无任务时取消 → 忽略不崩溃")
    comm.communication_to(col, "faceService", {}, EVENT_FACE_RECOGNIZE_CANCEL)
    print("  ✓ 忽略取消请求")

    print("\n=== FaceService 验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
