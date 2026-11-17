# -*- coding: utf-8 -*-
"""把 content.py 里的结构化内容渲染为符合格式要求的 .docx。

格式要求：标题 4 号宋体加粗；正文小 4 号宋体；英文 Times New Roman；行距 1.35 倍。
"""
import os, sys
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
CN = '宋体'
EN = 'Times New Roman'
TITLE_SIZE = 14      # 四号
BODY_SIZE = 12       # 小四
SMALL = 10.5         # 五号
LINE = 1.35


def set_font(run, size=BODY_SIZE, bold=False, cn=CN, en=EN, color=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = en
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), en)
    rFonts.set(qn('w:hAnsi'), en)
    rFonts.set(qn('w:eastAsia'), cn)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def para(doc, text='', size=BODY_SIZE, bold=False, align='left', indent=True,
         space_before=0, space_after=6, line=LINE, cn=CN, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = line
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER,
                   'right': WD_ALIGN_PARAGRAPH.RIGHT, 'just': WD_ALIGN_PARAGRAPH.JUSTIFY}[align]
    if indent and align in ('left', 'just'):
        p.paragraph_format.first_line_indent = Pt(size * 2)
    if text:
        r = p.add_run(text)
        set_font(r, size=size, bold=bold, cn=cn, color=color)
    return p


def add_page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement('w:shd')
    sh.set(qn('w:val'), 'clear')
    sh.set(qn('w:fill'), color)
    tcPr.append(sh)


def set_cell_borders(cell, color='D9D9D9'):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '6')
        el.set(qn('w:color'), color)
        borders.append(el)
    tcPr.append(borders)


def cell_text(cell, text, size=SMALL, bold=False, align='left', color=None):
    cell.text = ''
    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER}[align]
    r = p.add_run(str(text))
    set_font(r, size=size, bold=bold, color=color)
    # 垂直居中
    tcPr = cell._tc.get_or_add_tcPr()
    va = OxmlElement('w:vAlign')
    va.set(qn('w:val'), 'center')
    tcPr.append(va)


def add_table(doc, spec):
    caption = spec.get('caption')
    if caption:
        para(doc, caption, size=SMALL, align='center', indent=False, space_before=8, space_after=4)
    header = spec['header']
    rows = spec['rows']
    widths = spec.get('widths')
    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        cell_text(c, h, bold=True, align='center', color='FFFFFF')
        shade(c, '3E6B63')
        set_cell_borders(c)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            al = 'center' if (spec.get('center_cols') and i in spec['center_cols']) else 'left'
            cell_text(cells[i], v, align=al)
            set_cell_borders(cells[i])
            if ri % 2 == 1:
                shade(cells[i], 'F4F6F5')
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = Cm(w)
    para(doc, '', size=6, indent=False, space_after=2)
    return t


def add_figure(doc, spec):
    path = os.path.join(HERE, spec['path']) if not os.path.isabs(spec['path']) else spec['path']
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(path, width=Cm(spec.get('width', 14.5)))
    para(doc, spec['caption'], size=SMALL, align='center', indent=False, space_after=8)


def add_code(doc, text):
    for line in text.strip('\n').split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Pt(14)
        r = p.add_run(line if line else ' ')
        set_font(r, size=SMALL, cn='等线', en='Consolas')
    para(doc, '', size=6, indent=False, space_after=4)


def add_toc(doc, entries, pages):
    for level, title, num in entries:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.3
        p.paragraph_format.space_after = Pt(2)
        if level == 2:
            p.paragraph_format.left_indent = Pt(18)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(15.0), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = p.add_run(title + '\t' + (str(num) if num else ''))
        set_font(r, size=BODY_SIZE, bold=(level == 1))


def add_ref(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.3
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Pt(22)
    p.paragraph_format.first_line_indent = Pt(-22)
    r = p.add_run(text)
    set_font(r, size=SMALL)


def render(doc, blocks):
    # 预处理：位于 h1 之前的显式分页符只保留第一处（封面 → 摘要），
    # 其余改为 h1 的「段前分页」属性。两者叠加会产生空白页。
    kept = False
    cleaned = []
    for i, item in enumerate(blocks):
        if item[0] == 'pagebreak':
            nxt = blocks[i + 1][0] if i + 1 < len(blocks) else None
            if nxt == 'h1':
                if kept:
                    continue
                kept = True
        cleaned.append(item)
    blocks = cleaned

    import json
    pages = {}
    pj = os.path.join(HERE, 'toc_pages.json')
    if os.path.exists(pj):
        pages = json.load(open(pj, encoding='utf-8'))
    toc_entries = []
    for item in blocks:
        if item[0] not in ('h1', 'h2'):
            continue
        title = item[1]
        if title.replace(' ', '').replace('\u3000', '') == '目录':
            continue          # 目录不列自身
        toc_entries.append((1 if item[0] == 'h1' else 2, title, pages.get(title)))
    h1_count = 0
    for item in blocks:
        kind = item[0]
        payload = item[1] if len(item) > 1 else None
        if kind == 'h1':
            h1p = para(doc, payload, size=TITLE_SIZE, bold=True, align='center',
                       indent=False, space_before=16, space_after=12)
            if h1_count > 0:
                h1p.paragraph_format.page_break_before = True
            h1_count += 1
        elif kind == 'h2':
            para(doc, payload, size=TITLE_SIZE, bold=True, align='left',
                 indent=False, space_before=12, space_after=8)
        elif kind == 'h3':
            para(doc, payload, size=BODY_SIZE, bold=True, align='left',
                 indent=False, space_before=8, space_after=6)
        elif kind == 'p':
            para(doc, payload, align='just')
        elif kind == 'lead':
            para(doc, payload, bold=True, align='just', space_before=6)
        elif kind == 'bullets':
            for b in payload:
                p = doc.add_paragraph()
                p.paragraph_format.line_spacing = LINE
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.left_indent = Pt(24)
                p.paragraph_format.first_line_indent = Pt(-12)
                r = p.add_run('· ' + b)
                set_font(r)
        elif kind == 'fig':
            add_figure(doc, payload)
        elif kind == 'table':
            add_table(doc, payload)
        elif kind == 'toc':
            add_toc(doc, toc_entries, pages)
        elif kind == 'ref':
            add_ref(doc, payload)
        elif kind == 'code':
            add_code(doc, payload)
        elif kind == 'pagebreak':
            add_page_break(doc)
        elif kind == 'center':
            para(doc, payload, align='center', indent=False, space_after=6)
        elif kind == 'cover-title':
            para(doc, payload, size=22, bold=True, align='center', indent=False,
                 space_before=0, space_after=10, line=1.4)
        elif kind == 'cover-sub':
            para(doc, payload, size=16, bold=True, align='center', indent=False,
                 space_after=24, line=1.4)
        elif kind == 'cover-info':
            k, v = payload
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.6
            p.paragraph_format.space_after = Pt(4)
            r1 = p.add_run(k)
            set_font(r1, size=TITLE_SIZE, bold=False)
            r2 = p.add_run(v)
            set_font(r2, size=TITLE_SIZE, bold=False)
        else:
            raise ValueError('未知块类型: ' + kind)


def setup(doc):
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(3.0)
    sec.right_margin = Cm(3.0)
    style = doc.styles['Normal']
    style.font.name = EN
    style.font.size = Pt(BODY_SIZE)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), CN)
    # 页脚页码
    footer = sec.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld1 = OxmlElement('w:fldChar'); fld1.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = ' PAGE '
    fld2 = OxmlElement('w:fldChar'); fld2.set(qn('w:fldCharType'), 'end')
    run._r.append(fld1); run._r.append(instr); run._r.append(fld2)
    set_font(run, size=SMALL)


def main():
    sys.path.insert(0, HERE)
    import content_v2 as content
    doc = Document()
    setup(doc)
    render(doc, content.blocks())
    out = os.path.join(HERE, content.OUTPUT_NAME)
    doc.save(out)
    print('已生成:', out)


if __name__ == '__main__':
    main()
