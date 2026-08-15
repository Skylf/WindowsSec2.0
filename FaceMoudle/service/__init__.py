# -*- coding: utf-8 -*-
"""
FaceMoudle/service 包
=====================
事件驱动的业务服务层: 把 FaceMoudle 工具库包装为可经中心调度调用的服务。
- worker.py      后台任务执行器(线程 + 取消标志)
- faceService.py 人脸识别服务(识别请求/取消/进度/结果)
"""
