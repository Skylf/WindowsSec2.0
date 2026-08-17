# Windows 安全系统 2.0 — 项目描述（供 Codex / AI Agent 使用）

> 面向 AI 开发助手的最新项目快照：技术栈、架构、模块职责、事件协议、测试方式、
> 已知坑与下一步建议。改动代码前请先读本文件 + 对应模块 docstring。

---

## 1. 项目概览

一个基于 **人脸识别 + 活体检测** 的 Windows 安全系统原型（PyQt6 桌面控制面板）。
当前已实现四个业务模块并全部接入 UI，中介者架构统一调度：

- **FaceMoudle**：人脸录入 → 特征提取 → 识别，双层活体检测（静默 MiniFASNet + 5 个主动动作：左转/右转/抬头/眨眼/张嘴），相似度阈值 0.85
- **BsodMoudle**：蓝屏识别（事件日志 BugCheck 1001 解析，兼容新旧 WER 格式），26 个蓝屏码知识库，报告弹窗，开机自启动检查，AI 分析接口预留
- **FreezeMoudle**：卡死检测（9 维度：CPU/单进程 CPU/内存/交换分区/磁盘繁忙/磁盘满/进程风暴/UI 无响应/系统卡顿），误报抑制（连续确认/冷却/恢复清零），配套 6 种故障模拟器
- **WatermarkMoudle**：视频去水印（静态/动态水印检测 + 像素级无痕修复，fast OpenCV / 高清 LaMa ONNX 双引擎，GPU 加速），本地离线
- **CenterMoudle**：中介者调度核心 + 各模块的系统级封装（securityModule / freezeModule / watermarkModule）
- **UI（FaceModuleUI）**：PyQt6 控制面板"Windows 安全系统 2.0 控制面板"，完全复刻设计图（深色科技风，无边框 1024x632）

Git：github.com/Skylf/WindowsSec2.0，版本标签 v0.1A~v0.6L。

---

## 2. 技术栈与依赖（.venv，Python 3.11.9）

| 项目 | 版本/说明 |
|---|---|
| Python | 3.11.9（虚拟环境 `.venv`）|
| PyQt6 | 6.11.0（注意：`Property` 已移除，用 `pyqtProperty`）|
| OpenCV | opencv-python 4.9.0 |
| NumPy | 1.26.4（**必须 <2**，InsightFace 依赖 1.x）|
| InsightFace | 1.0.1（`buffalo_l` 模型在 `FaceMoudle/moudleTrainner/models/`）|
| onnxruntime-gpu | **1.20.2**（CUDA 12.6 时代；1.27/1.28 需 CUDA 13，当前驱动 566.36 不支持）|
| NVIDIA 运行时 | pip 包：nvidia-cuda-runtime/cublas/cudnn 9.1/cufft/nvrtc/nvjitlink 12.6（免装系统 CUDA）|
| 硬件 | RTX 4060 Laptop 8GB（驱动 566.36，最高 CUDA 12.7）|
| psutil | 7.2.2（FreezeMoudle 采样用）|

GPU 注意：`onnxruntime-gpu 1.20.2` + pip 版 CUDA 12.6 DLL；`WatermarkMoudle/gpuDetector.py` 启动时自动把
site-packages 下 `nvidia/*/bin` 注入 DLL 搜索路径（PATH + os.add_dll_directory），
并用最小 Conv 会话实测 CUDA 可用性（`verifyCuda()`），实测失败才回退 CPU（防谎报）。

---

## 3. 目录结构与模块职责

```
windows安全系统2.0/
├── CenterMoudle/            # 中介者调度 + 系统级封装
│   ├── communicationObject.py   # 中介者(注册模块/事件投递/主线程桥注入)
│   ├── observerObject.py        # Observer 基类(all_event/notify_observer)
│   ├── securityModule.py        # 蓝屏检测封装(事件协议 BSOD_*)
│   ├── freezeModule.py          # 卡死监控封装(FREEZE_*)
│   ├── watermarkModule.py       # 去水印封装(WATERMARK_*)，后台线程
│   └── communicationModule.py / observerModule.py   # 早期版本(可忽略)
├── FaceMoudle/              # 人脸模块
│   ├── service/faceService.py   # 服务入口(识别/录入状态机，经调度通信)
│   ├── faceInputer/             # 录入：inputter.py / faceEnroll.py
│   ├── faceDetecter/            # 特征：faceDataGetter.py
│   ├── facialRecognition/       # 识别：recognition.py
│   ├── liveness/                # 活体：livenessDetector.py(双线程) / silentLiveness.py
│   └── modelConfig.py           # 猴子补丁限制 ONNX 线程为 4(修复 32 核抢占)
├── BsodMoudle/              # 蓝屏识别
│   ├── bsodDetector.py          # wevtutil 解析 BugCheck 1001(新旧格式) + 自启动注册
│   ├── bsodKnowledge.py         # 26 个蓝屏码知识库(含义/建议)
│   ├── bsodReporter.py          # 报告构建 + tkinter 弹窗
│   ├── aiAnalyzer.py            # AI 分析接口(预留, ai_config.json 含 key, 不进 git)
│   └── sample_bsod_events.xml   # 模拟数据
├── FreezeMoudle/            # 卡死检测
│   ├── freezeConfig.py          # json 配置(enabled/阈值/冷却/确认次数)
│   ├── freezeMonitor.py         # 9 维度采样 + 误报抑制
│   ├── freezeReporter.py
│   └── simulator/               # sim_cpu/sim_memory/sim_disk_io/sim_disk_full/
│                                # sim_process_storm/sim_ui_freeze + simulate.py 菜单
├── WatermarkMoudle/         # 视频去水印
│   ├── watermarkDetector.py     # 静态(时域中值)+半透明(时域方差)+动态(模板跟踪)
│   ├── inpainter.py             # fast(Telea) / lama(fp32 ONNX, 512 裁剪式推理)
│   ├── videoProcessor.py        # 管线: 定位→细化→统一膨胀→逐帧修复
│   ├── gpuDetector.py           # CUDA 检测/开关 auto|on|off + DLL 注入 + 实测
│   ├── watermarkConfig.py       # json 配置
│   ├── log.py                   # 分级控制台日志(WM_DEBUG=1 或 --debug)
│   └── models/                  # lama_fp32.onnx(198MB, git 忽略, 已就绪)
├── UI/FaceModuleUI/         # PyQt6 控制面板
│   ├── UI.py                    # MainWindow + 各页面(概览/识别/密码/蓝屏/卡死/去水印/
│   │                            #   账户/占位页) + WatermarkSelectDialog(手动框选)
│   ├── UI_object.py             # GUI 基类 + UiRsp(响应层, 事件分发, 状态机)
│   ├── texts.py                 # 中英文字典(string.xml 风格, get_text)
│   ├── appConfig.py             # UI 全局配置(内存; 提示音开关等)
│   ├── threadBridge.py          # QtMainThreadBridge(跨线程事件切主线程)
│   ├── userInfo.py              # 当前用户(占位 admin)
│   └── runTest.py               # 启动入口(装配调度+服务+UI)
├── discription/              # 设计文档/UI 设计图/本文件
├── docs/bug-logs/            # 历史 bug 日志(重要经验, 改动相关模块前建议读)
└── test/                     # 回归测试 5~16(用 .venv\Scripts\python.exe 运行)
```

---

## 4. 核心架构（重要，改代码前必读）

### 4.1 中介者模式（CenterMoudle）
- **模块间禁止直接通信**，一切经 `CommunicationObject`（中介者）转接：
  `module.communication_to(sender, target_name, content_dict, event_str)` → 调度调用目标模块 `all_event(event, content)`
- 模块继承 `observerObject.Observer`，`observe(target_name)` 订阅目标事件
- **Qt 主线程桥**：`scheduler.set_main_thread_dispatcher(QtMainThreadBridge())`，
  跨线程操作 QWidget 会硬崩溃（0xCFFFFFFF）——UI 模块的事件统一切主线程投递
- 装配示例见 `UI/FaceModuleUI/runTest.py`：注册 FaceService/SecurityModule/FreezeModule/WatermarkModule + UiRsp，`uiRsp.observe(...)` 订阅各模块

### 4.2 事件协议（字符串常量）
```
人脸: FACE_RECOGNIZE_REQUEST/CANCEL/PROGRESS/RESULT, FACE_ENROLL_REQUEST/CANCEL/PROGRESS/RESULT
蓝屏: BSOD_CHECK_REQUEST/BSOD_AUTOSTART_REQUEST/BSOD_AUTOSTART_STATUS_REQUEST
      → BSOD_CHECK_RESULT/BSOD_AUTOSTART_RESULT/BSOD_AUTOSTART_STATUS_RESULT, BSOD_DETECTED
卡死: FREEZE_START/STOP/STATUS/CONFIG_STATUS/SET_CONFIG_REQUEST → *_RESULT, FREEZE_ALERT
水印: WATERMARK_PROCESS/CANCEL/CONFIG_REQUEST → WATERMARK_PROGRESS{RESULT/BUSY/CONFIG_RESULT}
通用: MODULE_STATUS(调度广播模块上线/下线)
```
所有模块的 UI 更新经 UiRsp.all_event 分发 → GUI 信号(pyqtSignal) → 页面槽函数。

### 4.3 线程模型
- FaceService / WatermarkModule / SecurityModule 的后台任务都在独立线程运行，经事件+主线程桥回 UI
- WatermarkModule：单任务互斥 + threading.Event 取消；进度回调(percent, info) 每 5 帧发布

### 4.4 命名约定
函数 camelCase、变量 snake_case、类 PascalCase、常量 UPPER；日志统一走
`WatermarkMoudle/log.py`（时间戳+级别+模块标记）；UI 文案全部进 texts.py。

---

## 5. 各模块关键实现要点

### 5.1 水印（最近迭代最完整）
- **检测**：`detectWatermarkMask` 组合法一次采样(30 帧均匀分布全片)：
  - 中值法（不透明水印：与中值帧差异 < 阈值）
  - 方差法（半透明水印：`噪声底 < 时域std < 局部背景std×0.75`，局部背景用均值滤波估计）
  - 边缘先验（只保留边缘带 12% 内候选）+ 面积过滤（0.01%~15%）
- **手动框选**：UI 对话框拖拽画矩形（多选）→ 逐框细化 `refineMaskFromVideo`（方差+中值候选收紧到文字笔画）→ 并集 mask
- **修复**：
  - fast：OpenCV Telea，mask 轻度膨胀
  - lama：裁剪式 512 推理（非水印区逐像素保留）；**输入 mask 区域填充为高斯模糊背景(σ=12)而非置黑**（置黑会让模型生成偏暗内容）；输出范围自适应(0-255 vs 0-1)
  - **统一兜底**：processVideo 每帧对 mask 膨胀 5x5×2(≈12px)，消除半透明水印边缘与细化漏检的残留
- **GPU**：开关 auto/on/off + CUDA 实测验证；RTX 4060 上 LaMa 约 200-500ms/帧
- CLI：`python WatermarkMoudle/runTest.py --once 视频 --mode static --quality lama --gpu on --bbox x1,y1,x2,y2(多框分号分隔)`

### 5.2 卡死检测
`freezeMonitor.py` sampleOnce 采样 9 维度，报警经确认次数(默认2次)去重 + 冷却期 + 恢复清零；
配置 json 持久化(`FreezeMoudle/freeze_config.json`, git 忽略)；`simulator/simulate.py` 菜单驱动各故障模拟器。

### 5.3 蓝屏识别
`bsodDetector.checkLatestBugCheck(count, simulate)` 解析 wevtutil 输出：
旧格式 `BugcheckCode` 与 新 WER 格式 `param1="0x0000009f (0x..., ...)"` 都支持；
自启动注册表(开机检测)由 `--autostart` 参数安装；报告弹窗 tkinter。

### 5.4 人脸识别
录入(引导式多角度+主动活体)→ 特征提取(insightface 512 维 .npy+.json 持久化到 cache/faceData)→ 识别(静默活体+动作活体+余弦相似度)。
**注意**：识别目前仅 UI 手动触发；系统级触发（锁屏/开机自动识别）是预留目标，尚未实现。

---

## 6. 测试

回归测试 `test/5_center_moudle_test.py` ~ `test/16_ui_watermark_test.py`（12 个）：
5 中介者 / 6 UI对象 / 7 人脸服务 / 8 UI窗口 / 9 人脸录入UI / 10 蓝屏 / 11 蓝屏UI /
12 卡死 / 13 模拟器 / 14 卡死UI / 15 水印功能 / 16 水印UI(离屏 QT_QPA_PLATFORM=offscreen)。

运行方式（注意 PowerShell 编码坑）：
```
$env:PYTHONIOENCODING='utf-8'
& .venv\Scripts\python.exe test\15_watermark_test.py *> out.txt
```
全部通过后才可提交；提交消息格式 `v0.xA dev: ...`，并打注解标签 + 推送 main --tags。

---

## 7. 已知约束与坑（改动时注意）

1. **PowerShell**：`*> out.txt` 会误报退出码；`2>$null`/管道会吞错；中文路径/GBK 编码需 `$env:PYTHONIOENCODING='utf-8'`；`\"` 会破坏命令 → 用临时 .py 文件
2. **PyQt6**：跨线程操作 QWidget 硬崩溃(0xCFFFFFFF)——必须经主线程桥；`drawEllipse/drawArc` 参数要 int
3. **onnxruntime 版本锁定**：1.20.2（CUDA 12.6），别升 1.27+（需 CUDA 13）；NumPy <2
4. **模型文件**：`WatermarkMoudle/models/*.onnx`（~400MB）、`cache/`、各 `*_config.json`、`ai_config.json` 均 git 忽略，勿提交
5. **GBK 控制台**：print 中文/✓ 符号需 UTF-8 环境
6. **GPU 占用**：用户机器上 Minecraft/壁纸引擎可能占满 GPU（WDDM 时间片），推理变慢属环境问题
7. `FaceMoudle`（拼写 moudle 非 module）、`moudleTrainner` 为历史命名，勿改

---

## 8. 下一步建议（按优先级）

1. **系统级安全联动（项目核心目标）**：人脸识别成功 → 解锁/锁屏/关屏保护；
   开机自启管家 + 识别无 UI 触发（用户明确：识别触发留系统级安全，不走 UI）
2. **配置持久化**：`appConfig.py` 目前是内存配置 → 落盘 JSON/注册表（freeze/watermark 已有 json 先例）
3. **蓝屏 AI 分析接入**：`aiAnalyzer.py` 接口预留，接入 LLM 分析蓝屏原因（api key 走 ai_config.json）
4. **水印批量/队列**：多文件排队处理、任务历史
5. **UI 收尾**：安全中心/防护日志/设置占位页填充；账户系统（userInfo 占位 admin）；统一设置页
6. **打包发布**：PyInstaller 打包 exe（含模型文件处理策略）
7. **测试完善**：人脸/蓝屏模块补全自动化覆盖；CI 脚本

---

*生成时间：2026-08-17 · 对应 git HEAD：v0.6L*
