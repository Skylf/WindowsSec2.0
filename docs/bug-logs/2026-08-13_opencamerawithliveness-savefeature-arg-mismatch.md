# Bug: openCameraWithLiveness 保存特征时参数不匹配崩溃

**日期**: 2026-08-13
**版本**: v0.0.1F
**优先级**: 高

## 现象
活体检测 5 个动作全部通过后,进入"保存特征"阶段时报错
(预期 TypeError: saveFeatureNpy() takes 2 positional arguments but 3 were given,
以及 cleanOldModelFiles 参数顺序颠倒导致清理/命名异常)。

## 根因
`FaceMoudle/faceInputer/inputter.py` 的 `openCameraWithLiveness()` 中,
对 `faceDataGetter` 的保存函数调用方式与其真实签名不匹配:
1. `saveFeatureNpy(feature, filePath)` / `saveFeatureJson(feature, filePath)` 均只接受 2 个参数,
   但调用处写成了 `saveFeatureNpy(meanFeature, faceDataDir, fileName)`(3 个参数),
   且把返回值(实为 None)赋给 npyPath/jsonPath 用于后续返回
2. `cleanOldModelFiles(faceDataDir, userName)` 参数顺序是 (目录, 用户名),
   调用处写成了 `cleanOldModelFiles(userName, faceDataDir)`

## 修复
修改 `inputter.py` 的 `openCameraWithLiveness()` Step 5 保存段:
1. `cleanOldModelFiles(faceDataDir, userName)` 参数顺序修正
2. 先用 `generateFileName` 得到 baseName,再用 `os.path.join` 构造完整
   `npyPath`/`jsonPath`,最后 `saveFeatureNpy(meanFeature, npyPath)`、
   `saveFeatureJson(meanFeature, jsonPath)` 各传 2 个参数
3. 返回值 npyPath/jsonPath 现在指向真实存在的完整文件路径

## 验证
- `inspect.signature` 确认 faceDataGetter 各函数签名:
  saveFeatureNpy(feature, filePath)、saveFeatureJson(feature, filePath)、
  cleanOldModelFiles(faceDataDir, userName)
- 源码检查确认 inputter 调用已改为两参数且路径用 os.path.join 构造
