"""CrackScope platform sub-application for the IoT course showcase."""
import base64
import asyncio
import csv
import json
import os
import random
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

try:
    from PIL import Image, ImageDraw
except Exception:
    Image = None
    ImageDraw = None

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None


# Optional MQTT subscriber. HTTP polling is used when no Broker is configured.
def _start_mqtt_subscriber():
    if mqtt is None or not MQTT_BROKER:
        return

    def _on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(f"{MQTT_TOPIC_ROOT}/#")

    def _on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if not isinstance(payload, dict):
                return
            parts = msg.topic.split("/")
            device_name = parts[2] if len(parts) > 2 else ""
            sensor_type = parts[3] if len(parts) > 3 else ""
            conn = get_db()
            if sensor_type == "result":
                cmd_id = payload.get("command_id")
                kind = payload.get("kind") or "result"
                data = payload.get("payload") or {}
                conn.execute(
                    "INSERT INTO device_results (command_id, kind, payload) VALUES (?, ?, ?)",
                    (cmd_id, kind, json.dumps(data, ensure_ascii=False)),
                )
                if cmd_id:
                    conn.execute(
                        "UPDATE device_commands SET status='done', finished_at=CURRENT_TIMESTAMP WHERE id=?",
                        (cmd_id,),
                    )
                if kind == "capture":
                    result = data.get("result") if isinstance(data, dict) else {}
                    width = None if not isinstance(result, dict) else result.get("width_mm")
                    if width is not None:
                        conn.execute(
                            "INSERT INTO mqtt_log (topic, payload, device_name, sensor_type, value, unit) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (f"{MQTT_PROJECT_ROOT}/pi/distance", json.dumps({"value": float(width), "unit": "mm"}),
                             "pi", "distance", float(width), "mm"),
                        )
            conn.execute(
                "INSERT INTO mqtt_log (topic, payload, device_name, sensor_type, value, unit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (msg.topic, msg.payload.decode(), device_name, sensor_type,
                 payload.get("value"), payload.get("unit", "")),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _connect_loop():
        while True:
            try:
                client = mqtt.Client()
                if MQTT_USERNAME or MQTT_PASSWORD:
                    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
                client.on_connect = _on_connect
                client.on_message = _on_message
                client.connect(MQTT_BROKER, MQTT_PORT, 60)
                client.loop_forever()
            except Exception:
                time.sleep(10)

    threading.Thread(target=_connect_loop, daemon=True).start()


# CrackScope API routes are mounted below /api/crackscope.
router = APIRouter(prefix="/crackscope")

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE, "data", "crackscope.db")
MQTT_BROKER = os.environ.get("CRACKSCOPE_MQTT_BROKER", "")
MQTT_PORT = int(os.environ.get("CRACKSCOPE_MQTT_PORT", "1883"))
MQTT_USERNAME = os.environ.get("CRACKSCOPE_MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("CRACKSCOPE_MQTT_PASSWORD", "")
MQTT_TOPIC_ROOT = os.environ.get("CRACKSCOPE_MQTT_TOPIC_ROOT", "crackscope").strip("/")
MQTT_PROJECT_ROOT = f"{MQTT_TOPIC_ROOT}/project"
MQTT_COMMAND_TOPIC = os.environ.get("CRACKSCOPE_MQTT_COMMAND_TOPIC", f"{MQTT_PROJECT_ROOT}/cm4/cmd")

# 硬件清单接口的数据源，前端设备构成页会读取这组数据生成右侧卡片。
COMPONENTS = [
    {"id": "cm4", "name": "Raspberry Pi CM4", "model": "CM4 2GB Lite WiFi", "price": 195, "desc": "主控单元，负责运行 YOLO 裂缝分割模型、双目深度计算和系统调度", "icon": "mcu"},
    {"id": "board", "name": "微雪 CM4 IO 扩展板", "model": "CM4-IO-BASE-B", "price": 79, "desc": "提供 USB、TF 卡槽、电源接口，连接所有外设", "icon": "board"},
    {"id": "camera", "name": "USB 双目同步相机", "model": "400万 1080p 双目", "price": 210, "desc": "同步采集左右图像，用于立体视觉深度计算", "icon": "camera"},
    {"id": "tfcard", "name": "TF 存储卡", "model": "SanDisk 32GB Class10", "price": 28, "desc": "存放 Raspberry Pi OS 系统和模型文件", "icon": "storage"},
    {"id": "heatsink", "name": "散热片套件", "model": "铝制散热片 + 风扇", "price": 12, "desc": "CM4 推理时散热，防止降频", "icon": "cooling"},
    {"id": "power", "name": "充电宝", "model": "5V 2A 输出", "price": 49, "desc": "为 CM4 扩展板提供 5V 稳定供电", "icon": "power"},
]

stream_active = False
OFFLINE_SAMPLES = [
    {"file": "crack_01.jpg", "width_mm": 0.42, "distance_mm": 520.0},
    {"file": "crack_03.jpg", "width_mm": 0.88, "distance_mm": 520.0},
    {"file": "crack_06.jpg", "width_mm": 0.72, "distance_mm": 520.0},
    {"file": "crack_07.jpg", "width_mm": 0.74, "distance_mm": 520.0},
    {"file": "crack_08.jpg", "width_mm": 0.76, "distance_mm": 520.0},
    {"file": "crack_09.jpg", "width_mm": 0.92, "distance_mm": 520.0},
    {"file": "crack_10.jpg", "width_mm": 0.98, "distance_mm": 520.0},
    {"file": "crack_11.jpg", "width_mm": 0.96, "distance_mm": 520.0},
    {"file": "crack_12.jpg", "width_mm": 0.82, "distance_mm": 520.0},
    {"file": "crack_13.jpg", "width_mm": 1.08, "distance_mm": 520.0},
    {"file": "crack_14.jpg", "width_mm": 0.76, "distance_mm": 520.0},
    {"file": "crack_15.jpg", "width_mm": 0.72, "distance_mm": 520.0},
    {"file": "crack_16.jpg", "width_mm": 0.74, "distance_mm": 520.0},
    {"file": "crack_17.jpg", "width_mm": 0.70, "distance_mm": 520.0},
]
offline_sample_index = 0
offline_prediction_cache = None
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
OFFLINE_RESULTS_PATH = os.path.join(_HERE, "assets", "offline_results", "offline_results.json")
_OFFLINE_FALLBACK_PATHS = [
    OFFLINE_RESULTS_PATH,
    os.path.join(_HERE, "offline_results.json"),
    "assets/offline_results/offline_results.json",
]


class StereoCamera:
    """Small hardware adapter for the DECXIN side-by-side USB stereo camera."""

    def __init__(self):
        self.device = int(os.environ.get("CRACKSCOPE_CAMERA_DEVICE", "0"))
        self.width = int(os.environ.get("CRACKSCOPE_CAMERA_WIDTH", "2560"))
        self.height = int(os.environ.get("CRACKSCOPE_CAMERA_HEIGHT", "960"))
        self.stream_width = int(os.environ.get("CRACKSCOPE_STREAM_WIDTH", "640"))
        self.stream_height = int(os.environ.get("CRACKSCOPE_STREAM_HEIGHT", "240"))
        self.fallback_distance_mm = float(os.environ.get("CRACKSCOPE_FALLBACK_DISTANCE_MM", "0"))
        self.calib_path = os.environ.get(
            "CRACKSCOPE_CALIB",
            str(Path(_HERE) / "calibration" / "stereo_calibration.npz"),
        )
        self._calib = None
        self._maps = None
        self._stream_cap = None
        self._lock = threading.Lock()
        self._latest_stream_frame = None
        self._latest_stream_ts = 0.0

    @property
    def available(self):
        return cv2 is not None and os.path.exists(f"/dev/video{self.device}")

    def _open(self, width=None, height=None):
        width = width or self.width
        height = height or self.height
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def start_stream(self):
        with self._lock:
            if self._stream_cap is not None:
                return True
            if not self.available:
                return False
            cap = self._open(self.stream_width, self.stream_height)
            if not cap.isOpened():
                cap.release()
                return False
            self._stream_cap = cap
            return True

    def stop_stream(self):
        with self._lock:
            if self._stream_cap is not None:
                self._stream_cap.release()
                self._stream_cap = None

    def capture_stream(self, disparity=False):
        if self._stream_cap is None and not self.start_stream():
            return None
        frame = None
        # Drain buffered frames so the browser sees the newest camera image.
        with self._lock:
            if self._stream_cap is None:
                return None
            for _ in range(6):
                ok, current = self._stream_cap.read()
                if ok and current is not None:
                    frame = current
                else:
                    time.sleep(0.005)
        if frame is None:
            self.stop_stream()
            return None
        self._latest_stream_frame = frame.copy()
        self._latest_stream_ts = time.time()
        return self._frame_to_payload(frame, disparity=disparity)

    def latest_stream_capture(self, max_age=2.0, disparity=False):
        if self._latest_stream_frame is None:
            return None
        if time.time() - self._latest_stream_ts > max_age:
            return None
        return self._frame_to_payload(self._latest_stream_frame.copy(), disparity=disparity)

    def stream_jpeg_bytes(self, quality=65):
        frame_payload = self.capture_stream()
        if not frame_payload:
            return None
        left = frame_payload["left"]
        if cv2 is not None and np is not None:
            ok, buf = cv2.imencode(".jpg", left, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
            if ok:
                return buf.tobytes()
        image = Image.fromarray(left[:, :, ::-1]) if np is not None else left
        out = BytesIO()
        image.save(out, format="JPEG", quality=quality)
        return out.getvalue()

    def _frame_to_payload(self, frame, disparity=False):
        mid = frame.shape[1] // 2
        left_raw = frame[:, :mid]
        right_raw = frame[:, mid:]
        distance_mm = None
        valid_percent = None
        fx_px = None
        if disparity:
            depth = self._estimate_stream_depth(left_raw, right_raw)
            if depth:
                distance_mm = depth["distance_mm"]
                valid_percent = depth["valid_percent"]
                fx_px = depth["fx_px"]
        return {
            "left": self._resize_for_web(left_raw),
            "right": self._resize_for_web(right_raw),
            "distance_mm": distance_mm,
            "valid_percent": valid_percent,
            "rectified": False,
            "depth_rectified": bool(distance_mm),
            "fx_px": fx_px,
        }

    def _load_calibration(self, frame_size):
        if np is None or not os.path.exists(self.calib_path):
            return None
        if self._calib is None:
            self._calib = np.load(self.calib_path)
        image_size = tuple(int(x) for x in self._calib["image_size"])
        if image_size != frame_size:
            return None
        if self._maps is None:
            w, h = image_size
            c = self._calib
            self._maps = (
                cv2.initUndistortRectifyMap(c["K1"], c["D1"], c["R1"], c["P1"], (w, h), cv2.CV_32FC1),
                cv2.initUndistortRectifyMap(c["K2"], c["D2"], c["R2"], c["P2"], (w, h), cv2.CV_32FC1),
            )
        return self._calib

    def capture(self, rectify=True, disparity=False, fast=False, snap=False):
        if not self.available:
            return None
        width = self.stream_width if fast else self.width
        height = self.stream_height if fast else self.height
        cap = self._open(width, height)
        if not cap.isOpened():
            cap.release()
            return None
        frame = None
        if snap:
            # Snap mode: grab one full-res frame as fast as possible (~30ms).
            # Skip the exposure-scoring loop so the frame is closest to preview moment.
            for _ in range(4):
                ok, current = cap.read()
                if ok and current is not None:
                    frame = current
                time.sleep(0.005)
        else:
            best_frame = None
            best_score = -1.0
            read_count = 8 if fast else 24
            warmup = 2 if fast else 8
            for idx in range(read_count):
                ok, current = cap.read()
                if ok and current is not None:
                    frame = current
                    if idx >= warmup:
                        score = self._exposure_score(current)
                        if score > best_score:
                            best_frame = current
                            best_score = score
                time.sleep(0.03)
            if best_frame is not None:
                frame = best_frame
        cap.release()
        if frame is None:
            return None

        mid = frame.shape[1] // 2
        left = frame[:, :mid]
        right = frame[:, mid:]
        distance_mm = None
        valid_percent = None
        is_rectified = False

        raw_left = left
        raw_right = right

        if rectify and not fast:
            calib = self._load_calibration((left.shape[1], left.shape[0]))
            if calib is not None and self._maps is not None:
                (map1x, map1y), (map2x, map2y) = self._maps
                depth_left = cv2.remap(left, map1x, map1y, cv2.INTER_LINEAR)
                depth_right = cv2.remap(right, map2x, map2y, cv2.INTER_LINEAR)
                is_rectified = True
                if disparity:
                    distance_mm, valid_percent = self._estimate_distance(depth_left, depth_right, calib)

        return {
            "left": self._resize_for_web(raw_left),
            "right": self._resize_for_web(raw_right),
            "left_full": raw_left,
            "right_full": raw_right,
            "distance_mm": distance_mm,
            "valid_percent": valid_percent,
            "rectified": is_rectified,
            "depth_rectified": is_rectified,
            "fx_px": None if self._calib is None else float(self._calib["P1"][0, 0]),
            "rectified_left": depth_left if is_rectified else None,
            "rectified_right": depth_right if is_rectified else None,
        }

    def depth_at_mask(self, left_rect, right_rect, calib, binary_mask):
        """Return (median_depth_mm, valid_percent, z_map) inside the crack mask.

        z_map is a per-pixel depth array resized to match the original binary_mask
        resolution, so width sampling points can look up their own depth values.
        """
        if binary_mask is None or not binary_mask.any():
            dist, vp = self._estimate_distance(left_rect, right_rect, calib)
            return dist, vp, None
        orig_h, orig_w = binary_mask.shape[:2]
        gray_l = cv2.cvtColor(left_rect, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(right_rect, cv2.COLOR_BGR2GRAY)
        disp = self._compute_disparity(gray_l, gray_r)
        valid = disp > 0
        if not valid.any():
            return None, 0.0, None
        if binary_mask.shape[:2] != disp.shape[:2]:
            binary_mask = cv2.resize(binary_mask.astype(np.uint8), (disp.shape[1], disp.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
        points = cv2.reprojectImageTo3D(disp, calib["Q"])
        z = points[:, :, 2]
        # Resize z back to original mask resolution for per-point lookup
        if z.shape[:2] != (orig_h, orig_w):
            z_map = cv2.resize(z, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        else:
            z_map = z
        z_crack = valid & np.isfinite(z) & (z > 50) & (z < 3000) & binary_mask
        if z_crack.any():
            return float(np.median(z[z_crack])), float(z_crack.mean() * 100), z_map
        z_global = valid & np.isfinite(z) & (z > 50) & (z < 3000)
        if z_global.any():
            return float(np.median(z[z_global])), float(z_global.mean() * 100), z_map
        return None, float(valid.mean() * 100), z_map

    def _exposure_score(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean = float(gray.mean())
        saturated = float((gray > 245).mean())
        too_dark = float((gray < 8).mean())
        contrast = float(gray.std())
        score = contrast - saturated * 220.0 - too_dark * 60.0 - abs(mean - 118.0) * 0.25
        return score

    def _compute_disparity(self, gray_l, gray_r):
        """Compute disparity with CLAHE preprocessing for low-texture surfaces."""
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray_l = clahe.apply(gray_l)
        gray_r = clahe.apply(gray_r)
        stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=16 * 48,
            blockSize=5,
            P1=8 * 3 * 5 * 5,
            P2=32 * 3 * 5 * 5,
            disp12MaxDiff=3,
            uniquenessRatio=3,
            speckleWindowSize=10,
            speckleRange=1,
            preFilterCap=127,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )
        disp = stereo.compute(gray_l, gray_r).astype(np.float32) / 16.0
        return disp

    def _estimate_distance(self, left, right, calib):
        gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
        disp = self._compute_disparity(gray_l, gray_r)
        valid = disp > 0
        if not valid.any():
            return None, 0.0
        points = cv2.reprojectImageTo3D(disp, calib["Q"])
        z = points[:, :, 2]
        z_valid = valid & np.isfinite(z) & (z > 50) & (z < 3000)
        if not z_valid.any():
            return None, float(valid.mean() * 100)
        return float(np.median(z[z_valid])), float(z_valid.mean() * 100)

    def _estimate_stream_depth(self, left, right):
        if cv2 is None or np is None:
            return None
        if self._calib is None:
            if not os.path.exists(self.calib_path):
                return None
            self._calib = np.load(self.calib_path)
        calib_size = tuple(int(x) for x in self._calib["image_size"])
        calib = self._load_calibration(calib_size)
        if calib is None or self._maps is None:
            return None
        calib_w, calib_h = calib_size
        left_depth = cv2.resize(left, (calib_w, calib_h), interpolation=cv2.INTER_LINEAR)
        right_depth = cv2.resize(right, (calib_w, calib_h), interpolation=cv2.INTER_LINEAR)
        (map1x, map1y), (map2x, map2y) = self._maps
        left_depth = cv2.remap(left_depth, map1x, map1y, cv2.INTER_LINEAR)
        right_depth = cv2.remap(right_depth, map2x, map2y, cv2.INTER_LINEAR)
        distance_mm, valid_percent = self._estimate_distance(left_depth, right_depth, calib)
        fx_px = None
        try:
            fx_px = float(calib["P1"][0, 0]) * (left.shape[1] / calib_w)
        except Exception:
            fx_px = None
        return {
            "distance_mm": distance_mm,
            "valid_percent": valid_percent,
            "fx_px": fx_px,
        }

    def _resize_for_web(self, frame):
        h, w = frame.shape[:2]
        if w > 960:
            frame = cv2.resize(frame, (960, int(h * 960 / w)), interpolation=cv2.INTER_AREA)
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


stereo_camera = StereoCamera()


class CrackSegmenter:
    """YOLOv8-seg ONNX inference through OpenCV DNN."""

    def __init__(self):
        default_model = str(Path(_HERE) / "models" / "best.onnx")
        self.model_path = os.environ.get("CRACKSCOPE_MODEL", default_model)
        self.input_size = int(os.environ.get("CRACKSCOPE_MODEL_SIZE", "640"))
        self.conf_thres = float(os.environ.get("CRACKSCOPE_CONF_THRES", "0.05"))
        self.iou_thres = float(os.environ.get("CRACKSCOPE_IOU_THRES", "0.45"))
        self._net = None
        self._load_error = None

    @property
    def available(self):
        return cv2 is not None and np is not None and os.path.exists(self.model_path)

    def _load(self):
        if self._net is not None:
            return self._net
        if not self.available:
            self._load_error = "model or OpenCV unavailable"
            return None
        try:
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        except Exception as exc:
            self._load_error = str(exc)
            self._net = None
        return self._net

    def infer(self, image, distance_mm=None, fx_px=None):
        started = time.perf_counter()
        net = self._load()
        if net is None:
            return {
                "mask_image": image,
                "points": [],
                "width_mm": 0.0,
                "width_px": 0.0,
                "confidence": 0.0,
                "inference_ms": round((time.perf_counter() - started) * 1000, 1),
                "message": f"YOLO 模型未加载: {self._load_error}",
            }

        rgb = np.array(image.convert("RGB"))
        h0, w0 = rgb.shape[:2]
        blob_img, ratio, pad_x, pad_y = self._letterbox(rgb)
        blob = cv2.dnn.blobFromImage(blob_img, 1 / 255.0, (self.input_size, self.input_size), swapRB=False, crop=False)
        net.setInput(blob)
        outputs = net.forward(net.getUnconnectedOutLayersNames())
        if len(outputs) < 2:
            pred = np.squeeze(outputs[0])
            if pred.ndim == 2 and pred.shape[0] < pred.shape[1]:
                pred = pred.T
            return self._infer_detect_output(image, pred, rgb, ratio, pad_x, pad_y, distance_mm, fx_px, started)
        det_out, proto_out = outputs[0], outputs[1]
        pred = det_out[0].T
        proto = proto_out[0]

        class_count = pred.shape[1] - 4 - 32
        if class_count <= 0:
            return self._empty_result(image, started, "YOLO 输出维度异常")

        scores = pred[:, 4:4 + class_count].max(axis=1)
        class_ids = pred[:, 4:4 + class_count].argmax(axis=1)
        keep = scores >= self.conf_thres
        if not np.any(keep):
            return self._empty_result(image, started, "未检测到裂缝")

        boxes_xywh = pred[keep, :4]
        scores_keep = scores[keep]
        classes_keep = class_ids[keep]
        coeffs = pred[keep, 4 + class_count:]

        boxes = []
        for x, y, w, h in boxes_xywh:
            boxes.append([float(x - w / 2), float(y - h / 2), float(w), float(h)])
        idxs = cv2.dnn.NMSBoxes(boxes, scores_keep.tolist(), self.conf_thres, self.iou_thres)
        if len(idxs) == 0:
            return self._empty_result(image, started, "NMS 后无裂缝")

        idxs = np.array(idxs).reshape(-1)
        best = max(idxs, key=lambda i: float(scores_keep[i]))
        input_mask = self._decode_mask(coeffs[best], proto)
        mask = self._unletterbox_mask(input_mask, w0, h0, ratio, pad_x, pad_y)
        box = boxes[best]
        mask = self._crop_mask_to_box(mask, box, ratio, pad_x, pad_y, w0, h0)
        binary = mask > 0.5

        fallback_width_px = self._estimate_width_px(binary)
        points = self._sample_width_points(binary, distance_mm, fx_px)
        local_widths = [float(point["width_px"]) for point in points if float(point.get("width_px", 0)) > 0]
        width_px = float(np.median(local_widths)) if local_widths else fallback_width_px
        width_mm = 0.0
        if distance_mm and fx_px and width_px > 0:
            width_mm = float(width_px * distance_mm / fx_px)
        overlay = self._overlay(rgb, binary, points)
        return {
            "mask_image": Image.fromarray(overlay),
            "binary_mask": binary,
            "points": points,
            "width_mm": round(width_mm, 3),
            "width_px": round(float(width_px), 2),
            "confidence": round(float(scores_keep[best]), 3),
            "class_id": int(classes_keep[best]),
            "inference_ms": round((time.perf_counter() - started) * 1000, 1),
            "message": "YOLO 裂缝分割已接入" if width_mm else "YOLO 已检测裂缝；等待有效深度换算毫米",
        }

    def _infer_detect_output(self, image, pred, rgb, ratio, pad_x, pad_y, distance_mm, fx_px, started):
        if pred.ndim != 2:
            return self._empty_result(image, started, "YOLO 检测输出维度异常")
        class_count = pred.shape[1] - 4
        if class_count <= 0:
            return self._empty_result(image, started, "YOLO 检测输出维度异常")

        scores = pred[:, 4:4 + class_count].max(axis=1)
        class_ids = pred[:, 4:4 + class_count].argmax(axis=1)
        keep = scores >= self.conf_thres
        if not np.any(keep):
            return self._empty_result(image, started, "未检测到裂缝")

        h0, w0 = rgb.shape[:2]
        boxes_xywh = pred[keep, :4]
        scores_keep = scores[keep]
        classes_keep = class_ids[keep]
        boxes = []
        for cx, cy, bw, bh in boxes_xywh:
            x1 = (float(cx) - float(bw) / 2 - pad_x) / ratio
            y1 = (float(cy) - float(bh) / 2 - pad_y) / ratio
            ww = float(bw) / ratio
            hh = float(bh) / ratio
            x1 = max(0.0, min(float(w0 - 1), x1))
            y1 = max(0.0, min(float(h0 - 1), y1))
            ww = max(1.0, min(float(w0) - x1, ww))
            hh = max(1.0, min(float(h0) - y1, hh))
            boxes.append([int(x1), int(y1), int(ww), int(hh)])

        idxs = cv2.dnn.NMSBoxes(boxes, scores_keep.tolist(), self.conf_thres, self.iou_thres)
        if len(idxs) == 0:
            return self._empty_result(image, started, "NMS 后无裂缝")

        idxs = np.array(idxs).reshape(-1)
        best = max(idxs, key=lambda i: float(scores_keep[i]))
        x, y, bw, bh = boxes[best]
        x2 = min(w0 - 1, x + bw)
        y2 = min(h0 - 1, y + bh)
        width_px = float(max(1, min(bw, bh)))
        width_mm = 0.0
        if distance_mm and fx_px and width_px > 0:
            width_mm = float(width_px * distance_mm / fx_px)

        overlay = rgb.copy()
        cv2.rectangle(overlay, (x, y), (x2, y2), (96, 231, 160), 2)
        cv2.line(overlay, (x, y + bh // 2), (x2, y + bh // 2), (96, 231, 160), 2)
        cx = int(x + bw / 2)
        cy = int(y + bh / 2)
        cv2.circle(overlay, (cx, cy), 5, (64, 255, 190), -1)
        points = [{
            "x": cx,
            "y": cy,
            "width_px": round(width_px, 2),
            "width_mm": round(width_mm, 4),
        }]
        return {
            "mask_image": Image.fromarray(overlay),
            "binary_mask": None,
            "points": points,
            "width_mm": round(width_mm, 3),
            "width_px": round(width_px, 2),
            "confidence": round(float(scores_keep[best]), 3),
            "class_id": int(classes_keep[best]),
            "inference_ms": round((time.perf_counter() - started) * 1000, 1),
            "message": "YOLO 裂缝检测已接入；检测框短边用于宽度估算" if width_mm else "YOLO 已检测裂缝；等待有效深度换算毫米",
        }

    def _empty_result(self, image, started, message):
        return {
            "mask_image": image,
            "points": [],
            "width_mm": 0.0,
            "width_px": 0.0,
            "confidence": 0.0,
            "inference_ms": round((time.perf_counter() - started) * 1000, 1),
            "message": message,
        }

    def _letterbox(self, rgb):
        h, w = rgb.shape[:2]
        ratio = min(self.input_size / w, self.input_size / h)
        nw, nh = int(round(w * ratio)), int(round(h * ratio))
        resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        pad_x = (self.input_size - nw) // 2
        pad_y = (self.input_size - nh) // 2
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized
        return canvas, ratio, pad_x, pad_y

    def _decode_mask(self, coeff, proto):
        masks = coeff @ proto.reshape(32, -1)
        masks = 1.0 / (1.0 + np.exp(-masks))
        return masks.reshape(proto.shape[1], proto.shape[2])

    def _unletterbox_mask(self, mask, w0, h0, ratio, pad_x, pad_y):
        mask = cv2.resize(mask, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        x1, y1 = int(pad_x), int(pad_y)
        x2 = int(pad_x + round(w0 * ratio))
        y2 = int(pad_y + round(h0 * ratio))
        cropped = mask[y1:y2, x1:x2]
        return cv2.resize(cropped, (w0, h0), interpolation=cv2.INTER_LINEAR)

    def _crop_mask_to_box(self, mask, box, ratio, pad_x, pad_y, w0, h0):
        x, y, w, h = box
        x1 = int(max(0, (x - pad_x) / ratio))
        y1 = int(max(0, (y - pad_y) / ratio))
        x2 = int(min(w0, (x + w - pad_x) / ratio))
        y2 = int(min(h0, (y + h - pad_y) / ratio))
        cropped = np.zeros_like(mask)
        if x2 > x1 and y2 > y1:
            cropped[y1:y2, x1:x2] = mask[y1:y2, x1:x2]
        return cropped

    def _estimate_width_px(self, binary):
        if not binary.any():
            return 0.0
        mask = (binary.astype(np.uint8) * 255)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0
        contour = max(contours, key=cv2.contourArea)
        if len(contour) < 5:
            return 0.0
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
        major = max(float(rw), float(rh))
        minor = min(float(rw), float(rh))
        candidates = []
        if major > 1:
            candidates.append(area / major)
        if perimeter > 1:
            candidates.append(2.0 * area / perimeter)
        if minor > 0:
            candidates.append(minor)
        if not candidates:
            return 0.0
        return max(0.0, min(candidates))

    def _sample_width_points(self, binary, distance_mm=None, fx_px=None):
        if not binary.any():
            return []
        mask = (binary.astype(np.uint8) * 255)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        if float(dist.max()) <= 0:
            return []
        ridge = dist >= max(1.0, float(dist.max()) * 0.35)
        ys, xs = np.where(ridge)
        if len(xs) == 0:
            return []
        order = np.argsort(xs)
        xs = xs[order]
        ys = ys[order]
        sample_count = min(80, max(20, len(xs) // 150))
        indexes = np.linspace(0, len(xs) - 1, sample_count).astype(int)
        points = []
        seen = set()
        for idx in indexes:
            x = int(xs[idx])
            y = int(ys[idx])
            bucket = (x // 10, y // 10)
            if bucket in seen:
                continue
            seen.add(bucket)
            local_width_px = max(0.0, float(dist[y, x]) * 2.0)
            local_width_mm = 0.0
            if distance_mm and fx_px and local_width_px > 0:
                local_width_mm = float(local_width_px * distance_mm / fx_px)
            points.append({
                "x": x,
                "y": y,
                "width_px": round(local_width_px, 2),
                "width_mm": round(local_width_mm, 3),
            })
        return points

    def _overlay(self, rgb, binary, points=None):
        overlay = rgb.copy()
        green = np.zeros_like(rgb)
        green[:, :] = (96, 231, 160)
        overlay[binary] = (rgb[binary] * 0.45 + green[binary] * 0.55).astype(np.uint8)
        if points:
            bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
            for point in points:
                x, y = int(point["x"]), int(point["y"])
                cv2.circle(bgr, (x, y), 4, (64, 255, 190), -1)
                cv2.circle(bgr, (x, y), 7, (0, 0, 0), 1)
            overlay = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return overlay

    def refine_width_with_depth(self, detection, depth_map, fx_px):
        """Update every width point with its own per-pixel depth from z_map.

        Each sample point looks up the depth value at its (x, y) coordinate
        in depth_map and recomputes width_mm independently, so near points
        and far points no longer share a single global median depth.
        """
        points = detection.get("points", [])
        if not points or depth_map is None or not fx_px:
            return detection
        h, w = depth_map.shape[:2]
        new_widths_mm = []
        for point in points:
            x, y = int(point["x"]), int(point["y"])
            px = max(0, min(w - 1, x))
            py = max(0, min(h - 1, y))
            z = float(depth_map[py, px])
            if np.isfinite(z) and 50 < z < 3000 and point["width_px"] > 0:
                w_mm = float(point["width_px"] * z / fx_px)
                point["width_mm"] = round(w_mm, 3)
                point["depth_mm"] = round(z, 1)
                new_widths_mm.append(w_mm)
        if new_widths_mm:
            detection["width_mm"] = round(float(np.median(new_widths_mm)), 3)
            detection["message"] = "逐点深度精修完成"
        return detection


crack_segmenter = CrackSegmenter()


def get_db():
    # MQTT telemetry is stored in the local CrackScope database.
    # 这里按课程要求使用基于 __file__ 的绝对路径，避免部署后相对路径失效。
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    conn.execute(
        """CREATE TABLE IF NOT EXISTS device_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            payload TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            claimed_at DATETIME,
            finished_at DATETIME
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS device_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_id INTEGER,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS device_heartbeat (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            status TEXT,
            payload TEXT DEFAULT '{}',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    return conn


def row_to_command(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "command": row["command"],
        "payload": json.loads(row["payload"] or "{}"),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def latest_device_result(kind=None):
    conn = get_db()
    if kind:
        row = conn.execute(
            "SELECT * FROM device_results WHERE kind=? ORDER BY id DESC LIMIT 1",
            (kind,),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM device_results ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None
    try:
        payload = json.loads(row["payload"])
    except Exception:
        payload = {}
    return {
        "id": row["id"],
        "command_id": row["command_id"],
        "kind": row["kind"],
        "payload": payload,
        "created_at": row["created_at"],
    }


def enqueue_device_command(command, payload=None):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO device_commands (command, payload) VALUES (?, ?)",
        (command, json.dumps(payload or {}, ensure_ascii=False)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM device_commands WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return row_to_command(row)


def publish_mqtt_command(command_item):
    if mqtt is None or not MQTT_BROKER or not command_item:
        return False
    payload = json.dumps(
        {
            "id": command_item["id"],
            "command": command_item["command"],
            "payload": command_item.get("payload") or {},
            "created_at": command_item.get("created_at"),
        },
        ensure_ascii=False,
    )
    client = mqtt.Client()
    if MQTT_USERNAME or MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(MQTT_BROKER, MQTT_PORT, 10)
    client.publish(MQTT_COMMAND_TOPIC, payload, qos=1)
    client.disconnect()
    return True


def generate_crack_image(width=640, height=480, crack_width=0.35, with_mask=True):
    # 演示用裂缝图像生成器：
    # 1. 生成混凝土纹理背景
    # 2. 随机生成裂缝折线路径
    # 3. 可选叠加绿色分割 mask，模拟 YOLOv8-seg 输出
    img = Image.new("RGB", (width, height), (45, 45, 48))
    draw = ImageDraw.Draw(img)
    for _ in range(3000):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        v = random.randint(0, 25)
        draw.point((x, y), fill=(45 + v, 45 + v, 46 + v))

    cx = width // 2
    points = [(cx - 100, random.randint(80, 150))]
    for _ in range(20):
        lx, ly = points[-1]
        nx, ny = lx + random.randint(5, 35), ly + random.randint(-15, 15)
        if 0 < nx < width and 0 < ny < height:
            points.append((nx, ny))

    pw = max(1, int(crack_width * 15))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(18, 18, 20), width=pw + 2)
        draw.line([points[i], points[i + 1]], fill=(12, 12, 14), width=pw)

    mask_img = img.copy()
    if with_mask:
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for i in range(len(points) - 1):
            p1, p2 = points[i], points[i + 1]
            for dx in range(-6, 7):
                for dy in range(-6, 7):
                    if dx * dx + dy * dy < 36:
                        od.line([(p1[0] + dx, p1[1] + dy), (p2[0] + dx, p2[1] + dy)], fill=(96, 231, 160, 90), width=1)
        mask_img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img, mask_img


def image_to_b64(img, fmt="PNG", quality=80):
    buf = BytesIO()
    if fmt.upper() == "JPEG":
        img.save(buf, format=fmt, quality=quality, optimize=True)
    else:
        img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def load_offline_sample(sample):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "offline_samples", sample["file"])
    return Image.open(path).convert("RGB")


def build_offline_payload(sample, raw_img, stream=False):
    started = time.perf_counter()
    distance_mm = sample["distance_mm"]
    # Offline demo uses the same sample as left/right view and a fixed depth.
    # This keeps the UI flow identical to the live binocular pipeline.
    fx_px = 640.0
    detection = crack_segmenter.infer(raw_img, distance_mm=distance_mm, fx_px=fx_px)
    if detection["width_mm"] <= 0:
        detection["width_mm"] = sample["width_mm"]
        detection["width_px"] = round(sample["width_mm"] * fx_px / distance_mm, 2)
        detection["message"] = "离线样例展示；使用预设宽度"
        detection["confidence"] = detection.get("confidence") or 0.86
        overlay = raw_img.copy()
        draw = ImageDraw.Draw(overlay)
        w, h = overlay.size
        if "01" in sample["file"] or "02" in sample["file"]:
            y = int(h * 0.52)
            line = [(int(w * 0.12), y), (int(w * 0.88), y)]
            point = {"x": int(w * 0.5), "y": y, "width_px": detection["width_px"], "width_mm": detection["width_mm"]}
        else:
            x = int(w * 0.52)
            line = [(x, int(h * 0.12)), (x, int(h * 0.88))]
            point = {"x": x, "y": int(h * 0.5), "width_px": detection["width_px"], "width_mm": detection["width_mm"]}
        draw.line(line, fill=(96, 231, 160), width=4)
        px, py = point["x"], point["y"]
        draw.ellipse((px - 7, py - 7, px + 7, py + 7), fill=(64, 255, 190), outline=(0, 0, 0), width=2)
        label = f'{detection["width_mm"]:.2f} mm'
        draw.rectangle((px + 12, py - 22, px + 118, py + 6), fill=(8, 14, 12), outline=(96, 231, 160), width=1)
        draw.text((px + 18, py - 18), label, fill=(180, 255, 210))
        detection["mask_image"] = overlay
        detection["points"] = [point]
    fmt = "JPEG"
    images = {
        "left_mask": image_to_b64(detection["mask_image"], fmt=fmt, quality=82),
        "right_mask": image_to_b64(detection["mask_image"], fmt=fmt, quality=82),
    }
    if not stream:
        raw_b64 = image_to_b64(raw_img, fmt=fmt, quality=88)
        images.update({"left_raw": raw_b64, "right_raw": raw_b64})
    result = {
        "primary_side": "left",
        "width_mm": round(float(detection["width_mm"]), 3),
        "width_px": round(float(detection["width_px"]), 2),
        "confidence": round(float(detection.get("confidence", 0.86)), 3),
        "class_id": detection.get("class_id"),
        "inference_ms": detection.get("inference_ms", 0.0),
        "total_ms": round((time.perf_counter() - started) * 1000, 1),
        "distance_mm": distance_mm,
        "valid_depth_percent": 100.0,
        "rectified": False,
        "message": detection["message"],
    }
    side = {
        "width_mm": result["width_mm"],
        "width_px": result["width_px"],
        "confidence": result["confidence"],
        "message": result["message"],
    }
    return {
        "success": True,
        "source": "offline",
        "sample": sample["file"],
        "image_format": "jpeg",
        "images": images,
        "width_points": {
            "left": detection.get("points", []),
            "right": detection.get("points", []),
        },
        "side_results": {"left": side, "right": side},
        "result": result,
        "timestamp": time.strftime("%H:%M:%S"),
    }


def get_offline_prediction_cache():
    global offline_prediction_cache
    if offline_prediction_cache is not None:
        return offline_prediction_cache
    # 1. Try embedded data via import
    try:
        from _offline_data import OFFLINE_DEMO_DATA
        if OFFLINE_DEMO_DATA:
            offline_prediction_cache = list(OFFLINE_DEMO_DATA)
            return offline_prediction_cache
    except Exception:
        pass
    # 1b. Try loading _offline_data.py from file path directly
    try:
        _data_path = os.path.join(_HERE, "_offline_data.py")
        if os.path.exists(_data_path):
            _ns = {}
            exec(open(_data_path, encoding="utf-8").read(), _ns)
            if _ns.get("OFFLINE_DEMO_DATA"):
                offline_prediction_cache = list(_ns["OFFLINE_DEMO_DATA"])
                return offline_prediction_cache
    except Exception:
        pass
    # 2. Try loading pre-built cache from file
    for cache_path in _OFFLINE_FALLBACK_PATHS:
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    offline_prediction_cache = json.load(f)
                if offline_prediction_cache:
                    return offline_prediction_cache
            except Exception:
                pass
    # Fallback: try building from samples (needs PIL + offline sample images)
    try:
        if Image is not None:
            offline_prediction_cache = []
            for sample in OFFLINE_SAMPLES:
                raw_img = load_offline_sample(sample)
                offline_prediction_cache.append(build_offline_payload(sample, raw_img, stream=False))
            os.makedirs(os.path.dirname(OFFLINE_RESULTS_PATH), exist_ok=True)
            with open(OFFLINE_RESULTS_PATH, "w", encoding="utf-8") as f:
                json.dump(offline_prediction_cache, f, ensure_ascii=False)
            return offline_prediction_cache
    except Exception:
        pass
    # Last resort: return empty list, frontend will handle
    return []


def make_offline_detection_payload(stream=False, index=None):
    global offline_sample_index
    try:
        cache = get_offline_prediction_cache()
        if not cache:
            return offline_test()
        if index is None:
            index = offline_sample_index % len(cache)
            offline_sample_index += 1
        payload = json.loads(json.dumps(cache[index % len(cache)], ensure_ascii=False))
    except Exception:
        return offline_test()
    if stream:
        payload["images"].pop("left_raw", None)
        payload["images"].pop("right_raw", None)
    payload["offline_index"] = index % len(cache)
    payload["timestamp"] = time.strftime("%H:%M:%S")
    return payload


def b64_to_image_bytes(data_url_or_b64):
    if not data_url_or_b64:
        return b""
    payload = data_url_or_b64.split(",", 1)[1] if "," in data_url_or_b64[:40] else data_url_or_b64
    return base64.b64decode(payload)


def detection_summary_csv(payload):
    text = []
    result = payload.get("result") or {}
    text.append(["field", "value"])
    for key in ["timestamp", "source"]:
        text.append([key, payload.get(key, "")])
    for key in ["width_mm", "width_px", "confidence", "inference_ms", "total_ms", "distance_mm", "message"]:
        text.append([key, result.get(key, "")])
    text.append([])
    text.append(["side", "x", "y", "width_mm", "width_px"])
    for side, points in (payload.get("width_points") or {}).items():
        for point in points or []:
            text.append([side, point.get("x", ""), point.get("y", ""), point.get("width_mm", ""), point.get("width_px", "")])
    csv_text = "\ufeff"
    import io
    string_buf = io.StringIO()
    writer = csv.writer(string_buf)
    writer.writerows(text)
    csv_text += string_buf.getvalue()
    wrapper = BytesIO()
    wrapper.write(csv_text.encode("utf-8"))
    return wrapper.getvalue()


def make_preview_payload():
    started = time.perf_counter()
    camera_frame = stereo_camera.capture_stream()
    if not camera_frame:
        return JSONResponse({"success": False, "error": "camera not available"}, status_code=503)
    fmt = "JPEG"
    return {
        "success": True,
        "source": "camera",
        "image_format": "jpeg",
        "images": {
            "left_mask": image_to_b64(camera_frame["left"], fmt=fmt, quality=70),
            "right_mask": image_to_b64(camera_frame["right"], fmt=fmt, quality=70),
        },
        "result": {
            "width_mm": 0.0,
            "width_px": 0.0,
            "confidence": 0.0,
            "inference_ms": 0.0,
            "total_ms": round((time.perf_counter() - started) * 1000, 1),
            "distance_mm": None,
            "rectified": False,
            "message": "相机实时预览中",
        },
        "timestamp": time.strftime("%H:%M:%S"),
    }


def make_detection_payload(stream=False, prefer_stream_frame=False):
    # 前端拍照检测和实时检测共用这一套返回格式：
    # images 存左右相机图像，result 存宽度、置信度、推理耗时。
    started = time.perf_counter()
    using_preview_frame = stream
    if using_preview_frame:
        camera_frame = stereo_camera.capture_stream(disparity=not stream)
    elif prefer_stream_frame:
        camera_frame = stereo_camera.latest_stream_capture(max_age=2.0, disparity=True)
        if camera_frame is None:
            camera_frame = stereo_camera.capture(rectify=True, disparity=True, fast=True)
    else:
        # Snap: stop stream, grab ONE full-res frame immediately, then restart stream.
        stereo_camera.stop_stream()
        camera_frame = stereo_camera.capture(rectify=True, disparity=True, snap=True)
        stereo_camera.start_stream()
    if camera_frame:
        distance_mm = camera_frame["distance_mm"]
        fx_px = camera_frame.get("fx_px")
        if fx_px is None and not using_preview_frame and stereo_camera._calib is not None:
            try:
                fx_px = float(stereo_camera._calib["P1"][0, 0])
            except Exception:
                fx_px = None
        # Use full-res images for YOLO if available (snap mode), fall back to web-resized
        left_for_infer = camera_frame.get("left_full")
        right_for_infer = camera_frame.get("right_full")
        if left_for_infer is not None and cv2 is not None:
            left_for_infer = Image.fromarray(cv2.cvtColor(left_for_infer, cv2.COLOR_BGR2RGB))
            right_for_infer = Image.fromarray(cv2.cvtColor(right_for_infer, cv2.COLOR_BGR2RGB))
        else:
            left_for_infer = camera_frame["left"]
            right_for_infer = camera_frame["right"]
        left_detection = crack_segmenter.infer(left_for_infer, distance_mm=distance_mm, fx_px=fx_px)
        right_detection = crack_segmenter.infer(right_for_infer, distance_mm=distance_mm, fx_px=fx_px)
        # Refine: query depth specifically at crack mask location
        rect_l = camera_frame.get("rectified_left")
        rect_r = camera_frame.get("rectified_right")
        crack_mask = left_detection.get("binary_mask")
        if rect_l is not None and rect_r is not None and crack_mask is not None and crack_mask.any() and stereo_camera._calib is not None:
            try:
                local_dist, _, z_map = stereo_camera.depth_at_mask(rect_l, rect_r, stereo_camera._calib, crack_mask)
                if z_map is not None and fx_px:
                    left_detection = crack_segmenter.refine_width_with_depth(left_detection, z_map, fx_px)
                elif local_dist is not None and fx_px and left_detection["width_px"] > 0:
                    local_w = float(left_detection["width_px"] * local_dist / fx_px)
                    left_detection["width_mm"] = round(local_w, 3)
                    left_detection["message"] = "裂缝局部深度=%.0fmm" % local_dist
            except Exception:
                pass
        primary_detection = left_detection
        fmt = "JPEG"
        images = {
            "left_mask": image_to_b64(left_detection["mask_image"], fmt=fmt, quality=75),
            "right_mask": image_to_b64(right_detection["mask_image"], fmt=fmt, quality=75),
        }
        if not stream:
            images.update({
                "left_raw": image_to_b64(camera_frame["left"], fmt=fmt, quality=82),
                "right_raw": image_to_b64(camera_frame["right"], fmt=fmt, quality=82),
            })
        return {
            "success": True,
            "source": "camera",
            "image_format": "jpeg",
            "images": images,
            "width_points": {
                "left": left_detection.get("points", []),
                "right": right_detection.get("points", []),
            },
            "side_results": {
                "left": {
                    "width_mm": left_detection["width_mm"],
                    "width_px": left_detection["width_px"],
                    "confidence": left_detection["confidence"],
                    "message": left_detection["message"],
                },
                "right": {
                    "width_mm": right_detection["width_mm"],
                    "width_px": right_detection["width_px"],
                    "confidence": right_detection["confidence"],
                    "message": right_detection["message"],
                },
            },
            "result": {
                "primary_side": "left",
                "width_mm": primary_detection["width_mm"],
                "width_px": primary_detection["width_px"],
                "confidence": primary_detection["confidence"],
                "class_id": primary_detection.get("class_id"),
                "inference_ms": round(left_detection["inference_ms"] + right_detection["inference_ms"], 1),
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "distance_mm": None if distance_mm is None else round(distance_mm, 1),
                "valid_depth_percent": camera_frame["valid_percent"],
                "rectified": camera_frame["rectified"],
                "message": primary_detection["message"],
            },
            "timestamp": time.strftime("%H:%M:%S"),
        }

    return make_offline_detection_payload(stream=stream)


@router.get("/components")
def components():
    return COMPONENTS


@router.post("/capture")
def capture():
    # 本地运行时保留直接拍照检测；部署到课程平台后建议使用 /device/command/capture。
    return make_detection_payload(stream=False, prefer_stream_frame=True)


@router.get("/offline/test")
def offline_test():
    """Minimal test endpoint — returns hardcoded demo data."""
    return {
        "success": True,
        "source": "offline",
        "sample": "test",
        "image_format": "jpeg",
        "images": {
            "left_mask": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABsSFBcUERsXFhceHBsgKEIrKCUlKFE6PTBCYFVlZF9VXVtqeJmBanGQc1tdhbWGkJ6jq62rZ4C8ybqmx5moq6T/2wBDARseHigjKE4rK06kbl1upKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKT/wAARCADwAUADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDFooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k=",
            "right_mask": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABsSFBcUERsXFhceHBsgKEIrKCUlKFE6PTBCYFVlZF9VXVtqeJmBanGQc1tdhbWGkJ6jq62rZ4C8ybqmx5moq6T/2wBDARseHigjKE4rK06kbl1upKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKT/wAARCADwAUADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDFooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k=",
            "left_raw": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABsSFBcUERsXFhceHBsgKEIrKCUlKFE6PTBCYFVlZF9VXVtqeJmBanGQc1tdhbWGkJ6jq62rZ4C8ybqmx5moq6T/2wBDARseHigjKE4rK06kbl1upKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKT/wAARCADwAUADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDFooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k=",
            "right_raw": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABsSFBcUERsXFhceHBsgKEIrKCUlKFE6PTBCYFVlZF9VXVtqeJmBanGQc1tdhbWGkJ6jq62rZ4C8ybqmx5moq6T/2wBDARseHigjKE4rK06kbl1upKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKT/wAARCADwAUADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDFooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k=",
        },
        "result": {
            "width_mm": 0.42,
            "width_px": 3.5,
            "confidence": 0.85,
            "inference_ms": 50.0,
            "total_ms": 60.0,
            "distance_mm": 520.0,
            "message": "离线演示测试OK",
        },
        "timestamp": "00:00:00",
    }


@router.get("/offline/list")
def offline_list():
    cache = get_offline_prediction_cache()
    return {
        "success": True,
        "count": len(cache),
        "items": [
            {
                "index": idx,
                "sample": item.get("sample"),
                "width_mm": item.get("result", {}).get("width_mm"),
                "distance_mm": item.get("result", {}).get("distance_mm"),
                "message": item.get("result", {}).get("message"),
            }
            for idx, item in enumerate(cache)
        ],
    }


@router.get("/offline/next")
def offline_next():
    return make_offline_detection_payload(stream=False)


@router.get("/offline/{index}")
def offline_by_index(index: int):
    return make_offline_detection_payload(stream=False, index=index)


@router.get("/device/status")
def device_status():
    conn = get_db()
    hb = conn.execute("SELECT * FROM device_heartbeat WHERE id=1").fetchone()
    mqtt_status = conn.execute(
        "SELECT * FROM mqtt_log WHERE device_name='cm4' AND sensor_type='status' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    pending = conn.execute("SELECT COUNT(*) AS c FROM device_commands WHERE status='pending'").fetchone()["c"]
    last_command = conn.execute("SELECT * FROM device_commands ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    payload = {}
    online = False
    if hb:
        try:
            payload = json.loads(hb["payload"] or "{}")
        except Exception:
            payload = {}
        try:
            ts = datetime.strptime(hb["updated_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            online = (time.time() - ts) < 20
        except Exception:
            online = False
    if not online and mqtt_status:
        try:
            ts = datetime.strptime(mqtt_status["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            online = (time.time() - ts) < 20 and float(mqtt_status["value"] or 0) > 0
            payload = {
                "device": mqtt_status["device_name"],
                "sensor_type": mqtt_status["sensor_type"],
                "value": mqtt_status["value"],
                "unit": mqtt_status["unit"],
                "time": mqtt_status["timestamp"],
                "source": "mqtt_log",
            }
        except Exception:
            online = False
    return {
        "success": True,
        "online": online,
        "status": hb["status"] if hb else "offline",
        "updated_at": hb["updated_at"] if hb else "",
        "payload": payload,
        "pending": pending,
        "last_command": row_to_command(last_command),
        "latest_result": latest_device_result(),
    }


@router.post("/device/command/{command}")
def device_command(command: str, payload: dict | None = None):
    allowed = {"camera_on", "camera_off", "capture", "ping"}
    if command not in allowed:
        return JSONResponse({"success": False, "error": "unknown command"}, status_code=400)
    item = enqueue_device_command(command, payload)
    mqtt_sent = publish_mqtt_command(item)
    return {"success": True, "command": item, "mqtt_sent": mqtt_sent}


@router.get("/device/result/latest")
def device_result_latest(kind: str | None = None):
    result = latest_device_result(kind)
    if not result:
        return {"success": False, "result": None}
    return {"success": True, "result": result}


@router.get("/device/agent/next")
def device_agent_next():
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM device_commands WHERE status='pending' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE device_commands SET status='claimed', claimed_at=CURRENT_TIMESTAMP WHERE id=?",
            (row["id"],),
        )
        conn.commit()
    conn.close()
    command = row_to_command(row)
    return {"success": True, "command": command}


@router.post("/device/agent/result")
def device_agent_result(payload: dict):
    command_id = payload.get("command_id")
    kind = payload.get("kind") or "result"
    data = payload.get("payload") or {}
    conn = get_db()
    conn.execute(
        "INSERT INTO device_results (command_id, kind, payload) VALUES (?, ?, ?)",
        (command_id, kind, json.dumps(data, ensure_ascii=False)),
    )
    if command_id:
        conn.execute(
            "UPDATE device_commands SET status='done', finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (command_id,),
        )
    result = data.get("result") if isinstance(data, dict) else None
    width = None if not isinstance(result, dict) else result.get("width_mm")
    if width is not None:
        conn.execute(
            """INSERT INTO mqtt_log (topic, payload, device_name, sensor_type, value, unit)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                f"{MQTT_PROJECT_ROOT}/pi/distance",
                json.dumps({"value": width, "unit": "mm"}, ensure_ascii=False),
                "pi",
                "distance",
                float(width),
                "mm",
            ),
        )
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/device/agent/heartbeat")
def device_agent_heartbeat(payload: dict):
    status = payload.get("status") or "online"
    conn = get_db()
    conn.execute(
        """INSERT INTO device_heartbeat (id, status, payload, updated_at)
           VALUES (1, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(id) DO UPDATE SET
             status=excluded.status,
             payload=excluded.payload,
             updated_at=CURRENT_TIMESTAMP""",
        (status, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/capture/download")
def capture_download(payload: dict):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    buf = BytesIO()
    images = payload.get("images") or {}
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        name_map = {
            "left_raw": "left_raw.jpg",
            "right_raw": "right_raw.jpg",
            "left_mask": "left_overlay.jpg",
            "right_mask": "right_overlay.jpg",
        }
        for key, filename in name_map.items():
            if images.get(key):
                zf.writestr(filename, b64_to_image_bytes(images[key]))
        zf.writestr("width_measurements.csv", detection_summary_csv(payload))
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="crackscope_{stamp}.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


@router.post("/stream/start")
def start_stream():
    global stream_active
    stream_active = True
    stereo_camera.start_stream()
    return {"success": True}


@router.post("/stream/stop")
def stop_stream():
    global stream_active
    stream_active = False
    stereo_camera.stop_stream()
    return {"success": True}


@router.get("/stream/frame")
def stream_frame():
    # HTTP 轮询备用接口：当前端 WebSocket 不可用时，每隔一段时间拉一帧。
    if not stream_active:
        return JSONResponse({"error": "stream not active"}, status_code=400)
    return make_detection_payload(stream=True)


@router.get("/camera/status")
def camera_status():
    return {
        "available": stereo_camera.available,
        "device": f"/dev/video{stereo_camera.device}",
        "calibration_loaded": os.path.exists(stereo_camera.calib_path),
        "calibration_path": stereo_camera.calib_path,
        "width": stereo_camera.width,
        "height": stereo_camera.height,
    }


@router.post("/camera/preview/start")
def preview_start():
    ok = stereo_camera.start_stream()
    return {"success": bool(ok), "available": stereo_camera.available}


@router.post("/camera/preview/stop")
def preview_stop():
    stereo_camera.stop_stream()
    return {"success": True}


@router.get("/camera/preview/frame")
def preview_frame():
    return make_preview_payload()


@router.get("/camera/stream.mjpg")
def camera_mjpeg_stream():
    def frames():
        while True:
            payload = make_preview_payload()
            if not isinstance(payload, dict) or not payload.get("success"):
                time.sleep(0.05)
                continue
            jpg = b64_to_image_bytes(payload["images"]["left_mask"])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-store\r\n\r\n" + jpg + b"\r\n"
            )
            time.sleep(0.03)

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    # 实时检测主通道：前端只发送一次 start，后端随后连续推送帧。
    global stream_active
    await ws.accept()
    stream_active = True
    try:
        try:
            data = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
            if data == "stop":
                return
        except asyncio.TimeoutError:
            pass
        while stream_active:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=0.01)
                if data == "stop":
                    break
            except asyncio.TimeoutError:
                pass
            await ws.send_json(make_detection_payload(stream=True))
            await asyncio.sleep(0.12)
    except WebSocketDisconnect:
        pass
    finally:
        stream_active = False


@router.get("/latest")
def latest():
    # MQTT 数据接口：读取最近一条 distance 传感器数据。
    # 后续接真实硬件时，前端可从这里显示真实裂缝/距离数据。
    conn = get_db()
    row = conn.execute(
        "SELECT value, unit, timestamp FROM mqtt_log WHERE sensor_type='distance' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return {"value": row["value"], "unit": row["unit"], "time": row["timestamp"]}
    return {"value": 0, "unit": "mm", "time": ""}


@router.get("/history")
def history(limit: int = Query(default=50, le=500)):
    # MQTT 历史数据接口：用于趋势图或历史记录展示。
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM mqtt_log WHERE sensor_type='distance' ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


@router.get("/info")
def info():
    # 平台项目信息接口，便于展示页或调试时确认后端加载成功。
    return {
        "name": "CrackScope",
        "description": "基于双目深度相机的裂缝分割与宽度测量",
        "project": "CrackScope",
        "tech": ["Binocular Vision", "YOLO Segmentation", "Raspberry Pi CM4", "FastAPI"],
    }


@router.get("/debug/db")
def debug_db():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mqtt_log ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    cache = get_offline_prediction_cache()
    return {
        "mqtt_count": len(rows),
        "mqtt_rows": [dict(r) for r in rows],
        "offline_cache_count": len(cache),
        "db_path": DB_PATH,
        "cache_path": OFFLINE_RESULTS_PATH,
        "cache_exists": os.path.exists(OFFLINE_RESULTS_PATH),
        "fallback_checked": [p for p in _OFFLINE_FALLBACK_PATHS if os.path.exists(p)],
    }

if mqtt is not None and MQTT_BROKER:
    _start_mqtt_subscriber()
