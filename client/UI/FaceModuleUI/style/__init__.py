"""
coding:utf-8
file: UI/FaceModuleUI/style/__init__.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260815
lateCodedTime:20260815
"""

# 样式资源模块(QSS 样式表加载器)
# ==============================
# 样式与代码解耦合: 所有 QSS 集中在 style/main.qss,
# UI 启动时调用 load_stylesheet() 读取并应用, 修改样式无需改代码。
# 后续可扩展: 多主题(main_dark.qss / main_light.qss), 按需切换。

import os

# 样式文件路径(本文件位于 style/ 下)
STYLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.qss")

# 样式缓存(重复加载避免反复读文件)
_cache = None


def load_stylesheet(force_reload=False):
    """
    读取全局样式表(QSS)
    :param force_reload: 是否强制重新读取文件<bool>, 默认 False(用缓存)
    :return: 样式表文本<str>, 读取失败返回空字符串
    """
    global _cache
    if _cache is not None and not force_reload:
        return _cache
    try:
        with open(STYLE_FILE, 'r', encoding='utf-8') as f:
            _cache = f.read()
        return _cache
    except OSError as e:
        print(f"[style] 样式文件读取失败: {e}")
        return ""
