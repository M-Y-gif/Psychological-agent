#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评测任意 OpenAI 兼容大模型的心理风险识别效果（微调前后对比用）。
与项目 RiskEvaluator 使用相同的关键词规则与提示词，保证口径一致。

用法：
  python3 scripts/eval_model.py --base-url https://api.deepseek.com \
      --api-key sk-xxx --model deepseek-chat
  # 也可自动读取 .env（AI_API_KEY / AI_BASE_URL / AI_CHAT_MODEL）
  python3 scripts/eval_model.py

输出：
  - 终端指标汇总（纯规则 / 纯LLM / 规则+LLM混合）
  - evaluation/reports/model_eval_cases.csv（逐条结果）
"""
import argparse
import csv
import json
import os
import sys
import time

import requests

TEST_SET = "evaluation/data/test_set.csv"
REPORT = "evaluation/reports/model_eval_cases.csv"

HIGH_RISK_KEYWORDS = [
    "自杀", "自伤", "想死", "不想活", "活不下去", "结束生命", "结束自己",
    "伤害自己", "割腕", "跳楼", "安眠药", "遗书", "告别", "活着没意思",
    "消失", "解脱", "自我了断", "不想醒来", "没意义了",
]
MODERATE_RISK_KEYWORDS = [
    "绝望", "崩溃", "撑不下去", "撑不住", "受不了", "毫无希望", "没有希望",
    "无意义", "空虚", "无助", "痛苦",
]

PROMPT = """请评估下面用户消息的自伤/自杀风险等级，只输出 JSON：{{"riskLevel": 0-3, "reasons": "简短中文理由"}}。
0=无明显风险；1=轻度情绪困扰；2=中高风险；3=极高风险（有明确自伤/自杀意图或计划）。
用户消息：{text}"""


def rule_level(text):
    high = sum(1 for kw in HIGH_RISK_KEYWORDS if kw in text)
    moderate = sum(1 for kw in MODERATE_RISK_KEYWORDS if kw in text)
    if high >= 2:
        return 3
    if high == 1:
        return 2
    if moderate >= 2:
        return 2
    if moderate == 1:
        return 1
    return 0


def parse_json_level(json_str):
    if not json_str:
        return 0
    try:
        cleaned = json_str.replace("```json", "").replace("```", "").strip()
        s, e = cleaned.find("{"), cleaned.rfind("}")
        if s >= 0 and e > s:
            cleaned = cleaned[s:e + 1]
        return max(0, min(3, json.loads(cleaned).get("riskLevel", 0)))
    except Exception:
        return 0


def llm_level(text, base_url, api_key, model):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是心理风险筛查助手，只输出 JSON，不要输出其他内容。"},
            {"role": "user", "content": PROMPT.format(text=text)},
        ],
        "temperature": 0.0,
        "max_tokens": 100,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    url = base_url.rstrip("/") + "/chat/completions"
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            return parse_json_level(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            if attempt == 2:
                print(f"  [warn] LLM 调用失败: {e}", file=sys.stderr)
                return 0
            time.sleep(2)


def metrics(cases, use_rule, use_llm):
    tp = fp = fn = tn = 0
    for c in cases:
        pred = c["rule"] if use_rule else (c["llm"] if use_llm else c["combined"])
        gpos, ppos = c["gold"] >= 2, pred >= 2
        if gpos and ppos:
            tp += 1
        elif not gpos and ppos:
            fp += 1
        elif gpos and not ppos:
            fn += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    acc = (tp + tn) / n * 100
    prec = tp / (tp + fp) * 100 if tp + fp else 0
    rec = tp / (tp + fn) * 100 if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return acc, prec, rec, f1, fp, fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url")
    ap.add_argument("--api-key")
    ap.add_argument("--model")
    ap.add_argument("--limit", type=int, default=0, help="只评测前 N 条（调试用）")
    args = ap.parse_args()

    # 从 .env 读取默认值
    env = {}
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    base_url = args.base_url or env.get("AI_BASE_URL", "https://api.deepseek.com")
    api_key = args.api_key or env.get("AI_API_KEY", "EMPTY")
    model = args.model or env.get("AI_CHAT_MODEL", "deepseek-chat")
    print(f"评测模型: {model} @ {base_url}")

    cases = []
    with open(TEST_SET, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cases.append({"id": int(row["id"]), "text": row["text"], "gold": int(row["gold_level"])})
    if args.limit:
        cases = cases[: args.limit]

    print(f"测试集: {len(cases)} 条，开始评测（每条约 1-2 秒）…")
    for i, c in enumerate(cases):
        c["rule"] = rule_level(c["text"])
        c["llm"] = llm_level(c["text"], base_url, api_key, model)
        c["combined"] = max(c["rule"], c["llm"])
        if (i + 1) % 20 == 0:
            print(f"  已评测 {i + 1}/{len(cases)}")

    rule = metrics(cases, True, False)
    llm = metrics(cases, False, True)
    combined = metrics(cases, False, False)

    exact = sum(1 for c in cases if c["combined"] == c["gold"]) / len(cases) * 100
    near = sum(1 for c in cases if abs(c["combined"] - c["gold"]) <= 1) / len(cases) * 100

    print("\n=== 评测结果（高风险 = 等级 >= 2）===")
    print(f"精确等级准确率: {exact:.1f}% | 误差<=1级: {near:.1f}%")
    print(f"{'方法':<14}{'准确率':>8}{'精确率':>8}{'召回率':>8}{'F1':>8}{'误报':>6}{'漏报':>6}")
    for name, m in (("纯规则", rule), ("纯LLM", llm), ("规则+LLM混合", combined)):
        print(f"{name:<14}{m[0]:>7.1f}%{m[1]:>7.1f}%{m[2]:>7.1f}%{m[3]:>7.1f}%{m[4]:>6}{m[5]:>6}")

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "gold", "rule", "llm", "combined", "text"])
        for c in cases:
            w.writerow([c["id"], c["gold"], c["rule"], c["llm"], c["combined"], c["text"]])
    print(f"\n逐条结果已写入 {REPORT}")


if __name__ == "__main__":
    main()
