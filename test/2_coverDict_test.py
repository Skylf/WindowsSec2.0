# -*- coding: utf-8 -*-
"""
coverDict 完整流程测试
=====================
1. 正常流程:152 张(含 2 张无脸)→ faceCheck → handleNoFace → coverDict → 150 张
2. 失败场景 A:传空 newDict → 应返回原字典
3. 失败场景 B:newDict 含 hasFace=False 条目 → 应返回原字典
4. 失败场景 C:newDict 包含原字典不存在的 key → 应返回原字典
"""
import os
import sys
import cv2
import numpy as np

# 加入项目根路径
projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, projectRoot)

from FaceMoudle.faceInputer.inputter import faceCheck, handleNoFace, coverDict


def makeNoFaceImages(targetDir, count=2):
    """生成 N 张纯色无脸图"""
    colors = [(255, 0, 0), (0, 0, 255), (0, 255, 0), (255, 255, 0)]
    names = []
    for i in range(count):
        b, g, r = colors[i % len(colors)]
        img = np.full((480, 640, 3), (b, g, r), dtype=np.uint8)
        name = f"noface_test_{i}.jpg"
        path = os.path.join(targetDir, name)
        is_success, buffer = cv2.imencode('.jpg', img)
        buffer.tofile(path)
        names.append(name)
    return names


def main():
    test_dir = os.path.join(projectRoot, "FaceMoudle", "faceInputer", "captured_photos")

    # === 准备测试数据:插入 2 张无脸图 ===
    print("=" * 60)
    print("[准备] 插入 2 张无脸测试图")
    noface_names = makeNoFaceImages(test_dir, 2)
    print(f"  生成: {noface_names}")
    print(f"  当前目录文件数: {len(os.listdir(test_dir))}")

    # === 场景 1:正常流程 ===
    print("\n" + "=" * 60)
    print("[场景 1] 正常流程:faceCheck → handleNoFace → coverDict")
    sharedDict = faceCheck(test_dir, maxWorkers=4)
    print(f"[Step2] 检测完成: 共 {len(sharedDict)} 张")

    cleanedDict = handleNoFace(sharedDict)
    print(f"[Step3] 清理完成: 剩余 {len(cleanedDict)} 张")

    sharedDict = coverDict(sharedDict, cleanedDict)
    print(f"[Step4] 覆盖完成: sharedDict 当前 {len(sharedDict)} 张")

    # === 场景 2:传入空 newDict(应返回原字典) ===
    print("\n" + "=" * 60)
    print("[场景 2] 失败场景:传入空 newDict")
    fakeOriginal = {"path_a": {"hasFace": True, "status": "success", "msg": "ok"}}
    result = coverDict(fakeOriginal, {})
    expected = fakeOriginal
    print(f"  结果: 返回值是原字典? {result is expected}")
    assert result is expected, "应返回原字典"

    # === 场景 3:newDict 含 hasFace=False 条目(应返回原字典) ===
    print("\n" + "=" * 60)
    print("[场景 3] 失败场景:newDict 含 hasFace=False 条目")
    fakeOriginal2 = {
        "path_a": {"hasFace": True, "status": "success", "msg": "ok"},
        "path_b": {"hasFace": False, "status": "fail", "msg": "无脸"},
    }
    fakeNew2 = {
        "path_a": {"hasFace": True, "status": "success", "msg": "ok"},
        "path_b": {"hasFace": False, "status": "fail", "msg": "无脸"},  # 不应出现的脏数据
    }
    result2 = coverDict(fakeOriginal2, fakeNew2)
    print(f"  结果: 返回值是原字典? {result2 is fakeOriginal2}")
    assert result2 is fakeOriginal2, "应返回原字典"

    # === 场景 4:newDict 包含原字典不存在的 key(应返回原字典) ===
    print("\n" + "=" * 60)
    print("[场景 4] 失败场景:newDict 包含原字典不存在的 key")
    fakeOriginal3 = {"path_a": {"hasFace": True, "status": "success", "msg": "ok"}}
    fakeNew3 = {
        "path_a": {"hasFace": True, "status": "success", "msg": "ok"},
        "path_xxx": {"hasFace": True, "status": "success", "msg": "ok"},  # 原 dict 没有
    }
    result3 = coverDict(fakeOriginal3, fakeNew3)
    print(f"  结果: 返回值是原字典? {result3 is fakeOriginal3}")
    assert result3 is fakeOriginal3, "应返回原字典"

    # === 最终结论 ===
    print("\n" + "=" * 60)
    print("[最终结论]")
    print(f"  sharedDict 大小: {len(sharedDict)} (预期 150)")
    print(f"  所有失败场景校验通过(空/脏数据/超集均拒绝覆盖)")
    print(f"  全部测试 PASSED ✓")


if __name__ == '__main__':
    main()
