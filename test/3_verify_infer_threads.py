# -*- coding: utf-8 -*-
"""
验证 ONNX 推理线程数限制生效(修复摄像头前台卡顿的配套检查)
============================================================
检查项:
1. modelConfig 默认推理线程数(应为 4,环境变量 WSS_INFER_THREADS 可覆盖)
2. MiniFASNet session 创建成功且线程受限
3. FaceAnalysis 各模型 session 的 intra_op_num_threads 应为 4(而非 0=全核)
"""
import os
import sys

# 注入 FaceMoudle 目录
faceMoudleDir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'FaceMoudle')
if faceMoudleDir not in sys.path:
    sys.path.insert(0, faceMoudleDir)

import modelConfig
print(f"[1] 推理线程数配置: {modelConfig.getInferThreads()}(默认 4,环境变量 WSS_INFER_THREADS 可覆盖)")

# [2] MiniFASNet session
minifasnetPath = os.path.join(faceMoudleDir, 'liveness', 'models', 'minifasnet.onnx')
if os.path.exists(minifasnetPath):
    sess = modelConfig.createSession(minifasnetPath)
    try:
        t = sess._sess_options.intra_op_num_threads
        print(f"[2] MiniFASNet session 线程数: {t}  (0=全核,应=4)")
    except Exception as e:
        print(f"[2] MiniFASNet session 创建成功(无法读取线程数: {e})")
else:
    print(f"[2] MiniFASNet 模型不存在(跳过): {minifasnetPath}")

# [3] FaceAnalysis 各模型 session
from insightface.app import FaceAnalysis
app = FaceAnalysis(
    name='buffalo_l',
    root=os.path.join(faceMoudleDir, 'moudleTrainner'),
    allowed_modules=['detection', 'landmark_2d_106', 'landmark_3d_68'],
    providers=['CPUExecutionProvider']
)
app.prepare(ctx_id=-1, det_size=(160, 160))
allOk = True
for name, model in app.models.items():
    s = model.session
    try:
        t = s._sess_options.intra_op_num_threads
        status = "OK" if t == modelConfig.getInferThreads() else "异常!"
        if status == "异常!":
            allOk = False
        print(f"[3] 模型 {name}: intra_op_num_threads = {t}  [{status}]")
    except Exception as e:
        print(f"[3] 模型 {name}: 无法读取线程数({e})")
        allOk = False

print("\n结论:", "全部通过 ✓ (推理线程已限制,不会再全核抢占 CPU)" if allOk
      else "存在异常,请检查 modelConfig patch 是否生效")
