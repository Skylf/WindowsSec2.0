# -*- coding: utf-8 -*-
"""
诊断脚本:检查运行时使用的解释器、sys.path、insightface 是否可导入
不触发模型下载(只做 import 自检)
"""
import sys

print("=" * 60)
print("[诊断] Python 解释器路径:", sys.executable)
print("[诊断] Python 版本      :", sys.version)
print()
print("[诊断] sys.path 前 8 条(能反映 import 搜索顺序):")
for i, p in enumerate(sys.path[:8], 1):
    print(f"  {i}. {p}")
if len(sys.path) > 8:
    print(f"  ... 还有 {len(sys.path)-8} 条省略")
print()

# ---- 检查 insightface 导入 ----
print("-" * 60)
try:
    import insightface
    print(f"[OK] import insightface 成功, 版本={insightface.__version__}")
    print(f"[OK] insightface 文件位置: {insightface.__file__}")
except Exception as e:  # 经验:不止 ImportError,还可能是 numpy DLL 崩溃等(捕获更全)
    print(f"[FAIL] import insightface 失败: type={type(e).__name__}, msg={e}")
    sys.exit(1)

# ---- 检查子模块导入 ----
try:
    from insightface.app import FaceAnalysis
    print("[OK] from insightface.app import FaceAnalysis 成功")
except Exception as e:
    print(f"[FAIL] FaceAnalysis 导入失败: type={type(e).__name__}, msg={e}")
    sys.exit(2)

try:
    from insightface.data import get_image as ins_get_image
    print("[OK] from insightface.data import get_image 成功")
except Exception as e:
    print(f"[FAIL] ins_get_image 导入失败: type={type(e).__name__}, msg={e}")
    sys.exit(3)

print()
print("=" * 60)
print("所有 import 检查通过!下一步可以测试模型加载。")
print("提示:首次调用 FaceAnalysis().prepare() 会从 GitHub 下载模型 zip。")
print("      如果网络不通,请先离线把 buffalo_l.zip 解压到:")
print("      C:\\Users\\Administrator\\.insightface\\models\\buffalo_l\\")
