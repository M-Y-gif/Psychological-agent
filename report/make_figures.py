# -*- coding: utf-8 -*-
"""生成工程实践报告所需的示意图（PIL 绘制，2 倍超采样后缩放）。"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figures')
os.makedirs(OUT, exist_ok=True)

FONT_PATH = '/System/Library/Fonts/STHeiti Medium.ttc'
FONT_LIGHT = '/System/Library/Fonts/STHeiti Light.ttc'

INK = '#15181C'; INK2 = '#5B6472'
BOX_BG = '#F4F5F6'; BOX_LN = '#C3C9CE'
ACC_BG = '#E8F3F0'; ACC_LN = '#2E7D6F'; ACC_TX = '#1D594F'
WARN_BG = '#FDF1EF'; WARN_LN = '#C86B60'; WARN_TX = '#8C241A'
BLUE_BG = '#EDF2F9'; BLUE_LN = '#7A93B4'; BLUE_TX = '#2C4A6E'
S = 2  # 超采样倍数


def font(size, light=False):
    return ImageFont.truetype(FONT_LIGHT if light else FONT_PATH, size * S)


def new_canvas(w, h, bg='white'):
    return Image.new('RGB', (w * S, h * S), bg), ImageDraw.Draw(Image.new('RGB', (1, 1)))


def canvas(w, h, bg='white'):
    img = Image.new('RGB', (w * S, h * S), bg)
    return img, ImageDraw.Draw(img)


def box(d, x, y, w, h, text, fill=BOX_BG, ln=BOX_LN, tx=INK, size=13, radius=10, bold=True, lw=2):
    d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=radius * S,
                        fill=fill, outline=ln, width=lw * S // 2)
    f = font(size, light=not bold)
    lines = text.split('\n')
    lh = size * 1.35 * S
    total = lh * len(lines)
    cy = (y + h / 2) * S - total / 2 + lh / 2
    for i, line in enumerate(lines):
        d.text(((x + w / 2) * S, cy + i * lh), line, font=f, fill=tx, anchor='mm')


def label(d, x, y, text, size=12, color=INK2, anchor='mm', bold=False):
    d.text((x * S, y * S), text, font=font(size, light=not bold), fill=color, anchor=anchor)


def arrow(d, x1, y1, x2, y2, color=INK2, width=2, head=7, dash=False):
    if dash:
        # 简单虚线
        import math
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        steps = max(1, int(dist / 10))
        for i in range(0, steps, 2):
            t0, t1 = i / steps, min((i + 1) / steps, 1)
            d.line([(x1 + dx * t0) * S, (y1 + dy * t0) * S, (x1 + dx * t1) * S, (y1 + dy * t1) * S],
                   fill=color, width=width * S // 2)
    else:
        d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=color, width=width * S // 2)
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    p = [(x2, y2),
         (x2 - head * math.cos(ang - 0.42), y2 - head * math.sin(ang - 0.42)),
         (x2 - head * math.cos(ang + 0.42), y2 - head * math.sin(ang + 0.42))]
    d.polygon([(px * S, py * S) for px, py in p], fill=color)


def save(img, name, w, h):
    img = img.resize((w, h), Image.LANCZOS)
    path = os.path.join(OUT, name)
    img.save(path, 'PNG')
    print('生成', name, img.size)


# ---------------- 图 1：系统总体架构 ----------------
def fig_arch():
    W, H = 900, 600
    img, d = canvas(W, H)
    label(d, 30, 26, '图 4-1  系统总体架构', size=15, color=INK, anchor='lm', bold=True)

    # 前端层
    label(d, 30, 70, '表现层', size=12, color=INK2, anchor='lm')
    box(d, 110, 52, 200, 46, '文字对话页\n（SSE 流式）', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11.5)
    box(d, 325, 52, 200, 46, '实时语音对话页\n（VAD 断句 / 打断）', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11.5)
    box(d, 540, 52, 150, 46, '呼吸练习\n放松干预', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11.5)
    box(d, 705, 52, 165, 46, '进入页 / 风险记录\n身份与留痕', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11.5)

    arrow(d, 450, 102, 450, 128)

    # 后端
    label(d, 30, 155, '应用层', size=12, color=INK2, anchor='lm')
    box(d, 110, 128, 760, 118, '', fill='#FAFAFA', ln=BOX_LN, size=12, radius=12)
    box(d, 128, 142, 168, 42, '对话编排\nRagService', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)
    box(d, 308, 142, 168, 42, '风险研判\nRiskEvaluator', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)
    box(d, 488, 142, 168, 42, '长期记忆与主动关怀\nMemoryService / CareService', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11)
    box(d, 668, 142, 184, 42, '会话分析\nSessionAnalysisService', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)
    box(d, 128, 192, 348, 40, 'Agent 工具层：search_psychology_kb / evaluate_risk_level', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12', size=11)
    box(d, 488, 192, 364, 40, 'MCP 服务端：send_warning_email / write_risk_record_excel', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12', size=11)

    arrow(d, 450, 250, 450, 278)
    arrow(d, 300, 278, 300, 250)

    # 服务层
    label(d, 30, 305, '服务层', size=12, color=INK2, anchor='lm')
    box(d, 110, 278, 240, 52, 'DeepSeek 对话模型\n（OpenAI 兼容协议）', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)
    box(d, 366, 278, 240, 52, '多模态感知服务\nWhisper + OpenCV YuNet', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)
    box(d, 622, 278, 230, 52, '本地向量模型\nmultilingual-e5-small', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)

    arrow(d, 450, 334, 450, 362)

    # 数据层
    label(d, 30, 390, '数据层', size=12, color=INK2, anchor='lm')
    box(d, 110, 362, 240, 50, 'Chroma 向量库\n心理学知识片段', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11.5)
    box(d, 366, 362, 240, 50, 'JSON 记忆档案\n用户画像与事实', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11.5)
    box(d, 622, 362, 230, 50, 'Excel 风险留痕\n预警记录', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11.5)

    # 说明
    box(d, 110, 440, 742, 96, '', fill='#FFFFFF', ln=BOX_LN, radius=10)
    label(d, 132, 462, '关键设计', size=12, color=INK, anchor='lm', bold=True)
    label(d, 132, 488, '· 流式输出与 Agent 工具调用并存：通过 ToolContext 显式传递请求级上下文，避免响应式线程下作用域失效',
          size=11, color=INK2, anchor='lm')
    label(d, 132, 510, '· 记忆与关怀解耦：对话轮次落盘为记忆档案，定时任务据此生成主动关怀，避免随机打扰',
          size=11, color=INK2, anchor='lm')
    save(img, 'fig_arch.png', W, H)


# ---------------- 图 2：Agentic RAG 问答闭环 ----------------
def fig_rag():
    W, H = 880, 470
    img, d = canvas(W, H)
    label(d, 30, 26, '图 5-1  Agentic RAG 问答与工具调用流程', size=15, color=INK, anchor='lm', bold=True)

    box(d, 40, 70, 150, 48, '用户提问\n（含情绪特征）', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX)
    box(d, 240, 70, 170, 48, '组装系统提示词\n人格 / 结构 / 约束', fill=BOX_BG)
    box(d, 460, 70, 170, 48, '注入长期记忆\n（跨会话事实）', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX)

    arrow(d, 190, 94, 240, 94)
    arrow(d, 410, 94, 460, 94)
    arrow(d, 630, 94, 700, 94)
    box(d, 700, 70, 150, 48, 'DeepSeek\n推理', fill=BOX_BG)

    arrow(d, 775, 118, 775, 155)
    box(d, 620, 155, 255, 60, 'Agent 自主决策\n是否调用工具', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX)
    arrow(d, 620, 185, 520, 185)

    box(d, 250, 152, 265, 30, 'search_psychology_kb（向量检索）', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12', size=11)
    box(d, 250, 190, 265, 30, 'evaluate_risk_level（规则+语义）', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12', size=11)
    box(d, 250, 228, 265, 30, 'send_warning_email / write_excel', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11)
    label(d, 380, 122, '命中高风险时', size=10.5, color=WARN_TX)

    arrow(d, 250, 185, 180, 185)
    box(d, 40, 152, 140, 106, '工具结果\n写回上下文\n（检索片段 /\n风险等级）', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11)
    arrow(d, 110, 258, 110, 300)
    box(d, 40, 300, 250, 44, '流式生成回答（SSE 逐段推送）', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)
    arrow(d, 290, 322, 340, 322)
    box(d, 340, 300, 240, 44, '前端边接收边呈现\n并按句朗读', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11.5)
    arrow(d, 580, 322, 630, 322)
    box(d, 630, 300, 220, 44, '结束后推送元数据\n来源 / 风险等级', fill=BOX_BG, size=11.5)

    box(d, 40, 372, 810, 66, '', fill='#FFFFFF', ln=BOX_LN)
    label(d, 60, 392, '设计要点', size=11.5, color=INK, anchor='lm', bold=True)
    label(d, 60, 416, '工具调用在响应式线程中执行，因此上下文的传递方式由请求作用域改为 ToolContext 显式传参，'
                       '保证流式与工具调用可以同时成立。', size=10.5, color=INK2, anchor='lm')
    save(img, 'fig_rag.png', W, H)


# ---------------- 图 3：风险识别与预警闭环 ----------------
def fig_risk():
    W, H = 880, 380
    img, d = canvas(W, H)
    label(d, 30, 26, '图 5-2  风险识别与预警闭环', size=15, color=INK, anchor='lm', bold=True)

    box(d, 40, 72, 160, 52, '用户输入\n文本 / 语音 / 表情', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX)
    arrow(d, 200, 98, 250, 98)

    box(d, 250, 62, 170, 30, '规则层：关键词命中', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12', size=11)
    box(d, 250, 100, 170, 30, '语义层：模型结构化判定', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12', size=11)
    arrow(d, 420, 98, 470, 98)
    box(d, 470, 72, 150, 52, '合并取较大值\n得到 0-3 级', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)

    arrow(d, 620, 85, 670, 85)
    arrow(d, 620, 120, 670, 120)
    box(d, 670, 60, 180, 40, '等级 ≥ 2：触发预警', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11.5)
    box(d, 670, 108, 180, 36, '等级 ≤ 1：常态陪伴', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX, size=11.5)

    arrow(d, 760, 100, 760, 168)
    box(d, 470, 168, 380, 46, '预警动作（MCP 工具）\n发送预警邮件 · 写入 Excel 留痕', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11.5)
    arrow(d, 470, 191, 420, 191)
    box(d, 250, 168, 170, 46, '前端风险提示条\n含一键拨打求助热线', fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11)
    arrow(d, 250, 191, 210, 191)
    box(d, 40, 168, 170, 46, '会话内风险留痕\n按使用者隔离', fill=BOX_BG, size=11)

    box(d, 40, 250, 810, 100, '', fill='#FFFFFF', ln=BOX_LN)
    label(d, 60, 272, '评测口径', size=11.5, color=INK, anchor='lm', bold=True)
    label(d, 60, 296, '数据集：PsyCrisis-Bench 高风险语料 + 自建常规语料，共 130 条测试样本；判定高风险阈值为等级 ≥ 2。', size=10.5, color=INK2, anchor='lm')
    label(d, 60, 320, '对比方法：纯规则、纯大模型、规则与大模型混合；评价指标为准确率、精确率、召回率、F1 与误报漏报数。', size=10.5, color=INK2, anchor='lm')
    save(img, 'fig_risk.png', W, H)


# ---------------- 图 4：实时语音对话状态机 ----------------
def fig_voice():
    W, H = 880, 400
    img, d = canvas(W, H)
    label(d, 30, 26, '图 5-3  实时语音对话状态机', size=15, color=INK, anchor='lm', bold=True)

    box(d, 60, 90, 150, 60, '待命\nidle', fill=BOX_BG)
    box(d, 300, 90, 150, 60, '聆听\nlistening', fill=ACC_BG, ln=ACC_LN, tx=ACC_TX)
    box(d, 540, 90, 150, 60, '思考\nthinking', fill='#FFF9E8', ln='#D9B45E', tx='#7A5A12')
    box(d, 540, 240, 150, 60, '说话\nspeaking', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX)

    arrow(d, 210, 120, 300, 120)
    label(d, 255, 106, '开始对话', size=10)
    arrow(d, 450, 120, 540, 120)
    label(d, 495, 106, '静音 0.9 秒', size=10)
    arrow(d, 615, 150, 615, 240)
    label(d, 668, 195, '首段文字到达', size=10)
    arrow(d, 540, 270, 375, 270)
    arrow(d, 375, 270, 375, 150)
    label(d, 452, 286, '朗读播完', size=10)

    # 打断
    arrow(d, 690, 240, 690, 200, color=WARN_LN, width=3)
    arrow(d, 690, 200, 690, 150, color=WARN_LN, width=3)
    arrow(d, 690, 150, 690, 120, color=WARN_LN, width=3)
    label(d, 760, 190, '用户开口\n打断', size=10.5, color=WARN_TX)

    box(d, 60, 250, 230, 100,
        '打断处理\n· 语音合成立即取消\n· 生成请求中止\n· 轮次令牌作废旧结果',
        fill=WARN_BG, ln=WARN_LN, tx=WARN_TX, size=11)
    arrow(d, 290, 300, 375, 300, color=WARN_LN)

    box(d, 40, 366, 810, 26, '状态迁移约束：文字流结束不等于播报结束，只有文字流完成且朗读队列清空后才回到聆听状态。',
        fill='#FFFFFF', ln=BOX_LN, size=10.5, radius=6)
    save(img, 'fig_voice.png', W, H)


# ---------------- 图 5：ER 图 ----------------
def fig_er():
    W, H = 1180, 620
    img, d = canvas(W, H)
    label(d, 30, 26, '图 6-1  数据库实体关系（ER）图', size=15, color=INK, anchor='lm', bold=True)

    def entity(x, y, w, title, fields, fill=ACC_BG, ln=ACC_LN, tx=ACC_TX):
        h = 30 + len(fields) * 17
        d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=8 * S,
                            fill='white', outline=ln, width=S)
        d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + 28) * S], radius=8 * S, fill=fill, outline=ln, width=S)
        d.rectangle([x * S, (y + 20) * S, (x + w) * S, (y + 28) * S], fill=fill)
        d.text(((x + w / 2) * S, (y + 14) * S), title, font=font(11.5), fill=tx, anchor='mm')
        for i, f in enumerate(fields):
            d.text(((x + 8) * S, (y + 38 + i * 17) * S), f, font=font(9.8, light=True), fill=INK2, anchor='lm')
        return (x, y, w, h)

    # 第 1 列：使用者与对话
    entity(35, 70, 165, 'app_user 使用者', ['PK id', 'role 角色', 'name 称呼', 'created_at', 'last_active'])
    entity(35, 235, 165, 'conversation 会话', ['PK id', 'FK user_id', 'started_at', 'ended_at'])
    entity(35, 380, 165, 'message 消息', ['PK id', 'FK conversation_id', 'speaker 角色', 'content', 'created_at'])

    # 第 2 列：风险与关怀
    entity(320, 70, 190, 'risk_record 风险记录', ['PK id', 'FK user_id', 'FK message_id', 'level 等级', 'reason 依据', 'created_at'])
    entity(320, 245, 190, 'care_message 主动关怀', ['PK id', 'FK user_id', 'type 类型', 'content 内容', 'reason 触发原因', 'delivered 已送达'])
    entity(320, 445, 190, 'warning_log 预警日志', ['PK id', 'FK risk_record_id', 'channel 渠道', 'sent_at'])

    # 第 3 列：记忆
    entity(625, 70, 185, 'memory_fact 记忆事实', ['PK id', 'FK user_id', 'fact_text 事实', 'created_at'])
    entity(625, 215, 185, 'memory_event 日程事件', ['PK id', 'FK user_id', 'event_text 事件', 'event_date 日期', 'reminded 已回访'])
    entity(625, 395, 185, 'mood_score 情绪打卡', ['PK id', 'FK user_id', 'score 分值', 'source 来源', 'created_at'])

    # 第 4 列：知识库与日记
    entity(925, 70, 220, 'knowledge_doc 知识文档', ['PK id', 'title 标题', 'chunk_count 片段数', 'indexed_at 向量化时间'])
    entity(925, 240, 220, 'kb_chunk 知识片段', ['PK id', 'FK doc_id', 'content 正文', 'embedding_ref 向量标识'])
    entity(925, 405, 220, 'diary 心情日记', ['PK id', 'FK user_id', 'content 正文', 'mood 心情 1-5', 'mood_score 映射分', 'reply 回信', 'risk_level 回信风险'])

    def rel(x1, y1, x2, y2, dash=False):
        arrow(d, x1, y1, x2, y2, color=INK2, width=2, dash=dash)

    # 使用者 → 各归属实体
    rel(200, 120, 320, 120)          # app_user → risk_record
    rel(200, 150, 320, 300)          # app_user → care_message
    rel(200, 190, 625, 120)          # app_user → memory_fact
    rel(200, 205, 625, 265)          # app_user → memory_event
    rel(200, 230, 625, 445)          # app_user → mood_score
    rel(200, 245, 925, 460)          # app_user → diary
    rel(117, 175, 117, 235)          # app_user → conversation
    rel(117, 340, 117, 380)          # conversation → message

    # 其他关系
    rel(415, 200, 415, 245)          # risk_record → care_message（同一使用者）
    rel(510, 105, 625, 105, dash=True)   # risk_record → 记忆（同源）
    rel(510, 300, 510, 445)          # care_message → warning_log
    rel(1035, 175, 1035, 240)        # knowledge_doc → kb_chunk

    for x, y, t in [(240, 108, '1:N'), (255, 210, '1:N'), (400, 96, '1:N'),
                    (123, 208, '1:N'), (123, 362, '1:N')]:
        label(d, x, y, t, size=9.5, color=INK2)
    label(d, 35, 590, '说明：实线为主关系，虚线为可选关联。记忆域按数据类型分表存储，'
                      '便于分别做检索式注入（事实/事件）与趋势分析（情绪打卡）。',
          size=10.5, color=INK2, anchor='lm')
    save(img, 'fig_er.png', W, H)


# ---------------- 图 6：用例图 ----------------
def fig_usecase():
    W, H = 900, 470
    img, d = canvas(W, H)
    label(d, 30, 26, '图 4-2  系统用例图', size=15, color=INK, anchor='lm', bold=True)

    # 参与者
    box(d, 40, 120, 110, 44, '长者 / 儿童\n（使用者）', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11)
    box(d, 40, 300, 110, 44, '家属 / 咨询师', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11)
    box(d, 750, 210, 110, 44, '管理员', fill=BLUE_BG, ln=BLUE_LN, tx=BLUE_TX, size=11)

    # 系统边界
    d.rectangle([210 * S, 70 * S, 740 * S, 410 * S], outline=BOX_LN, width=S * 2, fill='#FCFCFC')
    label(d, 475, 88, '心理预警与咨询 Agent 系统', size=11.5, color=INK, bold=True)

    uc = [
        (230, 110, '选择身份并进入'),
        (230, 175, '文字对话'),
        (230, 240, '实时语音对话'),
        (230, 305, '接收风险提示'),
        (230, 370, '呼吸放松练习'),
        (520, 110, '风险识别与预警'),
        (520, 175, '主动关怀'),
        (520, 240, '心理分析报告'),
        (520, 305, '查看风险记录'),
        (520, 370, '知识库与预警管理'),
    ]
    for x, y, t in uc:
        d.rounded_rectangle([x * S, y * S, (x + 190) * S, (y + 46) * S], radius=23 * S,
                            fill='#FFFFFF', outline=ACC_LN, width=S)
        d.text(((x + 95) * S, (y + 23) * S), t, font=font(11), fill=INK, anchor='mm')

    def link(x1, y1, x2, y2):
        d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=INK2, width=S // 2)

    for y in (133, 198, 263, 328, 393):
        link(150, y, 230, y)
    link(150, 322, 230, 198)
    link(150, 322, 230, 328)
    link(750, 232, 710, 133)
    link(750, 232, 710, 328)

    label(d, 40, 450, '说明：使用者侧用例全部可在同一会话内闭环；管理员侧知识库与预警管理在本次实践中完成设计，实现范围见第 8 章。',
          size=10.5, color=INK2, anchor='lm')
    save(img, 'fig_usecase.png', W, H)


if __name__ == '__main__':
    fig_arch()
    fig_rag()
    fig_risk()
    fig_voice()
    fig_er()
    fig_usecase()
    print('全部示意图生成完成')
