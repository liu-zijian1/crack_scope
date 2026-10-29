# 硬件搭建

## 硬件组成

本项目的实机配置为 Raspberry Pi CM4 2 GB Lite Wi-Fi、Waveshare CM4-IO-BASE-B 扩展板、DECXIN USB 同步双目相机、microSD 卡、稳定 5 V 供电和散热组件。设备清单也列在仓库首页。

## 连接顺序

1. 断开电源，把 CM4 安装到兼容的 IO 扩展板并固定散热组件。
2. 把已写入 Raspberry Pi OS Lite 64-bit 的 microSD 卡插入扩展板。
3. 将双目相机连接到扩展板 USB 接口。相机输出应为左右拼接的一帧图像；当前代码默认读取 2560×960，并把左右图像分别按 1280×960 处理。
4. 连接网络。设备和开发电脑在同一局域网时，可通过设备 IP 打开仪表盘。
5. 最后接通符合扩展板要求的电源。供电规格以扩展板和 CM4 厂商文档为准。

不同硬件版本的针脚、电源接口和 USB 速率可能不同，请依照对应产品手册操作。不要按本教程推断未标注的 GPIO 接线。

## 验证相机

在 Raspberry Pi OS 上先确认设备节点：

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
```

如果系统未安装 `v4l2-ctl`，可安装 `v4l-utils`。使用 OpenCV 确认相机索引和分辨率能读到 2560×960 拼接帧；如果相机驱动报告其他分辨率，在 `.env` 中调整 `CRACKSCOPE_CAMERA_WIDTH` 和 `CRACKSCOPE_CAMERA_HEIGHT`，并重新标定。

## 烧录系统

建议使用 Raspberry Pi Imager 选择 Raspberry Pi OS Lite (64-bit)，在烧录选项里设置用户名、密码和 Wi-Fi。不要把含有个人 Wi-Fi 配置的系统镜像放进 Git 仓库。首次启动后运行系统更新，再安装 Python 依赖，详见[部署教程](deployment.md)。
