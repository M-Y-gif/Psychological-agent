# 心理预警与咨询 Agent —— 多模态 Agentic RAG + 深度学习全链路

> 多模态 Agentic RAG 心理预警与咨询 Agent（课程大作业），全链路已实测跑通：
> - **第一步**：用户提问 -> 检索知识库（Chroma）-> 大模型生成回答（支持 SSE 流式）
> - **第二步**：Agent 工具调用（Function Calling）——`search_psychology_kb` / `evaluate_risk_level`
> - **第三步**：MCP 封装外部能力——高风险自动触发 `send_warning_email` / `write_risk_record_excel`
> - **第四步**：多模态感知——Whisper 语音转写 + 韵律特征、人脸表情特征，作为上下文参与综合研判
> - **第五步**：人格化陪伴——长者/孩子/家属三套人设 + 长期记忆（检索式注入）+ 主动关怀 + 心情日记/情绪打卡 + edge-tts 语音合成
> - **第六步（深度学习）**：自训练 BERT 文本风险分类模型 + MobileNetV2 CNN 面部表情识别模型，替代原有规则方案
> - **评测**：风险识别（PsyCrisis-Bench）+ 情感陪伴质量（LLM-as-judge 四维评分）+ BERT/CNN 模型评测（v1 vs v2 消融实验）

## 技术栈

| 组件 | 选型 | 说明 |
| --- | --- | --- |
| 语言/框架 | Java 17+ · Spring Boot 3.5.15 · Spring AI 1.1.8 | 本机 JDK 25 可运行 |
| 对话模型 | DeepSeek（`deepseek-chat`） | OpenAI 兼容协议，国内直连 |
| 向量模型 | 本地 ONNX `multilingual-e5-small` | 中文效果好，免费离线，首次自动下载约 470MB |
| 向量库 | Chroma（本机 8000 端口） | 启动时自动建集合 |
| 语音合成 | edge-tts（微软在线神经音色） | Python 微服务提供，7 天缓存，支持代理 |
| **BERT 风险分类** | **bert-base-chinese 微调（自训练）** | **3 类风险判定，Accuracy 92.1%，F1 85.0%** |
| **CNN 表情识别** | **MobileNetV2 迁移学习（自训练）** | **7 类表情分类，Accuracy 63.9%，F1 59.4%** |
| 深度学习框架 | PyTorch 2.x + transformers 4.x + torchvision | GPU 训练，CPU/GPU 推理 |

架构上「对话」和「向量化」分离：对话调 DeepSeek 云端 API，向量化完全在本地完成，**不需要第二个 API Key**。

## 目录结构

```
├── pom.xml                     # Maven 配置
├── run.sh                      # 本地启动脚本（自动读取 .env）
├── start_services.sh           # 🆕 一键启动所有 Python 微服务
├── .env                        # 模型配置（已 gitignore，不会提交）
├── docker-compose.yml          # Chroma 一键启动（可选）
├── docs/                       # 心理学文献（启动时自动向量化）
├── multimodal/                 # Python 多模态微服务
│   ├── app.py                  #   Whisper 转写 / 表情特征(CNN/YuNet/MediaPipe) / edge-tts
│   └── risk_classifier.py      #   🆕 BERT 风险分类推理微服务（8091 端口）
├── scripts/                    # 🆕 深度学习训练脚本
│   ├── prepare_risk_data.py    #   BERT 数据预处理（含 SoulChatCorpus 弱标注）
│   ├── prepare_fer_data.py     #   CNN 数据预处理（FER2013 + 数据增强）
│   ├── train_risk_bert_v2.py   #   BERT V2 训练（3 分类 + EarlyStopping）
│   ├── train_fer_cnn_v2.py     #   CNN V2 训练（Mixup + CosineAnnealing）
│   ├── eval_model.py           #   微调前后对比评测
│   └── prepare_dialogue_data.py #  LoRA 微调数据转换
├── data/                       # 运行时数据（已 gitignore）
│   ├── bert_risk/              #   🆕 BERT 训练数据 + 模型权重
│   │   ├── train.jsonl / val.jsonl / test.jsonl
│   │   └── best_model_v2/checkpoint.pt  (需从训练电脑拷贝)
│   ├── fer_cnn/                #   🆕 CNN 训练数据 + 模型权重
│   │   ├── train/ / val/ / test/  (ImageFolder 格式)
│   │   └── best_model_v2/checkpoint.pt  (需从训练电脑拷贝)
│   ├── users/                  #   用户记忆文件
│   ├── emails/                 #   预警邮件落盘
│   └── risk_records.xlsx       #   风险记录 Excel
├── frontend/                   # Vue3 + Vite 前端
├── evaluation/                 # 评测数据与报告
│   ├── data/                   #   PsyCrisis-Bench.xlsx, test_set.csv
│   ├── reports/                #   评测报告（风险识别 + 陪伴质量 + BERT/CNN）
│   └── figures/                #   🆕 训练曲线图 + 混淆矩阵图
├── ppt/ · report/              # 答辩 PPT、课程报告生成脚本与成品
└── src/main/java/com/psyagent/
    ├── PsyAgentApplication.java
    ├── config/                 # 配置类（PersonaProperties 人格设定等）
    ├── controller/             # REST 接口（Chat / Diary / Care / Tts / Analysis / Eval / Multimodal）
    ├── dto/                    # 请求/响应对象（含 Caller：按请求头识别使用者）
    ├── eval/                   # RiskEvalService、CompanionEvalService 评测服务
    ├── service/
    │   ├── RagService.java         # 问答闭环（Prompt 六层组装）
    │   ├── RiskEvaluator.java      # 🔄 风险判定器（规则 + LLM + BERT 三重取 max）
    │   ├── MemoryService.java      # 长期记忆（JSON 文件 + 向量检索式注入）
    │   ├── DiaryService.java       # 日记回信 + 风险检测
    │   ├── CareService.java        # 主动关怀调度
    │   ├── DocIngestionService.java # 文档向量化导入
    │   ├── MultimodalClient.java   # 多模态微服务 HTTP 客户端
    │   └── ToolCallContext.java    # Agent 工具调用上下文
    ├── tool/
    │   ├── PsychologyTools.java    # Agent 工具：search_psychology_kb / evaluate_risk_level
    │   └── WarningTools.java       # MCP 工具：send_warning_email / write_risk_record_excel
    ├── util/TextChunker.java       # 中文分块
    └── runner/StartupIngestRunner.java  # 启动时自动导入文档
```

## 快速启动

### 启动顺序（共 4 个服务）

```bash
cd /Users/yuansunming/Documents/ChatGPT/心理agent

# ① Chroma 向量数据库（必须，8000 端口）
pip install chromadb   # 已装可跳过
chroma run --host 0.0.0.0 --port 8000 --path ./chroma-data

# ② BERT 风险分类微服务（可选，8091 端口，不启动则自动降级为规则+LLM双重判定）
./start_services.sh bert
# 或手动：
# /Users/yuansunming/miniconda3/envs/yolov5/bin/python3 multimodal/risk_classifier.py

# ③ 多模态感知微服务（可选，8090 端口，视频对话需要）
EMOTION_ENGINE=cnn python3 multimodal/app.py    # CNN 7 类表情引擎
# 或：python3 multimodal/app.py                  # 默认 YuNet 3 类规则引擎

# ④ Java 后端（必须，8080 端口）
./run.sh
# 或 IDEA 中运行 PsyAgentApplication.java

# ⑤ Vue 前端（可选，开发模式 5173 端口）
cd frontend && npm install && npm run dev
```

> 💡 **一键启动 Python 服务**：`./start_services.sh`（同时启动 BERT + 多模态）
> 💡 **一键停止**：`./start_services.sh stop`
> 💡 **降级安全**：BERT 微服务未启动时，Java 端自动跳过 BERT 层，仅用规则+LLM 双重判定，系统正常运行。

### 配置 .env

项目根目录已有 `.env`（gitignore 忽略）。若没有，复制 `.env.example` 为 `.env` 并填写：

```bash
AI_API_KEY=你的 DeepSeek Key
AI_BASE_URL=https://api.deepseek.com      # 注意：不要带 /v1
AI_CHAT_MODEL=deepseek-chat
```

### 访问

- 后端测试页：**http://localhost:8080**
- Vue 前端：**http://localhost:5173**（开发模式）
- BERT 健康检查：**http://localhost:8091/api/health**
- 测试 BERT 风险分类：
  ```bash
  curl -X POST http://localhost:8091/api/risk_classify \
    -H "Content-Type: application/json" \
    -d '{"text":"一切灰蒙蒙的，不知道还能撑多久"}'
  ```

## 深度学习模型（第六步）

### BERT 文本风险分类

基于 `bert-base-chinese` 微调的 3 类心理风险分类器，替代原有的关键词硬编码规则。

| 指标 | V1（基线，517 条） | V2（改进，~4500 条） | 提升 |
| --- | --- | --- | --- |
| Accuracy | 62.69% | **92.14%** | **+29.4%** |
| F1-macro | 53.71% | **85.00%** | **+31.3%** |
| 高风险 Recall | 59.26% | 60.42% | +1.2% |

**V2 改进措施**：SoulChatCorpus 数据扩充（517→4500 条）、合并标签（4→3 类）、降低学习率（2e-5→1e-5）、增大 Dropout（0.3→0.4）、EarlyStopping（patience=2）。

**核心价值**：能识别隐晦的风险表达（如「一切灰蒙蒙的，不知道还能撑多久」），原关键词规则无法检测。

### MobileNetV2 CNN 面部表情识别

基于 ImageNet 预训练的 MobileNetV2 迁移学习，7 类细粒度表情分类，替代原有的手工几何规则（仅 3 类）。

| 指标 | V1（基线，20 轮） | V2（改进，40 轮） | 提升 |
| --- | --- | --- | --- |
| Accuracy | 59.95% | **63.92%** | **+4.0%** |
| F1-macro | 52.34% | **59.43%** | **+7.1%** |
| disgust F1 | 0.19 | **0.44** | **+132%** |

**V2 改进措施**：增加训练轮数（20→40）、CosineAnnealing 学习率调度、Mixup 数据增强、AdamW 优化器、更强数据增强（旋转 20°/缩放/擦除）。

**核心价值**：从只能判断「笑没笑」（3 类）升级为区分开心/悲伤/愤怒/恐惧/惊讶/厌恶/中性（7 类），为 Agent 提供更精确的情绪线索。

### 训练复现

```bash
# 环境准备
conda create -n psy-dl python=3.10 -y
conda activate psy-dl
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install transformers scikit-learn matplotlib pillow openpyxl modelscope

# 数据准备
python3 scripts/prepare_risk_data.py --add-soulchat    # BERT 数据（需先下载 SoulChatCorpus）
python3 scripts/prepare_fer_data.py --auto-download     # CNN 数据（自动下载 FER2013）

# 训练
python3 scripts/train_risk_bert_v2.py --epochs 15 --lr 1e-5 --dropout 0.4
python3 scripts/train_fer_cnn_v2.py --epochs 40 --mixup-alpha 0.2
```

### 风险判定三重保障

```
用户消息 → RiskEvaluator.evaluate()
  ├── 规则层：24 个高危 + 11 个中危关键词匹配（零延迟）
  ├── LLM 层：DeepSeek 语义分析（1-3 秒）
  └── BERT 层：自训练模型 HTTP 调用（15-20ms）  ← 🆕
  → 取三者最大值 → 最终风险等级(0-3)
```

任何一层检测到高风险都会触发预警。BERT 微服务不可达时自动降级，不影响其他两层。

## 配置项速查

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AI_API_KEY` | 无 | DeepSeek API Key（必填） |
| `AI_BASE_URL` | `https://api.deepseek.com` | 对话服务地址（**不带 /v1**） |
| `AI_CHAT_MODEL` | `deepseek-chat` | 对话模型 |
| `CHROMA_HOST` | `http://localhost` | Chroma 主机（**带 http:// 前缀**） |
| `CHROMA_PORT` | `8000` | Chroma 端口 |
| `CHROMA_COLLECTION` | `psychology_kb` | 集合名 |
| `DOCS_PATH` | `docs` | 文献目录 |
| `INGEST_ON_STARTUP` | `true` | 启动时自动导入 |
| `RAG_TOP_K` | `3` | 检索返回片段数 |
| `BERT_CLASSIFIER_ENABLED` | `true` | 是否启用 BERT 风险分类层 |
| `BERT_CLASSIFIER_BASE_URL` | `http://localhost:8091` | BERT 微服务地址 |
| `EMOTION_ENGINE` | `opencv` | 表情引擎：`opencv`(3 类) / `cnn`(7 类) / `mediapipe` |
| `MULTIMODAL_BASE_URL` | `http://localhost:8090` | 多模态微服务地址 |

## 多模态感知（第四步）

**架构**：Python 多模态感知微服务（`multimodal/`，端口 8090）+ Java 后端 HTTP 调用。

| 接口 | 能力 |
| --- | --- |
| `POST /api/stt` | Whisper 语音转写（中文）+ 韵律特征（语速、停顿次数/时长） |
| `POST /api/emotion` | 人脸检测 + 表情分类（`opencv`: 3 类规则 / `cnn`: 7 类 CNN / `mediapipe`: blendshapes） |
| `POST /api/tts` | edge-tts 语音合成（微软在线神经音色），返回 mp3，7 天缓存 |

**接入方式**：
1. `POST /api/multimodal/analyze`（multipart：audio / image）一次返回转写文本 + 情绪特征；
2. 前端把特征作为 `emotionContext` 随 `/api/chat` 提交；
3. Agent 的 `evaluate_risk_level` 把情绪特征作为上下文传入，大模型综合研判。

**启动**：`EMOTION_ENGINE=cnn python3 multimodal/app.py`（CNN 7 类表情），首次启动自动下载 Whisper 模型。

## MCP 预警机制（第三步）

- 应用内置 **MCP 服务端**（`spring.ai.mcp.server.type=SYNC`，SSE 端点 `/sse`），通过标准 MCP 协议对外暴露 2 个工具：
  - `send_warning_email`：发预警邮件（配置 SMTP 后真实发送；默认演示模式落盘 `data/emails/`）
  - `write_risk_record_excel`：风险留痕（追加写入 `data/risk_records.xlsx`，含时间/等级/依据/消息）
- Agent 在 `evaluate_risk_level` 判定 2-3 级高风险时，自动调用这两个工具完成「预警 + 留痕」闭环。

## 人格化陪伴模式（第五步）

对话按使用者切换人设（请求头 `X-User-Role`）：**elder**（长者陪伴「晚晴」）、**child**（儿童陪伴「小暖」）、**family**（照护家属助手「晚晴」）。

| 能力 | 说明 |
| --- | --- |
| 长期记忆 | `MemoryService`：每个使用者一个 JSON 文件，从对话中异步沉淀事实，跨会话"接得上上次的话" |
| 检索式注入 | 用本地 ONNX 嵌入做相似度 Top-K 选择，让 Agent 接得上更久远、更相关的事 |
| 心情日记 | `POST /api/diary`：保存日记 + 情绪打卡，Agent 写回信；高风险日记自动触发预警 |
| 主动关怀 | `CareService`：问候、情绪低落关怀、断连回访、睡前故事 |
| 语音合成 | `POST /api/tts`：edge-tts，音色/语速按角色默认 |
| 流式回答 | `POST /api/chat/stream`（SSE）：token / meta / done 事件 |

## Agent 工具说明

| 工具 | 功能 | 触发条件 |
| --- | --- | --- |
| `search_psychology_kb(query)` | 向量检索知识库 | Agent 需要专业心理学知识时 |
| `evaluate_risk_level(userMessage, emotionContext)` | 规则 + LLM + BERT 三重风险判定 | 检测到负面情绪/自伤话语时 |
| `send_warning_email(...)` | 发送预警邮件（MCP） | 风险等级 ≥ 2 时自动触发 |
| `write_risk_record_excel(...)` | 写入 Excel 风险记录（MCP） | 风险等级 ≥ 2 时自动触发 |

## 评测结果

### 风险识别（PsyCrisis-Bench，130 条测试集）

| 方法 | 准确率 | 精确率 | 召回率(高风险) | F1 | 误报 | 漏报 |
| --- | --- | --- | --- | --- | --- | --- |
| 纯规则 | 66.2% | 100% | 51.1% | 67.6% | 0 | 44 |
| 纯 LLM | 86.9% | 100% | 81.1% | 89.6% | 0 | 17 |
| **规则+LLM 混合** | **90.0%** | **100%** | **85.6%** | **92.2%** | **0** | **13** |
| **BERT V2（单独）** | **92.1%** | — | 60.4% | **85.0%** | — | — |

### 情感陪伴质量（LLM-as-judge 四维评分）

| 维度 | 均分 |
| --- | --- |
| 共情 empathy | 4.15 |
| 记忆使用 memoryUse | 3.45 |
| 安全 safety | 4.00 |
| 人设口吻 tone | 3.75 |
| **综合通过率** | **75.0%** |

### 深度学习模型评测

详见 `evaluation/reports/bert_eval_summary_v2.md` 和 `evaluation/reports/cnn_eval_summary_v2.md`。

## 常见问题

- **启动报 `connection refused` 连不上 Chroma**：先启动 Chroma（`chroma run --host 0.0.0.0 --port 8000 --path ./chroma-data`）
- **8080 端口被占用**：改 `application.yml` 的 `server.port`，或 `lsof -i :8080 | grep LISTEN | awk '{print $2}' | xargs kill`
- **8091 端口被占用**（BERT 微服务）：`./start_services.sh stop` 后重启
- **问答报 401/404**：确认 `.env` 里的 `AI_API_KEY` / `AI_BASE_URL` 正确（地址不要带 `/v1`）
- **BERT 微服务启动慢**：首次加载 bert-base-chinese 约 20-30 秒（Mac CPU），之后推理约 100-200ms/条
- **CNN 表情引擎不生效**：确认启动时设置了 `EMOTION_ENGINE=cnn`，且 `data/fer_cnn/best_model_v2/checkpoint.pt` 存在
- **IDEA 中文乱码**：`Settings -> Editor -> File Encodings` 全部设为 UTF-8

## Vue3 前端

前端在 `frontend/`（Vue 3 + Vite），提供以下功能页：

| 页面 | 功能 |
| --- | --- |
| 🚪 进入页 | 选择陪伴角色（长者/孩子/家属），切换人格与语音音色 |
| 💬 文字对话 | SSE 流式打字机效果，显示命中片段与风险预警条，支持语音播报 |
| 🎥 视频对话 | 多轮语音对话 + 实时表情分析（CNN 7 类），结束后生成心理分析报告 |
| 📖 心情日记 | 情绪打卡 + AI 回信 + 高风险自动预警 |
| 👁 它眼里的你 | 情绪轨迹曲线 + 记住的事实 + 关怀时间线 |
| 🌬️ 呼吸练习 | 4-4-6 腹式呼吸引导 |
| 📋 风险记录 | 历史预警留痕查看 |

**启动**：`cd frontend && npm install && npm run dev`（端口 5173，`/api` 自动代理到 8080）

## 实施进度

1. ✅ 第一步：基础 RAG 问答链路（SSE 流式）
2. ✅ 第二步：Agent 工具调用（Function Calling）
3. ✅ 第三步：MCP 封装外部服务（邮件预警、Excel 留痕）
4. ✅ 第四步：多模态感知（Whisper + 表情特征）
5. ✅ 第五步：人格化陪伴（记忆/关怀/TTS/日记）+ Vue3 前端
6. ✅ 第六步：深度学习模型训练与集成（BERT 风险分类 + CNN 表情识别）
