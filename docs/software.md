# 软件安装与模型准备

## 本机运行网页 Demo

在仓库根目录创建虚拟环境并安装依赖：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

然后访问 <http://127.0.0.1:8000>。离线 Demo 使用仓库中的裂缝样例和预计算结果，不会运行真实 YOLO 推理。

## 准备 ONNX 模型

真实推理部分通过 OpenCV DNN 加载 YOLOv8-seg ONNX。仓库不包含训练权重。使用你有权使用的 YOLOv8 分割模型（例如自己训练的 `best.pt`），安装 Ultralytics 后导出：

```bash
pip install ultralytics
yolo export model=/path/to/your/best.pt format=onnx imgsz=640
```

把生成的 ONNX 文件放到 `models/best.onnx`，或设置 `CRACKSCOPE_MODEL` 指向它。Windows PowerShell 示例：

```powershell
$env:CRACKSCOPE_MODEL = "D:\models\best.onnx"
python run.py
```

树莓派上建议用电脑导出 ONNX 后再复制到设备。模型输入尺寸、类别数和分割头输出必须与当前后处理兼容；更换 YOLO 版本或模型结构时，需检查 `CrackSegmenter` 的输出解析。

## 环境变量

运行前可以复制 `.env.example` 作为配置参考。应用不会自动读取 `.env` 文件；在 PowerShell 中用 `$env:NAME="value"` 设置变量，在 Linux shell 中用 `export NAME="value"` 设置。常用变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CRACKSCOPE_MODEL` | `models/best.onnx` | ONNX 模型路径 |
| `CRACKSCOPE_CALIB` | `calibration/stereo_calibration.npz` | 双目标定文件 |
| `CRACKSCOPE_CAMERA_DEVICE` | `0` | OpenCV 相机索引 |
| `CRACKSCOPE_CAMERA_WIDTH` | `2560` | 左右拼接帧宽度 |
| `CRACKSCOPE_CAMERA_HEIGHT` | `960` | 左右拼接帧高度 |
| `CRACKSCOPE_MQTT_BROKER` | 空 | 留空时禁用 MQTT，使用 HTTP 轮询 |

## Python 入口

- `python run.py`：同时启动 FastAPI 仪表盘和 CM4 Agent。
- `python -m uvicorn src.main:app --host 0.0.0.0 --port 8000`：仅启动仪表盘/API。
- `python src/cm4_device_agent.py --base-url http://127.0.0.1:8000/api/crackscope`：单独启动 Agent。
