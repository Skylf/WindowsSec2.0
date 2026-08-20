"""
coding:utf-8
file: LogSystem/logConfig.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 日志系统配置常量
# ===============

# ── 日志等级 ──
# 数值越大越严重, 用于过滤最低日志等级
DEBUG = 0       # 调试信息: 变量值、函数调用、中间状态
INFO = 1        # 一般信息: 操作成功、状态变更、流程节点
WARNING = 2     # 警告: 非致命异常、降级处理、资源不足
ERROR = 3       # 错误: 操作失败、异常捕获、功能不可用
CRITICAL = 4    # 严重: 系统崩溃、数据损坏、安全威胁

# 等级名称映射
LEVEL_NAMES = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL",
}

# ── 日志类别 ──
CATEGORY_SYSTEM = "SYSTEM"           # 系统级: 启动/关闭/配置/进程
CATEGORY_NETWORK = "NETWORK"         # 网络: 连接/断开/心跳/重连/超时
CATEGORY_DATABASE = "DATABASE"       # 数据库: 建表/CRUD/连接/事务
CATEGORY_AUTH = "AUTH"               # 认证: 登录/注册/Token/鉴权/登出
CATEGORY_FILE = "FILE"               # 文件: 读写/备份/完整性校验/锁
CATEGORY_FACE = "FACE"               # 人脸: 检测/录入/识别/活体/特征
CATEGORY_UI = "UI"                   # 界面: 页面跳转/按钮事件/渲染
CATEGORY_SECURITY = "SECURITY"       # 安全: 蓝屏检测/卡死检测/威胁告警
CATEGORY_PERFORMANCE = "PERFORMANCE" # 性能: 耗时/内存/CPU/帧率

# ── 控制台颜色 ──
# Windows 控制台 ANSI 颜色码
COLOR_RESET = "\033[0m"
COLOR_LEVEL = {
    DEBUG: "\033[36m",       # 青色
    INFO: "\033[32m",        # 绿色
    WARNING: "\033[33m",     # 黄色
    ERROR: "\033[31m",       # 红色
    CRITICAL: "\033[35m",    # 紫色
}

# ── 客户端配置 ──
CLIENT_LOG_DIR = "client/log"               # 日志目录(相对项目根目录)
CLIENT_LOG_FILE = "client.log"              # 当前日志文件名
CLIENT_LOG_MAX_SIZE = 10 * 1024 * 1024      # 单文件最大 10MB
CLIENT_LOG_BACKUP_COUNT = 10                # 最多保留 10 个备份
CLIENT_LOG_DEFAULT_LEVEL = DEBUG            # 默认最低输出等级(DEBUG=全部)
CLIENT_LOG_FORMAT = "[{datetime}] [{level}] [{category}] {message}"  # 日志格式

# ── 服务端配置 ──
SERVER_LOG_TABLE = "system_logs"            # 数据库日志表名
SERVER_LOG_DEFAULT_LEVEL = DEBUG            # 默认最低输出等级
SERVER_LOG_FORMAT = "[{datetime}] [{level}] [{category}] {message}"  # 日志格式