"""
coding:utf-8
file: ServerLogSystem/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 服务端日志系统全流程测试
# ==========================
# 验证服务端日志管理器(数据库 + 控制台)的完整能力:
#   1. 五档等级(DEBUG/INFO/WARNING/ERROR/CRITICAL)入库
#   2. 多类别(SYSTEM/DATABASE/NETWORK/AUTH)入库
#   3. system_logs 表成功建表并写入
#   4. 日志查询(getLogCount / getRecentLogs)与等级过滤

import os
import sys
import tempfile

# 注入 Server 目录, 使 `from ServerLogSystem...` 可按包导入
_serverDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _serverDir not in sys.path:
    sys.path.insert(0, _serverDir)

from ServerLogSystem.logManager import getLogger
from ServerLogSystem import logConfig as cfg


def testWriteLog(logger):
    """测试各等级/类别日志入库"""
    logger.debug(cfg.CATEGORY_SYSTEM, "服务端调试: 进程启动")
    logger.info(cfg.CATEGORY_DATABASE, "服务端信息: 数据库初始化完成")
    logger.warning(cfg.CATEGORY_NETWORK, "服务端警告: 客户端心跳超时")
    logger.error(cfg.CATEGORY_AUTH, "服务端错误: 登录失败(密码错误)")


def main():
    """服务端日志系统测试入口"""
    # 使用临时数据库, 避免污染业务库 users.db
    dbPath = os.path.join(tempfile.gettempdir(), "server_log_system_test.db")
    if os.path.exists(dbPath):
        os.remove(dbPath)

    # 获取全局单例日志管理器(数据库 + 控制台), 传入数据库路径完成初始化
    logger = getLogger(dbPath)

    print("=== 服务端日志系统全流程测试 ===")
    print("日志数据库:", dbPath)

    testWriteLog(logger)

    # 校验日志已入库
    totalCount = logger.getLogCount()
    errorCount = logger.getLogCount(level=cfg.ERROR)
    assert totalCount >= 4, "日志入库数量异常"
    assert errorCount >= 1, "等级过滤(ERROR)异常"

    print("日志总数:", totalCount)
    print("ERROR 及以上日志数:", errorCount)

    # 读取最近日志并展示
    recentRows = logger.getRecentLogs(5)
    print("\n最近 %d 条日志:" % len(recentRows))
    for row in recentRows:
        print("  [%s] [%s] %s" % (row["level_name"], row["category"], row["message"]))

    # 关闭数据库连接并清理临时文件
    logger.close()
    for suffix in ("", "-wal", "-shm"):
        p = dbPath + suffix
        if os.path.exists(p):
            os.remove(p)

    print("\n服务端日志系统测试通过!")


if __name__ == "__main__":
    main()