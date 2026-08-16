# 卡死模拟器(业务功能测试)

模拟各种卡死场景, 用于测试 FreezeMoudle 检测器(7 个检测维度)是否准确报警。

## 快速开始

```powershell
# 统一入口(菜单选择)
python FreezeMoudle/simulator/simulate.py

# 或直接指定类型
python FreezeMoudle/simulator/simulate.py --type cpu --duration 10
```

## 模拟类型与对应检测维度

| 菜单 | 脚本 | 模拟场景 | 检测维度 |
|---|---|---|---|
| 1 | `sim_cpu.py` | 多线程死循环占满 CPU | `cpu_high` |
| 2 | `sim_memory.py` | 持续分配内存 | `mem_high` / `swap_high` |
| 3 | `sim_disk_io.py` | 循环读写临时文件 | `disk_busy` |
| 4 | `sim_disk_full.py` | 写入大文件占用空间 | `disk_full` |
| 5 | `sim_process_storm.py` | 启动大量子进程 | `process_storm` |
| 6 | `sim_ui_freeze.py` | 窗口无响应演示(配合 CPU 模拟) | `ui_freeze`(系统级) |

## 测试流程示例

1. 启动持续监控: `python FreezeMoudle/runTest.py` → 选 2
2. 另开终端跑模拟: `python FreezeMoudle/simulator/simulate.py --type cpu --duration 30`
3. 观察监控端: 连续 3 次采样确认(约 15s)后弹出卡死检测报告
   (报告含: 异常详情 / 解读 / 建议 / 占用 TOP5 进程)

## 参数说明

- 所有脚本支持 `--duration`(持续秒数)
- `sim_cpu.py --threads N`(线程数, 默认=CPU 核心数)
- `sim_memory.py --mb N`(占用 MB, 默认 512)
- `sim_disk_io.py --mb N`(每轮读写 MB, 默认 64)
- `sim_disk_full.py --mb N --path X`(占用 MB, 默认 200, 写入系统 temp)
- `sim_process_storm.py --count N`(子进程数, 默认 100)
- `sim_ui_freeze.py --freeze N`(冻结秒数, 默认 10)

## ⚠ 安全警告

1. **内存模拟**(`--mb`)从 256 起步, 过大会导致系统无响应
2. **磁盘空间模拟**(`--mb`)会真实占用磁盘, 程序结束自动删除生成文件;
   默认写入系统 temp 目录, 指定 `--path` 时请确认可安全删除
3. **进程风暴**(`--count`)会启动大量子进程, 结束后自动终止
4. 所有模拟均支持 `Ctrl+C` 中断, 中断后自动清理
5. 建议在测试环境或确认系统状态正常时使用
