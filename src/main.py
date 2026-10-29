"""FastAPI entry point for CrackScope: stereo crack segmentation and width measurement."""
import os, sys, time, random, base64, asyncio, json
from io import BytesIO
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.requests import Request
from PIL import Image, ImageDraw
from src.crackscope import router as crackscope_router

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

app = FastAPI(title="CrackScope", version="2.0.0", description="基于双目深度相机的裂缝分割与宽度测量")
app.include_router(crackscope_router, prefix="/api")

# ===== Component data =====
COMPONENTS = [
    {"id": "cm4", "name": "Raspberry Pi CM4", "model": "CM4 2GB Lite WiFi", "price": 195, "desc": "主控单元，负责运行 YOLO 裂缝分割模型、双目深度计算和系统调度", "icon": "mcu"},
    {"id": "board", "name": "微雪 CM4 IO 扩展板", "model": "CM4-IO-BASE-B", "price": 79, "desc": "提供 USB、TF 卡槽、电源接口，连接所有外设", "icon": "board"},
    {"id": "camera", "name": "USB 双目同步相机", "model": "400万 1080p 双目", "price": 210, "desc": "同步采集左右图像，用于立体视觉深度计算", "icon": "camera"},
    {"id": "tfcard", "name": "TF 存储卡", "model": "SanDisk 32GB Class10", "price": 28, "desc": "存放 Raspberry Pi OS 系统和模型文件", "icon": "storage"},
    {"id": "heatsink", "name": "散热片套件", "model": "铝制散热片 + 风扇", "price": 12, "desc": "CM4 推理时散热，防止降频", "icon": "cooling"},
    {"id": "power", "name": "充电宝", "model": "5V 2A 输出", "price": 49, "desc": "为 CM4 扩展板提供 5V 稳定供电", "icon": "power"},
]

# ===== Fake crack image generator =====
def generate_crack_image(width=640, height=480, crack_width=0.35, with_mask=True):
    img = Image.new("RGB", (width, height), (45, 45, 48))
    draw = ImageDraw.Draw(img)
    for _ in range(3000):
        x, y = random.randint(0, width-1), random.randint(0, height-1)
        v = random.randint(0, 25)
        draw.point((x, y), fill=(45+v, 45+v, 46+v))

    cx, cy = width//2, height//2
    points = [(cx-100, random.randint(80, 150))]
    for i in range(20):
        lx, ly = points[-1]
        nx, ny = lx+random.randint(5,35), ly+random.randint(-15,15)
        if 0 < nx < width and 0 < ny < height:
            points.append((nx, ny))

    pw = max(1, int(crack_width*15))
    for i in range(len(points)-1):
        draw.line([points[i], points[i+1]], fill=(18,18,20), width=pw+2)
        draw.line([points[i], points[i+1]], fill=(12,12,14), width=pw)

    for _ in range(3):
        idx = random.randint(2, len(points)-3)
        bx, by = points[idx]
        for _ in range(5):
            bx += random.randint(-10, 10)
            by += random.randint(5, 15)
            if 0 < bx < width and 0 < by < height:
                draw.line([(bx-2,by-2),(bx+2,by+2)], fill=(12,12,14), width=1)

    mask_img = img.copy()
    if with_mask:
        overlay = Image.new("RGBA", (width, height), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for i in range(len(points)-1):
            p1, p2 = points[i], points[i+1]
            for dx in range(-6, 7):
                for dy in range(-6, 7):
                    if dx*dx+dy*dy < 36:
                        od.line([(p1[0]+dx,p1[1]+dy),(p2[0]+dx,p2[1]+dy)], fill=(96,231,160,90), width=1)
        mask_img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img, mask_img

def image_to_b64(img, fmt="PNG"):
    buf = BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

stream_active = False

# ===== Routes =====
@app.get("/", response_class=HTMLResponse)
def index():
    idx = os.path.join(BASE, "index.html")
    return FileResponse(idx) if os.path.exists(idx) else HTMLResponse("Not found", status_code=404)

@app.get("/api/components")
def get_components():
    return COMPONENTS

@app.post("/api/capture")
def capture_frame():
    cw = round(random.uniform(0.08, 0.52), 2)
    cf = round(random.uniform(0.78, 0.98), 2)
    left_raw, left_mask = generate_crack_image(640, 480, cw)
    right_raw, right_mask = generate_crack_image(640, 480, cw*(1+random.uniform(-0.05,0.05)))
    return {
        "success": True,
        "images": {
            "left_raw": image_to_b64(left_raw),
            "left_mask": image_to_b64(left_mask),
            "right_raw": image_to_b64(right_raw),
            "right_mask": image_to_b64(right_mask),
        },
        "result": {"width_mm": cw, "confidence": cf, "inference_ms": round(random.uniform(45,120),1)},
        "timestamp": time.strftime("%H:%M:%S"),
    }

@app.post("/api/stream/start")
def start_stream():
    global stream_active
    stream_active = True
    return {"success": True}

@app.post("/api/stream/stop")
def stop_stream():
    global stream_active
    stream_active = False
    return {"success": True}

@app.get("/api/stream/frame")
def get_stream_frame():
    if not stream_active:
        return JSONResponse({"error": "stream not active"}, status_code=400)
    cw = round(random.uniform(0.08, 0.52), 2)
    cf = round(random.uniform(0.78, 0.98), 2)
    left_raw, left_mask = generate_crack_image(640, 480, cw)
    right_raw, right_mask = generate_crack_image(640, 480, cw*(1+random.uniform(-0.05,0.05)))
    return {
        "images": {"left_mask": image_to_b64(left_mask), "right_mask": image_to_b64(right_mask)},
        "result": {"width_mm": cw, "confidence": cf, "inference_ms": round(random.uniform(45,120),1)},
    }

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    global stream_active
    await ws.accept()
    stream_active = True
    try:
        while True:
            data = await ws.receive_text()
            if data == "stop": break
            cw = round(random.uniform(0.08, 0.52), 2)
            cf = round(random.uniform(0.78, 0.98), 2)
            left_raw, left_mask = generate_crack_image(640, 480, cw)
            right_raw, right_mask = generate_crack_image(640, 480, cw*(1+random.uniform(-0.05,0.05)))
            await ws.send_json({
                "images": {"left_mask": image_to_b64(left_mask), "right_mask": image_to_b64(right_mask)},
                "result": {"width_mm": cw, "confidence": cf, "inference_ms": round(random.uniform(45,120),1)},
            })
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        stream_active = False

app.mount("/assets", StaticFiles(directory=os.path.join(BASE, "assets")), name="assets")
