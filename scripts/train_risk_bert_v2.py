#!/usr/bin/env python3
"""
BERT 心理风险分类 - 改进版训练脚本 (v2)
==========================================
改进点：
  1. 3分类（无风险/轻度困扰/高风险），合并原label 2+3 解决样本不足
  2. 学习率 1e-5（原来2e-5太高导致过拟合）
  3. Dropout 0.4（原来0.3）
  4. EarlyStopping patience=2（验证集F1连续2轮不提升就停）
  5. 支持 SoulChatCorpus 数据扩充
  6. Weight Decay 0.02（更强正则化）

用法：
  # 基本用法（用现有数据，3分类）
  python3 scripts/train_risk_bert_v2.py

  # 先用扩充数据重新生成数据集，再训练
  python3 scripts/prepare_risk_data.py --add-soulchat
  python3 scripts/train_risk_bert_v2.py

  # 自定义参数
  python3 scripts/train_risk_bert_v2.py --epochs 15 --lr 1e-5 --patience 3

输出：
  data/bert_risk/best_model_v2/checkpoint.pt
  evaluation/reports/bert_eval_summary_v2.md
  evaluation/figures/bert_training_curves_v2.png
  evaluation/figures/bert_confusion_matrix_v2.png
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
OUTPUT_DIR = DATA_DIR / "best_model_v2"
REPORT_DIR = PROJECT_ROOT / "evaluation" / "reports"
FIGURE_DIR = PROJECT_ROOT / "evaluation" / "figures"

# 3分类标签体系（合并原来的 2+3 → 高风险）
LABEL_NAMES = {0: "无风险", 1: "轻度困扰", 2: "高风险"}
NUM_LABELS = 3


# ============================================================
# Dataset（自动将 label 3 → 2）
# ============================================================
class RiskDatasetV2(Dataset):
    def __init__(self, jsonl_path: str, tokenizer, max_length=256):
        self.samples = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                # 关键改进：将 label 3 合并到 label 2
                label = min(obj["label"], 2)
                self.samples.append({"text": obj["text"], "label": label})
        self.tokenizer = tokenizer
        self.max_length = max_length
        print(f"[Data] Loaded {len(self.samples)} samples from {jsonl_path} (3-class)")

        # 打印分布
        from collections import Counter
        dist = Counter(s["label"] for s in self.samples)
        for k in sorted(dist.keys()):
            print(f"       Label {k} ({LABEL_NAMES[k]}): {dist[k]}")

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

    def forward(self, input_ids, attention_mask, labels=None, class_weights=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        logits = self.classifier(cls_output)

        loss = None
        if labels is not None:
            if class_weights is not None:
                loss_fn = nn.CrossEntropyLoss(weight=class_weights.to(logits.device))
            else:
                loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits, labels)

        return {"loss": loss, "logits": logits}


# ============================================================
# Training with EarlyStopping
# ============================================================
def train_one_epoch(model, dataloader, optimizer, scheduler, device, class_weights):
    model.train()
    total_loss = 0
    all_preds, all_labels = [], []

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        outputs = model(input_ids, attention_mask, labels, class_weights)
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
def evaluate(model, dataloader, device, class_weights):
    model.eval()
    total_loss = 0
    all_preds, all_labels = [], []

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        outputs = model(input_ids, attention_mask, labels, class_weights)
        total_loss += outputs["loss"].item()
        preds = torch.argmax(outputs["logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    # 高风险召回率（label=2）
    recall_high = recall_score(all_labels, all_preds, labels=[2], average="micro", zero_division=0)
    return avg_loss, acc, f1, recall_high, all_preds, all_labels


# ============================================================
# Visualization
# ============================================================
def plot_training_curves(history: dict, save_dir: Path, suffix="_v2"):
    save_dir.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(history["train_loss"], label="Train Loss", linewidth=2)
    ax1.plot(history["val_loss"], label="Val Loss", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("BERT v2 - Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(history["train_acc"], label="Train Acc", linewidth=2)
    ax2.plot(history["val_acc"], label="Val Acc", linewidth=2)
    ax2.plot(history["val_f1"], label="Val F1-macro", linewidth=2, linestyle="--")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("BERT v2 - Metrics (with EarlyStopping)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 标注早停点
    if history.get("stopped_epoch"):
        ax2.axvline(x=history["stopped_epoch"]-1, color='red', linestyle=':', alpha=0.7, label='Early Stop')
        ax2.legend()

    plt.tight_layout()
    plt.savefig(save_dir / f"bert_training_curves{suffix}.png", dpi=150)
    plt.close()
    print(f"[INFO] Training curves saved -> {save_dir / f'bert_training_curves{suffix}.png'}")


def plot_confusion_matrix(labels, preds, save_dir: Path, suffix="_v2"):
    save_dir.mkdir(parents=True, exist_ok=True)
    cm = confusion_matrix(labels, preds, labels=list(range(NUM_LABELS)))

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)

    tick_marks = list(range(NUM_LABELS))
    label_names = [f"{i}\n{LABEL_NAMES[i]}" for i in range(NUM_LABELS)]
    ax.set_xticks(tick_marks)
    ax.set_yticks(tick_marks)
    ax.set_xticklabels(label_names, fontsize=10)
    ax.set_yticklabels(label_names, fontsize=10)

    thresh = cm.max() / 2.0
    for i in range(NUM_LABELS):
        for j in range(NUM_LABELS):
            ax.text(j, i, format(cm[i, j], "d"),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black",
                    fontsize=14)

    ax.set_ylabel("True Label")
    ax.set_xlabel("Predicted Label")
    ax.set_title("BERT v2 - Confusion Matrix (3-class)")
    plt.tight_layout()
    plt.savefig(save_dir / f"bert_confusion_matrix{suffix}.png", dpi=150)
    plt.close()
    print(f"[INFO] Confusion matrix saved -> {save_dir / f'bert_confusion_matrix{suffix}.png'}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="BERT Risk Classification V2 (Improved)")
    parser.add_argument("--model", type=str, default="bert-base-chinese")
    parser.add_argument("--epochs", type=int, default=15, help="Max epochs (EarlyStopping may stop earlier)")
    parser.add_argument("--batch-size", type=int, default=16, help="Smaller batch for better generalization")
    parser.add_argument("--lr", type=float, default=1e-5, help="Lower LR to prevent overfitting")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--dropout", type=float, default=0.4, help="Higher dropout")
    parser.add_argument("--weight-decay", type=float, default=0.02, help="Stronger regularization")
    parser.add_argument("--patience", type=int, default=2, help="EarlyStopping patience")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 60)
    print(f"  BERT Risk Classification V2 (Improved)")
    print(f"  Device: {device}")
    print(f"  Classes: {NUM_LABELS} ({', '.join(LABEL_NAMES.values())})")
    print(f"  Epochs: {args.epochs} (max), Patience: {args.patience}")
    print(f"  LR: {args.lr}, Dropout: {args.dropout}, Weight Decay: {args.weight_decay}")
    print(f"  Batch Size: {args.batch_size}")
    print("=" * 60)

    # 1. Load tokenizer & datasets
    tokenizer = BertTokenizer.from_pretrained(args.model)
    train_dataset = RiskDatasetV2(DATA_DIR / "train.jsonl", tokenizer, args.max_length)
    val_dataset = RiskDatasetV2(DATA_DIR / "val.jsonl", tokenizer, args.max_length)
    test_dataset = RiskDatasetV2(DATA_DIR / "test.jsonl", tokenizer, args.max_length)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2)

    # 2. Compute class weights
    from collections import Counter
    train_labels = [s["label"] for s in train_dataset.samples]
    counter = Counter(train_labels)
    total = len(train_labels)
    weights = torch.tensor([total / (NUM_LABELS * counter.get(i, 1)) for i in range(NUM_LABELS)], dtype=torch.float)
    print(f"[INFO] Class weights: {[round(w, 3) for w in weights.tolist()]}")

    # 3. Build model
    model = BertRiskClassifierV2(args.model, NUM_LABELS, args.dropout)
    model.to(device)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[INFO] Trainable params: {trainable_params:,} / {total_params:,}")

    # 4. Optimizer & Scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    # 5. Training loop with EarlyStopping
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "val_f1": []}
    best_val_f1 = 0.0
    best_epoch = 0
    patience_counter = 0
    stopped_epoch = None
    start_time = time.time()

    print("\n[Training]")
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, scheduler, device, weights)
        val_loss, val_acc, val_f1, val_recall_high, _, _ = evaluate(model, val_loader, device, weights)

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
            patience_counter = 0
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_f1": val_f1,
                "config": vars(args),
                "label_names": LABEL_NAMES,
            }, OUTPUT_DIR / "checkpoint.pt")
            tokenizer.save_pretrained(str(OUTPUT_DIR))
            marker = " ★ BEST"
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                stopped_epoch = epoch
                print(f"\n  ⏹ EarlyStopping triggered at epoch {epoch}! "
                      f"(no improvement for {args.patience} epochs)")
                print(f"  Best model was at epoch {best_epoch} with F1={best_val_f1:.4f}")
                break

        overfit_gap = train_acc - val_acc
        print(f"  Epoch {epoch:3d}/{args.epochs} | "
              f"Train: {train_loss:.4f}/{train_acc:.4f} | "
              f"Val: {val_loss:.4f}/{val_acc:.4f}/F1:{val_f1:.4f} | "
              f"Recall(高):{val_recall_high:.4f} | "
              f"Gap:{overfit_gap:.3f} | {elapsed:.1f}s{marker}")

    history["stopped_epoch"] = stopped_epoch
    total_time = time.time() - start_time
    actual_epochs = stopped_epoch if stopped_epoch else args.epochs
    print(f"\n[Done] Training completed in {total_time:.1f}s. "
          f"Ran {actual_epochs} epochs. Best: epoch {best_epoch} (F1={best_val_f1:.4f})")

    # 6. Test evaluation
    print("\n[Test Evaluation]")
    checkpoint = torch.load(OUTPUT_DIR / "checkpoint.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc, test_f1, test_recall_high, test_preds, test_labels = evaluate(model, test_loader, device, weights)

    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Test F1-macro: {test_f1:.4f}")
    print(f"  Test Recall(高风险): {test_recall_high:.4f}")
    print(f"\n{classification_report(test_labels, test_preds, target_names=[LABEL_NAMES[i] for i in range(NUM_LABELS)], zero_division=0)}")

    # 7. Compare with v1
    v1_log = DATA_DIR / "training_log.json"
    comparison = ""
    if v1_log.exists():
        with open(v1_log) as f:
            v1 = json.load(f)
        v1_acc = v1["test_metrics"]["accuracy"]
        v1_f1 = v1["test_metrics"]["f1_macro"]
        comparison = f"""
## Comparison with V1 (4-class)
| Metric | V1 (4-class) | V2 (3-class) | Change |
|--------|-------------|-------------|--------|
| Accuracy | {v1_acc:.4f} | {test_acc:.4f} | {test_acc-v1_acc:+.4f} |
| F1-macro | {v1_f1:.4f} | {test_f1:.4f} | {test_f1-v1_f1:+.4f} |

### Improvements applied:
- Merged label 2+3 into single 'high-risk' class (solve sample scarcity)
- Lowered learning rate: 2e-5 → {args.lr}
- Increased dropout: 0.3 → {args.dropout}
- Added weight decay: 0.01 → {args.weight_decay}
- Reduced batch size: 32 → {args.batch_size}
- Added EarlyStopping (patience={args.patience})
- Added 2-layer classifier head with Tanh activation
"""

    # 8. Save results
    log = {
        "version": "v2",
        "config": vars(args),
        "history": history,
        "best_epoch": best_epoch,
        "best_val_f1": best_val_f1,
        "stopped_epoch": stopped_epoch,
        "test_metrics": {
            "loss": test_loss, "accuracy": test_acc,
            "f1_macro": test_f1, "recall_high_risk": test_recall_high,
        },
        "training_time_sec": total_time,
    }
    with open(DATA_DIR / "training_log_v2.json", "w") as f:
        json.dump(log, f, indent=2)

    plot_training_curves(history, FIGURE_DIR)
    plot_confusion_matrix(test_labels, test_preds, FIGURE_DIR)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# BERT Risk Classifier V2 Evaluation Report",
        "",
        "## Configuration",
        f"- Model: `{args.model}`",
        f"- Classes: {NUM_LABELS} ({', '.join(LABEL_NAMES.values())})",
        f"- Max Epochs: {args.epochs}, Actual: {actual_epochs}, Patience: {args.patience}",
        f"- LR: {args.lr}, Dropout: {args.dropout}, Weight Decay: {args.weight_decay}",
        f"- Batch Size: {args.batch_size}",
        f"- Device: {device}",
        f"- Training Time: {total_time:.1f}s",
        "",
        "## Test Set Results",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Accuracy | {test_acc:.4f} |",
        f"| F1-macro | {test_f1:.4f} |",
        f"| Recall (高风险) | {test_recall_high:.4f} |",
        f"| Loss | {test_loss:.4f} |",
        "",
        "## Classification Report",
        "```",
        classification_report(test_labels, test_preds, target_names=[LABEL_NAMES[i] for i in range(NUM_LABELS)], zero_division=0),
        "```",
        comparison,
        f"## Best Checkpoint",
        f"- Epoch: {best_epoch}, Val F1: {best_val_f1:.4f}",
        f"- Saved at: `{OUTPUT_DIR / 'checkpoint.pt'}`",
    ]
    with open(REPORT_DIR / "bert_eval_summary_v2.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ All outputs saved:")
    print(f"   Model:      {OUTPUT_DIR / 'checkpoint.pt'}")
    print(f"   Log:        {DATA_DIR / 'training_log_v2.json'}")
    print(f"   Curves:     {FIGURE_DIR / 'bert_training_curves_v2.png'}")
    print(f"   ConfMatrix: {FIGURE_DIR / 'bert_confusion_matrix_v2.png'}")
    print(f"   Report:     {REPORT_DIR / 'bert_eval_summary_v2.md'}")


if __name__ == "__main__":
    main()
