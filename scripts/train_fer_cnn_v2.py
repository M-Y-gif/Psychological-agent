#!/usr/bin/env python3
"""
CNN 面部表情分类 - 改进版训练脚本 (v2)
==========================================
改进点：
  1. 默认 epoch 40（上次第20轮还在提升，没学完）
  2. CosineAnnealing 学习率调度（比StepLR更平滑）
  3. 支持 EfficientNet-B0（更强的模型）
  4. Mixup 数据增强（提升泛化能力）
  5. 更大的图片尺寸 224→224（保持），但增加更多增强策略
  6. Label Smoothing 0.1（防止过度自信）

用法：
  # MobileNetV2 + 40 epoch（默认）
  python3 scripts/train_fer_cnn_v2.py

  # EfficientNet-B0（更强但更慢）
  python3 scripts/train_fer_cnn_v2.py --model efficientnet_b0

  # 自定义
  python3 scripts/train_fer_cnn_v2.py --epochs 50 --lr 0.0005 --mixup-alpha 0.2

输出：
  data/fer_cnn/best_model_v2/checkpoint.pt
  evaluation/reports/cnn_eval_summary_v2.md
  evaluation/figures/cnn_training_curves_v2.png
  evaluation/figures/cnn_confusion_matrix_v2.png
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from sklearn.metrics import (
    accuracy_score, f1_score, recall_score,
    classification_report, confusion_matrix,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "fer_cnn"
OUTPUT_DIR = DATA_DIR / "best_model_v2"
REPORT_DIR = PROJECT_ROOT / "evaluation" / "reports"
FIGURE_DIR = PROJECT_ROOT / "evaluation" / "figures"

LABEL_NAMES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
PSY_LABELS = ["愤怒/烦躁", "厌恶/排斥", "恐惧/焦虑", "积极/愉悦", "悲伤/低落", "惊讶/困惑", "平静/中性"]
NUM_CLASSES = 7


# ============================================================
# Mixup Augmentation
# ============================================================
def mixup_data(x, y, alpha=0.2):
    """Mixup: 将两张图片和标签混合，提升泛化能力"""
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1.0
    batch_size = x.size(0)
    index = torch.randperm(batch_size).to(x.device)
    mixed_x = lam * x + (1 - lam) * x[index, :]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    """Mixup loss"""
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


# ============================================================
# Models
# ============================================================
class MobileNetV2ClassifierV2(nn.Module):
    def __init__(self, num_classes=7, pretrained=True):
        super().__init__()
        weights = models.MobileNet_V2_Weights.IMAGENET1K_V1 if pretrained else None
        self.backbone = models.mobilenet_v2(weights=weights)

        # 冻结前面的层，只训练后面
        for param in list(self.backbone.features.parameters())[:-20]:
            param.requires_grad = False

        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(0.4),
            nn.Linear(in_features, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        return self.backbone(x)


class EfficientNetB0Classifier(nn.Module):
    def __init__(self, num_classes=7, pretrained=True):
        super().__init__()
        weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        self.backbone = models.efficientnet_b0(weights=weights)

        # 冻结前面的层
        for param in list(self.backbone.features.parameters())[:-15]:
            param.requires_grad = False

        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(0.4),
            nn.Linear(in_features, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        return self.backbone(x)


# ============================================================
# Data Transforms (增强版)
# ============================================================
def get_transforms(is_train=True):
    if is_train:
        return transforms.Compose([
            transforms.Grayscale(num_output_channels=3),
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(20),  # 增大旋转角度
            transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
            transforms.RandomAffine(degrees=0, translate=(0.1, 0.1), scale=(0.9, 1.1)),
            transforms.RandomGrayscale(p=0.1),  # 随机灰度
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
            transforms.RandomErasing(p=0.2, scale=(0.02, 0.1)),  # 随机擦除
        ])
    else:
        return transforms.Compose([
            transforms.Grayscale(num_output_channels=3),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])


# ============================================================
# Training
# ============================================================
def train_one_epoch(model, dataloader, criterion, optimizer, device, mixup_alpha=0.0):
    model.train()
    total_loss = 0
    all_preds, all_labels = [], []

    for images, labels in dataloader:
        images = images.to(device)
        labels = labels.to(device)

        if mixup_alpha > 0 and np.random.random() > 0.5:
            # 50%概率使用Mixup
            images, labels_a, labels_b, lam = mixup_data(images, labels, mixup_alpha)
            outputs = model(images)
            loss = mixup_criterion(criterion, outputs, labels_a, labels_b, lam)
            # 用原始labels记录预测（近似）
            preds = torch.argmax(outputs, dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())
        else:
            outputs = model(images)
            loss = criterion(outputs, labels)
            preds = torch.argmax(outputs, dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())

        loss.backward()
        optimizer.step()
        optimizer.zero_grad()

        total_loss += loss.item() * images.size(0)

    avg_loss = total_loss / len(dataloader.dataset)
    acc = accuracy_score(all_labels, all_preds)
    return avg_loss, acc


@torch.no_grad()
def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0
    all_preds, all_labels = [], []

    for images, labels in dataloader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        preds = torch.argmax(outputs, dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader.dataset)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    return avg_loss, acc, f1, all_preds, all_labels


# ============================================================
# Visualization
# ============================================================
def plot_training_curves(history: dict, save_dir: Path):
    save_dir.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(history["train_loss"], label="Train Loss", linewidth=2)
    ax1.plot(history["val_loss"], label="Val Loss", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("CNN v2 - Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(history["train_acc"], label="Train Acc", linewidth=2)
    ax2.plot(history["val_acc"], label="Val Acc", linewidth=2)
    ax2.plot(history["val_f1"], label="Val F1-macro", linewidth=2, linestyle="--")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("CNN v2 - Metrics (CosineAnnealing)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_dir / "cnn_training_curves_v2.png", dpi=150)
    plt.close()
    print(f"[INFO] Training curves saved -> {save_dir / 'cnn_training_curves_v2.png'}")


def plot_confusion_matrix(labels, preds, save_dir: Path):
    save_dir.mkdir(parents=True, exist_ok=True)
    cm = confusion_matrix(labels, preds, labels=list(range(NUM_CLASSES)))

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)

    tick_labels = [f"{LABEL_NAMES[i]}\n{PSY_LABELS[i]}" for i in range(NUM_CLASSES)]
    ax.set_xticks(range(NUM_CLASSES))
    ax.set_yticks(range(NUM_CLASSES))
    ax.set_xticklabels(tick_labels, fontsize=8, rotation=45, ha="right")
    ax.set_yticklabels(tick_labels, fontsize=8)

    thresh = cm.max() / 2.0
    for i in range(NUM_CLASSES):
        for j in range(NUM_CLASSES):
            ax.text(j, i, format(cm[i, j], "d"),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black",
                    fontsize=9)

    ax.set_ylabel("True Label")
    ax.set_xlabel("Predicted Label")
    ax.set_title("CNN v2 - Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_dir / "cnn_confusion_matrix_v2.png", dpi=150)
    plt.close()
    print(f"[INFO] Confusion matrix saved -> {save_dir / 'cnn_confusion_matrix_v2.png'}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="CNN Expression Recognition V2 (Improved)")
    parser.add_argument("--model", type=str, default="mobilenet_v2",
                        choices=["mobilenet_v2", "efficientnet_b0"])
    parser.add_argument("--epochs", type=int, default=40, help="More epochs (was 20)")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--mixup-alpha", type=float, default=0.2, help="Mixup alpha (0=disabled)")
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 60)
    print(f"  CNN Expression Recognition V2 (Improved)")
    print(f"  Device: {device}")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}, Batch Size: {args.batch_size}, LR: {args.lr}")
    print(f"  Mixup Alpha: {args.mixup_alpha}, Label Smoothing: {args.label_smoothing}")
    print("=" * 60)

    # 1. Check data
    train_dir = DATA_DIR / "train"
    val_dir = DATA_DIR / "val"
    test_dir = DATA_DIR / "test"
    if not train_dir.exists():
        print(f"[ERROR] Training data not found at {train_dir}")
        print("Please run: python3 scripts/prepare_fer_data.py first")
        return

    # 2. Load datasets
    train_dataset = ImageFolder(str(train_dir), transform=get_transforms(is_train=True))
    val_dataset = ImageFolder(str(val_dir), transform=get_transforms(is_train=False))
    test_dataset = ImageFolder(str(test_dir), transform=get_transforms(is_train=False))

    print(f"[Data] Train: {len(train_dataset)}, Val: {len(val_dataset)}, Test: {len(test_dataset)}")

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True,
                              num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)

    # 3. Build model
    if args.model == "mobilenet_v2":
        model = MobileNetV2ClassifierV2(NUM_CLASSES, pretrained=True)
    elif args.model == "efficientnet_b0":
        model = EfficientNetB0Classifier(NUM_CLASSES, pretrained=True)

    model.to(device)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[Model] Trainable: {trainable_params:,} / {total_params:,} ({trainable_params/total_params*100:.1f}%)")

    # 4. Loss, Optimizer, Scheduler (CosineAnnealing)
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)

    # 5. Training loop
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "val_f1": []}
    best_val_f1 = 0.0
    best_epoch = 0
    start_time = time.time()

    print("\n[Training]")
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device, args.mixup_alpha)
        val_loss, val_acc, val_f1, _, _ = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        elapsed = time.time() - epoch_start
        current_lr = optimizer.param_groups[0]["lr"]
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)

        marker = ""
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = epoch
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_f1": val_f1,
                "config": vars(args),
                "classes": train_dataset.classes,
            }, OUTPUT_DIR / "checkpoint.pt")
            marker = " ★ BEST"

        print(f"  Epoch {epoch:3d}/{args.epochs} | "
              f"Train: {train_loss:.4f}/{train_acc:.4f} | "
              f"Val: {val_loss:.4f}/{val_acc:.4f}/F1:{val_f1:.4f} | "
              f"LR:{current_lr:.6f} | {elapsed:.1f}s{marker}")

    total_time = time.time() - start_time
    print(f"\n[Done] Training completed in {total_time:.1f}s. Best: epoch {best_epoch} (F1={best_val_f1:.4f})")

    # 6. Test evaluation
    print("\n[Test Evaluation]")
    checkpoint = torch.load(OUTPUT_DIR / "checkpoint.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc, test_f1, test_preds, test_labels = evaluate(model, test_loader, criterion, device)

    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Test F1-macro: {test_f1:.4f}")
    print(f"\n{classification_report(test_labels, test_preds, target_names=LABEL_NAMES, zero_division=0)}")

    # 7. Compare with v1
    v1_log = DATA_DIR / "training_log.json"
    comparison = ""
    if v1_log.exists():
        with open(v1_log) as f:
            v1 = json.load(f)
        v1_acc = v1["test_metrics"]["accuracy"]
        v1_f1 = v1["test_metrics"]["f1_macro"]
        comparison = f"""
## Comparison with V1
| Metric | V1 (20ep, StepLR) | V2 ({args.epochs}ep, Cosine+Mixup) | Change |
|--------|-------------------|-------------------------------|--------|
| Accuracy | {v1_acc:.4f} | {test_acc:.4f} | {test_acc-v1_acc:+.4f} |
| F1-macro | {v1_f1:.4f} | {test_f1:.4f} | {test_f1-v1_f1:+.4f} |

### Improvements applied:
- More epochs: 20 → {args.epochs}
- CosineAnnealing LR schedule (smoother decay)
- Mixup augmentation (alpha={args.mixup_alpha})
- RandomErasing augmentation
- AdamW optimizer (was SGD)
- Stronger classifier head (512 hidden + BatchNorm)
- More aggressive data augmentation (rotation 20°, scale jitter)
"""

    # 8. Save results
    log = {
        "version": "v2",
        "config": vars(args),
        "history": history,
        "best_epoch": best_epoch,
        "best_val_f1": best_val_f1,
        "test_metrics": {"loss": test_loss, "accuracy": test_acc, "f1_macro": test_f1},
        "training_time_sec": total_time,
    }
    with open(DATA_DIR / "training_log_v2.json", "w") as f:
        json.dump(log, f, indent=2)

    plot_training_curves(history, FIGURE_DIR)
    plot_confusion_matrix(test_labels, test_preds, FIGURE_DIR)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# CNN Expression Recognition V2 Evaluation Report",
        "",
        "## Configuration",
        f"- Model: `{args.model}` (pretrained ImageNet)",
        f"- Epochs: {args.epochs}, Batch Size: {args.batch_size}, LR: {args.lr}",
        f"- Mixup Alpha: {args.mixup_alpha}, Label Smoothing: {args.label_smoothing}",
        f"- Scheduler: CosineAnnealingLR",
        f"- Device: {device}",
        f"- Training Time: {total_time:.1f}s",
        "",
        "## Test Set Results",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Accuracy | {test_acc:.4f} |",
        f"| F1-macro | {test_f1:.4f} |",
        f"| Loss | {test_loss:.4f} |",
        "",
        "## Classification Report",
        "```",
        classification_report(test_labels, test_preds, target_names=LABEL_NAMES, zero_division=0),
        "```",
        comparison,
        f"## Best Checkpoint",
        f"- Epoch: {best_epoch}, Val F1: {best_val_f1:.4f}",
        f"- Saved at: `{OUTPUT_DIR / 'checkpoint.pt'}`",
    ]
    with open(REPORT_DIR / "cnn_eval_summary_v2.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ All outputs saved:")
    print(f"   Model:      {OUTPUT_DIR / 'checkpoint.pt'}")
    print(f"   Log:        {DATA_DIR / 'training_log_v2.json'}")
    print(f"   Curves:     {FIGURE_DIR / 'cnn_training_curves_v2.png'}")
    print(f"   ConfMatrix: {FIGURE_DIR / 'cnn_confusion_matrix_v2.png'}")
    print(f"   Report:     {REPORT_DIR / 'cnn_eval_summary_v2.md'}")


if __name__ == "__main__":
    main()
