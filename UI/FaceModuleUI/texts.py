"""
coding:utf-8
file: UI/FaceModuleUI/texts.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260815
"""

# 文本资源模块(参考安卓 string.xml 设计)
# ======================================
# 以"空间名"对应文本内容, UI 统一经 get_text() 读取, 实现文字内容解耦合:
#   - 修改文案只需改本文件, 不涉及 UI 代码
#   - 支持多语言: 每种语言一份词典, set_language() 一键切换
#   - 支持格式化参数: get_text("overview.last_scan", "2024-01-15")
#   - 查找规则: 当前语言 → 回退中文 → 回退 key 本身(便于发现缺失项)


# 语言常量
LANG_ZH = "zh_CN"
LANG_EN = "en"

# 文本词典: {语言: {空间名: 文本}}
TEXTS = {
    LANG_ZH: {
        # ═══════════ 窗口 ═══════════
        "window.title": "Windows 安全系统 2.0 控制面板",
        "window.btn.min": "最小化",
        "window.btn.fullscreen": "全屏",
        "window.btn.close": "关闭",

        # ═══════════ 左侧导航栏(按 UI 最终效果图) ═══════════
        "nav.overview": "安全概览",
        "nav.recognition": "人脸识别",
        "nav.password": "密码管理",
        "nav.bsod": "蓝屏识别",
        "nav.freeze": "卡死检测",
        "nav.watermark": "视频去水印",
        "nav.security_center": "安全中心",
        "nav.protect_log": "防护日志",
        "nav.settings": "设置",

        # ═══════════ 用户信息(头像悬停/账户页; 数据在 userInfo.py, 此处仅文案) ═══════════
        "user.tooltip_title": "当前用户",
        "user.page_title": "账户管理",
        "user.page_hint": "用户系统建设中, 敬请期待",
        "user.back": "← 返回概览",
        "user.current": "当前用户: {0}",

        # ═══════════ 全屏摄像头画面页 ═══════════
        "live.btn.exit": "退出识别",
        "live.prompt.ready": "请正对摄像头",
        "live.prompt.loading": "正在加载中...",
        "live.prompt.processing": "正在处理中，请稍等",
        "live.prompt.success": "录入成功",

        # ═══════════ 安全概览页 ═══════════
        "overview.title": "安全概览",
        "overview.subtitle": "系统防护中，您的设备安全状态良好",
        "overview.score": "安全评分",
        "overview.last_scan": "上次扫描: {0}",
        "overview.scan_time": "2024-01-15 14:30:25",
        "overview.btn.scan": "立即扫描",
        "overview.grid.login": "人脸识别",
        "overview.grid.password": "密码管理",
        "overview.grid.bsod": "蓝屏识别",
        "overview.grid.freeze": "卡死检测",
        "overview.grid.real_time": "实时保护",
        "overview.grid.auto_update": "自动更新",
        "overview.status.enabled": "已启用",
        "overview.stat.today": "今日防护",
        "overview.stat.blocked": "威胁拦截",
        "overview.stat.optimized": "系统优化",
        "overview.stat.days": "运行天数",
        "overview.stat.today_value": "128 次",
        "overview.stat.blocked_value": "3 次",
        "overview.stat.optimized_value": "2 项",
        "overview.stat.days_value": "45 天",

        # ═══════════ 人脸识别页(识别 + 录入同页) ═══════════
        "recognition.page_title": "人脸识别",
        "recognition.tab.recognize": "人脸识别",
        "recognition.tab.enroll": "人脸录入",
        "recognition.preview_placeholder": "人脸画面区\n(占位, 待接入视频流)",
        "recognition.status.success": "识别成功",
        "recognition.status.progress": "当前阶段: {0}",
        "recognition.settings_title": "设置",
        "recognition.switch.login": "人脸识别登录",
        "recognition.switch.liveness": "活体检测",
        "recognition.threshold": "识别阈值",
        "recognition.threshold.strict": "严格 (0.85)",
        "recognition.threshold.normal": "普通 (0.70)",
        "recognition.threshold.loose": "宽松 (0.55)",
        "recognition.btn.reenroll": "重新录人脸",
        "enroll.hint": "将启动摄像头进行活体检测录入\n(静默检测 + 主动动作验证 + 人脸图像采集)",
        "enroll.btn.start": "开始录入",
        "enroll.status.idle": "等待开始录入",
        "enroll.status.success": "录入完成: {0}",
        "enroll.status.fail": "录入失败: {0}",
        "enroll.status.cancelled": "录入已取消",
        "enroll.status.not_connected": "未连接业务模块, 无法录入",
        "enroll.status.overwrite": "将覆盖当前用户 {0} 的特征, 确认后点击开始录入",
        "enroll.feature.have": "已有特征: {0}",
        "enroll.feature.none": "尚未录入特征",
        # 录入阶段名映射(进度事件 stage → 界面文字)
        "enroll.stage.liveness": "活体检测录入",
        "enroll.stage.silent": "静默检测",
        "enroll.stage.action": "动作检测",
        "enroll.stage.frontal": "正脸采集",
        "enroll.stage.capture": "正脸照片采集中",
        "enroll.stage.clean": "图片清洗",
        "enroll.stage.extract": "特征提取",
        # 识别阶段名映射
        "recognition.stage.silent": "静默检测",
        "recognition.stage.action": "动作检测",
        "recognition.stage.frontal": "正脸采集",
        "recognition.stage.recognize": "特征比对",

        # ═══════════ 密码管理页 ═══════════
        "password.title": "密码管理",
        "password.strength": "强",
        "password.percent": "95%",
        "password.range": "±9%",
        "password.check_title": "密码强度检查",
        "password.input_placeholder": "输入密码进行强度检查...",
        "password.check.len": "长度至少 8 位",
        "password.check.upper": "包含大小写字母",
        "password.check.digit": "包含数字",
        "password.check.special": "包含特殊字符",
        "password.btn.update": "更新密码",

        # ═══════════ 蓝屏识别页 ═══════════
        "bsod.title": "蓝屏识别",
        "bsod.sim_title": "你的设备遇到问题，需要重启",
        "bsod.sim_text": "我们只收集某些错误信息，然后为你重新启动。",
        "bsod.sim_progress": "— 20% 完成 —",
        "bsod.protect_title": "智能防护",
        "bsod.switch.auto_repair": "蓝屏自动修复",
        "bsod.switch.report": "错误分析上报",
        "bsod.switch.backup": "系统备份恢复",
        "bsod.btn.repair": "立即修复",
        "bsod.settings_title": "检测设置",
        "bsod.result_title": "最近蓝屏报告",
        "bsod.autostart": "开机自启动检查",
        "bsod.check.btn": "立即检测",
        "bsod.check.simulate": "模拟演示",
        "bsod.status.idle": "点击\"立即检测\"检查本机蓝屏记录",
        "bsod.status.checking": "检测中...",
        "bsod.status.none": "未检测到蓝屏记录",
        "bsod.status.found": "发现蓝屏记录, 报告已生成",
        "bsod.status.fail": "操作失败: {0}",

        # ═══════════ 卡死检测页 ═══════════
        "freeze.title": "卡死检测",
        "freeze.gauge_title": "系统状态",
        "freeze.gauge_status": "正常",
        "freeze.settings_title": "检测设置",
        "freeze.interval": "检测间隔",
        "freeze.cpu": "CPU 使用率阈值",
        "freeze.mem": "内存使用率阈值",
        "freeze.timeout": "无响应超时时间",
        "freeze.interval_30s": "30 秒",
        "freeze.interval_60s": "60 秒",
        "freeze.interval_120s": "120 秒",
        "freeze.percent_90": "90%",
        "freeze.percent_80": "80%",
        "freeze.percent_70": "70%",
        "freeze.timeout_10s": "10 秒",
        "freeze.timeout_20s": "20 秒",
        "freeze.timeout_30s": "30 秒",
        "freeze.auto_kill": "自动结束无响应程序",
        "freeze.status_title": "监控状态",
        "freeze.status.running": "监控运行中(采样间隔 {0}s)",
        "freeze.status.stopped": "监控已停止",
        "freeze.status.alert": "⚠ {0}",
        "freeze.alerts_title": "报警历史",
        "freeze.alerts_empty": "暂无报警(检测到卡死风险时会显示在这里)",
        "freeze.enabled": "检测总开关",
        "freeze.btn.start": "开始监控",
        "freeze.btn.stop": "停止监控",

        # ═══════════ 视频去水印页 ═══════════
        "watermark.title": "视频去水印",
        "watermark.settings_title": "处理设置",
        "watermark.result_title": "处理结果",
        "watermark.input": "输入视频",
        "watermark.input.placeholder": "选择需要去水印的视频文件",
        "watermark.output": "输出视频",
        "watermark.output.placeholder": "留空自动生成(输入同目录 + _nowm 后缀)",
        "watermark.btn.browse": "浏览",
        "watermark.mode": "水印类型",
        "watermark.mode.static": "静止水印(台标/角标)",
        "watermark.mode.dynamic": "动态水印(滚动/移动)",
        "watermark.quality": "修复质量",
        "watermark.quality.fast": "快速(OpenCV 算法)",
        "watermark.quality.lama": "高清(LaMa AI 模型)",
        "watermark.gpu": "GPU 加速",
        "watermark.gpu.auto": "自动(可用则用)",
        "watermark.gpu.on": "开启",
        "watermark.gpu.off": "关闭",
        "watermark.btn.start": "开始处理",
        "watermark.btn.cancel": "取消",
        "watermark.status.idle": "选择视频后点击\"开始处理\"",
        "watermark.status.processing": "处理中 {0}%: {1}",
        "watermark.status.done": "处理完成: {0}",
        "watermark.status.cancelled": "已取消",
        "watermark.status.fail": "处理失败: {0}",
        "watermark.status.busy": "已有任务在处理中",
        "watermark.result.done": "处理完成\n\n输出文件: {0}\n水印区域: {1}\n引擎: {2} | 平均帧耗时: {3}ms\n{4}",
        "watermark.result.none": "未检测到水印(已原样复制输出)",
        "watermark.result.cancelled": "任务已取消",

        # ═══════════ 占位页 ═══════════
        "placeholder.title": "功能开发中",
        "placeholder.text": "该模块即将上线, 敬请期待",
    },
    LANG_EN: {
        # ═══════════ Window ═══════════
        "window.title": "Windows Security System 2.0 Control Panel",
        "window.btn.min": "Minimize",
        "window.btn.fullscreen": "Fullscreen",
        "window.btn.close": "Close",

        # ═══════════ Navigation (per final UI design) ═══════════
        "nav.overview": "Overview",
        "nav.recognition": "Face Recognition",
        "nav.password": "Password Manager",
        "nav.bsod": "BSOD Detection",
        "nav.freeze": "Freeze Detection",
        "nav.watermark": "Watermark Removal",
        "nav.security_center": "Security Center",
        "nav.protect_log": "Protection Log",
        "nav.settings": "Settings",

        # ═══════════ User info (avatar hover / account page) ═══════════
        "user.name": "admin",
        "user.id": "ID: 1001",
        "user.role": "Role: Administrator",
        "user.tooltip_title": "Current User",
        "user.page_title": "Account",
        "user.page_hint": "User system under construction",
        "user.back": "← Back to Overview",
        "user.current": "Current User: {0}",

        # ═══════════ Live camera page ═══════════
        "live.btn.exit": "Exit",
        "live.prompt.ready": "Please face the camera",
        "live.prompt.loading": "Loading...",
        "live.prompt.processing": "Processing, please wait...",
        "live.prompt.success": "Enrollment Successful",

        # ═══════════ Overview page ═══════════
        "overview.title": "Overview",
        "overview.subtitle": "System protected, your device is secure",
        "overview.score": "Security Score",
        "overview.last_scan": "Last scan: {0}",
        "overview.scan_time": "2024-01-15 14:30:25",
        "overview.btn.scan": "Scan Now",
        "overview.grid.login": "Face Recognition",
        "overview.grid.password": "Password Manager",
        "overview.grid.bsod": "BSOD Detection",
        "overview.grid.freeze": "Freeze Detection",
        "overview.grid.real_time": "Real-time Protection",
        "overview.grid.auto_update": "Auto Update",
        "overview.status.enabled": "Enabled",
        "overview.stat.today": "Today's Protection",
        "overview.stat.blocked": "Threats Blocked",
        "overview.stat.optimized": "Optimizations",
        "overview.stat.days": "Running Days",
        "overview.stat.today_value": "128 times",
        "overview.stat.blocked_value": "3 times",
        "overview.stat.optimized_value": "2 items",
        "overview.stat.days_value": "45 days",

        # ═══════════ Face recognition page (recognize + enroll) ═══════════
        "recognition.page_title": "Face Recognition",
        "recognition.tab.recognize": "Recognize",
        "recognition.tab.enroll": "Enroll",
        "recognition.preview_placeholder": "Camera Preview\n(placeholder, video stream pending)",
        "recognition.status.success": "Recognized",
        "recognition.status.progress": "Stage: {0}",
        "recognition.settings_title": "Settings",
        "recognition.switch.login": "Face Recognition Login",
        "recognition.switch.liveness": "Liveness Detection",
        "recognition.threshold": "Threshold",
        "recognition.threshold.strict": "Strict (0.85)",
        "recognition.threshold.normal": "Normal (0.70)",
        "recognition.threshold.loose": "Loose (0.55)",
        "recognition.btn.reenroll": "Re-enroll Face",
        "enroll.hint": "Camera liveness enrollment\n(silent check + active actions + face capture)",
        "enroll.btn.start": "Start Enrollment",
        "enroll.status.idle": "Waiting to start enrollment",
        "enroll.status.success": "Enrollment done: {0}",
        "enroll.status.fail": "Enrollment failed: {0}",
        "enroll.status.cancelled": "Enrollment cancelled",
        "enroll.status.not_connected": "Business module not connected",
        "enroll.status.overwrite": "This will overwrite feature of user {0}, confirm and start",
        "enroll.feature.have": "Feature: {0}",
        "enroll.feature.none": "No feature enrolled yet",
        "enroll.stage.liveness": "Liveness enrollment",
        "enroll.stage.silent": "Silent check",
        "enroll.stage.action": "Action check",
        "enroll.stage.frontal": "Frontal capture",
        "enroll.stage.capture": "Capturing photos",
        "enroll.stage.clean": "Cleaning images",
        "enroll.stage.extract": "Extracting feature",
        "recognition.stage.silent": "Silent check",
        "recognition.stage.action": "Action check",
        "recognition.stage.frontal": "Frontal capture",
        "recognition.stage.recognize": "Comparing feature",

        # ═══════════ Password manager page ═══════════
        "password.title": "Password Manager",
        "password.strength": "Strong",
        "password.percent": "95%",
        "password.range": "±9%",
        "password.check_title": "Password Strength Check",
        "password.input_placeholder": "Type a password to check...",
        "password.check.len": "At least 8 characters",
        "password.check.upper": "Contains upper & lower case",
        "password.check.digit": "Contains digits",
        "password.check.special": "Contains special chars",
        "password.btn.update": "Update Password",

        # ═══════════ BSOD detection page ═══════════
        "bsod.title": "BSOD Detection",
        "bsod.sim_title": "Your device ran into a problem and needs to restart",
        "bsod.sim_text": "We're just collecting some error info, and then we'll restart for you.",
        "bsod.sim_progress": "— 20% complete —",
        "bsod.protect_title": "Smart Protection",
        "bsod.switch.auto_repair": "BSOD Auto Repair",
        "bsod.switch.report": "Error Report Upload",
        "bsod.switch.backup": "System Backup & Restore",
        "bsod.btn.repair": "Repair Now",
        "bsod.settings_title": "Detection Settings",
        "bsod.result_title": "Latest BSOD Report",
        "bsod.autostart": "Check on Startup",
        "bsod.check.btn": "Check Now",
        "bsod.check.simulate": "Simulate Demo",
        "bsod.status.idle": "Click \"Check Now\" to scan BSOD records",
        "bsod.status.checking": "Checking...",
        "bsod.status.none": "No BSOD record found",
        "bsod.status.found": "BSOD record found, report generated",
        "bsod.status.fail": "Operation failed: {0}",

        # ═══════════ Freeze detection page ═══════════
        "freeze.title": "Freeze Detection",
        "freeze.gauge_title": "System Status",
        "freeze.gauge_status": "Normal",
        "freeze.settings_title": "Detection Settings",
        "freeze.interval": "Check Interval",
        "freeze.cpu": "CPU Usage Threshold",
        "freeze.mem": "Memory Usage Threshold",
        "freeze.timeout": "No-response Timeout",
        "freeze.interval_30s": "30s",
        "freeze.interval_60s": "60s",
        "freeze.interval_120s": "120s",
        "freeze.percent_90": "90%",
        "freeze.percent_80": "80%",
        "freeze.percent_70": "70%",
        "freeze.timeout_10s": "10s",
        "freeze.timeout_20s": "20s",
        "freeze.timeout_30s": "30s",
        "freeze.auto_kill": "Auto-kill unresponsive programs",
        "freeze.status_title": "Monitor Status",
        "freeze.status.running": "Monitoring (interval {0}s)",
        "freeze.status.stopped": "Monitoring stopped",
        "freeze.status.alert": "⚠ {0}",
        "freeze.alerts_title": "Alert History",
        "freeze.alerts_empty": "No alerts (freeze risks will show here)",
        "freeze.enabled": "Detection Master Switch",
        "freeze.btn.start": "Start Monitor",
        "freeze.btn.stop": "Stop Monitor",

        # ═══════════ Watermark removal page ═══════════
        "watermark.title": "Watermark Removal",
        "watermark.settings_title": "Processing Settings",
        "watermark.result_title": "Result",
        "watermark.input": "Input Video",
        "watermark.input.placeholder": "Select the video file to remove watermark",
        "watermark.output": "Output Video",
        "watermark.output.placeholder": "Leave empty for auto (same dir + _nowm suffix)",
        "watermark.btn.browse": "Browse",
        "watermark.mode": "Watermark Type",
        "watermark.mode.static": "Static (logo/bug)",
        "watermark.mode.dynamic": "Dynamic (scrolling/moving)",
        "watermark.quality": "Repair Quality",
        "watermark.quality.fast": "Fast (OpenCV)",
        "watermark.quality.lama": "HD (LaMa AI model)",
        "watermark.gpu": "GPU Acceleration",
        "watermark.gpu.auto": "Auto (use when available)",
        "watermark.gpu.on": "On",
        "watermark.gpu.off": "Off",
        "watermark.btn.start": "Start",
        "watermark.btn.cancel": "Cancel",
        "watermark.status.idle": "Select a video, then click Start",
        "watermark.status.processing": "Processing {0}%: {1}",
        "watermark.status.done": "Done: {0}",
        "watermark.status.cancelled": "Cancelled",
        "watermark.status.fail": "Failed: {0}",
        "watermark.status.busy": "A task is already running",
        "watermark.result.done": "Done\n\nOutput: {0}\nWatermark region: {1}\nEngine: {2} | Avg frame time: {3}ms\n{4}",
        "watermark.result.none": "No watermark detected (copied as-is)",
        "watermark.result.cancelled": "Task cancelled",

        # ═══════════ Placeholder page ═══════════
        "placeholder.title": "Under Development",
        "placeholder.text": "This module is coming soon",
    },
}

# 当前语言(默认中文)
_current_lang = LANG_ZH


def get_text(key, *args, default=None):
    """
    按空间名获取当前语言的文本(支持 {0} 格式化参数)
    :param key: 空间名<str>, 如 "recognition.title"
    :param args: 格式化参数(可省略)
    :param default: 查找失败时的回退文本<str>, 默认 None(=回退中文, 再回退 key 本身)
    :return: 文本<str>
    """
    text = TEXTS.get(_current_lang, {}).get(key)
    if text is None:
        text = TEXTS.get(LANG_ZH, {}).get(key)
    if text is None:
        text = key if default is None else default
    if args:
        try:
            text = text.format(*args)
        except (IndexError, KeyError):
            pass  # 参数不匹配时返回未格式化文本, 不崩溃
    return text


def set_language(lang):
    """
    切换 UI 语言(需 UI 重新加载文本)
    :param lang: 语言常量<str>, 如 LANG_ZH / LANG_EN
    :return: None
    """
    global _current_lang
    if lang in TEXTS:
        _current_lang = lang
    else:
        print(f"[texts] 未支持的语言: {lang}, 保持当前语言")


def get_language():
    """
    获取当前语言
    :return: 语言常量<str>
    """
    return _current_lang
