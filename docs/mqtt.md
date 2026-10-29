# 可选 MQTT 配置

本项目默认使用 HTTP 轮询控制 CM4 Agent，因此网页 Demo 和单机实机模式不需要 MQTT。只有需要连接自己的 MQTT Broker 时才设置以下环境变量：

```text
CRACKSCOPE_MQTT_BROKER=your-broker-host
CRACKSCOPE_MQTT_PORT=1883
CRACKSCOPE_MQTT_USERNAME=your-username
CRACKSCOPE_MQTT_PASSWORD=your-password
CRACKSCOPE_MQTT_TOPIC_ROOT=crackscope
```

这些变量必须在启动 FastAPI 后端和设备 Agent 的进程环境中设置。MQTT bridge 仅用于开发时把 Broker 消息写入本地 SQLite：

```bash
python src/local_mqtt_bridge.py
```

Broker、topic 和认证策略由部署者决定。公开仓库只给通用示例，不包含学校/组织的 Broker 地址或账号。生产环境应使用 TLS、最小权限账号和访问控制列表；如果 Broker 不支持 TLS，不要通过不可信网络发送口令。
