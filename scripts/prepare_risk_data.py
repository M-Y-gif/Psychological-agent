#!/usr/bin/env python3
"""
BERT 心理风险分类 - 数据预处理脚本 (v2 - 修复SoulChat加载)
===================================
数据来源：
  1. PsyCrisis-Bench.xlsx  (608条, label 0/1/2)
  2. test_set.csv           (130条, gold_level 0-3, 带category)
  3. SoulChatCorpus         (258K条多轮对话, 通过关键词匹配提取风险样本)

输出：
  data/bert_risk/train.jsonl   (~80%)
  data/bert_risk/val.jsonl     (~10%)
  data/bert_risk/test.jsonl    (~10%)
  data/bert_risk/label_map.json

标签体系（3级，合并原2+3）：
  0 = 无明显风险
  1 = 轻度情绪困扰
  2 = 高风险（中高风险+极高风险合并）

用法：
  python3 scripts/prepare_risk_data.py
  python3 scripts/prepare_risk_data.py --add-soulchat   # 追加SoulChatCorpus
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

LABEL_NAMES = {
    0: "无风险",
    1: "轻度困扰",
    2: "高风险",
}

# 风险关键词（用于从SoulChatCorpus中提取有风险的用户消息）
HIGH_RISK_KEYWORDS = [
    "自杀", "自伤", "想死", "不想活", "活不下去", "结束生命", "结束自己",
    "伤害自己", "割腕", "跳楼", "安眠药", "遗书", "告别", "活着没意思",
    "消失", "解脱", "自我了断", "不想醒来", "没意义了", "去死", "寻死",
    "死了算了", "不如死了", "想不开", "轻生",
]

MODERATE_RISK_KEYWORDS = [
    "绝望", "崩溃", "撑不下去", "撑不住", "受不了", "毫无希望", "没有希望",
    "无意义", "空虚", "无助", "痛苦", "抑郁", "焦虑", "恐慌", "窒息",
    "喘不过气", "想哭", "好累", "疲惫", "孤独", "没人理解", "被抛弃",
    "讨厌自己", "恨自己", "没用", "废物", "失败",
]

MILD_KEYWORDS = [
    "烦", "难过", "不开心", "失落", "迷茫", "压力", "紧张", "担心",
    "害怕", "不安", "纠结", "困惑", "失眠", "睡不着", "食欲", "吃不下",
]


# ============================================================
# 数据加载
# ============================================================
def load_psycrisis_bench(filepath: Path) -> list[dict]:
    """加载 PsyCrisis-Bench.xlsx"""
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
        # 原始标签 0/1/2 → 映射到 0/1/2（2和3合并为2）
        label = min(label, 2)
        samples.append({"text": text, "label": label, "source": "psycrisis"})
    wb.close()
    print(f"[INFO] PsyCrisis-Bench: {len(samples)} samples loaded")
    return samples


def load_test_set(filepath: Path) -> list[dict]:
    """加载 test_set.csv"""
    samples = []
    if not filepath.exists():
        print(f"[WARN] {filepath} not found, skipping")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("text", "").strip()
            level = row.get("gold_level", "").strip()
            if not text or not level:
                continue
            label = min(int(level), 2)  # 合并2+3→2
            samples.append({
                "text": text,
                "label": label,
                "source": "test_set",
            })
    print(f"[INFO] test_set.csv: {len(samples)} samples loaded")
    return samples


def classify_text_by_keywords(text: str) -> int:
    """通过关键词匹配判断风险等级"""
    text_lower = text.lower()
    high_count = sum(1 for kw in HIGH_RISK_KEYWORDS if kw in text_lower)
    moderate_count = sum(1 for kw in MODERATE_RISK_KEYWORDS if kw in text_lower)
    mild_count = sum(1 for kw in MILD_KEYWORDS if kw in text_lower)

    if high_count >= 1:
        return 2  # 高风险
    elif moderate_count >= 2:
        return 2  # 多项中度关键词也算高风险
    elif moderate_count == 1:
        return 1  # 轻度困扰
    elif mild_count >= 2:
        return 1  # 多项轻度关键词
    else:
        return 0  # 无风险


def load_soulchat(data_dir: Path, max_samples: int = 5000) -> list[dict]:
    """
    加载 SoulChatCorpus 数据集。
    
    数据格式（ModelScope下载后）：
      data/soulchat/
      ├── xxx.jsonl 或 xxx.json
      每行一个JSON: {"id": 0, "topic": "成长", "messages": [{"role":"user","content":"..."},...]}
    
    策略：提取每条对话中所有 user 消息，用关键词匹配判断风险等级。
    只保留 label >= 1 的样本（有风险的），避免大量无风险样本稀释数据。
    """
    samples = []
    if not data_dir.exists():
        print(f"[WARN] SoulChat dir {data_dir} not found, skipping")
        return []

    # 递归搜索所有json/jsonl文件（包括子目录）
    json_files = list(data_dir.rglob("*.jsonl")) + list(data_dir.rglob("*.json"))
    # 排除非数据文件
    json_files = [f for f in json_files if f.stat().st_size > 1000]  # 至少1KB
    
    print(f"[INFO] Found {len(json_files)} JSON files in {data_dir}")

    total_user_msgs = 0
    risk_found = 0

    for fname in sorted(json_files):
        if len(samples) >= max_samples:
            break
            
        try:
            with open(fname, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except (UnicodeDecodeError, PermissionError):
            continue

        if not content:
            continue

        # 尝试两种格式：JSONL（每行一个JSON）或单个大JSON数组
        objects = []
        
        # 尝试JSONL
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                objects.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        
        # 如果JSONL解析失败，尝试整体JSON
        if not objects:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    objects = parsed
                elif isinstance(parsed, dict):
                    objects = [parsed]
            except json.JSONDecodeError:
                continue

        for obj in objects:
            if len(samples) >= max_samples:
                break
            if not isinstance(obj, dict):
                continue

            # 提取 messages 字段
            messages = obj.get("messages", obj.get("conversations", []))
            if not messages:
                continue

            # 提取所有 user 消息
            for msg in messages:
                if len(samples) >= max_samples:
                    break
                role = msg.get("role", msg.get("from", ""))
                if role not in ("user", "human"):
                    continue
                
                text = msg.get("content", msg.get("value", ""))
                if not text or len(text) < 5:  # 太短的跳过
                    continue
                
                total_user_msgs += 1
                text = text[:512]  # 截断
                
                # 用关键词判断风险等级
                label = classify_text_by_keywords(text)
                
                # 只保留有风险的样本（label >= 1），避免大量label=0稀释
                if label >= 1:
                    risk_found += 1
                    samples.append({
                        "text": text,
                        "label": label,
                        "source": "soulchat",
                    })
                    
                    # 同时加入一些无风险样本作为对比（每5个风险样本加1个无风险）
                elif risk_found > 0 and risk_found % 5 == 0 and len(samples) < max_samples:
                    samples.append({
                        "text": text,
                        "label": 0,
                        "source": "soulchat",
                    })

    print(f"[INFO] SoulChatCorpus: scanned {total_user_msgs} user messages, "
          f"found {risk_found} risk samples, total added: {len([s for s in samples if s['source']=='soulchat'])}")
    return samples


# ============================================================
# 去重 & 清洗
# ============================================================
def clean_text(text: str) -> str:
    """基础文本清洗"""
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:512]
    return text


def deduplicate(samples: list[dict]) -> list[dict]:
    """基于文本内容去重，保留更高风险标签"""
    seen = {}
    unique = []
    for s in samples:
        key = s["text"].strip().lower()
        if not key:
            continue
        if key in seen:
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
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"[INFO] Saved {len(samples)} samples -> {filepath}")


def print_stats(name: str, samples: list[dict]):
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
    parser = argparse.ArgumentParser(description="BERT Risk Classification Data Preparation V2")
    parser.add_argument("--add-soulchat", action="store_true",
                        help="Include SoulChatCorpus samples (keyword-matched)")
    parser.add_argument("--soulchat-dir", type=str, default=None,
                        help="Path to SoulChatCorpus data directory")
    parser.add_argument("--max-soulchat", type=int, default=5000,
                        help="Max SoulChat samples to include")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    print("=" * 60)
    print("  BERT Risk Classification - Data Preparation V2")
    print("  (3-class: 无风险/轻度困扰/高风险)")
    print("=" * 60)

    # 1. 加载所有数据源
    all_samples = []

    psycrisis_path = EVAL_DIR / "PsyCrisis-Bench.xlsx"
    all_samples.extend(load_psycrisis_bench(psycrisis_path))

    test_set_path = EVAL_DIR / "test_set.csv"
    all_samples.extend(load_test_set(test_set_path))

    if args.add_soulchat:
        soulchat_dir = Path(args.soulchat_dir) if args.soulchat_dir else PROJECT_ROOT / "data" / "soulchat"
        all_samples.extend(load_soulchat(soulchat_dir, max_samples=args.max_soulchat))

    # 2. 清洗 & 去重
    for s in all_samples:
        s["text"] = clean_text(s["text"])
    all_samples = [s for s in all_samples if s["text"]]
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

    label_map = {str(k): v for k, v in LABEL_NAMES.items()}
    with open(OUTPUT_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    # 6. 类别权重
    train_labels = [s["label"] for s in train]
    counter = Counter(train_labels)
    total = len(train_labels)
    num_classes = len(LABEL_NAMES)
    weights = {label: round(total / (num_classes * counter.get(label, 1)), 4)
               for label in sorted(LABEL_NAMES.keys())}
    with open(OUTPUT_DIR / "class_weights.json", "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2)
    print(f"[INFO] Class weights: {weights}")

    print("\n✅ Data preparation complete!")
    print(f"   Output directory: {OUTPUT_DIR}")
    print(f"   Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")


if __name__ == "__main__":
    main()
