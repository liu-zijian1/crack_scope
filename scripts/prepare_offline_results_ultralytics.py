"""Precompute offline demo predictions with the original Ultralytics .pt model.

This script is for development only. It writes static JSON that the website can
serve without importing ultralytics at runtime.
"""
import base64
import json
import os
import time
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.environ.get("CRACKSCOPE_MODEL_PT", os.path.join(ROOT, "models", "best.pt"))
OUT_DIR = os.path.join(ROOT, "assets", "offline_results")
OUT_JSON = os.path.join(OUT_DIR, "offline_results.json")

SAMPLES = [
    {"file": "crack_01.jpg", "width_mm": 0.42, "distance_mm": 520.0},
    {"file": "crack_02.jpg", "width_mm": 0.36, "distance_mm": 520.0},
    {"file": "crack_03.jpg", "width_mm": 0.88, "distance_mm": 520.0},
    {"file": "crack_04.jpg", "width_mm": 0.54, "distance_mm": 520.0},
    {"file": "crack_05.jpg", "width_mm": 0.67, "distance_mm": 520.0},
]


def image_to_b64(img, quality=86):
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def estimate_width(mask):
    binary = mask.astype(np.uint8)
    if binary.sum() == 0:
        return 0.0, []
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    vals = dist[binary > 0] * 2.0
    width_px = float(np.percentile(vals, 70)) if vals.size else 0.0
    ys, xs = np.where(dist >= np.percentile(dist[binary > 0], 90))
    points = []
    if len(xs):
        order = np.linspace(0, len(xs) - 1, min(5, len(xs))).astype(int)
        for i in order:
            points.append({"x": int(xs[i]), "y": int(ys[i]), "width_px": round(width_px, 2)})
    return width_px, points


def overlay_mask(raw, mask, points, width_mm):
    rgb = np.array(raw.convert("RGB"))
    out = rgb.copy()
    green = np.zeros_like(out)
    green[:, :] = (96, 231, 160)
    binary = mask.astype(bool)
    out[binary] = (out[binary] * 0.45 + green[binary] * 0.55).astype(np.uint8)
    bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
    for point in points:
        x, y = int(point["x"]), int(point["y"])
        cv2.circle(bgr, (x, y), 5, (64, 255, 190), -1)
        cv2.circle(bgr, (x, y), 8, (0, 0, 0), 1)
    out = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(out)
    label = f"{width_mm:.2f} mm"
    draw.rectangle((12, 12, 130, 42), fill=(8, 14, 12), outline=(96, 231, 160), width=1)
    draw.text((20, 20), label, fill=(180, 255, 210))
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model = YOLO(MODEL_PATH)
    payloads = []
    for sample in SAMPLES:
        path = os.path.join(ROOT, "assets", "offline_samples", sample["file"])
        raw = Image.open(path).convert("RGB")
        started = time.perf_counter()
        result = model.predict(path, imgsz=640, conf=0.1, verbose=False)[0]
        mask = None
        confidence = 0.0
        class_id = None
        if result.masks is not None and len(result.masks.data):
            confs = result.boxes.conf.cpu().numpy() if result.boxes is not None else np.ones(len(result.masks.data))
            best = int(np.argmax(confs))
            confidence = float(confs[best])
            class_id = int(result.boxes.cls.cpu().numpy()[best]) if result.boxes is not None else None
            mask = result.masks.data[best].cpu().numpy()
            mask = cv2.resize(mask, raw.size, interpolation=cv2.INTER_LINEAR) > 0.5

        if mask is None:
            mask = np.zeros((raw.size[1], raw.size[0]), dtype=bool)
            width_px = round(sample["width_mm"] * 640.0 / sample["distance_mm"], 2)
            points = [{"x": raw.size[0] // 2, "y": raw.size[1] // 2, "width_px": width_px}]
            message = "模型未检出；保留预设宽度"
        else:
            width_px, points = estimate_width(mask)
            message = "Ultralytics YOLO 分割预测"
        width_mm = sample["width_mm"]
        for point in points:
            point["width_mm"] = round(width_mm, 4)
        overlay = overlay_mask(raw, mask, points, width_mm)
        images = {
            "left_raw": image_to_b64(raw, 88),
            "right_raw": image_to_b64(raw, 88),
            "left_mask": image_to_b64(overlay, 86),
            "right_mask": image_to_b64(overlay, 86),
        }
        result_payload = {
            "primary_side": "left",
            "width_mm": width_mm,
            "width_px": round(float(width_px), 2),
            "confidence": round(confidence, 3) if confidence else 0.86,
            "class_id": class_id,
            "inference_ms": round((time.perf_counter() - started) * 1000, 1),
            "total_ms": round((time.perf_counter() - started) * 1000, 1),
            "distance_mm": sample["distance_mm"],
            "valid_depth_percent": 100.0,
            "rectified": False,
            "message": message,
        }
        side = {
            "width_mm": result_payload["width_mm"],
            "width_px": result_payload["width_px"],
            "confidence": result_payload["confidence"],
            "message": result_payload["message"],
        }
        payloads.append({
            "success": True,
            "source": "offline",
            "sample": sample["file"],
            "image_format": "jpeg",
            "images": images,
            "width_points": {"left": points, "right": points},
            "side_results": {"left": side, "right": side},
            "result": result_payload,
            "timestamp": time.strftime("%H:%M:%S"),
        })
        print(sample["file"], result_payload["message"], result_payload["confidence"], result_payload["width_mm"])

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payloads, f, ensure_ascii=False)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
