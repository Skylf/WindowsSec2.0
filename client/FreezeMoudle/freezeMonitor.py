# -*- coding: utf-8 -*-
"""
全方位卡死检测器(freezeMonitor)
================================
9 个检测维度, 从多角度最大程度正确检测卡死:

1. cpu_high       系统 CPU 使用率持续超阈值(满载)
2. proc_cpu_high  单个进程 CPU 占用持续超阈值(某程序吃满核)
3. mem_high       内存使用率持续超阈值(耗尽)
4. swap_high      交换内存(页面文件)使用率持续超阈值
5. disk_busy      磁盘读写速率持续超阈值(IO 瓶颈)
6. disk_full      系统盘剩余空间低于阈值
7. process_storm  进程数量超过阈值(进程风暴)
8. ui_freeze      关键界面进程(explorer 任务栏)消息超时(界面冻结)
9. sys_slow       系统响应延迟超阈值(sleep 实测超时 → 内核级卡死)

误报抑制(三层):
- 连续确认: 异常需连续 confirm_count 次采样仍存在才报警
- 冷却期:   同类型报警后 cooldown_seconds 内不重复
- 持续去重: 持续存在的异常(如磁盘空间不足)只报警一次, 恢复后再现才重报
- 忽略列表: 配置的进程不计入"谁在占用"; 监控器自身排除

使用:
    monitor = FreezeMonitor()
    monitor.setAlertCallback(on_alert)   # 报警回调(如弹窗)
    monitor.start()                      # 启动后台采样线程
    monitor.stop()                       # 停止
"""

import ctypes
import threading
import time

import psutil

import freezeConfig


# ── 异常类型 → 通俗解读/建议(报告用) ──
KNOWLEDGE = {
    "cpu_high": {
        "meaning": "CPU 被大量占用, 系统处理任务缓慢甚至卡死。",
        "advice": "结束占用最高的程序; 检查是否有异常进程/病毒; 关闭后台不必要的程序。",
    },
    "proc_cpu_high": {
        "meaning": "某个程序持续占满 CPU 核心, 拖慢整个系统。",
        "advice": "结束该程序(见报告中的进程名); 检查它是否异常死循环; 更新或卸载该软件。",
    },
    "mem_high": {
        "meaning": "内存(运行内存)几乎耗尽, 系统被迫大量使用硬盘虚拟内存, 严重变慢。",
        "advice": "结束占用内存最高的程序; 关闭未使用的软件; 考虑增加物理内存。",
    },
    "swap_high": {
        "meaning": "页面文件(虚拟内存)占用过高, 内存与硬盘频繁交换数据导致卡顿。",
        "advice": "释放内存(见内存过高建议); 检查硬盘健康; 清理开机自启动程序。",
    },
    "disk_busy": {
        "meaning": "硬盘读写繁忙, 磁盘 IO 成为系统瓶颈(程序读取/写入大量数据)。",
        "advice": "结束高磁盘占用进程; 检查是否有程序在下载/备份/索引; 机械硬盘考虑碎片整理。",
    },
    "disk_full": {
        "meaning": "系统盘剩余空间不足, 系统运行与虚拟内存写入受影响。",
        "advice": "清理系统盘(磁盘清理/删除大文件); 将个人文件移至其他盘; 释放至少 10% 空间。",
    },
    "process_storm": {
        "meaning": "系统中运行的程序(进程)数量异常多, 资源被大量进程瓜分。",
        "advice": "检查是否有异常程序反复启动; 清理自启动项; 结束不必要进程。",
    },
    "ui_freeze": {
        "meaning": "系统桌面界面(资源管理器)长时间无响应, 表现为点击无反应/转圈。",
        "advice": "等待系统恢复或按 Ctrl+Alt+Del 打开任务管理器结束无响应程序; 若频繁出现请检查磁盘与驱动。",
    },
    "sys_slow": {
        "meaning": "系统响应出现严重延迟(内核繁忙/资源耗尽), 表现为操作卡顿、假死。",
        "advice": "等待系统恢复; 检查任务管理器中高占用进程; 若频繁出现请检查磁盘健康、驱动与散热。",
    },
}


class FreezeMonitor:
    """全方位卡死检测器(后台采样线程)"""

    def __init__(self, config=None):
        self._config = config if config is not None else freezeConfig.load()
        self._thread = None
        self._stop_event = threading.Event()
        self._alert_callback = None

        self._pending = {}            # 类型 -> 连续异常次数(未达确认阈值)
        self._cooldown_until = {}     # 类型 -> 冷却截止时间戳
        self._reported = {}           # 类型 -> 已报警且未恢复(持续去重)
        self.alerts = []              # 报警历史(最近保留 50 条)

        self._last_disk_io = None     # 磁盘 IO 计数器快照
        self._last_sample_time = None

    # ============================================================
    # 生命周期
    # ============================================================
    def start(self) -> bool:
        """启动后台采样线程(总开关关闭时拒绝)"""
        if self.is_running():
            return False
        if not freezeConfig.isEnabled():
            print("[freezeMonitor] 检测开关已关闭(freezeConfig.enabled), 未启动")
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[freezeMonitor] 持续监控已启动(采样间隔 "
              f"{self._config.get('sample_interval', 5.0)}s, "
              f"连续 {self._config.get('confirm_count', 3)} 次确认报警)")
        return True

    def stop(self):
        """停止监控"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        print("[freezeMonitor] 监控已停止")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def setAlertCallback(self, callback):
        """
        设置报警回调(报警时调用, 在采样线程执行)
        :param callback: 签名 callback(alert_dict)
        """
        self._alert_callback = callback

    # ============================================================
    # 采样循环(后台线程)
    # ============================================================
    def _loop(self):
        interval = float(self._config.get("sample_interval", 5.0))
        # CPU 占用率需要两次调用才有值, 首轮预热
        psutil.cpu_percent(interval=None)
        self._last_sample_time = time.time()
        while not self._stop_event.is_set():
            issues = self.sampleOnce()
            self._accumulate(issues)
            self._stop_event.wait(interval)

    def sampleOnce(self) -> list:
        """
        单次全方位采样, 返回当前存在的异常列表
        :return: [{"type": str, "value": float, "threshold": float, "msg": str}, ...]
        """
        issues = []
        now = time.time()
        elapsed = max(0.1, (now - self._last_sample_time) if self._last_sample_time else 1.0)
        self._last_sample_time = now

        # 1. CPU 满载
        cpu = psutil.cpu_percent(interval=None)
        if cpu >= float(self._config.get("cpu_threshold", 90.0)):
            issues.append({
                "type": "cpu_high", "value": round(cpu, 1),
                "threshold": self._config.get("cpu_threshold", 90.0),
                "msg": f"CPU 使用率 {cpu:.0f}%(阈值 {self._config.get('cpu_threshold', 90.0):.0f}%)",
            })

        # 1.5 单进程 CPU 过高(某程序吃满核)
        top_proc = self._topProcesses(1)
        if top_proc and top_proc[0]["cpu"] >= float(self._config.get("proc_cpu_threshold", 80.0)):
            p = top_proc[0]
            issues.append({
                "type": "proc_cpu_high", "value": p["cpu"],
                "threshold": self._config.get("proc_cpu_threshold", 80.0),
                "msg": f"进程 {p['name']}(PID {p['pid']}) CPU 占用 "
                       f"{p['cpu']:.0f}%(阈值 {self._config.get('proc_cpu_threshold', 80.0):.0f}%)",
            })

        # 2. 内存过高
        mem = psutil.virtual_memory()
        if mem.percent >= float(self._config.get("mem_threshold", 90.0)):
            issues.append({
                "type": "mem_high", "value": round(mem.percent, 1),
                "threshold": self._config.get("mem_threshold", 90.0),
                "msg": f"内存使用率 {mem.percent:.0f}%(阈值 "
                       f"{self._config.get('mem_threshold', 90.0):.0f}%), "
                       f"可用 {mem.available / 1024 ** 3:.1f} GB",
            })

        # 3. 交换内存(页面文件)
        swap = psutil.swap_memory()
        if swap.percent >= float(self._config.get("swap_threshold", 80.0)):
            issues.append({
                "type": "swap_high", "value": round(swap.percent, 1),
                "threshold": self._config.get("swap_threshold", 80.0),
                "msg": f"页面文件使用率 {swap.percent:.0f}%",
            })

        # 4. 磁盘 IO 繁忙(两次计数器差值算速率)
        io = psutil.disk_io_counters()
        if io is not None and self._last_disk_io is not None:
            read_mb = (io.read_bytes - self._last_disk_io.read_bytes) / 1024 / 1024
            write_mb = (io.write_bytes - self._last_disk_io.write_bytes) / 1024 / 1024
            speed = (read_mb + write_mb) / elapsed
            if speed >= float(self._config.get("disk_busy_threshold", 50.0)):
                issues.append({
                    "type": "disk_busy", "value": round(speed, 1),
                    "threshold": self._config.get("disk_busy_threshold", 50.0),
                    "msg": f"磁盘读写 {speed:.0f} MB/s(阈值 "
                           f"{self._config.get('disk_busy_threshold', 50.0):.0f} MB/s), "
                           f"读 {read_mb / elapsed:.1f} / 写 {write_mb / elapsed:.1f} MB/s",
                })
        self._last_disk_io = io

        # 5. 磁盘空间不足
        try:
            usage = psutil.disk_usage(self._config.get("disk_path", "C:\\"))
            free_pct = usage.free / usage.total * 100.0
            if free_pct <= float(self._config.get("disk_free_threshold", 5.0)):
                issues.append({
                    "type": "disk_full", "value": round(free_pct, 1),
                    "threshold": self._config.get("disk_free_threshold", 5.0),
                    "msg": f"系统盘剩余空间仅 {free_pct:.1f}%(阈值 "
                           f"{self._config.get('disk_free_threshold', 5.0):.0f}%), "
                           f"剩余 {usage.free / 1024 ** 3:.1f} GB",
                })
        except OSError:
            pass

        # 6. 进程数量异常(进程风暴)
        pcount = len(psutil.pids())
        if pcount >= int(self._config.get("process_count_threshold", 800)):
            issues.append({
                "type": "process_storm", "value": pcount,
                "threshold": self._config.get("process_count_threshold", 800),
                "msg": f"进程数量 {pcount}(阈值 "
                       f"{self._config.get('process_count_threshold', 800)})",
            })

        # 7. 界面无响应(explorer 任务栏消息超时)
        if not self._checkUiResponds():
            issues.append({
                "type": "ui_freeze", "value": self._config.get("ui_timeout_ms", 5000),
                "threshold": self._config.get("ui_timeout_ms", 5000),
                "msg": f"桌面界面(资源管理器)无响应超过 "
                       f"{self._config.get('ui_timeout_ms', 5000) / 1000:.0f} 秒",
            })

        # 8. 系统响应延迟(内核级卡死直接度量):
        #    sleep(0.1) 实测耗时显著超时 → 系统时间被卡住(内核繁忙/冻结)
        delay = self._measureResponseDelay()
        if delay >= float(self._config.get("response_delay_threshold", 1.0)):
            issues.append({
                "type": "sys_slow", "value": round(delay, 2),
                "threshold": self._config.get("response_delay_threshold", 1.0),
                "msg": f"系统响应延迟 {delay:.2f} 秒(预期 0.1 秒, 阈值 "
                       f"{self._config.get('response_delay_threshold', 1.0):.1f} 秒)",
            })

        return issues

    def _measureResponseDelay(self) -> float:
        """
        测量系统响应延迟: sleep(0.1) 实际耗时(秒)。
        系统正常时 ~0.1s; 内核级卡死/冻结时显著超时(数秒)。
        在采样线程执行, 自身也随系统卡顿而变慢, 正好反映系统状态。
        """
        try:
            t0 = time.perf_counter()
            time.sleep(0.1)
            return time.perf_counter() - t0
        except Exception:
            return 0.0

    # ============================================================
    # 误报抑制: 连续确认 + 冷却期
    # ============================================================
    def _accumulate(self, issues):
        """
        累积异常状态: 连续确认达阈值 → 报警; 消失则清零
        持续去重: 已报警且未恢复的类型不再重复报警(如磁盘空间不足只报一次)
        """
        active_types = {i["type"] for i in issues}
        # 已不在异常状态的类型: 清零计数 / 清除"已报"标记与冷却(恢复后允许重报)
        for t in list(self._pending):
            if t not in active_types:
                self._pending[t] = 0
        for t in list(self._reported):
            if t not in active_types:
                del self._reported[t]
        for t in list(self._cooldown_until):
            if t not in active_types:
                del self._cooldown_until[t]

        confirm = int(self._config.get("confirm_count", 3))
        for issue in issues:
            t = issue["type"]
            # 持续去重: 该类型已报警且一直存在 → 不重复报
            if t in self._reported:
                continue
            # 冷却期内跳过
            if time.time() < self._cooldown_until.get(t, 0):
                continue
            self._pending[t] = self._pending.get(t, 0) + 1
            if self._pending[t] >= confirm:
                # 触发报警
                self._pending[t] = 0
                self._reported[t] = True
                self._cooldown_until[t] = time.time() + float(
                    self._config.get("cooldown_seconds", 60))
                self._fireAlert(issue)

    def _fireAlert(self, issue):
        """组装报警并分发(回调在采样线程执行)"""
        alert = dict(issue)
        alert["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        alert["top_processes"] = self._topProcesses(
            int(self._config.get("top_process_count", 5)))
        alert["info"] = KNOWLEDGE.get(issue["type"], {
            "meaning": "系统出现异常资源占用。",
            "advice": "观察占用情况, 结束异常程序或重启系统。",
        })
        self.alerts.append(alert)
        if len(self.alerts) > 50:
            self.alerts.pop(0)
        print(f"\n[freezeMonitor] ⚠ 检测到卡死风险: {alert['msg']} ({alert['time']})")
        if self._alert_callback is not None:
            try:
                self._alert_callback(alert)
            except Exception as e:
                print(f"[freezeMonitor] 报警回调异常: {e}")

    # ============================================================
    # 辅助: 占用进程 TOP / 界面响应探测
    # ============================================================
    def _topProcesses(self, count=5):
        """
        当前 CPU/内存占用最高的进程列表(忽略列表排除)
        :return: [{"name": str, "pid": int, "cpu": float, "mem": float}, ...]
        """
        ignore = set(self._config.get("ignore_processes", []))
        procs = []
        for p in psutil.process_iter(["name", "cpu_percent", "memory_percent", "pid"]):
            try:
                info = p.info
                if info["name"] in ignore:
                    continue
                procs.append({
                    "name": info["name"] or "?",
                    "pid": info["pid"],
                    "cpu": round(info["cpu_percent"] or 0.0, 1),
                    "mem": round(info["memory_percent"] or 0.0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x["cpu"], reverse=True)
        return procs[:count]

    def _checkUiResponds(self) -> bool:
        """
        探测桌面界面是否响应(explorer 任务栏窗口 SendMessageTimeout)
        :return: True=响应正常; 无桌面会话/探测异常也返回 True(不误报)
        """
        try:
            hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
            if not hwnd:
                return True   # 无任务栏窗口(如无桌面会话), 不判定
            result = ctypes.c_long()
            # WM_NULL + SMTO_ABORTIFHUNG|SMTO_BLOCK
            res = ctypes.windll.user32.SendMessageTimeoutW(
                hwnd, 0x0000, 0, 0, 0x0002 | 0x0001,
                int(self._config.get("ui_timeout_ms", 5000)),
                ctypes.byref(result))
            return res != 0
        except Exception:
            return True   # 探测异常不误报
