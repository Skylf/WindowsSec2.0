# -*- coding: utf-8 -*-
"""
蓝屏代码知识库(bsodKnowledge)
==============================
BugcheckCode → 名称 / 通俗含义 / 常见原因 / 普通用户建议。
让普通用户看懂"为什么蓝屏了、该怎么做"。
"""

# 知识库: {十六进制代码: {name, meaning, cause, advice}}
BSOD_KNOWLEDGE = {
    0x0000000A: {
        "name": "IRQL_NOT_LESS_OR_EQUAL",
        "meaning": "程序在错误的级别访问了内存地址, 通常是驱动程序引起。",
        "cause": "驱动 bug / 软件冲突 / 内存问题。",
        "advice": "更新或回滚最近安装的驱动程序; 运行 Windows 内存诊断; 卸载最近安装的可疑软件。",
    },
    0x0000001A: {
        "name": "MEMORY_MANAGEMENT",
        "meaning": "内存管理出现严重错误。",
        "cause": "内存条故障 / 驱动问题 / 超频不稳定。",
        "advice": "运行 Windows 内存诊断(建议重启后检查); 若超频请恢复默认; 更新驱动。",
    },
    0x0000001E: {
        "name": "KMODE_EXCEPTION_NOT_HANDLED",
        "meaning": "系统内核程序抛出了未处理的异常。",
        "cause": "驱动 bug / 不兼容硬件 / 系统文件损坏。",
        "advice": "更新所有驱动(尤其是主板/显卡); 运行 SFC /scannow; 检查新装硬件。",
    },
    0x00000023: {
        "name": "FAT_FILE_SYSTEM",
        "meaning": "FAT 文件系统驱动出错(旧磁盘格式)。",
        "cause": "磁盘坏道 / 硬盘故障。",
        "advice": "使用磁盘检查工具扫描硬盘; 及时备份重要数据。",
    },
    0x00000024: {
        "name": "NTFS_FILE_SYSTEM",
        "meaning": "NTFS 文件系统驱动出错, 常见于磁盘问题。",
        "cause": "磁盘坏道 / 硬盘老化 / 存储驱动异常。",
        "advice": "运行 chkdsk 检查磁盘; 更新存储驱动; 备份重要数据。",
    },
    0x00000027: {
        "name": "RDR_FILE_SYSTEM",
        "meaning": "网络重定向文件系统出错(较少见)。",
        "cause": "网络驱动 / 存储问题。",
        "advice": "更新网卡驱动; 检查磁盘健康。",
    },
    0x0000003B: {
        "name": "SYSTEM_SERVICE_EXCEPTION",
        "meaning": "系统服务在执行时抛出异常, 是较常见的蓝屏之一。",
        "cause": "驱动(尤其显卡) bug / 系统文件损坏 / 内存问题。",
        "advice": "更新显卡/芯片组驱动; 运行 SFC /scannow; 内存诊断。",
    },
    0x0000004E: {
        "name": "PFN_LIST_CORRUPT",
        "meaning": "系统内存页管理数据结构被破坏。",
        "cause": "内存故障 / 驱动 bug / 磁盘问题。",
        "advice": "内存诊断; 更新驱动; 检查硬盘健康。",
    },
    0x00000050: {
        "name": "PAGE_FAULT_IN_NONPAGED_AREA",
        "meaning": "程序访问了不存在的内存地址(常见于内存条或驱动问题)。",
        "cause": "内存条故障 / 驱动 bug / 杀毒软件冲突。",
        "advice": "运行 Windows 内存诊断; 更新驱动; 临时禁用杀毒软件测试。",
    },
    0x00000051: {
        "name": "REGISTRY_ERROR",
        "meaning": "注册表读取发生严重错误。",
        "cause": "注册表损坏 / 磁盘问题。",
        "advice": "使用系统还原; 磁盘检查; 备份注册表/数据。",
    },
    0x0000007E: {
        "name": "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED",
        "meaning": "系统线程抛出未处理异常, 常见于驱动不兼容。",
        "cause": "驱动 bug / 内存问题 / 系统文件损坏。",
        "advice": "更新驱动(按蓝屏参数或最新安装的驱动优先); 内存诊断; SFC 检查。",
    },
    0x0000007F: {
        "name": "UNEXPECTED_KERNEL_MODE_TRAP",
        "meaning": "内核发生了意外陷阱, 通常与硬件问题相关。",
        "cause": "CPU/内存故障 / 过热 / 超频不稳定 / 主板问题。",
        "advice": "检查 CPU 温度与散热; 恢复默认频率; 内存诊断; 检查电源。",
    },
    0x0000008E: {
        "name": "KERNEL_MODE_EXCEPTION_NOT_HANDLED",
        "meaning": "内核模式程序异常未处理。",
        "cause": "驱动 bug / 内存问题。",
        "advice": "更新驱动; 内存诊断。",
    },
    0x0000009F: {
        "name": "DRIVER_POWER_STATE_FAILURE",
        "meaning": "驱动程序在电源状态切换(睡眠/唤醒)时失败。",
        "cause": "电源相关驱动(显卡/网卡/USB) bug。",
        "advice": "更新主板/显卡/网卡驱动; 检查电源计划; 更新 BIOS。",
    },
    0x000000C2: {
        "name": "BAD_POOL_CALLER",
        "meaning": "驱动程序错误地请求了内存池操作。",
        "cause": "驱动 bug(常为第三方驱动)。",
        "advice": "更新/卸载最近安装的驱动或软件; 使用系统还原。",
    },
    0x000000C5: {
        "name": "DRIVER_CORRUPTED_EXPOOL",
        "meaning": "驱动程序破坏了内存池数据。",
        "cause": "驱动 bug。",
        "advice": "更新驱动; 系统还原到正常时间点。",
    },
    0x000000CA: {
        "name": "PNP_DETECTED_FATAL_ERROR",
        "meaning": "即插即用(硬件)检测到致命错误。",
        "cause": "外设/驱动问题。",
        "advice": "拔掉近期新增的外设; 更新外设驱动。",
    },
    0x000000D1: {
        "name": "DRIVER_IRQL_NOT_LESS_OR_EQUAL",
        "meaning": "驱动程序访问了非法内存地址(很常见, 多为驱动问题)。",
        "cause": "驱动 bug(显卡/网卡/声卡常见)。",
        "advice": "更新或回滚最近安装的驱动; 用事件日志定位故障驱动; 内存诊断。",
    },
    0x000000EF: {
        "name": "CRITICAL_PROCESS_DIED",
        "meaning": "系统关键进程意外终止。",
        "cause": "系统文件损坏 / 恶意软件 / 磁盘故障 / 驱动冲突。",
        "advice": "运行 SFC /scannow; 全盘杀毒; 磁盘检查; 更新驱动。",
    },
    0x000000F4: {
        "name": "CRITICAL_OBJECT_TERMINATION",
        "meaning": "系统关键对象(进程/线程)被终止。",
        "cause": "硬盘故障 / 驱动问题 / 电源不稳。",
        "advice": "检查硬盘健康(SMART); 更新驱动; 检查电源。",
    },
    0x000000FE: {
        "name": "BUGCODE_USB_DRIVER",
        "meaning": "USB 驱动导致蓝屏。",
        "cause": "USB 设备/驱动冲突。",
        "advice": "更新 USB 控制器驱动; 拔掉问题 USB 设备测试。",
    },
    0x00000101: {
        "name": "CLOCK_WATCHDOG_TIMEOUT",
        "meaning": "CPU 某个核心长时间无响应。",
        "cause": "CPU 故障 / 超频不稳定 / 驱动 bug / BIOS 问题。",
        "advice": "恢复 CPU 默认频率; 更新 BIOS 与驱动; 检查散热。",
    },
    0x00000116: {
        "name": "VIDEO_TDR_FAILURE",
        "meaning": "显卡驱动超时无响应(画面冻结后蓝屏)。",
        "cause": "显卡驱动崩溃 / 显卡过热 / 显卡超频。",
        "advice": "更新或重装显卡驱动; 检查显卡温度与供电; 关闭显卡超频。",
    },
    0x00000124: {
        "name": "WHEA_UNCORRECTABLE_ERROR",
        "meaning": "硬件级不可纠正错误(CPU/内存/主板/电源)。",
        "cause": "CPU 故障 / 内存故障 / 超频 / 电源不足 / BIOS 问题。",
        "advice": "恢复默认频率; 内存诊断; 更新 BIOS; 检查电源功率; 若持续出现建议检修硬件。",
    },
    0x00000133: {
        "name": "DPC_WATCHDOG_VIOLATION",
        "meaning": "系统响应超时(有驱动长时间占用 CPU 不释放)。",
        "cause": "驱动 bug(存储/显卡驱动常见)。",
        "advice": "更新存储/显卡驱动; 检查 SSD 固件; 系统还原。",
    },
    0x00000139: {
        "name": "KERNEL_SECURITY_CHECK_FAILURE",
        "meaning": "内核安全检查失败(内存被破坏或驱动越权)。",
        "cause": "内存问题 / 驱动 bug / 系统文件损坏。",
        "advice": "内存诊断; 更新驱动; SFC 检查; 若频繁出现考虑硬件检修。",
    },
    0x00000154: {
        "name": "UNEXPECTED_STORE_EXCEPTION",
        "meaning": "存储设备(SSD/硬盘)出现意外异常。",
        "cause": "SSD 固件/硬件问题 / 存储驱动 bug。",
        "advice": "更新存储驱动与 SSD 固件; 检查磁盘健康; 备份数据。",
    },
}

# 未知代码的通用解读
UNKNOWN_INFO = {
    "name": "未知蓝屏代码",
    "meaning": "系统记录了蓝屏, 但该代码不在内置知识库中。",
    "cause": "可能是较少见的驱动/硬件/软件组合问题。",
    "advice": "更新所有驱动; 运行内存诊断与磁盘检查; 记录蓝屏代码后搜索该代码+驱动关键词; 若频繁出现建议检修硬件。",
}


def getBsodInfo(bugcheck_code):
    """
    按 BugcheckCode 查询蓝屏解读
    :param bugcheck_code: 蓝屏代码<int>(十进制) 或 <str>(含 0x 前缀十六进制)
    :return: {"name", "meaning", "cause", "advice"}; 未知代码返回通用解读
    """
    try:
        if isinstance(bugcheck_code, str):
            bugcheck_code = int(bugcheck_code, 16) if bugcheck_code.lower().startswith("0x") \
                else int(bugcheck_code)
        code = int(bugcheck_code)
    except (ValueError, TypeError):
        return dict(UNKNOWN_INFO)
    return BSOD_KNOWLEDGE.get(code, dict(UNKNOWN_INFO))


def formatCode(code):
    """
    格式化蓝屏代码为 0x 十六进制显示
    :param code: 十进制<int> 或 十六进制<str>
    :return: 如 "0x0000007E"<str>
    """
    try:
        value = int(code, 16) if isinstance(code, str) and code.lower().startswith("0x") \
            else int(code)
        return f"0x{value:08X}"
    except (ValueError, TypeError):
        return str(code)
