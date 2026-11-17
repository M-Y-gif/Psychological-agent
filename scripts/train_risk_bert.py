#!/usr/bin/env python3
"""
BERT 心理风险分类 - 训练脚本
==============================
模型：bert-base-chinese + 4分类头
数据：data/bert_risk/{train,val,test}.jsonl

用法：
  python3 scripts/train_risk_bert.py
  python3 scripts/train_risk_bert.py --epochs 15 --lr 3e-5
  python3 scripts/train_risk_bert.py --model bert-base-chinese   # 换基座模型

输出：
  data/bert_risk/best_model/   (最优checkpoint)
  data/bert_risk/training_log.json
  evaluation/reports/bert_eval_summary.md
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import BertModel, BertTokenizer, get_linear_schedule_with_warmup
from sklearn.metrics import (
    accuracy_score, f1_score, recall_score, precision_score,
    classification_report, confusion_matrix,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "bert_risk"
OUTPUT_DIR = DATA_DIR / "best_model"
REPORT_DIR = PROJECT_ROOT / "evaluation" / "reports"
FIGURE_DIR = PROJECT_ROOT / "evaluation" / "figures"

LABEL_NAMES = {0: "无风险", 1: "轻度困扰", 2: "中高风险", 3: "极高风险"}
NUM_LABELS = 4


# ============================================================
# Dataset
# ============================================================
class RiskDataset(Dataset):
    def __init__(self, jsonl_path: str, tokenizer, max_length=256):
        self.samples = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                self.samples.append(obj)
        self.tokenizer = tokenizer
        self.max_length = max_length
        print(f"[Data] Loaded {len(self.samples)} samples from {jsonl_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        encoding = self.tokenizer(
            item["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(item["label"], dtype=torch.long),
        }


# ============================================================
# Model
# ============================================================
class BertRiskClassifier(nn.Module):
    """BERT + Dropout + Linear 分类头"""

    def __init__(self, model_name="bert-base-chinese", num_labels=4, dropout=0.3):
        super().__init__()
        self.bert = BertModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask, labels=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        cls_output = self.dropout(cls_output)
        logits = self.classifier(cls_output)

        loss = None
        if labels is not None:
            loss_fn = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
            loss = loss_fn(logits, labels)

        return {"loss": loss, "logits": logits}

    def set_class_weights(self, weights: torch.Tensor):
        self.class_weights = weights


# ============================================================
# Training
# ============================================================
def train_one_epoch(model, dataloader, optimizer, scheduler, device):
    model.train()
    total_loss = 0
    all_preds, all_labels = [], []

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        outputs = model(input_ids, attention_mask, labels)
        loss = outputs["loss"]

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()
        optimizer.zero_grad()

        total_loss += loss.item()
        preds = torch.argmax(outputs["logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_labels, all_preds)
    return avg_loss, acc


@torch.no_grad()
def evaluate(model, dataloader, device):
    model.eval()
    total_loss = 0
    all_preds, all_labels = [], []

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        outputs = model(input_ids, attention_mask, labels)
        total_loss += outputs["loss"].item()
        preds = torch.argmax(outputs["logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    recall_high = recall_score(
        all_labels, all_preds, labels=[2, 3], average="micro", zero_division=0
    )
    return avg_loss, acc, f1, recall_high, all_preds, all_labels


# ============================================================
# Visualization
# ============================================================
def plot_training_curves(history: dict, save_dir: Path):
    """绘制训练曲线"""
    save_dir.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Loss curve
    ax1.plot(history["train_loss"], label="Train Loss", linewidth=2)
    ax1.plot(history["val_loss"], label="Val Loss", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Accuracy curve
    ax2.plot(history["train_acc"], label="Train Acc", linewidth=2)
    ax2.plot(history["val_acc"], label="Val Acc", linewidth=2)
    ax2.plot(history["val_f1"], label="Val F1-macro", linewidth=2, linestyle="--")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("Training & Validation Metrics")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_dir / "bert_training_curves.png", dpi=150)
    plt.close()
    print(f"[INFO] Training curves saved -> {save_dir / 'bert_training_curves.png'}")


def plot_confusion_matrix(labels, preds, save_dir: Path):
    """绘制混淆矩阵热力图"""
    save_dir.mkdir(parents=True, exist_ok=True)
    cm = confusion_matrix(labels, preds, labels=list(range(NUM_LABELS)))

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)

    tick_marks = list(range(NUM_LABELS))
    label_names = [f"{i}\n{LABEL_NAMES[i]}" for i in range(NUM_LABELS)]
    ax.set_xticks(tick_marks)
    ax.set_yticks(tick_marks)
    ax.set_xticklabels(label_names, fontsize=9)
    ax.set_yticklabels(label_names, fontsize=9)

    # 在每个格子中标注数字
    thresh = cm.max() / 2.0
    for i in range(NUM_LABELS):
        for j in range(NUM_LABELS):
            ax.text(j, i, format(cm[i, j], "d"),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black",
                    fontsize=12)

    ax.set_ylabel("True Label")
    ax.set_xlabel("Predicted Label")
    ax.set_title("BERT Risk Classifier - Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_dir / "bert_confusion_matrix.png", dpi=150)
    plt.close()
    print(f"[INFO] Confusion matrix saved -> {save_dir / 'bert_confusion_matrix.png'}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="BERT Risk Classification Training")
    parser.add_argument("--model", type=str, default="bert-base-chinese",
                        help="Pretrained model name (default: bert-base-chinese)")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Set seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 60)
    print(f"  BERT Risk Classification Training")
    print(f"  Device: {device}")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}, Batch Size: {args.batch_size}, LR: {args.lr}")
    print("=" * 60)

    # 1. Load tokenizer & datasets
    tokenizer = BertTokenizer.from_pretrained(args.model)
    train_dataset = RiskDataset(DATA_DIR / "train.jsonl", tokenizer, args.max_length)
    val_dataset = RiskDataset(DATA_DIR / "val.jsonl", tokenizer, args.max_length)
    test_dataset = RiskDataset(DATA_DIR / "test.jsonl", tokenizer, args.max_length)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2)

    # 2. Load class weights
    weights_path = DATA_DIR / "class_weights.json"
    if weights_path.exists():
        with open(weights_path) as f:
            weights_dict = json.load(f)
        class_weights = torch.tensor([weights_dict[str(i)] for i in range(NUM_LABELS)], dtype=torch.float)
        print(f"[INFO] Class weights loaded: {weights_dict}")
    else:
        class_weights = torch.ones(NUM_LABELS, dtype=torch.float)
        print("[WARN] No class weights found, using uniform weights")

    # 3. Build model
    model = BertRiskClassifier(args.model, NUM_LABELS, args.dropout)
    model.set_class_weights(class_weights)
    model.to(device)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[INFO] Trainable params: {trainable_params:,} / {total_params:,} ({trainable_params/total_params*100:.1f}%)")

    # 4. Optimizer & Scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # 5. Training loop
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "val_f1": []}
    best_val_f1 = 0.0
    best_epoch = 0
    start_time = time.time()

    print("\n[Training]")
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, scheduler, device)
        val_loss, val_acc, val_f1, val_recall_high, _, _ = evaluate(model, val_loader, device)

        elapsed = time.time() - epoch_start
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)

        marker = ""
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = epoch
            # Save best model
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_f1": val_f1,
                "config": {
                    "model_name": args.model,
                    "num_labels": NUM_LABELS,
                    "dropout": args.dropout,
                    "max_length": args.max_length,
                },
            }, OUTPUT_DIR / "checkpoint.pt")
            tokenizer.save_pretrained(str(OUTPUT_DIR))
            marker = " ★ BEST"

        print(f"  Epoch {epoch:3d}/{args.epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} F1: {val_f1:.4f} "
              f"Recall(2+3): {val_recall_high:.4f} | {elapsed:.1f}s{marker}")

    total_time = time.time() - start_time
    print(f"\n[Done] Training completed in {total_time:.1f}s. Best epoch: {best_epoch} (F1={best_val_f1:.4f})")

    # 6. Load best model & evaluate on test set
    print("\n[Test Evaluation]")
    checkpoint = torch.load(OUTPUT_DIR / "checkpoint.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc, test_f1, test_recall_high, test_preds, test_labels = evaluate(model, test_loader, device)

    print(f"  Test Loss: {test_loss:.4f}")
    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Test F1-macro: {test_f1:.4f}")
    print(f"  Test Recall(high-risk 2+3): {test_recall_high:.4f}")
    print(f"\n{classification_report(test_labels, test_preds, target_names=[LABEL_NAMES[i] for i in range(NUM_LABELS)], zero_division=0)}")

    # 7. Save results
    # Training log
    log = {
        "config": vars(args),
        "history": history,
        "best_epoch": best_epoch,
        "best_val_f1": best_val_f1,
        "test_metrics": {
            "loss": test_loss, "accuracy": test_acc,
            "f1_macro": test_f1, "recall_high_risk": test_recall_high,
        },
        "training_time_sec": total_time,
    }
    with open(DATA_DIR / "training_log.json", "w") as f:
        json.dump(log, f, indent=2)

    # Figures
    plot_training_curves(history, FIGURE_DIR)
    plot_confusion_matrix(test_labels, test_preds, FIGURE_DIR)

    # Report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# BERT Risk Classifier Evaluation Report",
        "",
        "## Configuration",
        f"- Model: `{args.model}`",
        f"- Epochs: {args.epochs}, Batch Size: {args.batch_size}, LR: {args.lr}",
        f"- Max Length: {args.max_length}, Dropout: {args.dropout}",
        f"- Device: {device}",
        f"- Training Time: {total_time:.1f}s",
        "",
        "## Test Set Results",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Accuracy | {test_acc:.4f} |",
        f"| F1-macro | {test_f1:.4f} |",
        f"| Recall (high-risk 2+3) | {test_recall_high:.4f} |",
        f"| Loss | {test_loss:.4f} |",
        "",
        "## Classification Report",
        "```",
        classification_report(test_labels, test_preds, target_names=[LABEL_NAMES[i] for i in range(NUM_LABELS)], zero_division=0),
        "```",
        "",
        f"## Best Checkpoint",
        f"- Epoch: {best_epoch}, Val F1: {best_val_f1:.4f}",
        f"- Saved at: `{OUTPUT_DIR / 'checkpoint.pt'}`",
    ]
    with open(REPORT_DIR / "bert_eval_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ All outputs saved:")
    print(f"   Model:      {OUTPUT_DIR / 'checkpoint.pt'}")
    print(f"   Log:        {DATA_DIR / 'training_log.json'}")
    print(f"   Curves:     {FIGURE_DIR / 'bert_training_curves.png'}")
    print(f"   ConfMatrix: {FIGURE_DIR / 'bert_confusion_matrix.png'}")
    print(f"   Report:     {REPORT_DIR / 'bert_eval_summary.md'}")


if __name__ == "__main__":
    main()
