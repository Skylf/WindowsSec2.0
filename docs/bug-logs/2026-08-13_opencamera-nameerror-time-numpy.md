# Bug: openCamera函数运行时 NameError(time/numpy 未导入)

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 高

## 现象
用户在 faceInputer/runTest.py 选择「2. 摄像头引导式采集」
→ 模型加载成功(det_10g + 2d106det)
→ 开始进入第一个阶段「正面」时崩溃:
```
Traceback (most recent call last):
  File "...runTest.py", line 151, in <module>
    collectResult = collectImage()
  File "...runTest.py", line 55, in collectImage
    img_dir = inputter.openCamera()
  File "...inputter.py", line 288, in openCamera
    stageStartTime = time.time()  # 阶段开始时间
                      ^^^^
NameError: name 'time' is not defined
```

## 根因
重写 `openCamera()` 时把导入语句写成了:
```python
import sys
from livenessDetector import (LivenessDetector, ...)
```
但函数体内实际使用了:
1. `time.time()` —— 阶段计时(stageStartTime, baselineStart)、连拍间隔(lastShotTime)
2. `np.mean()` —— 计算眨眼 baseline EAR 平均值
3. 间接依赖 numpy 数组计算 landmarks

这两个标准/三方库导入被遗漏，导致执行到第 288 行 `stageStartTime = time.time()` 时抛出 `NameError`。
根本原因：原 openCamera 使用全局的 `import time`(在函数外)，重写时把导入搬到函数内部，只保留了 `sys` 而漏掉 `time` / `numpy`。

## 修复
修改文件: `FaceMoudle/faceInputer/inputter.py` 的 `openCamera()` 函数(L185-L196 段)
在函数内导入 sys 后补上:
```python
import time          # time.time / time.sleep 用于阶段计时、连拍间隔
import numpy as np   # 眨眼 baseline EAR 平均值计算(np.mean)
```

## 验证
1. 语法检查: `python -c "import inputter; src=open(inputter.__file__,encoding='utf-8').read(); assert 'import time' in src and 'import numpy as np' in src"`
2. 运行选择模式 2，能顺利进入「正面」阶段，终端打印 `[正面] 请正对摄像头...`，不再出现 NameError。
