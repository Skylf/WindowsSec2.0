# -*- coding: utf-8 -*-
"""
FreezeMoudle 包
===============
全方位卡死检测模块(不依赖主控制面板 UI):
- freezeConfig.py    配置(总开关/阈值/采样与误报抑制参数, json 持久化)
- freezeMonitor.py   检测器(7 维度采样 + 连续确认/冷却期抑制误报)
- freezeReporter.py  报告组装 + 弹窗(复用蓝屏模块 tkinter 弹窗)
- runTest.py         交互菜单 + 开机自启动(--autostart 静默监控)
"""
