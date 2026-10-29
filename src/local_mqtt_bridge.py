"""Local MQTT bridge for CrackScope development.

Run this on the Windows development machine while `python run.py` is running.
It subscribes to your configured broker and writes messages into the same local
SQLite database that the FastAPI app reads.
"""
import json
import os
import sqlite3
import time

import paho.mqtt.client as mqtt


BROKER = os.environ.get("CRACKSCOPE_MQTT_BROKER", "")
PORT = int(os.environ.get("CRACKSCOPE_MQTT_PORT", "1883"))
USERNAME = os.environ.get("CRACKSCOPE_MQTT_USERNAME", "")
PASSWORD = os.environ.get("CRACKSCOPE_MQTT_PASSWORD", "")
TOPIC_ROOT = os.environ.get("CRACKSCOPE_MQTT_TOPIC_ROOT", "crackscope").strip("/")
TOPIC = os.environ.get("CRACKSCOPE_MQTT_SUB", f"{TOPIC_ROOT}/#")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "data", "crackscope.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS mqtt_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            payload TEXT,
            device_name TEXT,
            sensor_type TEXT,
            value REAL,
            unit TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    return conn


def parse_topic(topic):
    parts = topic.split("/")
    device = parts[2] if len(parts) > 2 else ""
    sensor = parts[3] if len(parts) > 3 else ""
    return device, sensor


def parse_payload(raw):
    try:
        data = json.loads(raw)
    except Exception:
        return None, ""
    value = data.get("value") if isinstance(data, dict) else None
    unit = data.get("unit", "") if isinstance(data, dict) else ""
    try:
        value = float(value)
    except Exception:
        value = None
    return value, unit


def on_connect(client, userdata, flags, rc):
    print(f"[bridge] connected rc={rc}, subscribing {TOPIC}", flush=True)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="replace")
    device, sensor = parse_topic(msg.topic)
    value, unit = parse_payload(raw)
    conn = get_db()
    conn.execute(
        """INSERT INTO mqtt_log (topic, payload, device_name, sensor_type, value, unit)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (msg.topic, raw, device, sensor, value, unit),
    )
    conn.commit()
    conn.close()
    print(f"[bridge] {msg.topic} {raw}", flush=True)


def main():
    if not BROKER:
        raise SystemExit("Set CRACKSCOPE_MQTT_BROKER before starting the bridge.")
    client = mqtt.Client()
    if USERNAME or PASSWORD:
        client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    print(f"[bridge] writing to {DB_PATH}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[bridge] stopping", flush=True)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
