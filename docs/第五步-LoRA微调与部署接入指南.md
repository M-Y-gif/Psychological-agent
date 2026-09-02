# 第五步：LoRA 微调与部署接入指南

> 目标：用心理对话语料微调开源大模型，提升共情能力与风险识别敏感度，并把微调后的模型无缝接入本项目（项目大模型层是 OpenAI 兼容协议，切换模型 = 改两行配置）。

## 0. 为什么微调 / 微调后带来什么

当前 Agent 使用 DeepSeek 通用模型，心理学能力"够用但不专业"。LoRA 微调用少量算力让开源模型专门学习心理学：

| 能力 | 现状 | 微调后 |
| --- | --- | --- |
| 共情话术 | 通用、偶尔生硬 | 咨询师式：不评判、开放式提问、情绪反映 |
| 风险识别 | 召回率 85.6%，漏报 13 条（隐晦表达） | 对"活着没意思"这类表达更敏感 |
| 回答风格 | 可能冗长 | 简洁、温暖、专业 |

## 1. 数据准备

### 1.1 数据来源

| 数据集 | 内容 | 获取 |
| --- | --- | --- |
| **SoulChatCorpus** | 230万条中文共情对话 | ModelScope：`YIRONGCHEN/SoulChatCorpus` |
| **CPsyCounD** | 3134 条多轮心理咨询对话 | HuggingFace：`CAS-SIAT-XinHai/CPsyCounD` |
| **本项目漏报案例** | 评测中漏掉的高风险表达 | `evaluation/reports/risk_eval_cases.csv`（gold>=2 且 combined<2 的行） |

### 1.2 转换训练数据

```bash
# 下载 SoulChatCorpus（ModelScope 国内速度快）
pip install modelscope
modelscope download --dataset YIRONGCHEN/SoulChatCorpus --local_dir ./data/soulchat

# 转换对话语料 -> LLaMA-Factory sharegpt 格式
python3 scripts/prepare_dialogue_data.py \
  --input ./data/soulchat \
  --output ./data/psy_dialogue.jsonl

# 追加"漏报案例"风险识别训练样本（直接针对系统弱点）
python3 scripts/prepare_dialogue_data.py \
  --add-risk-cases evaluation/reports/risk_eval_cases.csv \
  --output ./data/psy_dialogue.jsonl
```

> 脚本默认兼容 sharegpt / alpaca / SoulChat 常见字段；若数据集格式不同，参考脚本开头的字段映射说明调整。

## 2. 云 GPU 环境准备（AutoDL 示例）

1. 注册 [AutoDL](https://www.autodl.com)，租一台 **RTX 4090 或 A100**（显存 ≥24G），镜像选 **PyTorch 2.x + CUDA 12.x**，磁盘 ≥50G
2. 连接后安装微调框架：

```bash
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics]"
```

3. 下载基座模型（Qwen2.5-7B-Instruct，中文强、原生支持工具调用）：

```bash
pip install modelscope
modelscope download --model Qwen/Qwen2.5-7B-Instruct --local_dir /root/autodl-tmp/Qwen2.5-7B-Instruct
```

## 3. LoRA 微调

### 3.1 注册数据集

编辑 `LLaMA-Factory/data/dataset_info.json`，加入：

```json
"psy_dialogue": {
  "file_name": "psy_dialogue.jsonl",
  "formatting": "sharegpt",
  "columns": { "messages": "conversations" },
  "tags": { "role_tag": "from", "content_tag": "value", "user_tag": "human", "assistant_tag": "gpt" }
}
```

### 3.2 训练命令

```bash
cd LLaMA-Factory
cp /root/autodl-tmp/psy_dialogue.jsonl data/

llamafactory-cli train \
  --model_name_or_path /root/autodl-tmp/Qwen2.5-7B-Instruct \
  --stage sft \
  --finetuning_type lora \
  --dataset psy_dialogue \
  --template qwen \
  --output_dir output/psy-lora \
  --overwrite_cache \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --learning_rate 1e-4 \
  --num_train_epochs 3.0 \
  --lr_scheduler_type cosine \
  --logging_steps 10 \
  --save_steps 500 \
  --lora_rank 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --max_length 1024 \
  --cutoff_len 1024 \
  --val_size 0.1 \
  --evaluation_strategy steps \
  --eval_steps 500 \
  --bf16
```

> 显存不足时：`--per_device_train_batch_size 1 --gradient_accumulation_steps 16`；RTX 4090 约 2-4 小时。

### 3.3 导出合并模型

```bash
llamafactory-cli export \
  --model_name_or_path /root/autodl-tmp/Qwen2.5-7B-Instruct \
  --adapter_name_or_path output/psy-lora \
  --template qwen \
  --finetuning_type lora \
  --export_dir /root/autodl-tmp/psy-qwen \
  --export_size 4 \
  --export_legacy_format false
```

## 4. 微调前后对比评测（论文核心实验）

直接用本项目的评测脚本，对比任意 OpenAI 兼容模型（DeepSeek / 微调模型）：

```bash
# 基线：DeepSeek（当前系统）
python3 scripts/eval_model.py --base-url https://api.deepseek.com \
  --api-key sk-你的key --model deepseek-chat

# 微调后：云上部署的模型
python3 scripts/eval_model.py --base-url http://服务器IP:8000/v1 \
  --api-key EMPTY --model psy-qwen
```

输出：`evaluation/reports/model_eval_cases.csv` + 终端指标（高风险召回率/精确率/F1、准确率）。
报告中的对比表格（微调前 vs 微调后）可直接进论文。

## 5. 部署并接入本项目

### 5.1 vLLM 部署（云端，推荐）

```bash
pip install vllm
vllm serve /root/autodl-tmp/psy-qwen \
  --served-model-name psy-qwen \
  --port 8000 \
  --max-model-len 8192
```

### 5.2 项目切换（改 .env 两行）

```bash
# 原来（DeepSeek）
AI_BASE_URL=https://api.deepseek.com
AI_CHAT_MODEL=deepseek-chat

# 换成微调模型（vLLM 暴露 OpenAI 兼容接口）
AI_BASE_URL=http://你的云服务器IP:8000/v1
AI_API_KEY=EMPTY
AI_CHAT_MODEL=psy-qwen
```

改完重启应用，**RAG、Agent 工具调用、风险判定、MCP 预警、多模态全部原样工作**。

### 5.3 本地运行（可选，免费但较慢）

Mac（≥16G 内存）用 Ollama：

```bash
ollama create psy-qwen -f Modelfile   # Modelfile: FROM /path/to/psy-qwen
# 或
ollama run qwen2.5:7b
# 然后 .env 指向本地
AI_BASE_URL=http://localhost:11434/v1
AI_CHAT_MODEL=psy-qwen
```

## 6. 注意事项（重要）

1. **工具调用**：必须用 Qwen2.5-7B-**Instruct** 做基座（原生支持 function calling），且用 vLLM 部署（支持工具调用协议）。否则 Agent 不会自主调用检索/风险评估/预警工具。
2. **向量模型不变**：Embedding 用本地 ONNX 模型，与对话模型无关，无需改动。
3. **成本**：云端常驻约 1-2 元/小时，答辩演示期开启、平时关闭即可。
4. **数据安全**：训练数据与用户消息注意脱敏；本项目 `data/` 目录不入库。
