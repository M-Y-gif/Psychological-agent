#!/usr/bin/env python3
"""
BERT 心理风险分类 - 数据预处理脚本
===================================
数据来源：
  1. PsyCrisis-Bench.xlsx  (608条, label 0/1/2)
  2. test_set.csv           (130条, gold_level 0-3, 带category)
  3. risk_eval_cases.csv    (评测案例, 可选补充)

输出：
  data/bert_risk/train.jsonl   (~80%)
  data/bert_risk/val.jsonl     (~10%)
  data/bert_risk/test.jsonl    (~10%)
  data/bert_risk/label_map.json

标签体系（4级）：
  0 = 无明显风险
  1 = 轻度情绪困扰
  2 = 中高风险（强烈负面情绪/隐晦自伤意念）
  3 = 极高风险（明确自伤/自杀意图或计划）

用法：
  python3 scripts/prepare_risk_data.py
  python3 scripts/prepare_risk_data.py --add-soulchat   # 追加SoulChatCorpus（需先下载）
"""

import argparse
import csv
import json
import os
import random
import re
from collections import Counter
from pathlib import Path

# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "evaluation" / "data"
OUTPUT_DIR = PROJECT_ROOT / "data" / "bert_risk"
RANDOM_SEED = 42
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
# TEST_RATIO = 0.1 (remainder)

LABEL_NAMES = {
    0: "无风险",
    1: "轻度困扰",
    2: "中高风险",
    3: "极高风险",
}


# ============================================================
# 数据加载
# ============================================================
def load_psycrisis_bench(filepath: Path) -> list[dict]:
    """加载 PsyCrisis-Bench.xlsx，label 0/1/2 → 映射到 0/1/2"""
    try:
        import openpyxl
    except ImportError:
        print("[WARN] openpyxl not installed, skipping PsyCrisis-Bench")
        return []

    wb = openpyxl.load_workbook(str(filepath), read_only=True)
    ws = wb["Sheet1"]
    samples = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        label_raw, text = row[0], row[1]
        if label_raw is None or text is None:
            continue
        label = int(str(label_raw).strip())
        text = str(text).strip()
        if not text:
            continue
        # PsyCrisis-Bench 原始标签 0/1/2 直接对应我们的 0/1/2
        samples.append({"text": text, "label": label, "source": "psycrisis"})
    wb.close()
    print(f"[INFO] PsyCrisis-Bench: {len(samples)} samples loaded")
    return samples


def load_test_set(filepath: Path) -> list[dict]:
    """加载 test_set.csv，gold_level 0-3 直接使用"""
    samples = []
    if not filepath.exists():
        print(f"[WARN] {filepath} not found, skipping")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", "").strip()
            level = row.get("gold_level", "").strip()
            category = row.get("category", "").strip()
            if not text or not level:
                continue
            label = int(level)
            label = max(0, min(3, label))  # clamp to 0-3
            samples.append({
                "text": text,
                "label": label,
                "source": "test_set",
                "category": category,
            })
    print(f"[INFO] test_set.csv: {len(samples)} samples loaded")
    return samples


def load_risk_eval_cases(filepath: Path) -> list[dict]:
    """加载评测案例中的漏报样本（gold>=2 且模型判低的），作为难例补充"""
    samples = []
    if not filepath.exists():
        print(f"[WARN] {filepath} not found, skipping")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("message", row.get("text", "")).strip()
            gold = row.get("gold_level", row.get("gold", "")).strip()
            if not text or not gold:
                continue
            try:
                label = int(float(gold))
            except ValueError:
                continue
            label = max(0, min(3, label))
            samples.append({
                "text": text,
                "label": label,
                "source": "eval_cases",
            })
    print(f"[INFO] risk_eval_cases: {len(samples)} samples loaded")
    return samples


def load_soulchat_emotion(data_dir: Path, max_samples: int = 5000) -> list[dict]:
    """
    加载 SoulChatCorpus 情绪对话子集（可选）。
    将情绪标签映射为风险等级：
      - 积极/平静/希望 → 0
      - 焦虑/困惑/孤独 → 1
      - 悲伤/绝望/愤怒 → 2
      - 自伤/自杀相关 → 3
    """
    emotion_to_risk = {
        # 低风险
        "高兴": 0, "开心": 0, "平静": 0, "安心": 0, "感激": 0,
        "希望": 0, "放松": 0, "满足": 0, "自信": 0,
        # 轻度困扰
        "焦虑": 1, "紧张": 1, "困惑": 1, "孤独": 1, "担心": 1,
        "不安": 1, "迷茫": 1, "压力": 1, "疲惫": 1,
        # 中高风险
        "悲伤": 2, "难过": 2, "绝望": 2, "愤怒": 2, "痛苦": 2,
        "无助": 2, "空虚": 2, "崩溃": 2, "抑郁": 2,
        # 极高风险
        "自伤": 3, "自杀": 3, "想死": 3,
    }

    samples = []
    if not data_dir.exists():
        print(f"[WARN] SoulChat dir {data_dir} not found, skipping")
        return []

    # 尝试读取常见格式
    for fname in sorted(data_dir.glob("*.json*")):
        with open(fname, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 提取用户消息和情绪标签
                text = ""
                emotion = ""
                if isinstance(obj, dict):
                    # sharegpt 格式
                    convs = obj.get("conversations", obj.get("messages", []))
                    if convs:
                        for c in convs:
                            role = c.get("from", c.get("role", ""))
                            if role in ("human", "user"):
                                text = c.get("value", c.get("content", ""))
                                break
                    emotion = obj.get("emotion", obj.get("label", ""))
                elif isinstance(obj, list):
                    # 纯对话列表
                    for item in obj:
                        if isinstance(item, dict) and item.get("role") == "user":
                            text = item.get("content", "")
                            break

                if not text or not emotion:
                    continue

                # 映射情绪到风险等级
                risk = None
                for key, val in emotion_to_risk.items():
                    if key in str(emotion):
                        risk = val
                        break
                if risk is None:
                    continue

                samples.append({
                    "text": text[:500],  # 截断过长文本
                    "label": risk,
                    "source": "soulchat",
                    "emotion": emotion,
                })

                if len(samples) >= max_samples:
                    break
        if len(samples) >= max_samples:
            break

    print(f"[INFO] SoulChatCorpus: {len(samples)} emotion-mapped samples loaded")
    return samples


# ============================================================
# 去重 & 清洗
# ============================================================
def clean_text(text: str) -> str:
    """基础文本清洗"""
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:512]  # BERT max_length 安全上限
    return text


def deduplicate(samples: list[dict]) -> list[dict]:
    """
    基于文本内容去重。
    当同一文本出现多次且标签不同时，保留较高风险标签（安全优先原则）。
    """
    seen = {}  # key -> (index, label)
    unique = []
    for s in samples:
        key = s["text"].strip().lower()
        if not key:
            continue
        if key in seen:
            # 保留更高风险标签
            prev_idx, prev_label = seen[key]
            if s["label"] > prev_label:
                unique[prev_idx] = s
                seen[key] = (prev_idx, s["label"])
        else:
            seen[key] = (len(unique), s["label"])
            unique.append(s)
    removed = len(samples) - len(unique)
    if removed > 0:
        print(f"[INFO] Deduplication: removed {removed} duplicates (kept higher-risk labels)")
    return unique


# ============================================================
# 划分数据集
# ============================================================
def split_dataset(samples: list[dict], train_ratio=0.8, val_ratio=0.1, seed=42):
    """分层抽样划分 train/val/test"""
    random.seed(seed)

    # 按标签分组
    by_label = {}
    for s in samples:
        by_label.setdefault(s["label"], []).append(s)

    train, val, test = [], [], []
    for label, group in sorted(by_label.items()):
        random.shuffle(group)
        n = len(group)
        n_train = max(1, int(n * train_ratio))
        n_val = max(1, int(n * val_ratio))
        train.extend(group[:n_train])
        val.extend(group[n_train:n_train + n_val])
        test.extend(group[n_train + n_val:])

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    return train, val, test


# ============================================================
# 保存
# ============================================================
def save_jsonl(samples: list[dict], filepath: Path):
    """保存为 JSONL 格式（每行一个 JSON 对象）"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"[INFO] Saved {len(samples)} samples -> {filepath}")


def print_stats(name: str, samples: list[dict]):
    """打印数据集统计"""
    counter = Counter(s["label"] for s in samples)
    total = len(samples)
    print(f"\n{'='*50}")
    print(f"  {name}: {total} samples")
    print(f"{'='*50}")
    for label in sorted(LABEL_NAMES.keys()):
        count = counter.get(label, 0)
        pct = count / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  Label {label} ({LABEL_NAMES[label]:6s}): {count:5d} ({pct:5.1f}%) {bar}")
    sources = Counter(s.get("source", "unknown") for s in samples)
    print(f"\n  Sources: {dict(sources)}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="BERT Risk Classification Data Preparation")
    parser.add_argument("--add-soulchat", action="store_true",
                        help="Include SoulChatCorpus emotion-mapped samples")
    parser.add_argument("--soulchat-dir", type=str, default=None,
                        help="Path to SoulChatCorpus data directory")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    print("=" * 60)
    print("  BERT Risk Classification - Data Preparation")
    print("=" * 60)

    # 1. 加载所有数据源
    all_samples = []

    # PsyCrisis-Bench
    psycrisis_path = EVAL_DIR / "PsyCrisis-Bench.xlsx"
    all_samples.extend(load_psycrisis_bench(psycrisis_path))

    # test_set.csv
    test_set_path = EVAL_DIR / "test_set.csv"
    all_samples.extend(load_test_set(test_set_path))

    # 评测案例
    eval_cases_path = EVAL_DIR / "risk_eval_cases.csv"
    all_samples.extend(load_risk_eval_cases(eval_cases_path))

    # SoulChatCorpus（可选）
    if args.add_soulchat:
        soulchat_dir = Path(args.soulchat_dir) if args.soulchat_dir else PROJECT_ROOT / "data" / "soulchat"
        all_samples.extend(load_soulchat_emotion(soulchat_dir))

    # 2. 清洗 & 去重
    for s in all_samples:
        s["text"] = clean_text(s["text"])
    all_samples = [s for s in all_samples if s["text"]]  # 去除空文本
    all_samples = deduplicate(all_samples)

    print(f"\n[INFO] Total samples after cleaning: {len(all_samples)}")

    # 3. 划分
    train, val, test = split_dataset(
        all_samples,
        train_ratio=TRAIN_RATIO,
        val_ratio=VAL_RATIO,
        seed=args.seed,
    )

    # 4. 打印统计
    print_stats("Train", train)
    print_stats("Val", val)
    print_stats("Test", test)

    # 5. 保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_jsonl(train, OUTPUT_DIR / "train.jsonl")
    save_jsonl(val, OUTPUT_DIR / "val.jsonl")
    save_jsonl(test, OUTPUT_DIR / "test.jsonl")

    # 保存标签映射
    label_map = {str(k): v for k, v in LABEL_NAMES.items()}
    with open(OUTPUT_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] Label map saved -> {OUTPUT_DIR / 'label_map.json'}")

    # 6. 类别权重计算（供训练脚本使用）
    train_labels = [s["label"] for s in train]
    counter = Counter(train_labels)
    total = len(train_labels)
    weights = {label: round(total / (len(counter) * counter.get(label, 1)), 4)
               for label in sorted(LABEL_NAMES.keys())}
    with open(OUTPUT_DIR / "class_weights.json", "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2)
    print(f"[INFO] Class weights: {weights}")

    print("\n✅ Data preparation complete!")
    print(f"   Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
