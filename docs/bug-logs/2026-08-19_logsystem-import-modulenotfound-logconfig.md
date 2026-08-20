# Bug: 日志模块 logConfig 引入失败(ModuleNotFoundError)

**日期**: 2026-08-19
**版本**: v0.2A
**优先级**: 高

## 现象
运行日志系统测试时,执行 `from LogSystem.logManager import getLogger` 报错:

```
ModuleNotFoundError: No module named 'logConfig'
```

位于 `client/LogSystem/logManager.py`(以及 `Server/LogSystem/logManager.py`)的
`from logConfig import (...)` 一行。

## 根因
两个 `logManager.py` 顶部使用**隐式绝对导入** `from logConfig import (...)`。
当外部模块以包形式 `from LogSystem.logManager import getLogger` 引入时,
Python 只会在 `sys.path` 顶层查找 `logConfig`,而不会在同包目录内查找,
因此报 `No module named 'logConfig'`。

## 修复
把两者改为**包内相对导入**:

```python
from .logConfig import (...)
```

客户端 `client/LogSystem/logManager.py` 与服务端 `Server/LogSystem/logManager.py`
(后更名为 `ServerLogSystem/logManager.py`)同步修改。

## 验证
- `py_compile` 语法通过;
- 客户端跑 `client/LogSystem/runTest.py`:文件落盘 `client/log/client.log`,最近日志读取正常;
- 服务端跑 `Server/ServerLogSystem/runTest.py`:日志入库 `system_logs` 表,查询正常。