# -*- coding: utf-8 -*-
"""生成答辩 PPT。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deck import *
from pptx.enum.text import PP_ALIGN

FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'report', 'figures')
prs = new_deck()
page = 0


def pg(slide):
    global page
    page += 1
    footer(slide, page)


# ============ 1 封面 ============
s = blank(prs)
rect(s, 0, 0, SW, 0.22, fill=PRIMARY)
tb, tf = textbox(s, 1.15, 1.55, SW - 2.3, 1.6)
para(tf, '多模态 Agentic RAG', size=40, bold=True, color=PRIMARY_D, first=True, space_after=4, line=1.1)
para(tf, '心理预警与咨询 Agent 的设计与实现', size=30, bold=True, color=INK, space_after=0, line=1.15)
tb, tf = textbox(s, 1.15, 3.55, SW - 2.3, 0.5)
para(tf, '工程实践项目答辩', size=19, color=INK2, first=True, space_after=0)
rect(s, 1.15, 4.28, 2.2, 0.035, fill=PRIMARY, shape=MSO_SHAPE.RECTANGLE)
tb, tf = textbox(s, 1.15, 4.62, 6.3, 1.5)
para(tf, '汇报人：袁孙明    学号：9109223018', size=16, color=INK, first=True, space_after=8)
para(tf, '指导教师：幸玮    职称：讲师', size=16, color=INK, space_after=8)
para(tf, '数学与计算机学院计算机系 · 计算机科学与技术 231 班', size=15, color=INK2, space_after=0)
tb, tf = textbox(s, SW - 4.4, 6.35, 3.2, 0.4)
para(tf, '2026.08.29 — 2026.09.11', size=13, color=INK3, first=True, align=PP_ALIGN.RIGHT, space_after=0)

# ============ 2 汇报提纲 ============
s = blank(prs)
y = title(s, '汇报提纲')
items = [
    ('01　选题背景与项目目标', '为什么做这件事：陪伴缺口与通用助手的三点局限'),
    ('02　系统设计与关键技术', '架构、核心流程，以及四个真实技术难点的解决过程'),
    ('03　效果评测与系统展示', '风险识别在 130 条样本上的表现与界面实拍'),
    ('04　AI 辅助开发与总结', '工具选型、关键提示词记录与实践体会'),
]
cy = y + 0.25
for head, desc in items:
    tb, tf = textbox(s, M + 0.15, cy, 10.4, 0.95)
    para(tf, head, size=21, bold=True, color=PRIMARY_D, first=True, space_after=3)
    para(tf, desc, size=15.5, color=INK2, space_after=0)
    cy += 1.15
pg(s)

# ============ 3 选题背景 ============
s = blank(prs)
y = title(s, '需要陪伴的人很多，能提供的专业力量有限')
tb, tf = textbox(s, M, y, 5.9, 3.4)
para(tf, '两类人群的共同处境', size=17, bold=True, color=PRIMARY_D, first=True, space_after=10)
para(tf, '独居长者白天缺少可以说话的对象，留守儿童在成长中缺少稳定的情感回应。'
         '他们的困扰往往不表现为典型症状，而是睡眠变差、反复叹气、不愿出门，缓慢累积。',
     size=15.5, color=INK2, line=1.45, space_after=14)
para(tf, '而学校心理教师与社区咨询师的服务半径，难以覆盖日常性的陪伴需求。',
     size=15.5, color=INK2, line=1.45, space_after=0)
rect(s, 7.05, y - 0.06, 5.55, 4.95, fill=BG_SOFT, line=LINE, radius=0.04)
tb, tf = textbox(s, 7.35, y + 0.22, 4.95, 4.5)
para(tf, '通用助手能陪聊，但存在三点结构性局限', size=17, bold=True, color=INK, first=True, space_after=14)
for h, d in [
    ('记不住人', '记住的是对话，不是你。不知道你上次提到腰疼，也不知道你反复谈起哪位家人。'),
    ('不会主动', '你不开口它就不出现，而最需要陪伴的时刻，往往是不想主动开口的时候。'),
    ('没有手', '察觉危险之后，它能做的通常只是给出一串电话，无法联系到任何能帮上忙的人。'),
]:
    para(tf, h, size=16, bold=True, color=DANGER, space_before=6, space_after=2)
    para(tf, d, size=14.5, color=INK2, line=1.4, space_after=6)
pg(s)

# ============ 4 项目目标与主要工作 ============
s = blank(prs)
y = title(s, '项目目标与主要工作')
rect(s, M, y, SW - 2 * M, 0.78, fill=PRIMARY_L, line=None, radius=0.06)
tb, tf = textbox(s, M + 0.3, y + 0.13, SW - 2 * M - 0.6, 0.55)
para(tf, '目标：构建一个记得住使用者、会在合适时机主动开口、识别出风险时能触达他人的心理陪伴与预警系统',
     size=16.5, bold=True, color=PRIMARY_D, first=True, space_after=0, line=1.2)
work = [
    ('检索增强生成链路', '心理学文献切分向量化，回答先检索后生成，专业内容可溯源'),
    ('Agent 工具调用', '模型自主决定是否检索知识库、是否评估风险，而非固定流程'),
    ('MCP 预警闭环', '风险判定后自动发送预警邮件并写入 Excel 留痕'),
    ('多模态感知', '语音转写、韵律特征与面部表情共同参与研判'),
    ('实时语音对话', '自动断句、流式生成、按句朗读，支持随时打断'),
    ('长期记忆与主动关怀', '沉淀关于使用者的事实，在节律点主动开口'),
]
x0, y0 = M, y + 1.05
cw, ch = 5.85, 1.28
for i, (h, d) in enumerate(work):
    cx = x0 + (i % 2) * (cw + 0.35)
    cy = y0 + (i // 2) * (ch + 0.18)
    rect(s, cx, cy, 0.055, ch - 0.16, fill=PRIMARY, shape=MSO_SHAPE.RECTANGLE)
    tb, tf = textbox(s, cx + 0.22, cy, cw - 0.25, ch)
    para(tf, h, size=16.5, bold=True, color=INK, first=True, space_after=3)
    para(tf, d, size=14, color=INK2, line=1.35, space_after=0)
pg(s)

# ============ 5 系统总体架构 ============
s = blank(prs)
y = title(s, '系统总体架构', '四条主线解耦：模型能力与工程约束分离，日常陪伴与风险干预分离')
layers = [
    ('表现层', PRIMARY_L, PRIMARY_D, ['文字对话\n流式呈现', '实时语音对话\n断句与打断', '呼吸放松\n练习干预', '身份进入\n与风险留痕']),
    ('应用层', BLUE_BG, BLUE, ['对话编排\nRagService', '风险研判\nRiskEvaluator', '记忆与关怀\nMemory / Care', '会话分析\nSessionAnalysis']),
    ('服务层', WARN_BG, WARN, ['DeepSeek 对话模型\nOpenAI 兼容协议', '多模态感知服务\nWhisper + YuNet', '本地向量模型\nmultilingual-e5', 'MCP 服务端\n预警工具']),
    ('数据层', BG_SOFT, INK2, ['Chroma\n心理学知识片段', 'JSON 记忆档案\n画像与事实', 'Excel 留痕\n风险记录', '邮件留存\n预警记录']),
]
cy = y + 0.05
row_h = 0.92
for name, bg, fg, nodes in layers:
    tb, tf = textbox(s, M, cy + 0.22, 1.15, 0.4)
    para(tf, name, size=15, bold=True, color=fg, first=True, space_after=0)
    nx = M + 1.22
    avail = SW - M - nx
    n = len(nodes)
    gap = 0.18
    w = (avail - gap * (n - 1)) / n
    for i, txt in enumerate(nodes):
        node(s, nx + i * (w + gap), cy, w, row_h, txt, fill=bg, line=None, color=fg, size=12, bold=False)
    if cy + row_h + 0.28 < y + 4.9:
        for ax in (SW / 2 - 1.6, SW / 2 + 1.6):
            arrow_down(s, ax, cy + row_h + 0.035, h=0.16, color=LINE)
    cy += row_h + 0.30
pg(s)

# ============ 6 技术选型 ============
s = blank(prs)
y = title(s, '技术选型')
table(s, M, y + 0.05, SW - 2 * M,
      ['层次', '选型', '选择理由'],
      [
          ['后端框架', 'Java 17 · Spring Boot 3.5', '生态成熟，便于与现有 Java 课程体系衔接'],
          ['模型编排', 'Spring AI 1.1.8', '原生支持工具调用与流式输出，无需自行封装协议'],
          ['对话模型', 'DeepSeek deepseek-chat', '国内直连、成本可控，OpenAI 兼容协议'],
          ['向量化', '本地 ONNX multilingual-e5-small', '完全离线，只需一个对话模型密钥'],
          ['向量库', 'Chroma', '本地部署简单，支持持久化与集合管理'],
          ['多模态', 'FastAPI + faster-whisper + OpenCV', '语音与视觉生态在 Python 侧更成熟'],
          ['前端', 'Vue 3 + Vite', '组合式 API 便于组织对话与实时状态'],
      ],
      widths=[1.7, 3.4, 5.0], size=14, header_size=14, row_h=0.52, center_cols=(0,))
pg(s)

# ============ 7 Agentic RAG 闭环 ============
s = blank(prs)
y = title(s, '核心流程：Agentic RAG 问答闭环', '检索与风险研判由模型自主决定，而非固定流水线')
bw, bh = 2.28, 0.86
gapx = 0.42
x1 = M
rowy = y + 0.18
n1 = [('用户提问', '文本 / 语音转写\n含情绪特征'), ('组装提示词', '人格 · 结构约束\n注入长期记忆'), ('模型推理', 'DeepSeek\n决定是否调用工具')]
for i, (h, d) in enumerate(n1):
    x = x1 + i * (bw + gapx)
    node(s, x, rowy, bw, bh, h + '\n' + d, fill=PRIMARY_L, line=None, color=PRIMARY_D, size=12.5, bold=False)
    if i < len(n1) - 1:
        arrow_right(s, x + bw + 0.09, rowy + bh / 2, w=0.24)
tool_y = rowy + bh + 0.62
tb, tf = textbox(s, M, tool_y - 0.34, 3.0, 0.3)
para(tf, 'Agent 自主决策调用工具', size=13, bold=True, color=INK2, first=True, space_after=0)
tools = [('search_psychology_kb', '向量检索知识片段', WARN_BG, WARN),
         ('evaluate_risk_level', '规则 + 语义混合研判', WARN_BG, WARN),
         ('send_warning_email', '高风险时通知咨询师', DANGER_BG, DANGER),
         ('write_risk_record_excel', '写入风险留痕文件', DANGER_BG, DANGER)]
tw = (SW - 2 * M - 3 * 0.2) / 4
for i, (h, d, bg, fg) in enumerate(tools):
    node(s, M + i * (tw + 0.2), tool_y, tw, 0.78, h + '\n' + d, fill=bg, line=None, color=fg, size=11.5)
out_y = tool_y + 0.78 + 0.62
n2 = [('流式生成回答', 'SSE 逐段推送'), ('前端逐段呈现', '并按句朗读'), ('返回元数据', '来源与风险等级')]
for i, (h, d) in enumerate(n2):
    x = M + i * (bw + gapx)
    node(s, x, out_y, bw, bh, h + '\n' + d, fill=BLUE_BG, line=None, color=BLUE, size=12.5)
    if i < len(n2) - 1:
        arrow_right(s, x + bw + 0.09, out_y + bh / 2, w=0.24)
tb, tf = textbox(s, M + 3 * (bw + gapx) + 0.1, out_y + 0.06, 3.3, 0.8)
para(tf, '工具结果写回上下文，', size=12.5, color=INK2, first=True, space_after=2)
para(tf, '流结束时一并返回', size=12.5, color=INK2, space_after=0)
pg(s)

# ============ 8 风险识别与预警闭环 ============
s = blank(prs)
y = title(s, '核心流程：风险识别与预警闭环', '双通道设计：规则保证可解释不漏报，语义覆盖隐含表达')
node(s, M, y + 0.15, 2.0, 0.9, '用户输入\n文本 / 语音 / 表情', fill=BLUE_BG, line=None, color=BLUE, size=12.5)
arrow_right(s, M + 2.06, y + 0.6, w=0.28)
node(s, M + 2.42, y + 0.02, 2.5, 0.52, '规则层：关键词命中', fill=WARN_BG, line=None, color=WARN, size=13)
node(s, M + 2.42, y + 0.66, 2.5, 0.52, '语义层：模型结构化判定', fill=WARN_BG, line=None, color=WARN, size=13)
arrow_right(s, M + 4.98, y + 0.6, w=0.28)
node(s, M + 5.34, y + 0.15, 2.3, 0.9, '取较大值\n得到 0-3 级', fill=PRIMARY_L, line=None, color=PRIMARY_D, size=13)
arrow_right(s, M + 7.7, y + 0.6, w=0.28)
node(s, M + 8.06, y + 0.02, 2.55, 0.52, '等级 ≥ 2：触发预警', fill=DANGER_BG, line=None, color=DANGER, size=13)
node(s, M + 8.06, y + 0.66, 2.55, 0.52, '等级 ≤ 1：常态陪伴', fill=PRIMARY_L, line=None, color=PRIMARY_D, size=13)
by = y + 1.42
tb, tf = textbox(s, M, by, 4.2, 0.35)
para(tf, '达到阈值后自动执行', size=14, bold=True, color=INK, first=True, space_after=0)
acts = [('发送预警邮件', '通知咨询师或家属', DANGER_BG, DANGER),
        ('写入 Excel 留痕', '临时文件加原子替换', DANGER_BG, DANGER),
        ('前端风险提示条', '含一键拨打求助热线', DANGER_BG, DANGER),
        ('按使用者隔离记录', '切换身份互不可见', BG_SOFT, INK2)]
aw = (SW - 2 * M - 3 * 0.22) / 4
for i, (h, d, bg, fg) in enumerate(acts):
    node(s, M + i * (aw + 0.22), by + 0.42, aw, 0.82, h + '\n' + d, fill=bg, line=None, color=fg, size=12)
tb, tf = textbox(s, M, by + 1.42, SW - 2 * M, 0.6)
para(tf, '全部方案均未出现误报：把常规情绪表达误判为高风险会带来不必要的惊动，也会让使用者失去对系统的信任。',
     size=14, color=INK2, first=True, space_after=0, line=1.3)
pg(s)

# ============ 9 风险识别效果评测 ============
s = blank(prs)
y = title(s, '风险识别效果：混合方案准确率 90.0%，零误报', '测试集 130 条：高风险 90 条、常规表达 40 条；高风险判定阈值为等级 ≥ 2')
table(s, M, y + 0.1, SW - 2 * M,
      ['方法', '准确率', '精确率', '召回率（高风险）', 'F1', '误报', '漏报'],
      [
          ['纯规则', '66.2%', '100%', '51.1%', '67.6%', '0', '44'],
          ['纯大模型', '86.9%', '100%', '81.1%', '89.6%', '0', '17'],
          ['规则与大模型混合', '90.0%', '100%', '85.6%', '92.2%', '0', '13'],
      ],
      widths=[3.0, 1.4, 1.4, 2.0, 1.2, 0.9, 0.9], size=14.5, header_size=13.5,
      row_h=0.56, center_cols=(1, 2, 3, 4, 5, 6))
cy = y + 2.4
concl = [
    ('规则负责兜底，语义负责覆盖', '规则命中即可解释，但只能处理显式表达，召回率仅 51.1%；语义层可识别不含关键词的隐含表达。'),
    ('取较大值保证安全优先', '两层结果取较大值，混合后精确率仍为 100%，召回率提升到 85.6%，F1 达到 92.2%。'),
    ('漏报集中在隐晦的存在性困扰', '13 条漏报均为"活着是为了什么"这类无明确关键词的边界样本，是当前方案的改进方向。'),
]
for i, (h, d) in enumerate(concl):
    cx = M + i * ((SW - 2 * M) / 3)
    tb, tf = textbox(s, cx, cy, (SW - 2 * M) / 3 - 0.3, 1.6)
    para(tf, h, size=15.5, bold=True, color=PRIMARY_D, first=True, space_after=4, line=1.25)
    para(tf, d, size=13.5, color=INK2, line=1.4, space_after=0)
pg(s)

# ============ 10 技术难点一 ============
s = blank(prs)
y = title(s, '难点一：流式输出与 Agent 工具调用并存')
rows = [
    ('问题', '普通接口正常，改为流式后回答能生成，但检索来源与风险等级全部丢失', DANGER_BG, DANGER),
    ('根因', '工具调用在响应式线程执行，请求作用域的上下文对象取不到，写入的数据无法被读取', WARN_BG, WARN),
    ('方案', '改用框架提供的 ToolContext 显式传参，上下文与线程解耦，普通接口与流式共用同一套逻辑', PRIMARY_L, PRIMARY_D),
]
cy = y + 0.15
for tag, desc, bg, fg in rows:
    rect(s, M, cy, 1.25, 0.92, fill=bg, line=None, radius=0.12)
    tb, tf = textbox(s, M, cy + 0.24, 1.25, 0.4)
    para(tf, tag, size=16, bold=True, color=fg, first=True, align=PP_ALIGN.CENTER, space_after=0)
    tb, tf = textbox(s, M + 1.5, cy + 0.08, SW - 2 * M - 1.5, 0.85)
    para(tf, desc, size=15.5, color=INK, first=True, line=1.35, space_after=0)
    cy += 1.12
rect(s, M, cy + 0.08, SW - 2 * M, 1.35, fill=BG_SOFT, line=None, radius=0.05)
tb, tf = textbox(s, M + 0.3, cy + 0.26, SW - 2 * M - 0.6, 1.1)
para(tf, '验证结果', size=14.5, bold=True, color=INK, first=True, space_after=5)
para(tf, '一次流式请求实际推送 282 个文本片段事件，流结束时正确返回 3 条检索来源与风险判定结果，'
         'Agent 自主调用工具的能力没有被削弱。', size=14.5, color=INK2, line=1.35, space_after=0)
pg(s)

# ============ 11 技术难点二 ============
s = blank(prs)
y = title(s, '难点二：实时语音对话中的打断失效', '文字流结束并不等于播报结束')
states = [('待命', 'idle', BG_SOFT, INK2), ('聆听', 'listening', PRIMARY_L, PRIMARY_D),
          ('思考', 'thinking', WARN_BG, WARN), ('说话', 'speaking', BLUE_BG, BLUE)]
sw_, sh_ = 2.41, 0.95
sx = M
sy = y + 0.30
for i, (h, en, bg, fg) in enumerate(states):
    x = sx + i * (sw_ + 0.75)
    node(s, x, sy, sw_, sh_, h + '\n' + en, fill=bg, line=None, color=fg, size=14.5, bold=True)
    if i < 3:
        arrow_right(s, x + sw_ + 0.16, sy + sh_ / 2, w=0.43)
        lab = ['开始对话', '静音 0.9 秒', '首段文字到达'][i]
        tb, tf = textbox(s, x + sw_ - 0.06, sy - 0.38, 0.87, 0.34)
        para(tf, lab, size=9.5, color=INK3, first=True, align=PP_ALIGN.CENTER, space_after=0)
# 回到聆听
node(s, M + 3.15, sy + 1.62, 3.6, 0.72, '朗读播完 → 回到聆听', fill=PRIMARY_L, line=None, color=PRIMARY_D, size=14)
arrow_down(s, M + 1.5, sy + 1.03, h=0.5, color=LINE)
# 打断
tb, tf = textbox(s, M + 8.3, sy + 1.62, 3.4, 0.8)
para(tf, '用户开口 → 立即打断', size=14.5, bold=True, color=DANGER, first=True, space_after=3)
para(tf, '取消朗读 · 中止生成 · 作废旧轮次结果', size=12.5, color=INK2, space_after=0)
arrow_down(s, M + 9.1, sy + sh_ + 0.06, h=0.42, color=DANGER)
cy = sy + 2.7
tb, tf = textbox(s, M, cy, SW - 2 * M, 1.2)
para(tf, '根因与修正', size=15, bold=True, color=INK, first=True, space_after=6)
para(tf, '原实现在文字流结束时就把状态切回聆听，而语音还要继续朗读十余秒，打断判断在最需要生效的时段失效；'
         '同时按句朗读会不断提交新任务，取消后又被排上。修正后引入三个机制：未播报句子计数、播报凭证、轮次令牌。',
     size=14.5, color=INK2, line=1.4, space_after=0)
pg(s)

# ============ 12 记忆与主动关怀 ============
s = blank(prs)
y = title(s, '差异化能力：记得住人，也主动开口', '情感强度来自记忆，而不是话术优化')
rect(s, M, y + 0.05, 6.1, 4.45, fill=BG_SOFT, line=None, radius=0.05)
tb, tf = textbox(s, M + 0.34, y + 0.3, 5.45, 4.05)
para(tf, '实测对话（连续三轮）', size=14.5, bold=True, color=INK, first=True, space_after=10)
for who, txt in [('用户', '我孙女叫朵朵，今年上小学二年级'),
                 ('用户', '我最近腰疼得厉害，晚上睡不好'),
                 ('用户', '我平时喜欢听戏，尤其是京剧')]:
    para(tf, who + '：' + txt, size=14, color=INK2, line=1.35, space_after=7)
para(tf, '系统自动记住的事实', size=14.5, bold=True, color=PRIMARY_D, space_before=6, space_after=6)
para(tf, '孙女叫朵朵，上小学二年级 ／ 最近腰疼得厉害，晚上睡不好 ／ 平时喜欢听戏，尤其是京剧',
     size=14, color=PRIMARY_D, line=1.4, space_after=10)
para(tf, '主动关怀（由记忆生成）', size=14.5, bold=True, color=INK, space_after=6)
para(tf, '"有几天没聊了，王奶奶。我还记着你说的平时喜欢听戏，尤其是京剧，最近怎么样？"',
     size=14.5, color=INK, line=1.4, space_after=0)
tb, tf = textbox(s, M + 6.55, y + 0.15, 5.3, 4.4)
para(tf, '实现要点', size=15.5, bold=True, color=INK, first=True, space_after=10)
for h, d in [('按人存储', '每位使用者一份记忆档案，切换身份互不可见'),
             ('异步抽取', '每三轮对话由模型抽取一次事实，不拖慢回答'),
             ('节律触发', '只在早间问候与久未联系两类明确时机开口'),
             ('开口必须具体', '用记忆里的事实说话，不用"今天感觉怎么样"这类套话'),
             ('宁可少说', '主动关怀留痕且可关闭，避免造成打扰与依赖')]:
    para(tf, h, size=15, bold=True, color=PRIMARY_D, space_before=4, space_after=2)
    para(tf, d, size=13.5, color=INK2, line=1.35, space_after=4)
pg(s)

# ============ 13 系统界面 ============
s = blank(prs)
y = title(s, '系统界面：从测试页到完整交互')
picture(s, os.path.join(FIG, 'shot_entry.png'), M, y + 0.35, w=5.55)
picture(s, os.path.join(FIG, 'shot_chat.png'), M + 6.35, y + 0.35, w=5.55)
tb, tf = textbox(s, M, y + 4.0, 5.55, 0.5)
para(tf, '身份进入页：选择身份与称呼即可进入，不设密码', size=13, color=INK2, first=True, align=PP_ALIGN.CENTER, space_after=0)
tb, tf = textbox(s, M + 6.35, y + 4.0, 5.55, 0.5)
para(tf, '文字对话页：左侧导航、中间对话、右侧研判与记忆', size=13, color=INK2, first=True, align=PP_ALIGN.CENTER, space_after=0)
pg(s)

# ============ 14 功能测试 ============
s = blank(prs)
y = title(s, '功能测试：主要路径均通过', '测试覆盖使用者端完整链路与异常回退')
table(s, M, y + 0.08, SW - 2 * M,
      ['编号', '测试内容', '预期结果', '结果'],
      [
          ['F-02', '提交文字问题', '流式返回回答并展示检索来源', '通过'],
          ['F-03', '追问上一轮话题', '回答能引用前文关键信息', '通过'],
          ['F-04', '提交含风险表达的内容', '返回风险等级并显示求助入口', '通过'],
          ['F-05', '高风险时检查留痕', 'Excel 文件新增一条记录', '通过'],
          ['F-07', '重新进入系统后提问', '回答能引用此前提到的信息', '通过'],
          ['F-08', '触发主动关怀', '生成一条基于记忆的具体关怀', '通过'],
          ['F-09', '实时语音对话', '静音后自动识别并进入回答流程', '通过'],
          ['F-10', '朗读过程中开口打断', '立即停止朗读并转入聆听', '通过'],
          ['F-11', '流式通道不可用时提问', '自动回退到普通接口并返回回答', '通过'],
      ],
      widths=[1.1, 4.0, 5.4, 1.1], size=13.5, header_size=13, row_h=0.42, center_cols=(0, 3))
pg(s)

# ============ 15 AI 工具选型 ============
s = blank(prs)
y = title(s, 'AI 辅助编程工具选型', '按任务书给定的五个维度对比四款工具')
table(s, M, y + 0.08, SW - 2 * M,
      ['评价维度', 'GitHub Copilot', 'Cursor', '终端智能体类工具', '通义灵码'],
      [
          ['人机协作流畅度', '被动响应，补全不打断思路', '主动融入，编辑器内全流程', '任务委托式，可并行等待', '被动响应，中文顺畅'],
          ['既有代码理解', '以当前文件为主', '仓库级索引，理解结构', '仓库级检索并执行验证', '单文件与少量引用'],
          ['自主任务执行', '弱，需逐步下指令', '中，多文件编辑需确认', '强，可自主拆解多步任务', '弱至中'],
          ['出错与纠错', '给建议，需自行排查', '可读取编辑器报错', '可跑命令与测试，闭环修正', '可解释报错，闭环有限'],
          ['工作流覆盖', '编码为主', '编码、检索、重构', '需求到测试与文档全链路', '编码为主'],
      ],
      widths=[2.1, 2.4, 2.4, 2.8, 2.2], size=12.5, header_size=12.5, row_h=0.52, center_cols=())
tb, tf = textbox(s, M, y + 3.35, SW - 2 * M, 1.1)
para(tf, '选型结论：以终端智能体类工具为主力，IDE 补全工具为日常辅助', size=16, bold=True, color=PRIMARY_D, first=True, space_after=5)
para(tf, '本项目技术栈跨度大、存在多个依赖具体版本实现细节的集成问题，需要工具能够检索本地依赖、阅读源码并实际运行验证；'
         '而关键决策（是否牺牲 Agent 自主性换取流式、记忆如何存储、何时主动开口）始终由人判断。',
     size=14, color=INK2, line=1.4, space_after=0)
pg(s)

# ============ 16 AI 交互记录 ============
s = blank(prs)
y = title(s, 'AI 交互记录：五组关键提示词', '覆盖设计建议、调试修复与代码生成三类')
recs = [
    ('设计建议', '我想做出一个比通用助手在情感方面更强大的 agent，并能主动做一些事', '输出"情感强度来自记忆而非话术"的判断，给出记忆、节律、通知到人三条支点'),
    ('设计建议', '回答不要用 markdown；我没看出文字哪里有安慰到我', '实测取证：回答含 26 处加粗与 6 项方法清单，共情仅 1 句；据此重写提示词结构'),
    ('代码生成', '要真正的流式输出，但不能牺牲 Agent 自主调用工具的能力', '先查框架源码确认可行性，再实现 SSE 接口与前端解析，含不可用时的回退'),
    ('调试修复', '声音很难听，且我说别的话时上一段回答还在播放', '定位到音色选中趣味音效、状态在文字流结束时过早切回两项根因'),
    ('代码生成', '把讨论的改进全部做完：流式、实时语音、身份、记忆与主动关怀', '分批实现并逐项实测，发现主动关怀话术与触发条件不匹配后修正'),
]
cy = y + 0.12
for kind, prompt, out in recs:
    rect(s, M, cy, 1.15, 0.78, fill=PRIMARY_L, line=None, radius=0.14)
    tb, tf = textbox(s, M, cy + 0.2, 1.15, 0.4)
    para(tf, kind, size=12.5, bold=True, color=PRIMARY_D, first=True, align=PP_ALIGN.CENTER, space_after=0)
    tb, tf = textbox(s, M + 1.38, cy + 0.02, 5.15, 0.8)
    para(tf, '“' + prompt + '”', size=13, color=INK, first=True, line=1.3, space_after=0)
    tb, tf = textbox(s, M + 6.75, cy + 0.02, 4.5, 0.8)
    para(tf, out, size=13, color=INK2, first=True, line=1.3, space_after=0)
    cy += 0.98
pg(s)

# ============ 17 总结与展望 ============
s = blank(prs)
y = title(s, '总结与后续工作')
tb, tf = textbox(s, M, y + 0.05, 6.0, 4.4)
para(tf, '完成的工作', size=17, bold=True, color=PRIMARY_D, first=True, space_after=10)
for t in ['完整的 Agentic RAG 问答链路，检索与风险研判由模型自主决策',
          '规则与大模型混合的风险识别，准确率 90.0% 且零误报',
          '通过 MCP 触发的预警闭环：邮件通知与 Excel 留痕',
          '语音、韵律与表情在内的多模态感知',
          '支持自动断句与随时打断的实时语音对话',
          '跨会话长期记忆与基于记忆的主动关怀',
          '从测试页重构为完整交互界面，含身份进入与风险留痕']:
    p = tf.add_paragraph()
    p.space_after = Pt(6); p.line_spacing = 1.3
    r = p.add_run(); r.text = '· ' + t
    style(r, size=14.5, color=INK)
tb, tf = textbox(s, M + 6.55, y + 0.05, 5.3, 4.4)
para(tf, '不足与后续工作', size=17, bold=True, color=DANGER, first=True, space_after=10)
for t in ['管理侧功能不完整，知识库更新与对话审计依赖手工操作',
          '身份仅实现归属关系，尚无令牌校验与权限控制',
          '记忆与留痕以文件存储，多实例部署需迁移至数据库',
          '语音活动检测基于音量阈值，嘈杂环境可能误触发',
          '记忆可能存在遗漏或偏差，需补充查看与纠错入口',
          '任务书提到的 LoRA 微调尚未开展']:
    p = tf.add_paragraph()
    p.space_after = Pt(6); p.line_spacing = 1.3
    r = p.add_run(); r.text = '· ' + t
    style(r, size=14.5, color=INK2)
pg(s)

# ============ 18 致谢 ============
s = blank(prs)
rect(s, 0, 0, SW, 0.22, fill=PRIMARY)
tb, tf = textbox(s, 1.2, 2.6, SW - 2.4, 2.2)
para(tf, '感谢聆听', size=44, bold=True, color=PRIMARY_D, first=True, align=PP_ALIGN.CENTER, space_after=14)
para(tf, '恳请各位老师批评指正', size=20, color=INK2, align=PP_ALIGN.CENTER, space_after=0)
tb, tf = textbox(s, 1.2, 5.5, SW - 2.4, 0.6)
para(tf, '袁孙明　9109223018　指导教师：幸玮', size=15, color=INK3, first=True, align=PP_ALIGN.CENTER, space_after=0)

prs.save(OUT)
print('已生成:', OUT, '| 幻灯片数:', len(prs.slides._sldIdLst))
