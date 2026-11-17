#!/usr/bin/env python3
"""
CNN 面部表情分类 - 训练脚本
==============================
模型：MobileNetV2 (pretrained ImageNet) + 7分类头
数据：data/fer_cnn/{train,val,test}/ (ImageFolder格式)

用法：
  python3 scripts/train_fer_cnn.py
  python3 scripts/train_fer_cnn.py --epochs 30 --lr 0.001
  python3 scripts/train_fer_cnn.py --model efficientnet_b0   # 换基座模型

输出：
  data/fer_cnn/best_model/   (最优checkpoint)
  data/fer_cnn/training_log.json
  evaluation/reports/cnn_eval_summary.md
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
OUTPUT_DIR = DATA_DIR / "best_model"
REPORT_DIR = PROJECT_ROOT / "evaluation" / "reports"
FIGURE_DIR = PROJECT_ROOT / "evaluation" / "figures"

LABEL_NAMES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
PSY_LABELS = ["愤怒/烦躁", "厌恶/排斥", "恐惧/焦虑", "积极/愉悦", "悲伤/低落", "惊讶/困惑", "平静/中性"]
NUM_CLASSES = 7


# ============================================================
# Model
# ============================================================
class MobileNetV2Classifier(nn.Module):
    """MobileNetV2 + 自定义分类头"""

    def __init__(self, num_classes=7, pretrained=True, freeze_backbone_layers=10):
        super().__init__()
        weights = models.MobileNet_V2_Weights.IMAGENET1K_V1 if pretrained else None
        self.backbone = models.mobilenet_v2(weights=weights)

        # 冻结前N层（迁移学习）
        if pretrained and freeze_backbone_layers > 0:
            frozen_count = 0
            for param in self.backbone.features.parameters():
                param.requires_grad = False
                frozen_count += 1
            # 解冻最后几层以适配新任务
            for param in list(self.backbone.features[-3:].parameters()):
                param.requires_grad = True
            print(f"[Model] Frozen {frozen_count} backbone params, unfreezed last 3 blocks")

        # 替换分类头
        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(in_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        return self.backbone(x)


def get_efficientnet_b0(num_classes=7, pretrained=True):
    """备选模型：EfficientNet-B0"""
    weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
    model = models.efficientnet_b0(weights=weights)
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Linear(256, num_classes),
    )
    return model


# ============================================================
# Data Transforms
# ============================================================
def get_transforms(is_train=True):
    """数据预处理 + 增强"""
    if is_train:
        return transforms.Compose([
            transforms.Grayscale(num_output_channels=3),  # 灰度→RGB（适配预训练模型）
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
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
def train_one_epoch(model, dataloader, criterion, optimizer, device):
    model.train()
    total_loss = 0
    all_preds, all_labels = [], []

    for images, labels in dataloader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        loss.backward()
        optimizer.step()
        optimizer.zero_grad()

        total_loss += loss.item() * images.size(0)
        preds = torch.argmax(outputs, dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

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
    ax1.set_title("CNN Expression Recognition - Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(history["train_acc"], label="Train Acc", linewidth=2)
    ax2.plot(history["val_acc"], label="Val Acc", linewidth=2)
    ax2.plot(history["val_f1"], label="Val F1-macro", linewidth=2, linestyle="--")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("CNN Expression Recognition - Metrics")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_dir / "cnn_training_curves.png", dpi=150)
    plt.close()
    print(f"[INFO] Training curves saved -> {save_dir / 'cnn_training_curves.png'}")


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
    ax.set_title("CNN Expression Recognition - Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_dir / "cnn_confusion_matrix.png", dpi=150)
    plt.close()
    print(f"[INFO] Confusion matrix saved -> {save_dir / 'cnn_confusion_matrix.png'}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="CNN Face Expression Recognition Training")
    parser.add_argument("--model", type=str, default="mobilenet_v2",
                        choices=["mobilenet_v2", "efficientnet_b0"],
                        help="Backbone model")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--freeze-layers", type=int, default=10,
                        help="Number of backbone layers to freeze")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 60)
    print(f"  CNN Face Expression Recognition Training")
    print(f"  Device: {device}")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}, Batch Size: {args.batch_size}, LR: {args.lr}")
    print("=" * 60)

    # 1. Check data directory
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
    print(f"[Data] Classes: {train_dataset.classes}")

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)

    # 3. Build model
    if args.model == "mobilenet_v2":
        model = MobileNetV2Classifier(NUM_CLASSES, pretrained=True, freeze_backbone_layers=args.freeze_layers)
    elif args.model == "efficientnet_b0":
        model = get_efficientnet_b0(NUM_CLASSES, pretrained=True)
    else:
        raise ValueError(f"Unknown model: {args.model}")

    model.to(device)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[Model] Trainable: {trainable_params:,} / {total_params:,} ({trainable_params/total_params*100:.1f}%)")

    # 4. Loss, Optimizer, Scheduler
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.SGD(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, momentum=0.9, weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.5)

    # 5. Training loop
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "val_f1": []}
    best_val_f1 = 0.0
    best_epoch = 0
    start_time = time.time()

    print("\n[Training]")
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
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
                "optimizer_state_dict": optimizer.state_dict(),
                "val_f1": val_f1,
                "config": {
                    "model": args.model,
                    "num_classes": NUM_CLASSES,
                    "classes": train_dataset.classes,
                },
            }, OUTPUT_DIR / "checkpoint.pt")
            marker = " ★ BEST"

        print(f"  Epoch {epoch:3d}/{args.epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} F1: {val_f1:.4f} | "
              f"LR: {current_lr:.6f} | {elapsed:.1f}s{marker}")

    total_time = time.time() - start_time
    print(f"\n[Done] Training completed in {total_time:.1f}s. Best epoch: {best_epoch} (F1={best_val_f1:.4f})")

    # 6. Test evaluation
    print("\n[Test Evaluation]")
    checkpoint = torch.load(OUTPUT_DIR / "checkpoint.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc, test_f1, test_preds, test_labels = evaluate(model, test_loader, criterion, device)

    print(f"  Test Loss: {test_loss:.4f}")
    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Test F1-macro: {test_f1:.4f}")
    print(f"\n{classification_report(test_labels, test_preds, target_names=LABEL_NAMES, zero_division=0)}")

    # 7. Save results
    log = {
        "config": vars(args),
        "history": history,
        "best_epoch": best_epoch,
        "best_val_f1": best_val_f1,
        "test_metrics": {"loss": test_loss, "accuracy": test_acc, "f1_macro": test_f1},
        "training_time_sec": total_time,
    }
    with open(DATA_DIR / "training_log.json", "w") as f:
        json.dump(log, f, indent=2)

    plot_training_curves(history, FIGURE_DIR)
    plot_confusion_matrix(test_labels, test_preds, FIGURE_DIR)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# CNN Expression Recognition Evaluation Report",
        "",
        "## Configuration",
        f"- Model: `{args.model}` (pretrained ImageNet)",
        f"- Epochs: {args.epochs}, Batch Size: {args.batch_size}, LR: {args.lr}",
        f"- Freeze Layers: {args.freeze_layers}",
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
        "",
        f"## Best Checkpoint",
        f"- Epoch: {best_epoch}, Val F1: {best_val_f1:.4f}",
        f"- Saved at: `{OUTPUT_DIR / 'checkpoint.pt'}`",
    ]
    with open(REPORT_DIR / "cnn_eval_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ All outputs saved:")
    print(f"   Model:      {OUTPUT_DIR / 'checkpoint.pt'}")
    print(f"   Log:        {DATA_DIR / 'training_log.json'}")
    print(f"   Curves:     {FIGURE_DIR / 'cnn_training_curves.png'}")
    print(f"   ConfMatrix: {FIGURE_DIR / 'cnn_confusion_matrix.png'}")
    print(f"   Report:     {REPORT_DIR / 'cnn_eval_summary.md'}")


if __name__ == "__main__":
    main()
