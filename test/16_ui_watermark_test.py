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
    """等待处理结果(日志区出现 处理完成/处理失败/已取消)"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        text = page.log_text.toPlainText()
        if "处理完成 |" in text or "处理失败" in text or "已取消" in text:
            return text
        time.sleep(0.02)
    return page.log_text.toPlainText()


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
    # 进度条下提示词恢复 + 日志/结果合并为同一区域
    assert page.status_label is not None, "进度条下应有提示词"
    assert "选择视频后点击" in page.status_label.text(), \
        f"初始提示词应显示: {page.status_label.text()}"
    assert page.log_text is page.result_text, "日志区与结果区应合并为同一控件"
    assert page.open_btn.isVisible() is False, "初始打开按钮应隐藏"
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
    # ETA: 处理中进度条应显示预计剩余时间(等待进度 ≥40%)
    deadline = time.time() + 10.0
    eta_seen = False
    while time.time() < deadline:
        app.processEvents()
        if "剩余" in page.progress_bar.format():
            eta_seen = True
            break
        time.sleep(0.05)
    assert eta_seen, f"进度条应显示预计剩余时间: {page.progress_bar.format()}"
    print(f"  ✓ 处理中状态正确 + ETA 显示: {page.progress_bar.format()}")

    print("[4] 等待处理结果 → 结果文本 + 输出文件")
    final_status = waitResult(app, page)
    assert "处理完成 |" in final_status, f"应处理完成: {final_status}"
    text = page.result_text.toPlainText()
    assert "demo_nowm.mp4" in text, f"结果应含输出文件名: {text}"
    assert "水印区域" in text, f"结果应含水印区域: {text}"
    out_path = os.path.join(tmp, "demo_nowm.mp4")
    assert os.path.isfile(out_path), "输出视频应存在"
    assert page.start_btn.isEnabled(), "完成后开始按钮应恢复"
    # 处理日志: 应包含启动/阶段/完成信息(带阶段标签)
    log = page.log_text.toPlainText()
    assert "任务开始" in log, f"日志应含启动信息: {log}"
    assert "[启动]" in log, f"日志应含启动阶段标签: {log}"
    assert "[处理]" in log, f"日志应含处理阶段标签: {log}"
    assert "处理完成" in log, f"日志应含完成信息: {log}"
    assert page.progress_bar.format() == "%p%", "完成后 ETA 应复位"
    # 打开保存位置按钮(成功后显示)
    assert page.open_btn.isVisible(), "成功后应显示打开保存位置按钮"
    assert page.open_btn.text() == "打开保存位置"
    print(f"  ✓ 处理完成 → 输出文件存在 + 详细日志正常({len(log.splitlines())} 行)"
          f" + 打开按钮显示")

    print("[5] 手动指定水印区域(蒙太奇/半透明水印场景的可靠路径)")
    small = os.path.join(tmp, "manual.mp4")
    makeVideo(small, frames=60)
    page.input_edit.setText(small)
    page.output_edit.setText(os.path.join(tmp, "manual_out.mp4"))
    page.bbox_edit.setText("200,30,280,70")
    page.start_btn.click()
    final_status = waitResult(app, page)
    assert "处理完成 |" in final_status, f"应处理完成: {final_status}"
    assert "手动指定水印区域" in page.result_text.toPlainText(), \
        "结果应注明手动区域"
    assert os.path.isfile(os.path.join(tmp, "manual_out.mp4"))
    # 非法格式 → 应拒绝并提示(写日志区), 不发起任务
    page.bbox_edit.setText("abc,def")
    page.start_btn.click()
    pump(app, 0.5)
    assert "格式应为" in page.log_text.toPlainText(), \
        f"非法格式应提示: {page.log_text.toPlainText()}"
    page.bbox_edit.setText("")
    print("  ✓ 手动区域处理成功 + 非法格式校验")

    print("[5b] 手动多区域(分号分隔, 并集 mask)")
    page.output_edit.setText(os.path.join(tmp, "manual_multi.mp4"))
    page.bbox_edit.setText("200,30,280,70;20,150,90,200")
    page.start_btn.click()
    final_status = waitResult(app, page)
    assert "处理完成 |" in final_status, f"应处理完成: {final_status}"
    assert "2 块" in page.result_text.toPlainText(), \
        f"结果应注明 2 块: {page.result_text.toPlainText()}"
    assert os.path.isfile(os.path.join(tmp, "manual_multi.mp4"))
    print("  ✓ 多区域处理成功(2 块并集)")

    print("[5c] 框选对话框: 视频加载 + 模拟框选 + 回填")
    from UI import WatermarkSelectDialog
    dlg = WatermarkSelectDialog(small, win)
    pump(app, 0.5)
    assert dlg._frame is not None, "对话框应加载视频帧"
    assert dlg.slider.maximum() >= 59, "进度条范围应为总帧数"
    # 模拟拖拽框选(1 个)
    dlg.begin_drag(10, 10)
    dlg.update_drag(100, 80)
    dlg.end_drag()
    assert len(dlg.rects()) == 1, "应记录 1 个框选区域"
    # 撤销
    dlg._undo_rect()
    assert len(dlg.rects()) == 0, "撤销后应为 0"
    # 框选 2 个
    dlg.begin_drag(10, 10); dlg.update_drag(60, 60); dlg.end_drag()
    dlg.begin_drag(200, 100); dlg.update_drag(300, 180); dlg.end_drag()
    assert len(dlg.rects()) == 2, "应支持多选"
    assert dlg.rectsText() == "10,10,60,60; 200,100,300,180", \
        f"回填文本错误: {dlg.rectsText()}"
    # 模拟确认 → 回填到主页面
    page.bbox_edit.setText(dlg.rectsText())
    assert "10,10,60,60" in page.bbox_edit.text()
    dlg.close()
    print("  ✓ 框选对话框: 加载/拖拽/多选/撤销/回填正常")

    print("[6] 取消处理")
    big_video = os.path.join(tmp, "big.mp4")
    makeVideo(big_video, frames=600, size=(1280, 720))
    page.input_edit.setText(big_video)
    page.output_edit.setText(os.path.join(tmp, "big_out.mp4"))
    page.bbox_edit.setText("")           # 清空残留(走自动检测, 独立于前序步骤)
    page.start_btn.click()
    pump(app, 1.5)          # 留出处理时间(大视频)
    page.cancel_btn.click()
    final_status = waitResult(app, page, timeout=30.0)
    assert "已取消" in final_status, f"应显示已取消: {final_status}"
    assert not os.path.isfile(os.path.join(tmp, "big_out.mp4")), \
        "取消时应删除不完整输出"
    assert page.start_btn.isEnabled(), "取消后开始按钮应恢复"
    assert page.open_btn.isVisible() is False, "取消后打开按钮应隐藏"
    print(f"  ✓ 取消成功(不完整输出已清理)")

    print("\n=== UI 视频去水印接线验证全部通过 ✓ ===")


if __name__ == '__main__':
    main()
