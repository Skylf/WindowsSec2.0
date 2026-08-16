# -*- coding: utf-8 -*-
"""
BsodMoudle 包
=============
蓝屏识别模块(不依赖主控制面板 UI):
- bsodKnowledge.py  蓝屏代码知识库(代码 → 通俗解读/建议)
- bsodDetector.py   检测: 事件日志 BugCheck(1001) + 开机自启动(注册表 Run)
- bsodReporter.py   报告组装 + 轻量弹窗(tkinter)
- aiAnalyzer.py     AI 分析接口预留(api key 配置 + OpenAI 兼容骨架)
"""
