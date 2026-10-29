"""启动脚本 — 网页仪表盘 + 平台设备 agent 一起启动"""
import threading
import uvicorn

from src.cm4_device_agent import DeviceAgent


def start_agent():
    agent = DeviceAgent(
        "http://127.0.0.1:8000/api/crackscope",
        interval=0.12,
    )
    agent.run()


if __name__ == "__main__":
    t = threading.Thread(target=start_agent, daemon=True)
    t.start()
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)
