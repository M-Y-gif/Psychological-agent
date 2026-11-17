# 心理预警与咨询 Agent —— 多模态 Agentic RAG 全链路

> 多模态 Agentic RAG 心理预警与咨询 Agent（毕业设计），全链路已实测跑通：
> - **第一步**：用户提问 -> 检索知识库（Chroma）-> 大模型生成回答（支持 SSE 流式）
> - **第二步**：Agent 工具调用（Function Calling）——`search_psychology_kb` / `evaluate_risk_level`
> - **第三步**：MCP 封装外部能力——高风险自动触发 `send_warning_email` / `write_risk_record_excel`
> - **第四步**：多模态感知——Whisper 语音转写 + 韵律特征、人脸表情特征，作为上下文参与综合研判
> - **第五步**：人格化陪伴——长者/孩子/家属三套人设 + 长期记忆（检索式注入）+ 主动关怀 + 心情日记/情绪打卡 + edge-tts 语音合成；LoRA 微调接入
> - **评测**：风险识别（PsyCrisis-Bench，召回率 85.6%，零误报）+ 情感陪伴质量（LLM-as-judge 四维评分）

## 技术栈

| 组件 | 选型 | 说明 |
| --- | --- | --- |
| 语言/框架 | Java 17+ · Spring Boot 3.5.15 · Spring AI 1.1.8 | 本机 JDK 25 可运行 |
| 对话模型 | DeepSeek（`deepseek-chat`） | OpenAI 兼容协议，国内直连 |
| 向量模型 | 本地 ONNX `multilingual-e5-small` | 中文效果好，免费离线，首次自动下载约 470MB |
| 向量库 | Chroma（本机 8000 端口） | 启动时自动建集合 |
| 语音合成 | edge-tts（微软在线神经音色） | Python 微服务提供，7 天缓存，支持代理 |

架构上「对话」和「向量化」分离：对话调 DeepSeek 云端 API，向量化完全在本地完成，**不需要第二个 API Key**。

## 目录结构

```
├── pom.xml                     # Maven 配置
├── run.sh                      # 本地启动脚本（自动读取 .env）
├── .env                        # 模型配置（已 gitignore，不会提交）
├── docker-compose.yml          # Chroma 一键启动（可选）
├── docs/                       # 心理学文献（启动时自动向量化）
├── multimodal/                 # Python 多模态微服务：Whisper 转写 / 表情特征 / edge-tts
├── frontend/                   # Vue3 + Vite 前端（对话/日记/它眼里的你/风险记录）
├── evaluation/                 # 评测数据与报告（风险识别 + 陪伴质量）
├── ppt/ · report/              # 答辩 PPT、工程实践报告生成脚本与成品
└── src/main/java/com/psyagent/
    ├── PsyAgentApplication.java
    ├── config/                 # 配置类（PersonaProperties 人格设定等）
    ├── controller/             # REST 接口（Chat / Diary / Care / Tts / Analysis / Eval / Multimodal）
    ├── dto/                    # 请求/响应对象（含 Caller：按请求头识别使用者）
    ├── eval/                   # RiskEvalService、CompanionEvalService 评测服务
    ├── service/                # RagService（问答闭环）、MemoryService（长期记忆）、
    │                           # DiaryService（日记回信）、CareService（主动关怀）、
    │                           # DocIngestionService、ToolCallContext
    ├── tool/PsychologyTools.java # Agent 工具：search_psychology_kb / evaluate_risk_level
    ├── util/                   # TextChunker（中文分块）
    └── runner/                 # 启动时自动导入文档
```

## 在 IntelliJ IDEA 中启动

### 1. 先启动依赖服务（终端执行）

```bash
# Chroma 数据库（必须，8000 端口）
pip install chromadb   # 已装可跳过
chroma run --host 0.0.0.0 --port 8000 --path ./chroma-data

# 多模态感知引擎（可选，视频对话需要，8090 端口）
pip install -r multimodal/requirements.txt   # 已装可跳过
python3 multimodal/app.py

# Vue 前端（可选，开发模式 5173 端口）
cd frontend && npm install && npm run dev
```

### 2. IDEA 打开项目

1. `File -> Open` 选择项目根目录（`/Users/yuansunming/Documents/ChatGPT/心理agent`），等待 Maven 自动导入依赖（首次较慢）
2. `File -> Project Structure -> Project SDK` 选择 JDK 17+（本机 JDK 25 可用，项目编译目标为 17）
3. 确认 `Settings -> Build Tools -> Maven` 使用系统 Maven 或 IDEA 内置 Maven

### 3. 配置 .env（IDEA 启动会自动读取）

项目根目录已有 `.env`（gitignore 忽略，含你的 DeepSeek Key）。
若没有，复制 `.env.example` 为 `.env` 并填写。IDEA 中直接运行即可，无需手动设置环境变量。

### 4. 运行

- 找到 `src/main/java/com/psyagent/PsyAgentApplication.java`，右键 `Run`
- 日志出现 `Started PsyAgentApplication` 与 `文档导入完成` 即成功
- 访问：后端测试页 `http://localhost:8080`，Vue 前端 `http://localhost:5173`

### 常见问题

- **8080 端口被占用**：改 `application.yml` 的 `server.port`，或停掉旧进程
- **连不上 Chroma**：确认 Chroma 用 `--host 0.0.0.0` 启动
- **问答报 401/404**：确认 `.env` 里的 `AI_API_KEY` / `AI_BASE_URL` 正确（地址不要带 `/v1`）
- **IDEA 中文乱码**：`Settings -> Editor -> File Encodings` 全部设为 UTF-8

---

## 快速开始（命令行方式）


### 1. 启动 Chroma（二选一）

**方式 A：Docker（需安装 Docker Desktop）**

```bash
docker compose up -d
```

**方式 B：Python（本机已验证可用）**

```bash
pip install chromadb
# 注意：必须 --host 0.0.0.0，否则 Chroma 可能只监听 IPv6(::1)，Java 应用连不上
chroma run --host 0.0.0.0 --port 8000 --path ./chroma-data
```

### 2. 配置模型（编辑 .env）

`.env` 已在项目里（gitignore 忽略），按需修改：

```bash
AI_API_KEY=你的 DeepSeek Key
AI_BASE_URL=https://api.deepseek.com      # 注意：不要带 /v1，Spring AI 会自动拼
AI_CHAT_MODEL=deepseek-chat
```

> 向量模型无需配置：本地 ONNX 模型首次使用自动下载，缓存在 `.embedding-cache/`。

### 3. 启动应用

```bash
./run.sh
```

首次启动会下载向量模型（约 470MB，之后走缓存）。看到 `文档导入完成：2 个文件 -> 6 个片段` 即就绪。

### 4. 使用

- 浏览器打开 **http://localhost:8080** 可视化测试页面
- 或命令行：

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"什么是认知歪曲？常见的认知歪曲有哪些？"}'

curl "http://localhost:8080/api/rag/retrieve?question=腹式呼吸怎么练习"
```

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

## 常见问题

- **启动报 `Collection ... does not exist`**：确认 `spring.ai.vectorstore.chroma.initialize-schema: true` 已配置（骨架默认开启）。
- **启动报 `connection refused` 连不上 Chroma**：Chroma 要用 `--host 0.0.0.0` 启动。
- **对话报 HTTP 404**：`AI_BASE_URL` 不要带 `/v1`（Spring AI 1.1.8 会自动拼 `/v1/chat/completions`，带了会变成 `/v1/v1/...`）。
- **向量模型下载慢/失败**：模型缓存于 `.embedding-cache/`，删掉会重新下载；可配置 `EMBEDDING_MODEL_URI` / `EMBEDDING_TOKENIZER_URI` 换镜像源。
- **改了文档不生效**：Chroma 按集合名存储，重复导入会追加。调试时换集合名或清空 Chroma 数据目录。

## 多模态感知（第四步）

**架构**：Python 多模态感知微服务（`multimodal/`，端口 8090）+ Java 后端 HTTP 调用。

| 接口 | 能力 |
| --- | --- |
| `POST /api/stt` | Whisper 语音转写（中文）+ 韵律特征（语速、停顿次数/时长） |
| `POST /api/emotion` | 人脸关键点 -> 表情特征（微笑/皱眉/眼睛/头部姿态，OpenCV YuNet；可选 MediaPipe blendshapes） |
| `POST /api/tts` | edge-tts 语音合成（微软在线神经音色），返回 mp3，7 天缓存 |

**接入方式**：
1. `POST /api/multimodal/analyze`（multipart：audio / image）一次返回转写文本 + 情绪特征；
2. 前端把特征作为 `emotionContext` 随 `/api/chat` 提交；
3. Agent 的 `evaluate_risk_level` 把情绪特征作为上下文传入，大模型综合研判（实测风险原因中会引用"表情中性、头部倾斜大可能提示情绪压抑"）。

**启动**：`multimodal/start.sh`（或 `python3 multimodal/app.py`），首次启动自动下载 Whisper 模型。
**说明**：
- `EMOTION_ENGINE=mediapipe` 可切换 MediaPipe 表情引擎（需 GPU/Metal 环境）；默认 OpenCV YuNet 纯 CPU 稳定运行。
- edge-tts 需要联网；微软语音服务器国内网络可能无法直连，如本机有代理（如 Clash）可设 `TTS_PROXY=http://127.0.0.1:7897`。

## MCP 预警机制（第三步）

- 应用内置 **MCP 服务端**（`spring.ai.mcp.server.type=SYNC`，SSE 端点 `/sse`），通过标准 MCP 协议对外暴露 2 个工具：
  - `send_warning_email`：发预警邮件（配置 SMTP 后真实发送；默认演示模式落盘 `data/emails/`）
  - `write_risk_record_excel`：风险留痕（追加写入 `data/risk_records.xlsx`，含时间/等级/依据/消息）
- Agent 在 `evaluate_risk_level` 判定 2-3 级高风险时，自动调用这两个工具完成「预警 + 留痕」闭环。
- 已通过 MCP 协议验证：SSE 握手正常、`Registered tools: 2`、`tools/list` 可列出工具。

## 视频对话与心理分析（后端接口）

- `POST /api/chat`：支持 `history` 字段（多轮对话记忆），`emotionContext` 携带多模态情绪特征
- `POST /api/chat/stream`：SSE 流式对话（token / meta / done 事件），边生成边显示
- `POST /api/analysis/session`：会话结束后生成心理分析报告
  - 输入完整对话（含每轮情绪标签）
  - 输出：情绪变化轨迹、主要议题、整体情绪（negative/positive/neutral）、风险等级、**针对性反馈**、建议
  - 负面情绪 -> 鼓励与安慰；正面情绪 -> 同乐与鼓励
  - 整体风险 >= 2 时自动触发邮件预警 + Excel 留痕

## 人格化陪伴模式（第五步 · 核心体验）

对话按使用者切换人设（请求头 `X-User-Role`）：**elder**（长者陪伴「晚晴」）、**child**（儿童陪伴「小暖」）、**family**（照护家属助手「晚晴」）。人格设定与默认音色在 `application.yml` 的 `psy.persona.*` 配置。

| 能力 | 说明 |
| --- | --- |
| 长期记忆 | `MemoryService`：每个使用者一个 JSON 文件（`data/users/<id>.json`），从对话中异步沉淀事实（家人/健康/习惯），跨会话"接得上上次的话"；感知情绪趋势，持续低落时自动调整语气 |
| 检索式注入 | 注入记忆时不再固定取最近 N 条：用本地 ONNX 嵌入把「当前问题」与「事实/历史发言/日记」做相似度 Top-K 选择（带最近记忆兜底与旧逻辑回退），让 Agent 接得上更久远、更相关的事 |
| 心情日记 | `POST /api/diary`：保存日记 + 1-5 情绪打卡（映射进情绪曲线），Agent 以人格化口吻写回信；**高风险日记自动触发预警邮件 + Excel 留痕**（与对话同一套工具链路） |
| 主动关怀 | `CareService`：问候、情绪低落关怀、断连回访、睡前故事等；前端 `CareToast` 弹窗展示，确认后写入记忆避免重复打扰 |
| 语音合成 | `POST /api/tts`：转发 Python edge-tts 服务返回 mp3；音色/语速按角色默认（elder 晓晓 -20% / child 晓伊 +10% / family 云希），失败时前端降级浏览器 speechSynthesis |
| 流式回答 | `POST /api/chat/stream`（SSE）：token / meta（来源+风险等级）/ done 事件 |

记忆与关怀接口：`GET /api/care/pending`（轮询取待展示关怀）、`POST /api/care/ack`（确认已展示）、`POST /api/care/trigger`（演示触发）、`GET /api/memory`（记忆档案：事实/情绪轨迹/关怀时间线/日记，供「它眼里的你」页面展示）。

> 使用者由请求头 `X-User-Id` / `X-User-Name` / `X-User-Role` 识别（演示版不做鉴权）。

## LoRA 微调与部署接入（第五步 · 拔高项）

完整指南见 [docs/第五步-LoRA微调与部署接入指南.md](docs/第五步-LoRA微调与部署接入指南.md)，包含：
- 数据准备（SoulChatCorpus / CPsyCounD / 漏报案例）+ 转换脚本 `scripts/prepare_dialogue_data.py`
- LLaMA-Factory 训练命令（AutoDL 云 GPU，约 2-4 小时）
- 微调前后对比评测脚本 `scripts/eval_model.py`（任意 OpenAI 兼容模型）
- vLLM 部署 + `.env` 两行切换接入本项目

微调前基线（`python3 scripts/eval_model.py` 实测）：

| 方法 | 准确率 | 精确率 | 召回率(高风险) | F1 | 误报 | 漏报 |
| --- | --- | --- | --- | --- | --- | --- |
| 纯规则 | 66.2% | 100% | 51.1% | 67.6% | 0 | 44 |
| 纯LLM | 89.2% | 100% | 84.4% | 91.6% | 0 | 14 |
| **规则+LLM混合** | **91.5%** | **100%** | **87.8%** | **93.5%** | **0** | **11** |

> 微调后用同一脚本指向微调模型即可对比。

## 风险识别效果评测（论文实验章节）

**数据**：PsyCrisis-Bench（608 条真实中文高风险语句，CC BY-NC 4.0 学术许可）+ 自建 40 条常规低风险语句，共 **130 条测试集**（高风险 90 / 常规 40）。

**口径**：高风险 = 等级 >= 2。运行方式：`POST /api/eval/risk`（约 3-5 分钟），报告输出到 `evaluation/reports/`。

| 方法 | 准确率 | 精确率 | 召回率(高风险) | F1 | 误报 | 漏报 |
| --- | --- | --- | --- | --- | --- | --- |
| 纯规则 | 66.2% | 100% | 51.1% | 67.6% | 0 | 44 |
| 纯LLM | 86.9% | 100% | 81.1% | 89.6% | 0 | 17 |
| **规则+LLM混合** | **90.0%** | **100%** | **85.6%** | **92.2%** | **0** | **13** |

**结论**：
- 混合方案显著优于两个基线，验证了「规则 + 语义」双通道设计的价值；
- **零误报**：不会把正常用户误判为高风险；
- 13 条漏报均为**隐晦的存在性困扰**（"活着是为了什么""找不到活着的意义"），无明确关键词，属于边界案例；
- 等级精确率 58.5%，但误差 ≤1 级达 97.7%（对预警系统，等级粗粒度足够）。

## 情感陪伴质量评测（陪伴模式）

**数据**：自建 20 条测试集（elder 8 / child 8 / family 4，覆盖共情、记忆使用、安全、人设口吻）。运行方式：`POST /api/eval/companion`（需 Chroma 运行）。

**口径**：LLM-as-judge 四维评分（1-5 分），通过线 = 平均分 ≥ 3.5；评审走完整对话链路（人格注入 + 记忆注入 + 工具调用），评审模型为独立无工具模型。报告输出到 `evaluation/reports/`。

| 维度 | 均分 |
| --- | --- |
| 共情 empathy | 4.15 |
| 记忆使用 memoryUse | 3.45 |
| 安全 safety | 4.00 |
| 人设口吻 tone | 3.75 |
| **综合通过率** | **75.0%** |

> 按人格：长者 4.09 / 家属 3.81 / 孩子 3.59。记忆使用是当前短板（略低于 3.5 通过线），明细见 `evaluation/reports/companion_eval_cases.csv`。

## Agent 工具说明

- **`search_psychology_kb(query)`**：向量检索知识库，返回命中的知识片段。Agent 需要专业心理学知识时自主调用。
- **`evaluate_risk_level(userMessage)`**：规则 + LLM 混合风险判定，返回 0-3 级（3=极高风险，有自伤/自杀倾向）。
  - 规则层：自杀/自伤等关键词命中直接升 2-3 级，保证可解释、不漏报；
  - 语义层：独立 ChatClient 让大模型输出结构化判定（不递归调用工具）；
  - 最终等级取两者较大值，判定依据会随接口返回，前端展示风险提示。

接口返回新增 `riskLevel` / `riskReason` 字段，测试页面对高风险（>=2 级）显示醒目预警条。

## 实施进度

1. ✅ 第一步：基础 RAG 问答链路（已跑通，支持 SSE 流式）
2. ✅ 第二步：Agent 工具调用（Function Calling）—— `search_psychology_kb`、`evaluate_risk_level`（已跑通）
3. ✅ 第三步：MCP 封装外部服务（邮件预警、Excel 留痕）—— 高风险时自动触发
4. ✅ 第四步：多模态感知（Whisper + 表情特征，情绪特征入上下文）
5. ✅ 第五步：LoRA 微调 + Vue3 前端（音视频对话、呼吸小游戏）+ 人格化陪伴（记忆/关怀/TTS）

## Vue3 前端（第五步 · 界面部分）

前端在 `frontend/`（Vue 3 + Vite），提供五个功能页（首次进入先选陪伴角色）：

| 页面 | 功能 |
| --- | --- |
| 🚪 进入页 | 选择陪伴角色（长者/孩子/家属），切换人格与语音音色 |
| 💬 文字对话 | 提问 -> Agent 检索/评估/回答（SSE 流式打字机效果），显示命中片段与风险预警条，支持语音播报 |
| 🎥 视频对话 | 多轮语音对话：每句语音转写+表情分析，Agent 记住上下文回应；结束后生成**心理分析报告**（负面->安慰鼓励，正面->同乐鼓励，高风险自动预警留痕） |
| 📖 心情日记 | 1-5 表情打卡 + 写日记；保存后 AI 写温柔回信（可朗读）；高风险日记显示预警条并进风险记录；历史日记列表 |
| 👁 它眼里的你 | 情绪轨迹曲线（聊天/日记/会话分析分来源）+ 记住的事实 + 关怀时间线 + 档案 + 最近日记 |
| 🌬️ 放松小游戏 | 4-4-6 呼吸练习引导 |
| 📋 风险记录 | 查看历史预警留痕记录（时间/等级/依据） |

另有全局组件：`CareToast`（主动关怀弹窗，配合 `/api/care/pending` 轮询）、`RiskBanner`（高风险预警条）。

**启动**（开发模式，端口 5173，`/api` 自动代理到 8080）：

```bash
cd frontend && npm install && npm run dev
# 打开 http://localhost:5173
```

**部署**（生产演示，打包后由 Spring Boot 统一服务）：

```bash
cd frontend && npm run build
cp -r dist/* ../src/main/resources/static/
```

> 说明：视频对话中的表情分析由后端多模态引擎完成；浏览器端负责录音与抓帧，音频转 WAV 后上传。
