# Bug: 服务端日志数据库从未初始化,且 getRecentLogs 读取出错

**日期**: 2026-08-19
**版本**: v0.2A
**优先级**: 高

## 现象
1. 服务端日志只打印到控制台,从不写入数据库 `system_logs` 表;
2. 手动传入 dbPath 初始化后,调用 `getRecentLogs()` 报错:

```
TypeError: cannot convert dictionary update sequence element #0 to a sequence
```

## 根因
- `ServerLogSystem/logManager.py` 的 `getLogger(dbPath)` 支持传入数据库路径初始化,
  但所有服务端调用点(server/handler/database/loginSystem/enrollSystem/tokenManager)
  均写成 `getLogger()`,从未传 `dbPath`,因此 `_initDb()` 从未触发,`_dbConn` 一直为 `None`,
  数据库写入被跳过(只走控制台)。
- `_initDb()` 建立连接时未设置 `row_factory = sqlite3.Row`,
  导致 `getRecentLogs()` 中 `dict(row)` 对返回的 tuple 执行转换失败。

## 修复
- `Server/SocketModule/handler.py` 的 `HandlerRegister.__init__` 在建立业务数据库连接前,
  先用业务库路径初始化日志管理器:

```python
from ServerLogSystem.logManager import getLogger as getLogSystemLogger
getLogSystemLogger(database.DATA_BASE_PATH)
```

- `Server/ServerLogSystem/logManager.py` 的 `_initDb()` 增加
  `self._dbConn.row_factory = sqlite3.Row`(与 `database.get_connection()` 保持一致)。

## 验证
- 实例化 `HandlerRegister` 后,`get_connection` / `init_db` 的日志成功写入
  `system_logs` 表(`getLogCount()` 返回 3);
- `getRecentLogs()` / `getLogCount(level=...)` 正常返回,
  `runTest.py` 中按 `row['level_name']` / `row['category']` 取值成功。