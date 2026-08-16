"""
coding:utf-8
file: UI/FaceModuleUI/appConfig.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260815
"""

# 应用全局配置(占位数据源)
# =========================
# 界面设置项(识别阈值档位 / 人脸识别登录 / 活体检测开关等)统一存放在本模块,
# UI 控件变更时写入, 加载时读取; 未来系统级安全策略(如锁屏自动识别)
# 从此处读取配置, 与 UI 解耦。
#
# 说明: 用户系统/持久化尚未实现, 当前为内存配置; 后续可扩展为配置文件/注册表。

# 识别阈值档位: 档位名 -> 相似度阈值
THRESHOLD_LEVELS = {
    "strict": 0.85,   # 严格(安全门禁, 默认)
    "normal": 0.70,   # 普通(考勤)
    "loose": 0.55,    # 宽松(体验)
}
DEFAULT_THRESHOLD_LEVEL = "strict"

# 配置字典(内存)
_CONFIG = {
    "threshold_level": DEFAULT_THRESHOLD_LEVEL,  # 识别阈值档位
    "face_login_enabled": True,                  # 人脸识别登录开关
    "liveness_enabled": True,                    # 活体检测开关
    "watermark_sound_enabled": True,             # 视频去水印完成提示音开关
}


def get_threshold() -> float:
    """
    获取当前识别阈值(按档位)
    :return: 阈值<float>
    """
    level = _CONFIG.get("threshold_level", DEFAULT_THRESHOLD_LEVEL)
    return THRESHOLD_LEVELS.get(level, THRESHOLD_LEVELS[DEFAULT_THRESHOLD_LEVEL])


def get_threshold_level() -> str:
    """
    获取当前阈值档位名
    :return: 档位名<str>: strict/normal/loose
    """
    return _CONFIG.get("threshold_level", DEFAULT_THRESHOLD_LEVEL)


def set_threshold_level(level):
    """
    设置阈值档位
    :param level: 档位名<str>
    :return: None
    """
    if level in THRESHOLD_LEVELS:
        _CONFIG["threshold_level"] = level


def is_face_login_enabled() -> bool:
    """人脸识别登录开关是否开启"""
    return bool(_CONFIG.get("face_login_enabled", True))


def set_face_login_enabled(enabled):
    """设置人脸识别登录开关"""
    _CONFIG["face_login_enabled"] = bool(enabled)


def is_liveness_enabled() -> bool:
    """活体检测开关是否开启"""
    return bool(_CONFIG.get("liveness_enabled", True))


def set_liveness_enabled(enabled):
    """设置活体检测开关"""
    _CONFIG["liveness_enabled"] = bool(enabled)


def is_watermark_sound_enabled() -> bool:
    """视频去水印完成提示音开关是否开启"""
    return bool(_CONFIG.get("watermark_sound_enabled", True))


def set_watermark_sound_enabled(enabled):
    """设置视频去水印完成提示音开关"""
    _CONFIG["watermark_sound_enabled"] = bool(enabled)
