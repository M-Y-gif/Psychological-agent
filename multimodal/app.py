"""
多模态感知引擎（Python 微服务）
- /api/stt     : Whisper 语音转写 + 韵律特征（语速、停顿）
- /api/emotion : 人脸关键点 -> 表情特征
   默认引擎 OpenCV DNN YuNet（纯 CPU，稳定）；
   可选 EMOTION_ENGINE=mediapipe（MediaPipe FaceLandmarker 表情系数，需 GPU/Metal 环境）。
Java 后端通过 HTTP 调用本服务，把情绪特征作为上下文参数传给大模型。
"""
import json
import math
import os
import tempfile

import cv2
import numpy as np
from fastapi import FastAPI, Request
from faster_whisper import WhisperModel

MODEL_SIZE = "small"                     # whisper 模型：tiny/base/small/medium
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_PATH = os.path.join(BASE_DIR, "models", "yunet.onnx")
EMOTION_ENGINE = os.environ.get("EMOTION_ENGINE", "opencv").lower()

app = FastAPI(title="心理 Agent 多模态感知引擎")
whisper = None
yunet = None
face_mesh = None


@app.on_event("startup")
def load_models():
    global whisper, yunet, face_mesh
    whisper = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    if EMOTION_ENGINE == "mediapipe":
        _load_mediapipe()
    else:
        yunet = cv2.FaceDetectorYN_create(YUNET_PATH, "", (320, 320), 0.6, 0.3, 5000)
    print(f"[multimodal] Whisper({MODEL_SIZE}) + 表情引擎({EMOTION_ENGINE}) 已加载")


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


# ==================== 表情：OpenCV YuNet 人脸关键点 ====================
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
    if EMOTION_ENGINE == "mediapipe":
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return _emotion_mediapipe(rgb)
    return _emotion_opencv(img)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
