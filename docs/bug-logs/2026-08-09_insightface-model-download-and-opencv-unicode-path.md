# Bug: InsightFace 模型下载失败 + OpenCV 中文路径读图失败

**日期**: 2026-08-09
**版本**: v0.0.1F
**优先级**: 高

## 现象
执行 `test/1.py` 时连续遇到两个问题:
1. `FaceAnalysis(providers=['CPUExecutionProvider'])` 阶段报 `socket.gaierror: [Errno 11004] getaddrinfo failed`,无法解析 `release-assets.githubusercontent.com`
2. 模型下载解决后,`app.get(img)` 阶段报 `AttributeError: 'NoneType' object has no attribute 'shape'`,cv2.imread 返回 None

## 根因

### 问题 1:模型下载被墙
InsightFace 1.0.1 的 `insightface.utils.storage.download()` 默认从 `https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip` 下载模型,GitHub 会 302 重定向到 `release-assets.githubusercontent.com`,该域名在国内 DNS 解析失败(被墙)。

### 问题 2:OpenCV imread 不支持中文路径
项目路径 `D:\COMPUTER\Python\windows安全系统2.0` 含中文字符"安全系统"。OpenCV 的 `cv2.imread` 底层用 C 标准库 `fopen`,Windows 下 `fopen` 不支持非 ASCII 路径,导致读图失败返回 None。
- `insightface.data.get_image('t1')` 内部用 `Path(__file__).parent.absolute()` 拼出含中文的绝对路径,触发此 bug
- 用相对路径测试时 cv2.imread 能成功(因 cwd 已在中文目录内,相对路径不含中文)

## 修复

### 修复 1:用国内 GitHub 镜像离线下载模型
- 探测多个国内镜像,确认 `gh-proxy.com` 和 `ghfast.top` 可用(buffalo_l.zip 实际大小 275MB / 288621354 字节)
- 用 `gh-proxy.com` 镜像下载 `buffalo_l.zip`,解压到 `C:\Users\Administrator\.insightface\models\buffalo_l\`
- InsightFace 的 `storage.py` 第 12-13 行逻辑:目录已存在则跳过下载,因此离线放置后永久生效

模型文件清单(5 个 onnx,共约 332MB):
```
1k3d68.onnx      140MB  3D 68 点关键点
2d106det.onnx    4.9MB  2D 106 点关键点
det_10g.onnx     16.5MB 人脸检测(SCRFD)
genderage.onnx   1.3MB  年龄性别估计
w600k_r50.onnx   170MB  人脸识别/特征提取(ArcFace,R50)
```

### 修复 2:下载真实测试图 + 改用 imdecode 读图
- insightface wheel 包内的 `t1.jpg` 只有 12 字节(打包时图片内容缺失,只剩占位符),从 GitHub 镜像下载真实 t1.jpg(128KB)覆盖
- 修改 `test/1.py`,新增 `imreadUnicode()` 函数,用 `np.fromfile + cv2.imdecode` 替代 `cv2.imread`,绕过 OpenCV 中文路径 bug

修改的文件:
- [test/1.py](file:///d:/COMPUTER/Python/windows安全系统2.0/test/1.py) — 新增 `imreadUnicode` 函数,改用 `np.fromfile + cv2.imdecode` 读图
- `C:\Users\Administrator\.insightface\models\buffalo_l\` — 离线放置 5 个 onnx 模型文件
- `.venv\Lib\site-packages\insightface\data\images\t1.jpg` — 用真实图片(128KB)覆盖 12 字节占位文件

## 验证
执行 `.venv\Scripts\python.exe test\1.py` 输出:
```
find model: ... 1k3d68.onnx landmark_3d_68 ['None', 3, 192, 192] 0.0 1.0
find model: ... 2d106det.onnx landmark_2d_106 ['None', 3, 192, 192] 0.0 1.0
find model: ... det_10g.onnx detection [1, 3, '?', '?'] 127.5 128.0
find model: ... genderage.onnx genderage ['None', 3, 96, 96] 0.0 1.0
find model: ... w600k_r50.onnx recognition ['None', 3, 112, 112] 127.5 127.5
set det-size: [(128, 128), (640, 640)]
检测到 6 张人脸
特征向量维度: (512,)
年龄: 40, 性别: 男
```
5 个模型全部加载成功,人脸检测+识别+年龄性别估计全部正常,特征向量为 512 维(符合 buffalo_l 的 w600k_r50 模型规格)。

## 备注
- `np.fromfile + cv2.imdecode` 是 OpenCV 中文路径的标准 workaround,后续 FaceMoudle 所有读图操作都应使用此方式,建议封装到公共工具模块
- 镜像下载的模型可随项目打包分发到其他机器,避免每台机器都走一次下载
- `gh-proxy.com` 和 `ghfast.top` 是当前可用的国内 GitHub 加速镜像,但镜像服务寿命不确定,长期建议离线放置模型文件
