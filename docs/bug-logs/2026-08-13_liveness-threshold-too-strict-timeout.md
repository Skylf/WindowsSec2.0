# Bug: 活体检测动作阈值过严导致超时失败

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 高

## 现象
用户运行活体检测录入(模式 3)或引导式采集(模式 2)时,部分动作(尤其眨眼、张嘴)
在超时时间内始终无法通过,流程返回 "动作未完成"。

## 根因
`FaceMoudle/faceInputer/livenessDetector.py` 顶部的动作判定阈值偏严:
- 眨眼 `THRESHOLD_EAR_DROP = 0.3`(需 EAR 下降 30%),而正常人自然眨眼约下降 20%~25%,很多人达不到
- 张嘴 `THRESHOLD_MAR_OPEN = 0.5`,不同脸型 MAR 差异大,偏严
- 姿态 `±15°/10°`,非正面坐姿时偏严
- 动作超时 `ACTION_TIMEOUT = 2.0` 秒,反应时间偏紧
- `collectBaselineEAR` 采集失败时直接回退固定值 `0.3`,对不同用户不准确,导致眨眼判定失效

## 修复
修改 `livenessDetector.py`:
1. 放宽阈值:
   - `THRESHOLD_EAR_DROP` 0.3 → 0.2
   - `THRESHOLD_MAR_OPEN` 0.5 → 0.4
   - `THRESHOLD_YAW_LEFT` -15 → -20, `THRESHOLD_YAW_RIGHT` 15 → 20, `THRESHOLD_PITCH_UP` 10 → 15
   - `ACTION_TIMEOUT` 2.0 → 3.0
   - `BASELINE_DURATION` 1.0 → 1.5
2. `collectBaselineEAR` 增加失败重试(最多 2 次,每次 duration+1 秒),
   重试耗尽才用保守 fallback 0.25,不再直接套固定 0.3
3. `runLivenessCheck` 每帧实时打印当前数值(便于定位卡住动作),
   并将 `cv2.destroyWindow("Liveness")` 改为 `cv2.destroyAllWindows()` 避免窗口残留
4. 同步更新 `openCamera` 引导式采集里的 baseline 采集(同样最多重试 3 次)

## 验证
- `python -c` 导入校验: 阈值常量全部更新到位
- `collectBaselineEAR` 签名为 `(self, cap, duration=1.5, retryLeft=2)`
- `runLivenessCheck` 中已无 `destroyWindow`,含 `destroyAllWindows` 与实时日志
