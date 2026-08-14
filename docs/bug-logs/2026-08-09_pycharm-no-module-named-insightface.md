# Bug: PyCharm 中报 No module named 'insightface'

**日期**: 2026-08-09
**版本**: v0.0.1F
**优先级**: 高

## 现象
用户在 PyCharm 里编辑并运行 `test/1.py`:
```python
import insightface
from insightface.app import FaceAnalysis
from insightface.data import get_image as ins_get_image
...
```
编辑器爆红提示"不存在模块 insightface",运行时直接报 `ModuleNotFoundError: No module named 'insightface'`。
但用项目目录下的 `.venv\Scripts\python.exe` 直接 import insightface 是成功的。

## 根因
两重原因叠加:

1. **主因(90%):PyCharm 全局 SDK 配置 `jdk.table.xml` 中,"Python 3.11 (windows安全系统2.0)"这个虚拟环境 SDK 的 `classPath` 只列了系统 Python(`C:\Users\Administrator\AppData\Local\Programs\Python\Python311\...`)的路径,**缺少了项目 .venv 自身的两条**:
   - `D:/COMPUTER/Python/windows安全系统2.0/.venv`
   - `D:/COMPUTER/Python/windows安全系统2.0/.venv/Lib/site-packages`(insightface、onnxruntime、flatbuffers 等新安装的依赖全在这里面)
   
   导致 PyCharm 编辑器索引和运行时只能看到"裸系统 Python"的包,而 insightface 只装在 venv 里,自然找不到。
   (对比其他项目 SDK,如 `连点器`、`LianDian`、`ShouCang_ZhuShou` 都同时在 classPath 中列出了 venv 根目录和 venv/site-packages)

2. **次因(可能叠加)**:右上角 Run/Debug Configuration 里有可能选中了 `Python 3.11`(系统解释器)覆盖了项目默认 SDK,即使改好了 SDK 也仍会触发"找不到模块"。

## 修复
修改了以下文件:
- [jdk.table.xml](file:///C:/Users/Administrator/AppData/Roaming/JetBrains/PyCharm2025.3/options/jdk.table.xml#L471-L506) 在 "Python 3.11 (windows安全系统2.0)" 的 classPath 中补入了两条缺失的 root(插在 pythonwin 与 python_stubs 之间):
  ```xml
  <root url="file://D:/COMPUTER/Python/windows安全系统2.0/.venv" type="simple" />
  <root url="file://D:/COMPUTER/Python/windows安全系统2.0/.venv/Lib/site-packages" type="simple" />
  ```
- 新增 [test/0_env_diag.py](file:///d:/COMPUTER/Python/windows安全系统2.0/test/0_env_diag.py) 作为可反复执行的环境诊断脚本(打印解释器路径、sys.path、import 结果、异常类型)。

## 验证
**(1) 命令行基线验证**(已通过):
在 PowerShell 执行 `.venv\Scripts\python.exe test\0_env_diag.py` 输出:
```
解释器: D:\COMPUTER\Python\windows安全系统2.0\.venv\Scripts\python.exe
insightface 1.0.1 @ .venv\Lib\site-packages\insightface\__init__.py  ← 来自 venv(正确)
FaceAnalysis、get_image 全部导入成功
```

**(2) PyCharm 侧验证**(需用户执行):
1. 关闭并重新打开 PyCharm(让 jdk.table.xml 修改生效,PyCharm 启动时才读该文件)
2. 右键 `test/0_env_diag.py` → Run,确认输出与命令行一致(解释器为 .venv\Scripts\python.exe, 且 insightface 1.0.1 导入成功)
3. 再跑 `test/1.py` 验证业务逻辑。若 Run Configuration 仍报"找不到模块",打开 Run/Debug Configurations,确认 "Python interpreter" 下拉选的是 `Python 3.11 (windows安全系统2.0)`,而不是 `Python 3.11`(后者是裸系统解释器)
