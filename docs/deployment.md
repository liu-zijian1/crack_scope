# Raspberry Pi CM4 部署

## 1. 安装系统

用 Raspberry Pi Imager 将 Raspberry Pi OS Lite 64-bit 写入 microSD 卡，并在 Imager 设置中配置设备账户、网络和 SSH。启动后通过 SSH 登录，并升级系统：

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y python3 python3-venv python3-pip python3-opencv v4l-utils
```

## 2. 放置项目

在 CM4 上克隆公开仓库（仓库 URL 建好后替换示例地址）：

```bash
mkdir -p ~/crackscope
cd ~/crackscope
git clone https://github.com/OWNER/REPOSITORY.git .
```

创建环境并安装依赖：

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

确认 `calibration/stereo_calibration.npz` 存在。将你自己的 ONNX 模型放在 `models/best.onnx`，或设置 `CRACKSCOPE_MODEL`。模型没有包含在仓库里。

## 3. 设置配置

运行时可先在当前 shell 中设置变量：

```bash
export CRACKSCOPE_MODEL="$HOME/crackscope/models/best.onnx"
export CRACKSCOPE_CALIB="$HOME/crackscope/calibration/stereo_calibration.npz"
export CRACKSCOPE_CAMERA_DEVICE=0
export CRACKSCOPE_CAMERA_WIDTH=2560
export CRACKSCOPE_CAMERA_HEIGHT=960
```

MQTT 是可选项。默认 HTTP 控制无需 MQTT Broker；若启用 MQTT，再配置自己的 Broker 地址、用户名、密码和允许使用的 topic。不要把真实凭据写入源文件或提交 `.env`。

## 4. 启动与访问

```bash
cd ~/crackscope
source .venv/bin/activate
python run.py
```

在同一网络的电脑浏览器打开 `http://<CM4_IP>:8000`。Demo 模式可以先离线演示；关闭 Demo 后才会尝试调用相机、标定和模型进行实时检测。

## 5. 设置 systemd 开机启动（可选）

创建 `/etc/systemd/system/crackscope.service`，将 `User` 和路径改成设备上的实际账户：

```ini
[Unit]
Description=CrackScope stereo depth-camera crack segmentation and width measurement
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/crackscope
Environment=CRACKSCOPE_MODEL=/home/YOUR_USER/crackscope/models/best.onnx
Environment=CRACKSCOPE_CALIB=/home/YOUR_USER/crackscope/calibration/stereo_calibration.npz
ExecStart=/home/YOUR_USER/crackscope/.venv/bin/python /home/YOUR_USER/crackscope/run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并查看服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now crackscope
sudo systemctl status crackscope --no-pager
journalctl -u crackscope -f
```

## 排错

- **网页打不开：** 确认服务监听 8000 端口，电脑和 CM4 在可互通的网络中，并检查防火墙。
- **找不到相机：** 检查 `/dev/video*`、`v4l2-ctl --list-devices` 和相机索引；确认没有其他进程占用设备。
- **没有深度或宽度：** 检查相机是否输出左右拼接帧、标定文件是否对应当前分辨率和相机，以及左右图顺序。
- **模型未加载：** 检查 `CRACKSCOPE_MODEL` 文件存在，并且 ONNX 输出兼容当前分割后处理。
- **推理较慢：** CM4 CPU 推理速度取决于模型大小、图像尺寸和热设计；降低模型输入尺寸前，应验证测量精度。
