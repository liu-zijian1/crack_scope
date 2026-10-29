# CrackScope：基于双目深度相机的裂缝分割与宽度测量

CrackScope 是一个可在 Raspberry Pi CM4 上部署的项目，作用是基于双目深度相机进行裂缝分割与宽度测量。项目把同步双目相机、立体视觉测距、YOLO 实例分割和网页仪表盘连起来，演示如何从左右图像估计裂缝的实际宽度。

本仓库面向希望复现整个项目的读者，包含应用源码、相机标定样例、离线演示数据，以及硬件搭建和设备部署说明。实机推理模型权重不随仓库发布；可以使用自己的 YOLO 分割权重导出 ONNX 模型。

> **许可证：** 项目原创代码与文档采用 MIT License，详见 [LICENSE](LICENSE)。第三方库、图片、模型及其他素材各自遵循其原有许可；参见 [第三方素材与依赖记录](THIRD_PARTY_NOTICES.md)。

## 先看演示

需要 Python 3.9 或更新版本。克隆项目后，在仓库根目录运行：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Linux / Raspberry Pi OS：

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器打开 <http://127.0.0.1:8000>。离线演示不需要连接相机、MQTT 或加载模型。

## 项目如何工作

```text
双目 USB 相机
  └─ 同步左右图像 → 校正与视差 → 深度估计
                         └─ YOLO 分割 → 裂缝像素宽度
                                         └─ 深度换算实际宽度（mm）
                                                   └─ FastAPI → 网页仪表盘
```

CM4 上的设备 Agent 负责打开相机、执行采集命令并把结果传给 FastAPI。设备控制默认使用本机 HTTP 轮询；MQTT 是可选项，需要用户自行配置 Broker 和凭据。

## 硬件清单

| 部件 | 本项目使用的配置 | 作用 |
|---|---|---|
| 主控 | Raspberry Pi Compute Module 4，2 GB，Lite Wi-Fi | 运行 Linux、视觉处理和 Web 服务 |
| 扩展板 | Waveshare CM4-IO-BASE-B | 为 CM4 提供 USB、存储和供电接口 |
| 相机 | DECXIN USB 同步双目相机 | 输出左右拼接图像；当前配置为 2560×960，每目 1280×960 |
| 存储 | 32 GB 或更大 microSD 卡 | 安装 Raspberry Pi OS 并存放程序 |
| 供电与散热 | 稳定 5 V 电源、与扩展板匹配的散热组件 | 支持相机采集和持续推理 |

不同 CM4 扩展板、相机和电源的接口可能不同。接线与供电前先核对各自厂商的硬件说明；相机必须能向 Linux 提供同步左右图像。更多配置与连接步骤见 [硬件搭建](docs/hardware.md)。

## 文档导航

- [硬件搭建与接线](docs/hardware.md)
- [相机标定与深度换算](docs/calibration.md)
- [软件安装、模型导出与本机运行](docs/software.md)
- [CM4 部署与开机启动](docs/deployment.md)
- [MQTT 可选配置与排错](docs/mqtt.md)
- [素材、模型和依赖许可记录](THIRD_PARTY_NOTICES.md)

## 目录结构

```text
src/                  FastAPI 服务、双目相机处理和 CM4 Agent
assets/               网页、离线 Demo 样例和界面资源
calibration/          当前相机的标定样例；不同相机应重新标定
docs/                 从硬件搭建到部署的复现教程
models/               模型目录说明；实机 ONNX 权重由使用者自行准备
scripts/              离线预测生成脚本
run.py                启动本地仪表盘和 CM4 设备 Agent
```

## 复现提示

- 首次运行用 Demo 模式熟悉界面；实机模式需要双目相机、该相机对应的标定文件，以及兼容的 ONNX 分割模型。
- 仓库的标定文件来自一台具体相机，仅适合作为流程样例。更换相机、镜头焦距或分辨率后，请重新标定。
- 模型文件（`.pt` / `.onnx`）、`.env`、数据库、树莓派系统镜像和个人课程文档不会纳入仓库。
- 项目原先使用的 MQTT 服务凭据已移除。不要把自己的 Broker 密码、Wi-Fi 密码或令牌提交到 Git。
- 网页中的部分硬件图片和图示需要按 [素材许可记录](THIRD_PARTY_NOTICES.md) 核对来源；公开前确认自己有权发布这些文件。

## 许可证

项目原创代码和教程按 MIT License 发布。此许可仅适用于项目原创内容；第三方依赖、图片、商标和硬件品牌各自遵循其原有许可或权利，不因本仓库许可而自动获得再许可。发布者应确认对随仓库分发的素材拥有相应权利，并保留必要的署名与许可证文本。
