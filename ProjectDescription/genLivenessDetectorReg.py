# -*- coding: utf-8 -*-
"""
函数名注册表生成脚本(livenessDetector.py)
==========================================
将 livenessDetector.py 中所有函数/方法/类/常量登记到
ProjectDescription/FunctionNameReg_livenessDetector.xlsx
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
xlsxPath = os.path.join(xlsxDir, "FunctionNameReg_livenessDetector.xlsx")

# 创建工作簿
wb = Workbook()
ws = wb.active
ws.title = "livenessDetector.py 函数注册表"

# 表头
headers = ["函数名/类名", "类型", "参数", "返回值", "函数意义", "位置", "记录/修改时间", "其他"]
ws.append(headers)

# 当前时间
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 文件相对路径
fileRelPath = "FaceMoudle/liveness/livenessDetector.py"

# 函数登记数据(行号与 livenessDetector.py 当前实际一致)
records = [
    # ── 模块级常量 ──
    ("LEFT_EYE_INDICES", "常量", "无", "list<int>",
     "左眼 EAR 关键点索引(106 关键点官方定义)",
     f"({fileRelPath})[LEFT_EYE_INDICES:35]", now, "模块级常量"),
    ("RIGHT_EYE_INDICES", "常量", "无", "list<int>",
     "右眼 EAR 关键点索引(106 关键点官方定义)",
     f"({fileRelPath})[RIGHT_EYE_INDICES:38]", now, "模块级常量"),
    ("MOUTH_INDICES", "常量", "无", "list<int>",
     "嘴部外轮廓 20 点索引(52~71)",
     f"({fileRelPath})[MOUTH_INDICES:41]", now, "模块级常量"),
    ("THRESHOLD_YAW_LEFT", "常量", "无", "float<-15.0>",
     "左转动作相对基准 yaw 偏移阈值(度)",
     f"({fileRelPath})[THRESHOLD_YAW_LEFT:48]", now, "模块级常量"),
    ("THRESHOLD_YAW_RIGHT", "常量", "无", "float<15.0>",
     "右转动作相对基准 yaw 偏移阈值(度)",
     f"({fileRelPath})[THRESHOLD_YAW_RIGHT:49]", now, "模块级常量"),
    ("THRESHOLD_PITCH_UP", "常量", "无", "float<10.0>",
     "抬头动作相对基准 pitch 偏移阈值(度)",
     f"({fileRelPath})[THRESHOLD_PITCH_UP:50]", now, "模块级常量"),
    ("THRESHOLD_EAR_DROP", "常量", "无", "float<0.2>",
     "眨眼动作眼睛灰度标准差相对下降阈值(20%)",
     f"({fileRelPath})[THRESHOLD_EAR_DROP:53]", now, "模块级常量"),
    ("THRESHOLD_MAR_OPEN", "常量", "无", "float<0.4>",
     "张嘴动作嘴部纵横比阈值",
     f"({fileRelPath})[THRESHOLD_MAR_OPEN:54]", now, "模块级常量"),
    ("ACTION_SEQUENCE", "常量", "无", "list<str>",
     "动作序列(左转/右转/抬头/眨眼/张嘴)",
     f"({fileRelPath})[ACTION_SEQUENCE:57]", now, "模块级常量"),
    ("ACTION_TIMEOUT", "常量", "无", "float<15.0>",
     "单个动作超时时间(秒),避免用户来不及做动作被判失败",
     f"({fileRelPath})[ACTION_TIMEOUT:60]", now, "模块级常量"),
    ("BASELINE_DURATION", "常量", "无", "float<1.5>",
     "基准校准采集时长(秒),采集正面 Yaw/Pitch/EAR 基准",
     f"({fileRelPath})[BASELINE_DURATION:63]", now, "模块级常量"),
    ("SILENT_PASS_FRAMES", "常量", "无", "int<5>",
     "静默活体检测需连续通过的帧数",
     f"({fileRelPath})[SILENT_PASS_FRAMES:66]", now, "模块级常量"),
    ("MAX_FAIL_COUNT", "常量", "无", "int<2>",
     "动作检测累计失败次数阈值,达到则整体失败",
     f"({fileRelPath})[MAX_FAIL_COUNT:69]", now, "模块级常量"),
    ("CONTINUE_PROB_NO_FAIL", "常量", "无", "dict<int,float>",
     "无失败记录时继续下一动作的概率表(键=连续成功次数)",
     f"({fileRelPath})[CONTINUE_PROB_NO_FAIL:72]", now, "模块级常量"),
    ("CONTINUE_PROB_HAS_FAIL", "常量", "无", "dict<int,float>",
     "有失败记录时继续下一动作的概率表(键=连续成功次数)",
     f"({fileRelPath})[CONTINUE_PROB_HAS_FAIL:73]", now, "模块级常量"),
    ("FRONTAL_YAW_TOL", "常量", "无", "float<10.0>",
     "正脸采集 yaw 容差(度)",
     f"({fileRelPath})[FRONTAL_YAW_TOL:76]", now, "模块级常量"),
    ("FRONTAL_PITCH_TOL", "常量", "无", "float<8.0>",
     "正脸采集 pitch 容差(度)",
     f"({fileRelPath})[FRONTAL_PITCH_TOL:77]", now, "模块级常量"),
    ("SKIP_FRAME_INTERVAL", "常量", "无", "int<3>",
     "跳帧间隔(每 N 帧送一帧给子线程推理,降低 CPU 负担)",
     f"({fileRelPath})[SKIP_FRAME_INTERVAL:80]", now, "模块级常量"),
    ("DISPLAY_INTERVAL", "常量", "无", "int<2>",
     "显示节流(每 N 帧才更新一次 imshow,降低 HighGUI 消息泵压力)",
     f"({fileRelPath})[DISPLAY_INTERVAL:83]", now, "模块级常量"),
    ("DISPLAY_MAX_WIDTH", "常量", "无", "int<640>",
     "显示/推理帧最大宽度(像素),统一缩小高分辨率摄像头帧降低前台重绘/推理开销",
     f"({fileRelPath})[DISPLAY_MAX_WIDTH:88]", now, "模块级常量"),

    # ── 模块级函数 ──
    ("getProjectRoot", "函数", "无", "str<项目根目录绝对路径>",
     "获取项目根目录(livenessDetector.py 上三级)",
     f"({fileRelPath})[getProjectRoot:94]", now, "工具函数"),
    ("getModelRoot", "函数", "无", "str<模型根目录绝对路径>",
     "获取 InsightFace 模型根目录(FaceMoudle/moudleTrainner)",
     f"({fileRelPath})[getModelRoot:103]", now, "工具函数"),
    ("shrinkFrame", "函数", "frame<np.ndarray>, maxWidth<int=640>", "np.ndarray",
     "按宽度等比例缩小摄像头帧,降低前台重绘/拷贝/推理预处理开销",
     f"({fileRelPath})[shrinkFrame:111]", now, "性能优化工具函数"),

    # ── 类 ──
    ("LivenessDetector", "类", "useSilent<bool=True>", "无",
     "活体检测器(多层防御:第一层静默检测 + 第二层自适应动作检测)",
     f"({fileRelPath})[LivenessDetector:131]", now, "核心类"),

    # ── 类方法 ──
    ("__init__", "方法", "useSilent<bool=True>", "None",
     "初始化检测器:加载轻量模型(detection+landmark_2d_106+3d_68)与静默检测器",
     f"({fileRelPath})[LivenessDetector->__init__:144]", now, "构造方法"),
    ("getFullApp", "方法", "无", "FaceAnalysis<完整识别模型>",
     "懒加载完整 FaceAnalysis(检测+识别),仅动作通过后用于特征提取",
     f"({fileRelPath})[LivenessDetector->getFullApp:173]", now, "性能优化:懒加载"),
    ("computeEAR", "方法", "landmarks<np.ndarray>, eyeIndices<list<int>>", "float",
     "计算眼睛纵横比(EAR),眨眼时上下眼睑距离减小 EAR 下降",
     f"({fileRelPath})[LivenessDetector->computeEAR:191]", now, ""),
    ("computeMAR", "方法", "landmarks<np.ndarray>", "float",
     "计算嘴部纵横比(MAR),张嘴时增大",
     f"({fileRelPath})[LivenessDetector->computeMAR:211]", now, ""),
    ("_getPose", "方法", "face<Face>", "tuple<float,float,float>",
     "获取头部姿态(pitch,yaw,roll),优先用 InsightFace 自带 face.pose",
     f"({fileRelPath})[LivenessDetector->_getPose:230]", now, ""),
    ("_getEyeGrayStd", "方法", "frame<np.ndarray>, face<Face>", "float 或 None",
     "计算双眼区域灰度标准差(睁眼大闭眼小),替代 landmark EAR 做眨眼检测",
     f"({fileRelPath})[LivenessDetector->_getEyeGrayStd:243]", now, ""),
    ("checkActionWithFaces", "方法", "faces<list>, frame<np.ndarray>, actionName<str>",
     "tuple<bool,float,str>",
     "基于已检测到的人脸对象做动作判定(相对基准偏移,不重复推理)",
     f"({fileRelPath})[LivenessDetector->checkActionWithFaces:276]", now, ""),
    ("checkAction", "方法", "frame<np.ndarray>, actionName<str>", "tuple<bool,float>",
     "单线程动作判定(先检测人脸再复用 checkActionWithFaces)",
     f"({fileRelPath})[LivenessDetector->checkAction:341]", now, ""),
    ("_putText", "方法", "frame<np.ndarray>, text<str>, org<tuple>, color<tuple>", "None",
     "在画面上叠加文字提示",
     f"({fileRelPath})[LivenessDetector->_putText:352]", now, "显示辅助"),
    ("_runDetectLoop", "方法",
     "cap<VideoCapture>, inferFunc<function>, onResult<function>, timeout<float>, overlayFunc<function=None>",
     "dict<state>",
     "通用子线程推理+主线程显示循环,解决主线程推理阻塞消息泵导致前台窗口卡顿",
     f"({fileRelPath})[LivenessDetector->_runDetectLoop:356]", now, "性能优化核心"),
    ("calibrateBaseline", "方法", "cap<VideoCapture>", "bool",
     "采集正面姿态基准(相对偏移判定需要基准),用中位数消除系统偏差",
     f"({fileRelPath})[LivenessDetector->calibrateBaseline:461]", now, ""),
    ("runSilentCheck", "方法", "cap<VideoCapture>", "dict<{passed,avgLogitDiff}>",
     "静默活体检测阶段(第一层防御),连续多帧判定真人/攻击",
     f"({fileRelPath})[LivenessDetector->runSilentCheck:513]", now, ""),
    ("_detectSingleAction", "方法", "cap<VideoCapture>, action<str>", "tuple<bool,bool>",
     "检测单个动作(复用 _runDetectLoop 架构)",
     f"({fileRelPath})[LivenessDetector->_detectSingleAction:564]", now, ""),
    ("runAdaptiveActions", "方法", "cap<VideoCapture>", "tuple<bool,bool>",
     "自适应主动动作检测(第二层防御):随机动作+概率递推+累计失败计数",
     f"({fileRelPath})[LivenessDetector->runAdaptiveActions:601]", now, ""),
    ("runLivenessCheck", "方法", "cap<VideoCapture>, collectFrontal<bool=True>", "dict",
     "执行完整活体检测流程(静默+自适应动作+正脸采集)",
     f"({fileRelPath})[LivenessDetector->runLivenessCheck:654]", now, "对外主入口"),
    ("_collectFrontalFrame", "方法", "cap<VideoCapture>, timeout<float=5.0>",
     "np.ndarray 或 None",
     "采集一帧正面人脸(动作通过后调用,用于身份识别)",
     f"({fileRelPath})[LivenessDetector->_collectFrontalFrame:696]", now, ""),
]

# 写入数据
for record in records:
    ws.append(record)

# 设置列宽
column_widths = [24, 8, 40, 40, 55, 52, 20, 28]
for i, width in enumerate(column_widths, 1):
    ws.column_dimensions[chr(64 + i)].width = width

# 保存
wb.save(xlsxPath)
print(f"函数注册表已更新: {xlsxPath}")
print(f"共登记 {len(records)} 个条目")
