#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
心理对话语料 -> LLaMA-Factory sharegpt 训练格式。
用法：
  转换对话语料：
    python3 scripts/prepare_dialogue_data.py --input ./data/soulchat --output ./data/psy_dialogue.jsonl
  追加漏报风险案例作为风险识别训练样本：
    python3 scripts/prepare_dialogue_data.py --add-risk-cases evaluation/reports/risk_eval_cases.csv \
      --output ./data/psy_dialogue.jsonl

支持的输入格式（自动识别）：
  sharegpt  : [{"conversations":[{"from":"human|gpt","value":"..."}]}]
  alpaca    : [{"instruction":..., "input":..., "output":...}]
  soulchat  : [{"question"|"instruction":..., "answer"|"output":...}]
  jsonl     : 每行一条上述对象
"""
import argparse
import csv
import json
import os


def load_objects(path):
    """加载 json / jsonl 文件，返回对象列表"""
    objs = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in sorted(files):
                if f.endswith((".json", ".jsonl")):
                    objs.extend(load_objects(os.path.join(root, f)))
        return objs
    with open(path, "r", encoding="utf-8") as fh:
        if path.endswith(".jsonl"):
            for line in fh:
                line = line.strip()
                if line:
                    objs.append(json.loads(line))
        else:
            data = json.load(fh)
            objs.extend(data if isinstance(data, list) else [data])
    return objs


def to_sharegpt(obj):
    """把一条样本转成 sharegpt 对话列表，识别不了返回 None"""
    # 已有 conversations
    if "conversations" in obj:
        convs = []
        for c in obj["conversations"]:
            role = c.get("from", c.get("role", ""))
            value = c.get("value", c.get("content", ""))
            if role and value:
                convs.append({"from": "human" if role in ("human", "user") else "gpt", "value": value})
        return convs or None
    # alpaca / soulchat 单轮
    instr = obj.get("instruction") or obj.get("question") or obj.get("input") or ""
    output = obj.get("output") or obj.get("answer") or ""
    if instr and output:
        return [
            {"from": "human", "value": instr},
            {"from": "gpt", "value": output},
        ]
    return None


def main():
    ap = argparse.ArgumentParser(description="心理对话语料转 LLaMA-Factory 格式")
    ap.add_argument("--input", help="输入目录或文件（json/jsonl）")
    ap.add_argument("--add-risk-cases", help="漏报案例 CSV（risk_eval_cases.csv），生成风险识别训练样本")
    ap.add_argument("--output", required=True, help="输出 jsonl 路径")
    ap.add_argument("--append", action="store_true", help="追加而不是覆盖输出文件")
    args = ap.parse_args()

    out_mode = "a" if args.append else "w"
    count = 0
    with open(args.output, out_mode, encoding="utf-8") as out:
        if args.input:
            for obj in load_objects(args.input):
                convs = to_sharegpt(obj)
                if convs:
                    out.write(json.dumps({"conversations": convs}, ensure_ascii=False) + "\n")
                    count += 1
        if args.add_risk_cases:
            with open(args.add_risk_cases, encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    if int(row["gold"]) >= 2 and int(row["combined"]) < 2:  # 漏报
                        text = row["text"]
                        convs = [
                            {"from": "human", "value": f"请评估下面用户消息的自伤/自杀风险等级，只输出 JSON："
                                                       f'{{"riskLevel": 0-3, "reasons": "简短中文理由"}}。用户消息：{text}'},
                            {"from": "gpt", "value": f'{{"riskLevel": {row["gold"]}, '
                                                     f'"reasons": "用户表达存在性困扰/自伤倾向，需提高警惕"}}'},
                        ]
                        out.write(json.dumps({"conversations": convs}, ensure_ascii=False) + "\n")
                        count += 1
    print(f"已生成 {count} 条训练样本 -> {args.output}")


if __name__ == "__main__":
    main()
