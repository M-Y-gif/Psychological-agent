"""
多模态感知引擎（Python 微服务）
- /api/stt     : Whisper 语音转写 + 韵律特征（语速、停顿）
- /api/emotion : 人脸检测 + 表情分类
   默认引擎 opencv-yunet（纯 CPU，稳定，3类粗糙标签）；
   可选 EMOTION_ENGINE=cnn（自训练 MobileNetV2，7类细粒度表情，需 PyTorch）；
   可选 EMOTION_ENGINE=mediapipe（MediaPipe FaceLandmarker 表情系数，需 GPU/Metal 环境）。
- /api/tts     : edge-tts 语音合成（微软在线神经音色，需联网），结果缓存 7 天。
Java 后端通过 HTTP 调用本服务，把情绪特征作为上下文参数传给大模型。
"""
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timedelta

import cv2
import edge_tts
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from faster_whisper import WhisperModel

MODEL_SIZE = "small"                     # whisper 模型：tiny/base/small/medium
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
YUNET_PATH = os.path.join(BASE_DIR, "models", "yunet.onnx")
EMOTION_ENGINE = os.environ.get("EMOTION_ENGINE", "opencv").lower()
# CNN 表情模型路径
CNN_MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "fer_cnn", "best_model_v2")
if not os.path.exists(os.path.join(CNN_MODEL_DIR, "checkpoint.pt")):
    CNN_MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "fer_cnn", "best_model")
# 微软语音服务器在国内网络可能无法直连：如本机有代理（如 Clash），设置 TTS_PROXY=http://127.0.0.1:7897
TTS_PROXY = os.environ.get("TTS_PROXY", "")
TTS_CACHE_DIR = os.path.join(BASE_DIR, "tts_cache")
TTS_CACHE_DAYS = 7

# CNN 表情标签（与训练时一致）
CNN_LABEL_NAMES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
CNN_PSY_MAP = {
    "angry": "愤怒/烦躁", "disgust": "厌恶/排斥", "fear": "恐惧/焦虑",
    "happy": "积极/愉悦", "sad": "悲伤/低落", "surprise": "惊讶/困惑", "neutral": "平静/中性",
}

app = FastAPI(title="心理 Agent 多模态感知引擎")
whisper = None
yunet = None
face_mesh = None
cnn_model = None
cnn_device = None


@app.on_event("startup")
def load_models():
    global whisper, yunet, face_mesh, cnn_model, cnn_device
    whisper = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    if EMOTION_ENGINE == "mediapipe":
        _load_mediapipe()
    elif EMOTION_ENGINE == "cnn":
        _load_cnn()
    else:
        yunet = cv2.FaceDetectorYN_create(YUNET_PATH, "", (320, 320), 0.6, 0.3, 5000)
    _clean_tts_cache()
    print(f"[multimodal] Whisper({MODEL_SIZE}) + 表情引擎({EMOTION_ENGINE}) 已加载")


def _load_cnn():
    """加载自训练的 MobileNetV2 CNN 表情分类模型"""
    global cnn_model, cnn_device, yunet
    try:
        import torch
        import torch.nn as nn
        import torchvision.models as models

        checkpoint_path = os.path.join(CNN_MODEL_DIR, "checkpoint.pt")
        if not os.path.exists(checkpoint_path):
            print(f"[WARN] CNN checkpoint not found at {checkpoint_path}, falling back to opencv-yunet")
            yunet = cv2.FaceDetectorYN_create(YUNET_PATH, "", (320, 320), 0.6, 0.3, 5000)
            return

        cnn_device = "cuda" if torch.cuda.is_available() else "cpu"
        checkpoint = torch.load(checkpoint_path, map_location=cnn_device)

        # Build model (must match training script)
        backbone = models.mobilenet_v2(weights=None)
        in_features = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(
            nn.Dropout(0.4),
            nn.Linear(in_features, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, 7),
        )
        backbone.load_state_dict(checkpoint["model_state_dict"])
        backbone.to(cnn_device)
        backbone.eval()
        cnn_model = backbone

        # Still need YuNet for face detection (CNN only does classification)
        yunet = cv2.FaceDetectorYN_create(YUNET_PATH, "", (320, 320), 0.6, 0.3, 5000)

        print(f"[multimodal] CNN expression model loaded on {cnn_device} from {checkpoint_path}")
        print(f"             Best Val F1: {checkpoint.get('val_f1', 'N/A')}")
    except Exception as e:
        print(f"[WARN] Failed to load CNN model: {e}, falling back to opencv-yunet")
        yunet = cv2.FaceDetectorYN_create(YUNET_PATH, "", (320, 320), 0.6, 0.3, 5000)


def _clean_tts_cache():
    """删除超过 TTS_CACHE_DAYS 天的合成缓存"""
    if not os.path.isdir(TTS_CACHE_DIR):
        return
    cutoff = datetime.now() - timedelta(days=TTS_CACHE_DAYS)
    removed = 0
    for name in os.listdir(TTS_CACHE_DIR):
        path = os.path.join(TTS_CACHE_DIR, name)
        try:
            if os.path.isfile(path) and datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    if removed:
        print(f"[multimodal] 清理 TTS 缓存 {removed} 个文件")


# ==================== 语音合成：edge-tts（微软在线神经音色） ====================
@app.post("/api/tts")
async def tts(request: Request):
    """JSON 请求体：{"text": "...", "voice": "zh-CN-XiaoxiaoNeural", "rate": "-20%"} -> mp3 字节"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "JSON 请求体解析失败"}, status_code=400)
    text = (body.get("text") or "").strip()[:500]
    voice = body.get("voice") or "zh-CN-XiaoxiaoNeural"
    rate = body.get("rate") or "+0%"
    if not text:
        return JSONResponse({"error": "text 不能为空"}, status_code=400)

    key = hashlib.sha1(f"{text}|{voice}|{rate}".encode("utf-8")).hexdigest()
    cached = os.path.join(TTS_CACHE_DIR, key + ".mp3")
    hit = os.path.exists(cached)
    if not hit:
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        tmp = cached + ".tmp"
        try:
            communicate = edge_tts.Communicate(
                text, voice, rate=rate, proxy=TTS_PROXY or None)
            await communicate.save(tmp)
        except Exception as e:  # 离线 / 网络失败 / 音色名非法
            if os.path.exists(tmp):
                os.remove(tmp)
            return JSONResponse({"error": f"TTS 合成失败: {e}"}, status_code=502)
        os.replace(tmp, cached)
    return FileResponse(cached, media_type="audio/mpeg", headers={"X-TTS-Cache": "hit" if hit else "miss"})


def _load_mediapipe():
    """MediaPipe FaceLandmarker（需 Metal/GPU 环境，headless 环境会崩溃）"""
    global face_mesh
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=os.path.join(BASE_DIR, "models", "face_landmarker.task"),
            delegate=BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.IMAGE,
        output_face_blendshapes=True,
        num_faces=1)
    face_mesh = vision.FaceLandmarker.create_from_options(opts)


# ==================== 语音：Whisper 转写 + 韵律特征 ====================
@app.post("/api/stt")
async def stt(request: Request):
    """接收原始音频二进制流（wav/mp3 等），返回转写文本与韵律特征"""
    data = await request.body()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(data)
        path = f.name

    segments_iter, info = whisper.transcribe(
        path, language="zh", vad_filter=True, beam_size=5)
    segs = list(segments_iter)

    text = "".join(s.text for s in segs).strip()
    duration = info.duration or 0.0

    gaps = [segs[i].start - segs[i - 1].end
            for i in range(1, len(segs))
            if segs[i].start - segs[i - 1].end > 0.3]
    speech_rate = round(len(text) / duration, 2) if duration > 0 else 0.0
    avg_pause = round(sum(gaps) / len(gaps), 2) if gaps else 0.0

    return {
        "text": text,
        "language": info.language,
        "duration_sec": round(duration, 2),
        "speech_rate_chars_per_sec": speech_rate,
        "segment_count": len(segs),
        "pause_count": len(gaps),
        "avg_pause_sec": avg_pause,
        "features_json": json.dumps({
            "语速(字/秒)": speech_rate,
            "停顿次数": len(gaps),
            "平均停顿(秒)": avg_pause,
            "时长(秒)": round(duration, 2),
        }, ensure_ascii=False),
    }


# ==================== 表情：CNN MobileNetV2（自训练，7类） ====================
def _emotion_cnn(img):
    """使用自训练的 MobileNetV2 CNN 进行 7 类表情分类。
    仍用 YuNet 做人脸检测+裁剪，CNN 做表情分类。"""
    import torch
    import torchvision.transforms as transforms

    if cnn_model is None or yunet is None:
        return {"face_detected": False, "error": "CNN 模型未加载"}

    h, w = img.shape[:2]
    yunet.setInputSize((w, h))
    ok, faces = yunet.detect(img)
    if not ok or faces is None or len(faces) == 0:
        return {"face_detected": False, "error": "未检测到人脸"}

    # 裁剪人脸区域（稍微扩大边界以包含完整面部）
    f = faces[0]
    x, y, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
    pad = 0.2
    x1 = max(0, int(x - fw * pad))
    y1 = max(0, int(y - fh * pad))
    x2 = min(w, int(x + fw * (1 + pad)))
    y2 = min(h, int(y + fh * (1 + pad)))
    face_crop = img[y1:y2, x1:x2]

    if face_crop.size == 0:
        return {"face_detected": False, "error": "人脸裁剪失败"}

    # 预处理：BGR→RGB → PIL → transforms
    from PIL import Image
    face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(face_rgb)

    transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])
    tensor = transform(pil_img).unsqueeze(0).to(cnn_device)

    with torch.no_grad():
        logits = cnn_model(tensor)
        probs = torch.softmax(logits, dim=-1)[0].cpu().tolist()
        pred_idx = int(torch.argmax(logits, dim=-1).item())

    label_en = CNN_LABEL_NAMES[pred_idx]
    label_psy = CNN_PSY_MAP.get(label_en, label_en)
    confidence = probs[pred_idx]

    # 同时计算微笑分数（兼容原有接口）
    smile_score = probs[CNN_LABEL_NAMES.index("happy")] if "happy" in CNN_LABEL_NAMES else 0.0

    # 头部倾斜（仍用 YuNet 关键点）
    re_x, re_y = f[4], f[5]
    le_x, le_y = f[6], f[7]
    tilt_deg = math.degrees(math.atan2(re_y - le_y, re_x - le_x))

    return {
        "face_detected": True,
        "engine": "cnn-mobilenetv2",
        "emotion_label": label_psy,
        "emotion_label_en": label_en,
        "confidence": round(confidence, 3),
        "smile_score": round(smile_score, 3),
        "head_tilt_deg": round(float(tilt_deg), 2),
        "face_score": round(float(f[14]), 3),
        "probabilities": {CNN_LABEL_NAMES[i]: round(probs[i], 3) for i in range(len(CNN_LABEL_NAMES))},
        "features_json": json.dumps({
            "表情": label_psy,
            "置信度": round(confidence, 2),
            "头部倾斜(度)": round(float(tilt_deg), 1),
        }, ensure_ascii=False),
    }


# ==================== 表情：OpenCV YuNet 人脸关键点（原始规则方案，保留作为fallback） ====================
def _emotion_opencv(img):
    h, w = img.shape[:2]
    yunet.setInputSize((w, h))
    ok, faces = yunet.detect(img)
    if not ok or faces is None or len(faces) == 0:
        return {"face_detected": False, "error": "未检测到人脸"}

    # YuNet 15 维输出：bbox(4) + 右眼/左眼/鼻尖/右嘴角/左嘴角(10) + 置信度(1)
    f = faces[0]
    x, y, fw, fh = f[0], f[1], f[2], f[3]
    re_x, re_y = f[4], f[5]
    le_x, le_y = f[6], f[7]
    n_x, n_y = f[8], f[9]
    rm_x, rm_y = f[10], f[11]
    lm_x, lm_y = f[12], f[13]

    mouth_w = math.dist((lm_x, lm_y), (rm_x, rm_y))
    mouth_w_ratio = mouth_w / fw if fw > 0 else 0.0
    # 嘴角相对鼻尖的高度（上扬=微笑）
    corner_raise = (n_y - (lm_y + rm_y) / 2) / fh if fh > 0 else 0.0
    # 头部倾斜：两眼连线角度
    tilt_deg = math.degrees(math.atan2(re_y - le_y, re_x - le_x))

    width_score = max(0.0, min(1.0, (mouth_w_ratio - 0.30) / 0.12))
    raise_score = max(0.0, min(1.0, corner_raise / 0.10 + 0.5))
    smile_score = round(0.6 * width_score + 0.4 * raise_score, 3)

    if smile_score > 0.55:
        emotion_label = "积极"
    elif smile_score < 0.25:
        emotion_label = "中性"
    else:
        emotion_label = "中性"

    smile_score = float(smile_score)
    mouth_w_ratio = float(mouth_w_ratio)
    tilt_deg = float(tilt_deg)
    face_score = float(f[14])
    return {
        "face_detected": True,
        "engine": "opencv-yunet",
        "emotion_label": emotion_label,
        "smile_score": smile_score,
        "mouth_width_ratio": round(mouth_w_ratio, 3),
        "head_tilt_deg": round(tilt_deg, 2),
        "face_score": round(face_score, 3),
        "features_json": json.dumps({
            "表情": emotion_label,
            "微笑程度": round(smile_score, 2),
            "头部倾斜(度)": round(tilt_deg, 1),
        }, ensure_ascii=False),
    }


# ==================== 表情：MediaPipe（可选，需 Metal） ====================
def _emotion_mediapipe(rgb):
    import mediapipe as mp
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = face_mesh.detect(mp_image)
    if not result.face_landmarks:
        return {"face_detected": False, "error": "未检测到人脸"}
    bs = {b.category_name: b.score for b in result.face_blendshapes[0]}
    smile = bs.get("smile", 0.0)
    frown = max(bs.get("mouthFrownLeft", 0.0), bs.get("mouthFrownRight", 0.0))
    brow_down = max(bs.get("browDownLeft", 0.0), bs.get("browDownRight", 0.0))
    if smile > 0.45:
        label = "积极"
    elif frown > 0.4 or brow_down > 0.45:
        label = "消极"
    else:
        label = "中性"
    return {
        "face_detected": True,
        "engine": "mediapipe",
        "emotion_label": label,
        "smile_score": round(smile, 3),
        "frown_score": round(frown, 3),
        "brow_down_score": round(brow_down, 3),
        "features_json": json.dumps({"表情": label, "微笑": round(smile, 2), "皱眉": round(frown, 2)},
                                    ensure_ascii=False),
    }


@app.post("/api/emotion")
async def emotion(request: Request):
    """接收原始图片二进制流，返回表情特征"""
    data = await request.body()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"face_detected": False, "error": "无法解码图片"}
    if EMOTION_ENGINE == "cnn":
        return _emotion_cnn(img)
    elif EMOTION_ENGINE == "mediapipe":
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return _emotion_mediapipe(rgb)
    return _emotion_opencv(img)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
