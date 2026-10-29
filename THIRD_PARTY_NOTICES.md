# 第三方素材与依赖

项目原创代码与文档使用 [MIT License](LICENSE)。本文件记录第三方资源的边界；第三方资源不自动继承项目许可证。

## Python 依赖

依赖通过 `requirements.txt` 安装。FastAPI、Uvicorn、Pillow、NumPy、OpenCV 和 Paho MQTT 按各自上游许可证发布；使用或再分发时请遵守对应版本附带的许可证和通知。

## 浏览器资源

`assets/chart.umd.min.js` 是 Chart.js 的压缩发行文件。保留文件自带的许可证声明，并在再分发前核对对应 Chart.js 版本的上游许可证。

## 项目图片和模型

- `assets/offline_samples/`、`assets/paper_figures/`、`assets/stereo/`、`assets/yolo/` 和 `assets/hardware/` 中的内容是项目演示资源。发布前逐项确认每个文件为项目原创、已获许可，或已注明原始来源和许可；没有确认来源或再分发权的文件不要上传。
- `assets/szu_badge*.png` 和 `assets/szu_seal.png` 是学校标识，公开版不需要它们；请勿据此暗示学校为项目背书。
- `models/` 中不发布训练权重。使用者自行准备的模型可能有独立的数据、模型和训练框架许可。

## 核对清单

发布者应为每个非原创图像记录原始 URL/作者/许可，保留必要的署名和版权声明；无法确认授权的文件应在公开前移除或替换。项目名称和硬件品牌名称仅用于描述兼容设备，不表示与厂商存在关联。
