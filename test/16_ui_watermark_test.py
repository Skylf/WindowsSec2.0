# -*- coding: utf-8 -*-
"""
UI 视频去水印接线验证(离屏模式)
================================
验证端到端链路: 去水印页按钮 → UiRsp → 中心调度 → WatermarkModule(后台线程)
              → WATERMARK_PROGRESS/RESULT/BUSY 事件 → 主线程 → 页面更新
覆盖: 页面装配 / 开始处理 / 进度显示 / 结果输出 / 取消
"""
import os
import sys
import time
import tempfile

# 离屏渲染
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
centerDir = os.path.join(projectRoot, 'CenterMoudle')
wmDir = os.path.join(projectRoot, 'WatermarkMoudle')
uiDir = os.path.join(projectRoot, 'UI', 'FaceModuleUI')
for d in [centerDir, wmDir, uiDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from PyQt6.QtWidgets import QApplication

from communicationObject import CommunicationObject
from watermarkModule import WatermarkModule
from UI_object import UiRsp
from UI import MainWindow
from threadBridge import QtMainThreadBridge

import cv2
import numpy as np


def pump(app, seconds=3.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def makeVideo(path, frames=60, size=(320, 240)):
    """合成视频: 随机背景 + 固定水印矩形"""
    w, h = size
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), 25.0, (w, h))
    for i in range(frames):
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        frame[30:70, 200:280] = (200, 30, 30)   # 红色水印
        writer.write(frame)
    writer.release()


def waitResult(app, page, timeout=60.0):
    """等待处理结果(状态标签出现 完成/失败/取消)"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        text = page.status_label.text()
        if any(k in text for k in ("完成", "失败", "已取消")):
            return text
        time.sleep(0.02)
    return page.status_label.text()


def main():
    app = QApplication(sys.argv)
    tmp = tempfile.mkdtemp(prefix="wm_ui_")
    print("=" * 60)

    print("[1] 装配: 中心调度 + Qt桥 + WatermarkModule + UiRsp + MainWindow")
    comm = CommunicationObject()
    comm.set_main_thread_dispatcher(QtMainThreadBridge())
    wm_mod = WatermarkModule()
    uiRsp = UiRsp()
    win = MainWindow(uiRsp)
    comm.register_module(wm_mod)
    comm.register_module(uiRsp)
    uiRsp.observe("watermarkModule")
    win.show()
    print("  ✓ 装配完成")

    print("[2] 去水印页: 控件装配")
    win.switch_page("watermark")
    pump(app, 0.5)
    page = win.get_page("watermark")
    assert page is not None, "应存在去水印页"
    assert page.progress_bar is not None and page.result_text is not None
    assert page.start_btn.text() == "开始处理"
    assert page.cancel_btn.text() == "取消"
    assert page.mode_combo.currentData() == "static"
    assert page.quality_combo.currentData() == "fast"
    assert page.gpu_combo.currentData() == "auto"
    assert page.cancel_btn.isEnabled() is False, "初始应不可取消"
    print("  ✓ 页面控件装配正常(static/fast/auto 默认值)")

    print("[3] 开始处理 → 进度事件回 UI")
    video = os.path.join(tmp, "demo.mp4")
    makeVideo(video, frames=300, size=(960, 540))
    page.input_edit.setText(video)
    page.start_btn.click()
    # 等待进入处理中状态(中等视频处理耗时 >1s, 可观察到 busy)
    deadline = time.time() + 8.0
    while time.time() < deadline:
        app.processEvents()
        if page.cancel_btn.isEnabled():
            break
        time.sleep(0.02)
    assert page.cancel_btn.isEnabled(), "处理中应可取消"
    assert page.start_btn.isEnabled() is False, "处理中开始按钮应禁用"
    print(f"  ✓ 处理中状态正确(开始禁用/取消可用)")

    print("[4] 等待处理结果 → 结果文本 + 输出文件")
    final_status = waitResult(app, page)
    assert "处理完成" in final_status, f"应处理完成: {final_status}"
    text = page.result_text.toPlainText()
    assert "demo_nowm.mp4" in text, f"结果应含输出文件名: {text}"
    assert "水印区域" in text, f"结果应含水印区域: {text}"
    out_path = os.path.join(tmp, "demo_nowm.mp4")
    assert os.path.isfile(out_path), "输出视频应存在"
    assert page.start_btn.isEnabled(), "完成后开始按钮应恢复"
    print(f"  ✓ 处理完成 → 输出文件存在: {out_path}")

    print("[5] 取消处理")
    big_video = os.path.join(tmp, "big.mp4")
    makeVideo(big_video, frames=600, size=(1280, 720))
    page.input_edit.setText(big_video)
    page.output_edit.setText(os.path.join(tmp, "big_out.mp4"))
    page.start_btn.click()
    pump(app, 1.5)          # 留出处理时间(大视频)
    page.cancel_btn.click()
    final_status = waitResult(app, page, timeout=30.0)
    assert "已取消" in final_status, f"应显示已取消: {final_status}"
    assert not os.path.isfile(os.path.join(tmp, "big_out.mp4")), \
        "取消时应删除不完整输出"
    assert page.start_btn.isEnabled(), "取消后开始按钮应恢复"
    print(f"  ✓ 取消成功(不完整输出已清理)")

    print("\n=== UI 视频去水印接线验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
