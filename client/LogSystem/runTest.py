"""
coding:utf-8
file: LogSystem/runTest.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 客户端日志系统全流程测试
# ==========================
# 验证客户端日志管理器(文件 + 控制台)的完整能力:
#   1. 五档等级(DEBUG/INFO/WARNING/ERROR/CRITICAL)输出
#   2. 多类别(SYSTEM/NETWORK/AUTH/FILE/UI/SECURITY)输出
#   3. 日志文件成功落盘(client/log/client.log)
#   4. 最近日志读取(getRecentLogs)

import os
import sys

# 注入 client 目录, 使 `from LogSystem...` 可按包导入
_clientDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _clientDir not in sys.path:
    sys.path.insert(0, _clientDir)

from LogSystem.logManager import getLogger
from LogSystem import logConfig as cfg


def testLevelAndCategory(logger):
    """测试各等级及各类别日志的写入"""
    # 等级测试(数值越大越严重)
    logger.debug(cfg.CATEGORY_SYSTEM, "调试日志: 启动参数加载")
    logger.info(cfg.CATEGORY_SYSTEM, "信息日志: 系统启动完成")
    logger.warning(cfg.CATEGORY_NETWORK, "警告日志: 心跳超时")
    logger.error(cfg.CATEGORY_AUTH, "错误日志: 登录失败")
    logger.critical(cfg.CATEGORY_SECURITY, "严重日志: 检测到未授权访问")

    # 类别测试
    logger.info(cfg.CATEGORY_FILE, "文件操作: 完整性校验通过")
    logger.info(cfg.CATEGORY_UI, "界面操作: 用户点击登录按钮")


def main():
    """客户端日志系统测试入口"""
    # 获取全局单例日志管理器(文件 + 控制台)
    logger = getLogger()

    print("=== 客户端日志系统全流程测试 ===")
    print("日志目录:", logger.getLogDir())
    print("日志文件:", logger.getLogFilePath())

    testLevelAndCategory(logger)

    # 校验日志文件已落盘
    assert os.path.exists(logger.getLogFilePath()), "日志文件未成功生成"

    # 读取最近日志并展示
    recentLogs = logger.getRecentLogs(7)
    print("\n最近 %d 条日志:" % len(recentLogs))
    for line in recentLogs:
        print("  " + line.strip())

    print("\n客户端日志系统测试通过!")


if __name__ == "__main__":
    main()