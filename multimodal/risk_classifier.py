"""
BERT 心理风险分类推理微服务
===========================
加载训练好的 BERT v2 checkpoint，提供 HTTP 接口供 Java 后端调用。

启动方式：
  python3 multimodal/risk_classifier.py
  # 默认监听 0.0.0.0:8091

接口：
  POST /api/risk_classify
  Body: {"text": "用户消息文本"}
  Response: {"risk_level": 0-2, "confidence": 0.95, "label": "无风险", "probabilities": [0.95, 0.04, 0.01]}

标签体系（3类）：
  0 = 无风险
  1 = 轻度困扰
  2 = 高风险

注意：BERT输出3类(0-2)，Java端RiskEvaluator会将其映射到原4级体系(0-3)：
  BERT 0 → 原 0
  BERT 1 → 原 1
  BERT 2 → 原 2（中高风险，与LLM的2-3级取max后可能升到3）
"""
import json
import os
import sys

# 离线模式：禁止访问HuggingFace网络，只用本地缓存
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import torch.nn as nn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from transformers import BertModel, BertTokenizer

# ============================================================
# 配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
# 模型路径：优先找 best_model_v2，其次 best_model
MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "bert_risk", "best_model_v2")
if not os.path.exists(os.path.join(MODEL_DIR, "checkpoint.pt")):
    MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "bert_risk", "best_model")

PORT = int(os.environ.get("RISK_CLASSIFIER_PORT", "8091"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

LABEL_NAMES = {0: "无风险", 1: "轻度困扰", 2: "高风险"}

app = FastAPI(title="BERT Risk Classifier Service")
model = None
tokenizer = None


# ============================================================
# Model Definition (must match training script)
# ============================================================
class BertRiskClassifierV2(nn.Module):
    def __init__(self, model_name="bert-base-chinese", num_labels=3, dropout=0.4):
        super().__init__()
        self.bert = BertModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(self.bert.config.hidden_size, 256),
            nn.Tanh(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_labels),
        )

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        return self.classifier(cls_output)


# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
def load_model():
    global model, tokenizer

    checkpoint_path = os.path.join(MODEL_DIR, "checkpoint.pt")
    if not os.path.exists(checkpoint_path):
        print(f"[WARN] Checkpoint not found at {checkpoint_path}")
        print(f"[WARN] BERT risk classifier will be unavailable")
        return

    print(f"[INFO] Loading BERT checkpoint from {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
    config = checkpoint.get("config", {})

    model_name = config.get("model", "bert-base-chinese")
    num_labels = len(checkpoint.get("label_names", LABEL_NAMES))
    dropout = config.get("dropout", 0.4)

    # Load tokenizer from model dir (saved during training) or from pretrained
    if os.path.exists(os.path.join(MODEL_DIR, "vocab.txt")):
        tokenizer = BertTokenizer.from_pretrained(MODEL_DIR)
    else:
        tokenizer = BertTokenizer.from_pretrained(model_name)

    model = BertRiskClassifierV2(model_name, num_labels, dropout)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(DEVICE)
    model.eval()

    print(f"[INFO] BERT Risk Classifier loaded on {DEVICE}")
    print(f"       Labels: {checkpoint.get('label_names', LABEL_NAMES)}")
    print(f"       Best Val F1: {checkpoint.get('val_f1', 'N/A')}")


# ============================================================
# API Endpoint
# ============================================================
@app.post("/api/risk_classify")
async def risk_classify(request: Request):
    """
    输入：{"text": "用户消息"}
    输出：{"risk_level": 0-2, "confidence": float, "label": str, "probabilities": [float, float, float]}
    """
    if model is None or tokenizer is None:
        return JSONResponse(
            {"error": "BERT model not loaded", "risk_level": -1},
            status_code=503
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text is empty"}, status_code=400)

    # Tokenize
    max_length = 256
    encoding = tokenizer(
        text,
        max_length=max_length,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    input_ids = encoding["input_ids"].to(DEVICE)
    attention_mask = encoding["attention_mask"].to(DEVICE)

    # Inference
    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        probs = torch.softmax(logits, dim=-1)[0].cpu().tolist()
        pred_label = int(torch.argmax(logits, dim=-1).item())
        confidence = probs[pred_label]

    return {
        "risk_level": pred_label,
        "confidence": round(confidence, 4),
        "label": LABEL_NAMES.get(pred_label, "未知"),
        "probabilities": [round(p, 4) for p in probs],
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok" if model is not None else "model_not_loaded",
        "device": DEVICE,
        "model_dir": MODEL_DIR,
    }


if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] Starting BERT Risk Classifier on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
