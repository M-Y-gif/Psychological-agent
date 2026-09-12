# -*- coding: utf-8 -*-
"""工程实践答辩 PPT 生成脚本。

版式约定：16:9；左对齐单一标题栏；正文扁平排布，不使用卡片网格与装饰性面板。
配色沿用项目设计系统（低饱和青绿），保证投影下对比度充足。
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '多模态AgenticRAG心理预警与咨询Agent答辩PPT.pptx')

# ---------- 设计系统 ----------
PRIMARY = RGBColor(0x2E, 0x7D, 0x6F)
PRIMARY_D = RGBColor(0x1D, 0x59, 0x4F)
PRIMARY_L = RGBColor(0xE8, 0xF3, 0xF0)
INK = RGBColor(0x15, 0x18, 0x1C)
INK2 = RGBColor(0x5B, 0x64, 0x72)
INK3 = RGBColor(0x8C, 0x95, 0xA1)
LINE = RGBColor(0xD7, 0xDA, 0xDD)
BG_SOFT = RGBColor(0xF4, 0xF6, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
WARN = RGBColor(0xB4, 0x75, 0x1A)
WARN_BG = RGBColor(0xFF, 0xF6, 0xE6)
DANGER = RGBColor(0xA3, 0x22, 0x19)
DANGER_BG = RGBColor(0xFD, 0xF1, 0xEF)
BLUE = RGBColor(0x2C, 0x4A, 0x6E)
BLUE_BG = RGBColor(0xED, 0xF2, 0xF9)

FONT = '微软雅黑'
SW, SH = 13.333, 7.5
M = 0.72                      # 左右页边距
TITLE_SIZE = 30
BODY_SIZE = 17
SMALL = 13.5


def new_deck():
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill=None, line=None, radius=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    sh.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = 0.08 if radius is None else radius
        except Exception:
            pass
    sh.text_frame.text = ''
    return sh


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    return tb, tf


def style(run, size=BODY_SIZE, bold=False, color=INK, font=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def para(tf, text, size=BODY_SIZE, bold=False, color=INK, first=False,
         space_before=0, space_after=6, align=PP_ALIGN.LEFT, line=1.25):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    p.line_spacing = line
    r = p.add_run(); r.text = text
    style(r, size=size, bold=bold, color=color)
    return p


def title(slide, text, sub=None):
    tb, tf = textbox(slide, M, 0.46, SW - 2 * M, 0.66)
    para(tf, text, size=TITLE_SIZE, bold=True, color=INK, first=True, space_after=0)
    y = 1.16
    if sub:
        tb2, tf2 = textbox(slide, M, y, SW - 2 * M, 0.34)
        para(tf2, sub, size=SMALL, color=INK2, first=True, space_after=0)
        y += 0.42
    return y + 0.16


def footer(slide, page):
    tb, tf = textbox(slide, SW - M - 1.0, SH - 0.55, 1.0, 0.3)
    para(tf, str(page), size=10.5, color=INK3, first=True, align=PP_ALIGN.RIGHT, space_after=0)


def bullets(slide, x, y, w, items, size=BODY_SIZE, gap=0.52, line=1.3, color=INK):
    """items: [(小标题, 说明)] 或 [文本]"""
    cy = y
    for it in items:
        if isinstance(it, tuple):
            head, desc = it
            tb, tf = textbox(slide, x, cy, w, 0.4)
            para(tf, head, size=size, bold=True, color=PRIMARY_D, first=True, space_after=0)
            cy += gap * 0.62
            if desc:
                tb2, tf2 = textbox(slide, x, cy, w, 0.6)
                para(tf2, desc, size=size - 2.5, color=color, first=True, line=line, space_after=0)
                cy += gap
        else:
            tb, tf = textbox(slide, x, cy, w, 0.5)
            para(tf, it, size=size, color=color, first=True, line=line, space_after=0)
            cy += gap
    return cy


def arrow_down(slide, x, y, h=0.3, color=INK3):
    sh = rect(slide, x - 0.055, y, 0.11, h, fill=color, shape=MSO_SHAPE.RECTANGLE)
    sh2 = rect(slide, x - 0.085, y + h - 0.002, 0.17, 0.10, fill=color, shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
    sh2.rotation = 180
    return sh


def arrow_right(slide, x, y, w=0.3, color=INK3):
    rect(slide, x, y - 0.055, w, 0.11, fill=color, shape=MSO_SHAPE.RECTANGLE)
    t = rect(slide, x + w - 0.002, y - 0.085, 0.10, 0.17, fill=color, shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
    t.rotation = 90
    return t


def node(slide, x, y, w, h, text, fill=BG_SOFT, line=LINE, color=INK,
         size=SMALL, bold=False, radius=0.12):
    sh = rect(slide, x, y, w, h, fill=fill, line=line, radius=radius)
    tf = sh.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.06); tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.02); tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, line_txt in enumerate(text.split('\n')):
        para(tf, line_txt, size=size, bold=bold, color=color, first=(i == 0),
             align=PP_ALIGN.CENTER, space_after=0, line=1.1)
    return sh


def table(slide, x, y, w, header, rows, widths=None, size=12.5, header_size=12.5,
          row_h=0.34, center_cols=()):
    n_row = len(rows) + 1
    n_col = len(header)
    shape = slide.shapes.add_table(n_row, n_col, Inches(x), Inches(y), Inches(w), Inches(row_h * n_row))
    tbl = shape.table
    tbl.first_row = True
    if widths:
        total = sum(widths)
        for i, cw in enumerate(widths):
            tbl.columns[i].width = Emu(int(Inches(w) * cw / total))
    for j, htxt in enumerate(header):
        c = tbl.cell(0, j)
        c.text = ''
        c.fill.solid(); c.fill.fore_color.rgb = PRIMARY
        c.margin_left = Inches(0.08); c.margin_right = Inches(0.06)
        c.margin_top = Inches(0.04); c.margin_bottom = Inches(0.04)
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = htxt
        style(r, size=header_size, bold=True, color=WHITE)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = tbl.cell(i + 1, j)
            c.text = ''
            c.fill.solid(); c.fill.fore_color.rgb = WHITE if i % 2 == 0 else BG_SOFT
            c.margin_left = Inches(0.08); c.margin_right = Inches(0.06)
            c.margin_top = Inches(0.03); c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]
            p.line_spacing = 1.05
            p.alignment = PP_ALIGN.CENTER if j in center_cols else PP_ALIGN.LEFT
            r = p.add_run(); r.text = str(val)
            style(r, size=size, bold=False, color=INK)
    return tbl


def picture(slide, path, x, y, w=None, h=None):
    from PIL import Image
    iw, ih = Image.open(path).size
    ar = iw / ih
    if w and not h:
        h = w / ar
    elif h and not w:
        w = h * ar
    return slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
