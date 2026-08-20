# Bug: 注册用户名长度约束不一致导致 2 字符用户名注册失败

**日期**: 2026-08-19
**版本**: v0.2A
**优先级**: 高

## 现象
1. 注册用户名 `LF`（2 字符）失败，报错：

```
[ERROR] [DATABASE] 数据库INSERT失败: CHECK constraint failed: LENGTH(username) BETWEEN 3 AND 50
[ERROR] [AUTH] 注册失败: 数据库写入失败, username=LF, reason=错误：CHECK constraint failed: LENGTH(username) BETWEEN 3 AND 50
```

2. 紧随其后出现连锁异常：`[LogSystem] 数据库日志写入失败!` 和客户端 `注册请求超时`。

## 根因
- 数据库 `users` 表的 `username` 列 CHECK 约束为 `LENGTH(username) BETWEEN 3 AND 50`，
  而业务层 `enrollSystem.py` 中 `USERNAME_MIN_LEN=1 / USERNAME_MAX_LEN=10`，
  UI 提示文案也是“1-10 字符”。业务层允许 2 字符用户名，但数据库 CHECK 要求 ≥3，
  导致通过业务层校验后仍在 INSERT 时被数据库拦截。
- `database.py` 的 `__buildInsertSQL` 在 INSERT 失败时未 `rollback()`，
  未结束的事务残留写锁，导致服务端日志管理器（另一连接写 `system_logs` 表）写入失败。

## 修复
- `Server/UserSystem/database.py`：`users` 表 `username` 列 CHECK 约束
  由 `BETWEEN 3 AND 50` 改为 `BETWEEN 1 AND 10`（与业务层/UI 统一）。
- `Server/UserSystem/database.py`：`__buildInsertSQL` 的异常分支增加
  `self.db_conn.rollback()`，释放失败事务的写锁。
- 删除旧 `DataBase/users.db`（SQLite 的 `CREATE TABLE IF NOT EXISTS` 不会修改已存在表的约束），
  下次启动自动按新约束重建。

## 验证
- 2 字符用户名 `LF` 注册返回 `code=200` 注册成功,随后登录返回 `code=200`
  用户名 `LF`,不再出现“数据库日志写入失败”与“请求超时”。
- 运行 `client/SocketModule/runTest.py` 全链路测试,18 项全部通过,无回归。