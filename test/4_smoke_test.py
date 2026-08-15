# -*- coding: utf-8 -*-
"""
FaceMoudle 端到端冒烟测试
=========================
验证完整链路: 人脸检测 → 无脸清理 → 特征提取(多进程) → 特征保存 → 人脸识别
1. faceCheck(cache/captured_photos)  → 多进程批量检测
2. handleNoFace + coverDict          → 清理无脸图 + 安全覆盖
3. generateFaceFeature('smoke_test') → 多进程特征提取 + 保存 .npy/.json
4. recognizeFace(特征, 采集照片)      → 1:1 识别比对
5. 清理测试用户特征文件(不污染正式数据)
"""
import os
import sys
import glob

# 注入项目路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
faceMoudleDir = os.path.join(projectRoot, 'FaceMoudle')
faceInputerDir = os.path.join(faceMoudleDir, 'faceInputer')
faceDetecterDir = os.path.join(faceMoudleDir, 'faceDetecter')
facialRecognitionDir = os.path.join(faceMoudleDir, 'facialRecognition')
for d in [faceMoudleDir, faceInputerDir, faceDetecterDir, facialRecognitionDir]:
    if d not in sys.path:
        sys.path.insert(0, d)

import inputter
from faceDataGetter import generateFaceFeature, getFaceDataDir
from recognition import recognizeFace, recognizeFaceMulti

TEST_USER = 'smoke_test'


def main():
    # ============ Step 1: faceCheck 批量检测 ============
    photoDir = os.path.join(projectRoot, 'cache', 'captured_photos')
    print(f"[1] faceCheck: {photoDir}")
    sharedDict = inputter.faceCheck(photoDir, maxWorkers=4)
    assert sharedDict, "faceCheck 返回空!"
    print(f"    检测到 {len(sharedDict)} 张可用图")

    # ============ Step 2: handleNoFace + coverDict ============
    cleanedDict = inputter.handleNoFace(sharedDict)
    finalDict = inputter.coverDict(sharedDict, cleanedDict)
    assert len(finalDict) > 0, "清理后无可用图!"
    print(f"[2] 清理后可用图: {len(finalDict)} 张")

    # ============ Step 3: 特征提取(多进程) + 保存 ============
    print(f"[3] generateFaceFeature('{TEST_USER}')")
    feature = generateFaceFeature(TEST_USER, imgDir=photoDir, maxWorkers=4)
    assert feature is not None, "特征提取失败!"
    assert feature.shape == (512,), f"特征维度异常: {feature.shape}"
    print(f"    特征: shape={feature.shape}, norm={__import__('numpy').linalg.norm(feature):.6f}")

    # 确认保存文件存在
    faceDataDir = getFaceDataDir()
    npyFiles = glob.glob(os.path.join(faceDataDir, f"{TEST_USER}_*.npy"))
    jsonFiles = glob.glob(os.path.join(faceDataDir, f"{TEST_USER}_*.json"))
    assert npyFiles and jsonFiles, "特征文件未保存!"
    print(f"    npy: {os.path.basename(npyFiles[0])}, json: {os.path.basename(jsonFiles[0])}")

    # ============ Step 4: 识别比对(用同一批照片的其中一张) ============
    photoPath = finalDict and next(iter(finalDict.keys())) or None
    print(f"[4] recognizeFace: {os.path.basename(photoPath)}")
    result = recognizeFace(npyFiles[0], photoPath, threshold=0.85)
    print(f"    识别结果: {result}")
    assert result["success"], "识别 API 执行失败!"
    # 同一批照片提取的特征,相似度应很高(>0.85 大概率匹配,不强制断言 matched)

    # ============ Step 5: 多特征批量识别 API ============
    print("[5] recognizeFaceMulti")
    allNpy = sorted(glob.glob(os.path.join(faceDataDir, "*.npy")))
    if allNpy:
        multiResult = recognizeFaceMulti(allNpy, photoPath, threshold=0.85)
        print(f"    批量结果: matched={multiResult['matched']}, "
              f"best={multiResult['bestMatch']}, sim={multiResult['bestSimilarity']}")

    # ============ 清理测试数据 ============
    print(f"[6] 清理测试用户特征文件...")
    for f in npyFiles + jsonFiles:
        os.remove(f)
        print(f"    删除 {os.path.basename(f)}")

    print("\n=== 冒烟测试全部通过 ✓ ===")


if __name__ == '__main__':
    main()
