# -*- coding: utf-8 -*-
"""
函数名注册表生成脚本(inputter.py)
================================
将 inputter.py 中所有函数/常量登记到 ProjectDescription/FunctionNameReg_inputter.xlsx
按用户规范:针对不同代码文件分别创建表格
"""
import os
from openpyxl import Workbook
from datetime import datetime

# 获取项目根目录
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
xlsxDir = os.path.join(projectRoot, "ProjectDescription")
os.makedirs(xlsxDir, exist_ok=True)

# 表格路径
xlsxPath = os.path.join(xlsxDir, "FunctionNameReg_inputter.xlsx")

# 创建工作簿
wb = Workbook()
ws = wb.active
ws.title = "inputter.py 函数注册表"

# 表头
headers = ["函数名/类名", "类型", "参数", "返回值", "函数意义", "位置", "记录/修改时间", "其他"]
ws.append(headers)

# 当前时间
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 文件相对路径
fileRelPath = "FaceMoudle/faceInputer/inputter.py"

# 函数登记数据(行号 2026-08-12 定位,与 inputter.py 实际一致)
records = [
    # ── 常量 ──
    ("IMAGE_EXTENSIONS", "常量", "无", "set<{'.jpg', '.jpeg', '.png', '.bmp'}>",
     "支持的图片扩展名集合(小写)",
     f"({fileRelPath})[IMAGE_EXTENSIONS:32]", now, "模块级常量"),

    ("TARGET_CAPTURE_COUNT", "常量", "无", "int<30>",
     "摄像头批量采集的目标张数(30 张是质量与速度的最佳平衡点)",
     f"({fileRelPath})[TARGET_CAPTURE_COUNT:38]", now, "模块级常量,质量/速度平衡"),

    ("CAPTURE_SAVE_DIR", "常量", "无", "str<项目根/cache/captured_photos 绝对路径>",
     "摄像头采集的保存目录(项目根公共 cache 目录,基于 __file__ 推导,避免 cwd 依赖)",
     f"({fileRelPath})[CAPTURE_SAVE_DIR:40]", now, "模块级常量,多级路径 cache/captured_photos/,作为公共缓存目录"),

    ("DET_SIZE", "常量", "无", "tuple<(480, 480)>",
     "人脸检测尺寸,准确率优先选 480,平衡速度与精度",
     f"({fileRelPath})[DET_SIZE:42]", now, "模块级常量"),

    ("DEFAULT_MAX_WORKERS", "常量", "无", "int<4>",
     "进程池默认工作进程数",
     f"({fileRelPath})[DEFAULT_MAX_WORKERS:45]", now, "模块级常量"),

    # ── 工具函数 ──
    ("getProjectRoot", "函数", "无", "str<项目根目录绝对路径>",
     "获取项目根目录(inputter.py 上三级)",
     f"({fileRelPath})[getProjectRoot:51]", now, "工具函数"),

    ("getModelRoot", "函数", "无", "str<模型根目录绝对路径>",
     "获取 InsightFace 模型根目录(FaceMoudle/moudleTrainner)",
     f"({fileRelPath})[getModelRoot:60]", now, "工具函数"),

    ("imreadUnicode", "函数", "path<str>", "np.ndarray<BGR 图像矩阵> 或 None",
     "读取中文路径下的图片(OpenCV imread 不支持中文路径的 workaround)",
     f"({fileRelPath})[imreadUnicode:69]", now, "工具函数,np.fromfile+cv2.imdecode"),

    # ── 子进程相关 ──
    ("_APP", "变量", "无", "FaceAnalysis 或 None",
     "子进程全局模型实例,每个子进程独立持有",
     f"({fileRelPath})[_APP:84]", now, "子进程全局变量"),

    ("initWorkerProcess", "函数", "modelRoot<str>", "None",
     "子进程初始化函数,在每个子进程启动时加载一次 FaceAnalysis(只检测模块)",
     f"({fileRelPath})[initWorkerProcess:87]", now, "进程池 initializer,避免重复加载模型"),

    ("checkSingleImage", "函数", "imgPath<str>", "dict<{'path','status','msg'}>",
     "检查单张图片是否包含人脸(在子进程中执行,使用全局 _APP 实例)",
     f"({fileRelPath})[checkSingleImage:108]", now, "子进程任务函数"),

    # ── 主要功能函数 ──
    ("imgInputter", "函数", "无", "str<图片路径>",
     "从外部文件系统选择图片(测试用),弹出文件选择对话框",
     f"({fileRelPath})[imgInputter:136]", now, "主要功能函数"),

    ("openCamera", "函数", "无", "None",
     "摄像头实时批量采集照片,按 O 键开始/停止,按 ESC 退出,保存到 captured_photos/",
     f"({fileRelPath})[openCamera:154]", now, "主要功能函数"),

    ("faceCheck", "函数", "folderPath<str>, maxWorkers<int=4>", "dict<{路径: {hasFace,status,msg}}>",
     "批量预检文件夹中所有图片是否包含人脸,返回路径→结果字典,key=图片绝对路径",
     f"({fileRelPath})[faceCheck:218]", now, "主要功能函数,4 进程+只检测模型+det_size=480"),

    ("handleNoFace", "函数", "checkResultsDict<dict>", "dict<可用人脸数据集>",
     "Copy-on-Write 处理无脸图片:复制字典→删磁盘文件→从副本移除 key→返回新字典;不直接修改共用字典保证数据安全",
     f"({fileRelPath})[handleNoFace:283]", now, "主要功能函数,与 faceCheck 字典配套使用"),

    ("coverDict", "函数", "originalDict<dict>, newDict<dict>", "dict<校验通过返回 newDict,失败返回 originalDict>",
     "安全覆盖共用字典:4 重校验(类型/非空/子集关系/所有 hasFace=True),通过才覆盖,失败保持原状",
     f"({fileRelPath})[coverDict:349]", now, "主要功能函数,配合 handleNoFace 使用,一行赋值完成覆盖"),
]

# 写入数据
for record in records:
    ws.append(record)

# 设置列宽
column_widths = [25, 10, 35, 35, 55, 55, 22, 45]
for i, width in enumerate(column_widths, 1):
    ws.column_dimensions[chr(64 + i)].width = width

# 保存
wb.save(xlsxPath)
print(f"函数注册表已更新: {xlsxPath}")
print(f"共登记 {len(records)} 个条目")
