#!/usr/bin/env python3
"""
CNN 面部表情分类 - 数据预处理脚本
===================================
数据来源：
  FER2013 数据集（35,887张 48x48 灰度人脸表情图）
  7类标签：Angry(0), Disgust(1), Fear(2), Happy(3), Sad(4), Surprise(5), Neutral(6)

输出目录结构：
  data/fer_cnn/
  ├── train/
  │   ├── angry/
  │   ├── disgust/
  │   ├── fear/
  │   ├── happy/
  │   ├── sad/
  │   ├── surprise/
  │   └── neutral/
  ├── val/
  │   └── ... (同上)
  └── test/
      └── ... (同上)

用法：
  # 方式1：手动下载 fer2013.csv 放到 data/fer_cnn/fer2013.csv
  python3 scripts/prepare_fer_data.py

  # 方式2：自动从 kaggle 下载（需 pip install kagglehub）
  python3 scripts/prepare_fer_data.py --auto-download

  # 自定义输出路径
  python3 scripts/prepare_fer_data.py --output /path/to/output
"""

import argparse
import csv
import os
import random
from collections import Counter
from pathlib import Path

import numpy as np

# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "fer_cnn"
RANDOM_SEED = 42
VAL_RATIO = 0.1
TEST_RATIO = 0.1

# FER2013 标签映射
LABEL_NAMES = {
    0: "angry",
    1: "disgust",
    2: "fear",
    3: "happy",
    4: "sad",      # FER2013 原始标签4是 "Sad" (有些版本叫 "Surprise")
    5: "surprise",  # FER2013 原始标签5是 "Surprise" (有些版本叫 "Sad")
    6: "neutral",
}

# 心理咨询场景的情绪映射（可选，用于报告说明）
PSY_LABEL_MAP = {
    "angry": "愤怒/烦躁",
    "disgust": "厌恶/排斥",
    "fear": "恐惧/焦虑",
    "happy": "积极/愉悦",
    "sad": "悲伤/低落",
    "surprise": "惊讶/困惑",
    "neutral": "平静/中性",
}


# ============================================================
# 数据加载
# ============================================================
def auto_download_fer2013(output_dir: Path) -> Path:
    """尝试自动下载 FER2013 数据集"""
    csv_path = output_dir / "fer2013.csv"
    if csv_path.exists():
        print(f"[INFO] FER2013 already exists at {csv_path}")
        return csv_path

    # 尝试 kagglehub
    try:
        import kagglehub
        print("[INFO] Downloading FER2013 via kagglehub...")
        download_path = kagglehub.dataset_download("msambare/fer2013")
        # 查找 csv 文件
        for root, dirs, files in os.walk(download_path):
            for f in files:
                if f.endswith(".csv") and "fer" in f.lower():
                    src = Path(root) / f
                    output_dir.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(str(src), str(csv_path))
                    print(f"[INFO] Copied {src} -> {csv_path}")
                    return csv_path
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] kagglehub download failed: {e}")

    # 尝试 keras datasets
    try:
        print("[INFO] Trying alternative: generating synthetic placeholder...")
        print("[WARN] Please manually download fer2013.csv from:")
        print("       https://www.kaggle.com/datasets/msambare/fer2013")
        print(f"       and place it at: {csv_path}")
        return None
    except Exception:
        pass

    print(f"[ERROR] Cannot auto-download. Please manually download fer2013.csv")
    print(f"        and place it at: {csv_path}")
    return None


def load_fer2013(csv_path: Path) -> list[dict]:
    """
    加载 FER2013 CSV 文件。
    格式：emotion,pixels,Usage
      - emotion: 0-6 整数
      - pixels: 空格分隔的 2304 个像素值 (48x48)
      - Usage: Training / PublicTest / PrivateTest
    """
    samples = []
    usage_count = Counter()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header

        for row in reader:
            if len(row) < 3:
                continue
            try:
                emotion = int(row[0])
                pixels = [int(p) for p in row[1].split()]
                usage = row[2].strip()
            except (ValueError, IndexError):
                continue

            if emotion < 0 or emotion > 6:
                continue
            if len(pixels) != 2304:  # 48*48
                continue

            # 将像素转为 48x48 numpy array
            img_array = np.array(pixels, dtype=np.uint8).reshape(48, 48)

            samples.append({
                "image": img_array,
                "label": emotion,
                "label_name": LABEL_NAMES[emotion],
                "usage": usage,
            })
            usage_count[usage] += 1

    print(f"[INFO] FER2013 loaded: {len(samples)} images")
    print(f"[INFO] Usage split: {dict(usage_count)}")
    return samples


# ============================================================
# 数据增强
# ============================================================
def augment_image(img: np.ndarray) -> np.ndarray:
    """
    对单张 48x48 灰度图做随机数据增强。
    仅在训练时使用。
    """
    try:
        from PIL import Image, ImageOps, ImageFilter
    except ImportError:
        return img  # 无PIL则不增强

    pil_img = Image.fromarray(img, mode="L")

    # 随机水平翻转 (50%)
    if random.random() > 0.5:
        pil_img = ImageOps.mirror(pil_img)

    # 随机旋转 (-15° ~ +15°)
    angle = random.uniform(-15, 15)
    pil_img = pil_img.rotate(angle, resample=Image.BILINEAR, fillcolor=128)

    # 随机亮度调整 (0.8 ~ 1.2)
    factor = random.uniform(0.8, 1.2)
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Brightness(pil_img)
    pil_img = enhancer.enhance(factor)

    # 随机裁剪+缩放 (模拟平移)
    if random.random() > 0.5:
        crop_size = random.randint(40, 46)
        left = random.randint(0, 48 - crop_size)
        top = random.randint(0, 48 - crop_size)
        pil_img = pil_img.crop((left, top, left + crop_size, top + crop_size))
        pil_img = pil_img.resize((48, 48), Image.BILINEAR)

    return np.array(pil_img, dtype=np.uint8)


# ============================================================
# 划分 & 保存
# ============================================================
def split_by_usage(samples: list[dict]):
    """
    FER2013 自带 Training/PublicTest/PrivateTest 划分。
    我们使用：Training → train+val, PublicTest+PrivateTest → test
    """
    train_samples = [s for s in samples if s["usage"] == "Training"]
    test_samples = [s for s in samples if s["usage"] in ("PublicTest", "PrivateTest")]

    # 从 Training 中分出 val
    random.seed(RANDOM_SEED)
    random.shuffle(train_samples)
    n_val = max(1, int(len(train_samples) * VAL_RATIO))
    val_samples = train_samples[:n_val]
    train_samples = train_samples[n_val:]

    return train_samples, val_samples, test_samples


def save_image_dataset(samples: list[dict], output_dir: Path, split_name: str,
                       do_augment: bool = False, augment_factor: int = 3):
    """
    保存为图片文件夹结构（兼容 torchvision.datasets.ImageFolder）。
    每个类别一个子文件夹，图片保存为 PNG。
    """
    saved = 0
    label_counter = Counter()

    for s in samples:
        label_name = s["label_name"]
        class_dir = output_dir / split_name / label_name
        class_dir.mkdir(parents=True, exist_ok=True)

        # 保存原图
        idx = label_counter[label_name]
        img_path = class_dir / f"{idx:05d}.png"

        try:
            from PIL import Image
            pil_img = Image.fromarray(s["image"], mode="L")
            pil_img.save(str(img_path))
        except ImportError:
            # 无PIL时用numpy保存
            np.save(str(img_path).replace(".png", ".npy"), s["image"])

        label_counter[label_name] += 1
        saved += 1

        # 训练集做数据增强
        if do_augment:
            for aug_i in range(augment_factor):
                aug_img = augment_image(s["image"])
                aug_path = class_dir / f"{idx:05d}_aug{aug_i}.png"
                try:
                    from PIL import Image
                    pil_aug = Image.fromarray(aug_img, mode="L")
                    pil_aug.save(str(aug_path))
                except ImportError:
                    np.save(str(aug_path).replace(".png", ".npy"), aug_img)
                saved += 1

    print(f"[INFO] {split_name}: saved {saved} images ({len(samples)} original"
          f"{', ' + str(saved - len(samples)) + ' augmented' if do_augment else ''})")
    for label_name in sorted(label_counter.keys()):
        count = label_counter[label_name]
        total_aug = count * (augment_factor + 1) if do_augment else count
        psy_label = PSY_LABEL_MAP.get(label_name, label_name)
        print(f"    {label_name:10s} ({psy_label:8s}): {total_aug:5d}")


def print_stats(name: str, samples: list[dict]):
    """打印数据集统计"""
    counter = Counter(s["label"] for s in samples)
    total = len(samples)
    print(f"\n{'='*50}")
    print(f"  {name}: {total} samples")
    print(f"{'='*50}")
    for label in sorted(LABEL_NAMES.keys()):
        name_str = LABEL_NAMES[label]
        psy = PSY_LABEL_MAP.get(name_str, name_str)
        count = counter.get(label, 0)
        pct = count / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  {label} {name_str:10s} ({psy:8s}): {count:5d} ({pct:5.1f}%) {bar}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="CNN Face Expression Recognition Data Preparation")
    parser.add_argument("--auto-download", action="store_true",
                        help="Auto-download FER2013 via kagglehub")
    parser.add_argument("--csv-path", type=str, default=None,
                        help="Path to fer2013.csv (default: data/fer_cnn/fer2013.csv)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (default: data/fer_cnn/)")
    parser.add_argument("--augment-factor", type=int, default=3,
                        help="Number of augmented copies per training image (default: 3)")
    parser.add_argument("--no-augment", action="store_true",
                        help="Disable data augmentation for training set")
    args = parser.parse_args()

    print("=" * 60)
    print("  CNN Face Expression Recognition - Data Preparation")
    print("=" * 60)

    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取 FER2013 CSV
    csv_path = Path(args.csv_path) if args.csv_path else output_dir / "fer2013.csv"
    if not csv_path.exists():
        if args.auto_download:
            csv_path = auto_download_fer2013(output_dir)
        if csv_path is None or not csv_path.exists():
            print(f"\n[ERROR] fer2013.csv not found at {csv_path}")
            print("Please download from: https://www.kaggle.com/datasets/msambare/fer2013")
            print(f"And place it at: {output_dir / 'fer2013.csv'}")
            return

    # 2. 加载数据
    samples = load_fer2013(csv_path)
    if not samples:
        print("[ERROR] No valid samples loaded!")
        return

    # 3. 打印原始分布
    print_stats("Original (all)", samples)

    # 4. 划分
    train, val, test = split_by_usage(samples)
    print_stats("Train (before augment)", train)
    print_stats("Val", val)
    print_stats("Test", test)

    # 5. 保存为图片文件夹
    do_augment = not args.no_augment
    save_image_dataset(train, output_dir, "train",
                       do_augment=do_augment, augment_factor=args.augment_factor)
    save_image_dataset(val, output_dir, "val", do_augment=False)
    save_image_dataset(test, output_dir, "test", do_augment=False)

    # 6. 保存标签映射
    import json
    label_map = {str(k): {"en": v, "psy": PSY_LABEL_MAP.get(v, v)}
                 for k, v in LABEL_NAMES.items()}
    with open(output_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Data preparation complete!")
    print(f"   Output directory: {output_dir}")
    print(f"   Directory structure:")
    print(f"     {output_dir}/train/<class_name>/<image>.png")
    print(f"     {output_dir}/val/<class_name>/<image>.png")
    print(f"     {output_dir}/test/<class_name>/<image>.png")


if __name__ == "__main__":
    main()
