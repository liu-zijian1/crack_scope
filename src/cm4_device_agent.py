"""CM4 device agent for CrackScope.

Run this file on the Raspberry Pi CM4. It keeps the device online, pulls
commands from the local CrackScope service, executes camera actions locally, and sends
results back to the dashboard.
"""
import argparse
import json
import os
import socket
import time
import threading
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.crackscope import make_detection_payload, stereo_camera

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None


DEFAULT_BASE_URL = os.environ.get("CRACKSCOPE_BASE_URL", "http://127.0.0.1:8000/api/crackscope")
MQTT_BROKER = os.environ.get("CRACKSCOPE_MQTT_BROKER", "")
MQTT_PORT = int(os.environ.get("CRACKSCOPE_MQTT_PORT", "1883"))
MQTT_USERNAME = os.environ.get("CRACKSCOPE_MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("CRACKSCOPE_MQTT_PASSWORD", "")
MQTT_TOPIC_ROOT = os.environ.get("CRACKSCOPE_MQTT_TOPIC_ROOT", "crackscope").strip("/")
MQTT_PROJECT_ROOT = f"{MQTT_TOPIC_ROOT}/project"
MQTT_COMMAND_TOPIC = os.environ.get("CRACKSCOPE_MQTT_COMMAND_TOPIC", f"{MQTT_PROJECT_ROOT}/cm4/cmd")
MQTT_STATUS_TOPIC = os.environ.get("CRACKSCOPE_MQTT_STATUS_TOPIC", f"{MQTT_PROJECT_ROOT}/cm4/status")
MQTT_DISTANCE_TOPIC = os.environ.get("CRACKSCOPE_MQTT_DISTANCE_TOPIC", f"{MQTT_PROJECT_ROOT}/pi/distance")
MQTT_RESULT_TOPIC = os.environ.get("CRACKSCOPE_MQTT_RESULT_TOPIC", f"{MQTT_PROJECT_ROOT}/cm4/result")

def post_json(url, payload, timeout=20):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url, timeout=20):
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "cm4"


class DeviceAgent:
    def __init__(self, base_url, interval):
        self.base_url = base_url.rstrip("/")
        self.interval = interval
        self.last_heartbeat = 0
        self.mqtt_client = None
        self.seen_commands = set()
        self.http_backoff_until = 0
        self.preview_enabled = False
        self.last_preview = 0

    def mqtt_publish(self, topic, payload):
        if not self.mqtt_client:
            return
        try:
            self.mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        except Exception as exc:
            print(f"[agent] mqtt publish failed: {exc}", flush=True)

    def start_mqtt(self):
        if not MQTT_BROKER:
            print("[agent] MQTT not configured; HTTP polling is active", flush=True)
            return
        if mqtt is None:
            print("[agent] paho-mqtt not installed; HTTP polling fallback is active", flush=True)
            return

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                print(f"[agent] mqtt connected, subscribing {MQTT_COMMAND_TOPIC}", flush=True)
                client.subscribe(MQTT_COMMAND_TOPIC, qos=1)
            else:
                print(f"[agent] mqtt connect failed rc={rc}", flush=True)

        def on_message(client, userdata, msg):
            try:
                command = json.loads(msg.payload.decode("utf-8"))
                if not isinstance(command, dict):
                    return
                if "id" not in command or "command" not in command:
                    return
                threading.Thread(target=self.handle_command, args=(command,), daemon=True).start()
            except Exception as exc:
                print(f"[agent] bad mqtt command: {exc}", flush=True)

        client = mqtt.Client()
        if MQTT_USERNAME or MQTT_PASSWORD:
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        self.mqtt_client = client

    def heartbeat(self, status="online", extra=None):
        now = time.time()
        if now - self.last_heartbeat < 5 and status == "online":
            return
        payload = {
            "status": status,
            "device": hostname(),
            "camera_available": bool(stereo_camera.available),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if extra:
            payload.update(extra)
        try:
            post_json(self.base_url + "/device/agent/heartbeat", payload, timeout=3)
        except Exception as exc:
            print(f"[agent] heartbeat http failed: {exc}", flush=True)
        self.mqtt_publish(MQTT_STATUS_TOPIC, {"value": 1 if status != "offline" else 0, "unit": status})
        self.last_heartbeat = now

    def report(self, command_id, kind, payload):
        try:
            post_json(
                self.base_url + "/device/agent/result",
                {"command_id": command_id, "kind": kind, "payload": payload},
                timeout=10,
            )
        except Exception as exc:
            print(f"[agent] result http failed: {exc}", flush=True)
        # Publish result via MQTT so the platform receives it
        self.mqtt_publish(MQTT_RESULT_TOPIC, {
            "command_id": command_id,
            "kind": kind,
            "payload": payload,
        })
        if kind == "capture":
            result = payload.get("result") if isinstance(payload, dict) else {}
            width = result.get("width_mm") if isinstance(result, dict) else None
            if width is not None:
                self.mqtt_publish(MQTT_DISTANCE_TOPIC, {"value": float(width), "unit": "mm"})

    def next_command(self):
        if self.mqtt_client:
            return None
        if time.time() < self.http_backoff_until:
            return None
        data = get_json(self.base_url + "/device/agent/next", timeout=3)
        return data.get("command") if data.get("success") else None

    def handle_command(self, command):
        command_id = command["id"]
        name = command["command"]
        if command_id in self.seen_commands:
            return
        self.seen_commands.add(command_id)
        print(f"[agent] command #{command_id}: {name}", flush=True)
        if name == "ping":
            self.heartbeat("online", {"last_command": "ping"})
            self.report(command_id, "status", {"success": True, "message": "pong"})
            return
        if name == "camera_on":
            ok = stereo_camera.start_stream()
            self.preview_enabled = bool(ok)
            self.heartbeat("preview", {"camera_started": bool(ok)})
            self.report(command_id, "status", {"success": bool(ok), "message": "camera_on"})
            return
        if name == "camera_off":
            self.preview_enabled = False
            stereo_camera.stop_stream()
            self.heartbeat("online", {"camera_started": False})
            self.report(command_id, "status", {"success": True, "message": "camera_off"})
            return
        if name == "capture":
            self.heartbeat("capturing")
            payload = make_detection_payload(stream=False)
            payload["device"] = hostname()
            self.report(command_id, "capture", payload)
            self.heartbeat("online", {"last_capture": payload.get("timestamp", "")})
            return
        self.report(command_id, "error", {"success": False, "error": f"unknown command: {name}"})

    def maybe_publish_preview(self):
        if not self.preview_enabled:
            return
        now = time.time()
        if now - self.last_preview < 0.1:
            return
        self.last_preview = now
        try:
            from src.crackscope import make_preview_payload
            payload = make_preview_payload()
            if isinstance(payload, dict) and payload.get("success"):
                payload["device"] = hostname()
                self.report(None, "preview", payload)
        except Exception as exc:
            print(f"[agent] preview failed: {exc}", flush=True)

    def run(self):
        print(f"[agent] connecting to {self.base_url}", flush=True)
        self.start_mqtt()
        while True:
            try:
                self.heartbeat("online")
                try:
                    command = self.next_command()
                    if command:
                        self.handle_command(command)
                except (URLError, TimeoutError, OSError) as exc:
                    self.http_backoff_until = time.time() + 20
                    print(f"[agent] http polling paused: {exc}", flush=True)
                self.maybe_publish_preview()
            except (URLError, TimeoutError, OSError) as exc:
                print(f"[agent] network error: {exc}", flush=True)
                time.sleep(3)
            except Exception as exc:
                print(f"[agent] error: {exc}", flush=True)
                try:
                    self.heartbeat("error", {"error": str(exc)})
                except Exception:
                    pass
                time.sleep(3)
            time.sleep(self.interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--interval", type=float, default=0.12)
    args = parser.parse_args()
    DeviceAgent(args.base_url, args.interval).run()


if __name__ == "__main__":
    main()
