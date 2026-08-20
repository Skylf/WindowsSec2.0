# Bug: 客户端与服务端日志包同名导致命名空间冲突(LogSystem)

**日期**: 2026-08-19
**版本**: v0.2A
**优先级**: 高

## 现象
`main.py` 在同一进程内先后注入 `client/` 与 `Server/` 到 `sys.path`,
两者均含名为 `LogSystem` 的包。在该进程内:

```python
import LogSystem.logManager  # 始终解析为 client/LogSystem/logManager.py
```

导致服务端模块 `server.py` / `handler.py` / `database.py` / `loginSystem.py` /
`enrollSystem.py` / `tokenManager.py` 里所有 `from LogSystem.logManager import getLogger`
实际上拿到的是**客户端文件日志器**(写入 `client/log/client.log`),
而不是**服务端数据库日志器**(写入 `system_logs` 表)。服务端日志永远无法入库。

## 根因
Python 模块解析是进程级全局的;`client/` 在 `sys.path` 中排在 `Server/` 之前,
同名包 `LogSystem` 只会命中先被找到的客户端版本,服务端被覆盖。

## 修复
将服务端包重命名,消除冲突:

- 目录 `Server/LogSystem` → `Server/ServerLogSystem`;
- 上述 6 个服务端文件中的所有 `from LogSystem.` → `from ServerLogSystem.`;
- 同步更新相关注释与文件头(`file: ServerLogSystem/...`)。

客户端继续使用 `LogSystem`(文件 + 控制台),服务端使用 `ServerLogSystem`(数据库 + 控制台)。

## 验证
在同一进程内同时引入两边路径后:

```
client LogSystem         -> client\LogSystem\logManager.py
server ServerLogSystem   -> Server\ServerLogSystem\logManager.py
```

再实例化 `HandlerRegister`,确认服务端日志成功写入数据库 `system_logs` 表(入库 3 条)。