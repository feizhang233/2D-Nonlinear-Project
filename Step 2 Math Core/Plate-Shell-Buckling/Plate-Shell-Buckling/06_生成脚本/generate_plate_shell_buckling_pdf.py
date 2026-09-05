from __future__ import annotations

import math
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Plate_Shell_Buckling_完整數學推導與例題_繁中.pdf"

PAGE_W, PAGE_H = A4
MARGIN_L = 18 * mm
MARGIN_R = 16 * mm
MARGIN_T = 18 * mm
MARGIN_B = 17 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2E6F9E")
TEAL = colors.HexColor("#2B8A86")
PALE_BLUE = colors.HexColor("#EEF5FA")
PALE_TEAL = colors.HexColor("#ECF7F5")
PALE_GOLD = colors.HexColor("#FBF5E8")
GOLD = colors.HexColor("#B77A19")
INK = colors.HexColor("#1D2731")
MID = colors.HexColor("#52606D")
LIGHT = colors.HexColor("#D7E0E8")
RED = colors.HexColor("#B44949")


def register_fonts() -> None:
    fonts = {
        "HeitiL": "/System/Library/Fonts/STHeiti Light.ttc",
        "HeitiM": "/System/Library/Fonts/STHeiti Medium.ttc",
        "ArialU": "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "STIXText": "/System/Library/Fonts/Supplemental/STIXTwoText.ttf",
        "STIXItalic": "/System/Library/Fonts/Supplemental/STIXTwoText-Italic.ttf",
    }
    for name, path in fonts.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"缺少必要字型：{path}")
        kwargs = {"subfontIndex": 0} if path.endswith(".ttc") else {}
        pdfmetrics.registerFont(TTFont(name, path, **kwargs))


register_fonts()


class BucklingDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(
            MARGIN_L,
            MARGIN_B,
            CONTENT_W,
            PAGE_H - MARGIN_T - MARGIN_B,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="body",
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=draw_page)])
        self._bookmark_id = 0

    def beforeDocument(self):
        self._bookmark_id = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {
            "Heading1Custom",
            "Heading2Custom",
            "Heading3Custom",
        }:
            level = {
                "Heading1Custom": 0,
                "Heading2Custom": 1,
                "Heading3Custom": 2,
            }[flowable.style.name]
            text = flowable.getPlainText()
            self._bookmark_id += 1
            key = f"bk_{self._bookmark_id}"
            self.canv.bookmarkPage(key)
            try:
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
            except Exception:
                pass
            self.notify("TOCEntry", (level, text, self.page, key))


def draw_page(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    if page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#79C5D2"))
        canvas.rect(0, PAGE_H - 11 * mm, PAGE_W, 11 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("HeitiL", 8.5)
        canvas.drawCentredString(PAGE_W / 2, 10 * mm, "依工作區書籍整理 · 繁體中文技術講義")
        canvas.restoreState()
        return

    canvas.setStrokeColor(LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, PAGE_H - 11.5 * mm, PAGE_W - MARGIN_R, PAGE_H - 11.5 * mm)
    canvas.line(MARGIN_L, 12 * mm, PAGE_W - MARGIN_R, 12 * mm)

    canvas.setFont("HeitiL", 7.8)
    canvas.setFillColor(MID)
    canvas.drawString(MARGIN_L, PAGE_H - 8.5 * mm, "Plate / Shell Buckling：完整數學推導與例題")
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 8.5 * mm, "線性分岔 · 能量法 · 有限元素")
    canvas.drawString(MARGIN_L, 8 * mm, "Timoshenko-Gere · Koiter · de Borst 等")
    canvas.drawRightString(PAGE_W - MARGIN_R, 8 * mm, f"第 {page} 頁")
    canvas.restoreState()


styles = getSampleStyleSheet()
BODY = ParagraphStyle(
    "BodyCustom",
    parent=styles["BodyText"],
    fontName="HeitiL",
    fontSize=9.7,
    leading=15.3,
    textColor=INK,
    alignment=TA_JUSTIFY,
    spaceAfter=5.5,
    wordWrap="CJK",
)
BODY_INDENT = ParagraphStyle(
    "BodyIndent",
    parent=BODY,
    leftIndent=5 * mm,
    rightIndent=2 * mm,
    borderColor=LIGHT,
    borderWidth=0,
    borderPadding=(0, 0, 0, 0),
)
SMALL = ParagraphStyle(
    "SmallCustom",
    parent=BODY,
    fontSize=8.2,
    leading=12.5,
    textColor=MID,
)
CAPTION = ParagraphStyle(
    "CaptionCustom",
    parent=SMALL,
    alignment=TA_CENTER,
    spaceBefore=2,
    spaceAfter=8,
)
H1 = ParagraphStyle(
    "Heading1Custom",
    parent=styles["Heading1"],
    fontName="HeitiM",
    fontSize=18,
    leading=23,
    textColor=NAVY,
    spaceBefore=8,
    spaceAfter=10,
    keepWithNext=True,
    wordWrap="CJK",
)
H2 = ParagraphStyle(
    "Heading2Custom",
    parent=styles["Heading2"],
    fontName="HeitiM",
    fontSize=13,
    leading=18,
    textColor=BLUE,
    spaceBefore=10,
    spaceAfter=6,
    keepWithNext=True,
    wordWrap="CJK",
)
H3 = ParagraphStyle(
    "Heading3Custom",
    parent=styles["Heading3"],
    fontName="HeitiM",
    fontSize=10.5,
    leading=15,
    textColor=TEAL,
    spaceBefore=7,
    spaceAfter=4,
    keepWithNext=True,
    wordWrap="CJK",
)
EQ_STYLE = ParagraphStyle(
    "EquationCustom",
    fontName="ArialU",
    fontSize=9.8,
    leading=15,
    textColor=INK,
    alignment=TA_CENTER,
    wordWrap="CJK",
)
EQ_NO_STYLE = ParagraphStyle(
    "EquationNo",
    fontName="STIXText",
    fontSize=8.3,
    leading=12,
    textColor=MID,
    alignment=TA_RIGHT,
)
TABLE_HEAD = ParagraphStyle(
    "TableHead",
    fontName="HeitiM",
    fontSize=8.4,
    leading=11,
    textColor=colors.white,
    alignment=TA_CENTER,
    wordWrap="CJK",
)
TABLE_CELL = ParagraphStyle(
    "TableCell",
    fontName="HeitiL",
    fontSize=8.1,
    leading=11.5,
    textColor=INK,
    alignment=TA_LEFT,
    wordWrap="CJK",
)
CALLOUT = ParagraphStyle(
    "Callout",
    parent=BODY,
    fontSize=9.2,
    leading=14.2,
    leftIndent=5 * mm,
    rightIndent=5 * mm,
    borderPadding=7,
    borderColor=colors.HexColor("#9FC7D9"),
    borderWidth=0.8,
    borderRadius=3,
    backColor=PALE_BLUE,
)
WARNING = ParagraphStyle(
    "Warning",
    parent=CALLOUT,
    borderColor=colors.HexColor("#D6B36A"),
    backColor=PALE_GOLD,
)
SOURCE = ParagraphStyle(
    "Source",
    parent=SMALL,
    fontSize=7.8,
    leading=11.5,
    leftIndent=4 * mm,
    rightIndent=4 * mm,
    borderPadding=6,
    borderColor=colors.HexColor("#B9D8D3"),
    borderWidth=0.6,
    borderRadius=3,
    backColor=PALE_TEAL,
)
BULLET = ParagraphStyle(
    "BulletCustom",
    parent=BODY,
    leftIndent=5.5 * mm,
    firstLineIndent=-3.5 * mm,
    bulletIndent=0,
    spaceAfter=3.5,
)


def P(text: str, style=BODY):
    return Paragraph(text, style)


def bullet(text: str):
    return Paragraph(f"• {text}", BULLET)


def eq(text: str, label: str):
    table = Table(
        [[Paragraph(text, EQ_STYLE), Paragraph(label, EQ_NO_STYLE)]],
        colWidths=[CONTENT_W - 21 * mm, 15 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FA")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD6DF")),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return [Spacer(1, 2.5), table, Spacer(1, 5.5)]


def source(text: str):
    return [Spacer(1, 2), Paragraph(f"<b>原書對照：</b>{text}", SOURCE), Spacer(1, 4)]


def make_table(headers, rows, widths=None, aligns=None):
    data = [[Paragraph(str(h), TABLE_HEAD) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(cell), TABLE_CELL) for cell in row])
    if widths is None:
        widths = [CONTENT_W / len(headers)] * len(headers)
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.45, LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F7F9FB")))
    if aligns:
        for col, align in enumerate(aligns):
            commands.append(("ALIGN", (col, 1), (col, -1), align))
    table.setStyle(TableStyle(commands))
    return table


class PlateSchematic(Flowable):
    def __init__(self, width=CONTENT_W, height=58 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.saveState()
        x0, y0 = 40 * mm, 12 * mm
        w, h = 110 * mm, 34 * mm
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.2)
        c.setFillColor(colors.HexColor("#F0F6FA"))
        c.rect(x0, y0, w, h, fill=1, stroke=1)

        c.setStrokeColor(BLUE)
        c.setLineWidth(1)
        for j in range(6):
            yy = y0 + 4 * mm + j * 5 * mm
            c.line(x0 - 14 * mm, yy, x0, yy)
            c.line(x0 + w + 14 * mm, yy, x0 + w, yy)
            c.setFillColor(BLUE)
            c.wedge(x0 - 1.8 * mm, yy - 1.6 * mm, x0 + 1.8 * mm, yy + 1.6 * mm, 160, 40, fill=1)
            c.wedge(x0 + w - 1.8 * mm, yy - 1.6 * mm, x0 + w + 1.8 * mm, yy + 1.6 * mm, -20, 40, fill=1)

        c.setStrokeColor(TEAL)
        c.setLineWidth(0.9)
        c.line(x0, y0 - 7 * mm, x0 + w, y0 - 7 * mm)
        c.line(x0, y0 - 9 * mm, x0, y0 - 5 * mm)
        c.line(x0 + w, y0 - 9 * mm, x0 + w, y0 - 5 * mm)
        c.setFillColor(TEAL)
        c.setFont("STIXItalic", 9)
        c.drawCentredString(x0 + w / 2, y0 - 11 * mm, "a")
        c.line(x0 + w + 8 * mm, y0, x0 + w + 8 * mm, y0 + h)
        c.line(x0 + w + 6 * mm, y0, x0 + w + 10 * mm, y0)
        c.line(x0 + w + 6 * mm, y0 + h, x0 + w + 10 * mm, y0 + h)
        c.drawString(x0 + w + 11 * mm, y0 + h / 2 - 2, "b")

        c.setStrokeColor(INK)
        c.line(x0 + 10 * mm, y0 + 6 * mm, x0 + 25 * mm, y0 + 6 * mm)
        c.line(x0 + 10 * mm, y0 + 6 * mm, x0 + 10 * mm, y0 + 20 * mm)
        c.setFillColor(INK)
        c.setFont("STIXItalic", 8)
        c.drawString(x0 + 26 * mm, y0 + 4.5 * mm, "x")
        c.drawString(x0 + 7.5 * mm, y0 + 21 * mm, "y")
        c.setFont("HeitiL", 8)
        c.drawCentredString(x0 - 9 * mm, y0 + h + 3 * mm, "壓縮")
        c.drawCentredString(x0 + w + 9 * mm, y0 + h + 3 * mm, "壓縮")
        c.restoreState()


class CylinderSchematic(Flowable):
    def __init__(self, width=CONTENT_W, height=60 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.saveState()
        x0, y0 = 35 * mm, 13 * mm
        length, radius = 105 * mm, 16 * mm
        c.setFillColor(colors.HexColor("#EFF7F6"))
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.1)
        c.rect(x0, y0, length, 2 * radius, fill=1, stroke=0)
        c.ellipse(x0 - 5 * mm, y0, x0 + 5 * mm, y0 + 2 * radius, fill=1, stroke=1)
        c.ellipse(x0 + length - 5 * mm, y0, x0 + length + 5 * mm, y0 + 2 * radius, fill=1, stroke=1)
        c.line(x0, y0, x0 + length, y0)
        c.line(x0, y0 + 2 * radius, x0 + length, y0 + 2 * radius)

        c.setStrokeColor(BLUE)
        c.setLineWidth(1)
        for yy in [y0 + 5 * mm, y0 + radius, y0 + 2 * radius - 5 * mm]:
            c.line(x0 - 17 * mm, yy, x0 - 5 * mm, yy)
            c.line(x0 + length + 17 * mm, yy, x0 + length + 5 * mm, yy)
            c.setFillColor(BLUE)
            c.wedge(x0 - 7 * mm, yy - 1.5 * mm, x0 - 3 * mm, yy + 1.5 * mm, 160, 40, fill=1)
            c.wedge(x0 + length + 3 * mm, yy - 1.5 * mm, x0 + length + 7 * mm, yy + 1.5 * mm, -20, 40, fill=1)

        c.setStrokeColor(TEAL)
        c.line(x0, y0 - 7 * mm, x0 + length, y0 - 7 * mm)
        c.line(x0, y0 - 9 * mm, x0, y0 - 5 * mm)
        c.line(x0 + length, y0 - 9 * mm, x0 + length, y0 - 5 * mm)
        c.setFillColor(TEAL)
        c.setFont("STIXItalic", 9)
        c.drawCentredString(x0 + length / 2, y0 - 11 * mm, "L")
        c.line(x0 + length / 2, y0 + radius, x0 + length / 2, y0 + 2 * radius)
        c.drawString(x0 + length / 2 + 2 * mm, y0 + 1.5 * radius, "R")
        c.setFont("HeitiL", 8)
        c.setFillColor(INK)
        c.drawString(x0 + length / 2 - 8 * mm, y0 + 2 * radius + 4 * mm, "圓周座標 y = Rθ")
        c.drawString(x0 + 38 * mm, y0 + 5 * mm, "軸向 x")
        c.restoreState()


def add_story() -> list:
    story = []

    # Cover
    story.append(Spacer(1, 34 * mm))
    cover_title = ParagraphStyle(
        "CoverTitle",
        fontName="HeitiM",
        fontSize=27,
        leading=36,
        textColor=colors.white,
        alignment=TA_CENTER,
        wordWrap="CJK",
    )
    cover_sub = ParagraphStyle(
        "CoverSub",
        fontName="HeitiL",
        fontSize=13,
        leading=21,
        textColor=colors.HexColor("#CFE8EE"),
        alignment=TA_CENTER,
        wordWrap="CJK",
    )
    cover_note = ParagraphStyle(
        "CoverNote",
        fontName="HeitiL",
        fontSize=9.2,
        leading=15,
        textColor=colors.HexColor("#E7F2F5"),
        alignment=TA_CENTER,
        leftIndent=18 * mm,
        rightIndent=18 * mm,
        wordWrap="CJK",
    )
    story.append(P("Plate / Shell Buckling", cover_title))
    story.append(Spacer(1, 5 * mm))
    story.append(P("板與殼之線性屈曲：完整數學邏輯推導", cover_title))
    story.append(Spacer(1, 7 * mm))
    story.append(P("從三維運動學、二次變分、強式方程與解析模態<br/>一路推導至有限元素廣義特徵值問題", cover_sub))
    story.append(Spacer(1, 20 * mm))
    story.append(P("包含：單向／雙向壓縮薄板、純剪切板、軸壓圓柱殼、外壓球殼、幾何剛度與數值例題", cover_note))
    story.append(Spacer(1, 26 * mm))
    story.append(P("語言：繁體中文　｜　單位系統：N、mm、MPa", cover_note))
    story.append(Spacer(1, 4 * mm))
    story.append(P("編製日期：2026-07-30", cover_note))
    story.append(PageBreak())

    # Purpose and contents
    story.append(P("使用說明與推導範圍", H1))
    story.append(
        P(
            "本講義不是只列出臨界應力公式，而是把公式背後的邏輯鏈完整展開："
            "先由 Kirchhoff-Love 運動學得到 von Kármán 中面應變；再由厚度積分得到彎曲能；"
            "把預應力的二階作功寫成幾何勢能；對總勢能取一階變分得到屈曲微分方程；"
            "最後將同一個二次變分離散為有限元素的材料剛度與幾何剛度矩陣。"
        )
    )
    story.append(
        P(
            "<b>核心假設：</b>材料線彈性、薄板／薄殼、小應變、中等轉角、死載重、理想幾何、"
            "屈曲前狀態可視為線性，且求解的是第一個分岔點。若結構含初始缺陷、塑性、接觸、"
            "跟隨力或顯著屈曲前彎曲，線性特徵值只可作為理想上限與模態指引。",
            WARNING,
        )
    )
    story.extend(
        source(
            "[B06 | Ch. 9 | PDF p.268-333] 薄板屈曲；[B06 | Ch. 11 | PDF p.347-406] 殼屈曲；"
            "[B07 | §3.12 | PDF p.147-167] 平面內受載板；[B07 | §3.17 | PDF p.211-230] 圓柱殼；"
            "[B04 | §3.5 | PDF p.119-121] 線性屈曲有限元素；[B04 | §4.4 | PDF p.147-152] 穩定與唯一性。"
        )
    )
    story.append(P("符號與正負號約定", H2))
    story.append(
        make_table(
            ["符號", "定義", "量綱／正號"],
            [
                ["a, b, h", "矩形板 x、y 方向邊長與厚度", "mm"],
                ["L, R, h", "圓柱殼長度、半徑與厚度", "mm"],
                ["E, ν", "楊氏模數與泊松比", "MPa；無因次"],
                ["D", "等向性薄板／薄殼彎曲剛度", "N·mm"],
                ["N<sub>x</sub>, N<sub>y</sub>", "中面膜力合力，本文以壓縮為正", "N/mm"],
                ["N<sub>xy</sub>", "面內剪力合力；正負決定斜向模態", "N/mm"],
                ["w(x,y)", "中面法向位移；板取 +z，殼取向外為正", "mm"],
                ["λ, φ", "載重倍率與屈曲特徵向量", "無因次；任意正規化"],
            ],
            widths=[28 * mm, 96 * mm, CONTENT_W - 124 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(P("目錄", H2))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOC1",
            fontName="HeitiM",
            fontSize=9.5,
            leading=15,
            leftIndent=0,
            firstLineIndent=0,
            textColor=NAVY,
        ),
        ParagraphStyle(
            "TOC2",
            fontName="HeitiL",
            fontSize=8.7,
            leading=14,
            leftIndent=10 * mm,
            firstLineIndent=0,
            textColor=INK,
        ),
        ParagraphStyle(
            "TOC3",
            fontName="HeitiL",
            fontSize=8.1,
            leading=13,
            leftIndent=20 * mm,
            firstLineIndent=0,
            textColor=MID,
        ),
    ]
    story.append(toc)
    story.append(PageBreak())

    # Section 1
    story.append(P("1. 穩定、分岔與二次變分", H1))
    story.append(P("1.1 平衡不等於穩定", H2))
    story.append(
        P(
            "令結構自由度為 <font name='ArialU'>q</font>，死載重倍率為 "
            "<font name='ArialU'>λ</font>，總勢能為 "
            "<font name='ArialU'>Π(q,λ)=U(q)−λ f̄<super>T</super>q</font>。"
            "平衡只要求任意可容許變分下的一階變分為零。"
        )
    )
    story.extend(eq("δΠ(q,λ)=0", "(1-1)"))
    story.append(
        P(
            "在平衡點附近令擾動為 <font name='ArialU'>q+εφ</font>。對 "
            "<font name='ArialU'>ε</font> 作 Taylor 展開："
        )
    )
    story.extend(
        eq(
            "Π(q+εφ,λ)=Π(q,λ)+ε δΠ[q;φ]+(ε<super>2</super>/2) δ<super>2</super>Π[q;φ,φ]+O(ε<super>3</super>)",
            "(1-2)",
        )
    )
    story.append(
        P(
            "因平衡使第一階項消失，擾動後能量的第一個非零判別項通常是二次變分。"
            "若所有非零可容許 <font name='ArialU'>φ</font> 都使二次變分為正，則原平衡為穩定；"
            "若存在某一方向使其為負，則不穩定；臨界中性狀態則至少有一個非零方向使其為零。"
        )
    )
    story.extend(
        eq(
            "穩定：δ<super>2</super>Π[φ,φ]&gt;0　；　中性：δ<super>2</super>Π[φ,φ]=0　；　不穩定：存在 φ 使 δ<super>2</super>Π[φ,φ]&lt;0",
            "(1-3)",
        )
    )
    story.append(P("1.2 為何會出現特徵值", H2))
    story.append(
        P(
            "當預應力與外載倍率成正比時，二次變分可拆成不含載重倍率的彈性部分與乘上 "
            "<font name='ArialU'>λ</font> 的初應力部分。以壓縮造成負幾何剛度的慣例表示："
        )
    )
    story.extend(eq("δ<super>2</super>Π = φ<super>T</super>(K<sub>M</sub>+λK<sub>G,ref</sub>)φ", "(1-4)"))
    story.append(
        P(
            "中性狀態不只要求某個二次型為零；其對任意測試方向的雙線性形式都必須為零，"
            "因此得到齊次方程。非零解存在的必要條件是係數矩陣奇異。"
        )
    )
    story.extend(eq("(K<sub>M</sub>+λK<sub>G,ref</sub>)φ=0", "(1-5)"))
    story.extend(eq("det(K<sub>M</sub>+λK<sub>G,ref</sub>)=0", "(1-6)"))
    story.append(
        P(
            "這就是線性屈曲的廣義特徵值問題。第一個正特徵值是沿指定參考載重路徑首先可能發生"
            "分岔的倍率；它不是帶缺陷、材料非線性結構的保證破壞載重。"
        )
    )
    story.extend(source("[B04 | §3.5 | PDF p.119-121] 由兩個增量解相減得到齊次式；[B04 | §4.4 | PDF p.147-152] 由切線剛度正定性說明穩定、極限點與分岔。"))

    # Section 2
    story.append(P("2. 薄板屈曲方程：由運動學到強式", H1))
    story.append(P("2.1 Kirchhoff-Love 位移場", H2))
    story.append(
        P(
            "取板中面為 <font name='ArialU'>z=0</font>。Kirchhoff-Love 假設法線變形後仍保持直且垂直於中面，"
            "並忽略厚度伸長。因此任一厚度座標 <font name='ArialU'>z</font> 的位移為："
        )
    )
    story.extend(eq("u(x,y,z)=u<sub>0</sub>(x,y)−z w<sub>,x</sub>", "(2-1a)"))
    story.extend(eq("v(x,y,z)=v<sub>0</sub>(x,y)−z w<sub>,y</sub>", "(2-1b)"))
    story.extend(eq("w(x,y,z)=w(x,y)", "(2-1c)"))
    story.append(P("2.2 von Kármán 中等轉角應變，逐項保留", H2))
    story.append(
        P(
            "以 <font name='ArialU'>x</font> 向 Green-Lagrange 正應變為例，精確形式中的主項可寫成"
            "<font name='ArialU'>ε<sub>x</sub>=u<sub>,x</sub>+(u<sub>,x</sub><super>2</super>+v<sub>,x</sub><super>2</super>+w<sub>,x</sub><super>2</super>)/2</font>。"
            "令中面內應變為 <font name='ArialU'>O(ε)</font>，轉角為 <font name='ArialU'>O(√ε)</font>。"
            "則面內位移梯度平方為 <font name='ArialU'>O(ε<super>2</super>)</font> 可刪除，"
            "但 <font name='ArialU'>w<sub>,x</sub><super>2</super>/2</font> 是 <font name='ArialU'>O(ε)</font> 必須保留。"
        )
    )
    story.extend(eq("ε<sub>x</sub>=u<sub>0,x</sub>+(1/2)w<sub>,x</sub><super>2</super>−z w<sub>,xx</sub>", "(2-2a)"))
    story.extend(eq("ε<sub>y</sub>=v<sub>0,y</sub>+(1/2)w<sub>,y</sub><super>2</super>−z w<sub>,yy</sub>", "(2-2b)"))
    story.extend(
        eq(
            "γ<sub>xy</sub>=u<sub>0,y</sub>+v<sub>0,x</sub>+w<sub>,x</sub>w<sub>,y</sub>−2z w<sub>,xy</sub>",
            "(2-2c)",
        )
    )
    story.append(
        P(
            "把與 <font name='ArialU'>z</font> 無關部分稱為膜應變，把乘上 "
            "<font name='ArialU'>z</font> 的部分稱為曲率。採工程剪應變向量："
        )
    )
    story.extend(
        eq(
            "{ε}={ε<super>0</super>}+z{κ}，　{κ}={−w<sub>,xx</sub>, −w<sub>,yy</sub>, −2w<sub>,xy</sub>}<super>T</super>",
            "(2-3)",
        )
    )
    story.extend(source("[B07 | §3.12 | PDF p.147-149] 原書由板的非線性應變張量與厚度積分建立能量泛函。"))
    story.append(P("2.3 厚度積分與彎曲剛度", H2))
    story.append(
        P(
            "等向性平面應力本構矩陣為："
        )
    )
    story.extend(
        eq(
            "{σ}=Q{ε}，　Q=[E/(1−ν<super>2</super>)] [[1,ν,0],[ν,1,0],[0,0,(1−ν)/2]]",
            "(2-4)",
        )
    )
    story.append(
        P(
            "單位中面面積的彎曲應變能，先在厚度方向積分。由於 "
            "<font name='ArialU'>∫<sub>−h/2</sub><super>h/2</super> z<super>2</super>dz=h<super>3</super>/12</font>："
        )
    )
    story.extend(
        eq(
            "U<sub>b</sub>=(1/2)∫<sub>A</sub>∫<sub>−h/2</sub><super>h/2</super> (zκ)<super>T</super>Q(zκ) dz dA",
            "(2-5)",
        )
    )
    story.extend(
        eq(
            "D=E h<super>3</super>/[12(1−ν<super>2</super>)]",
            "(2-6)",
        )
    )
    story.extend(
        eq(
            "U<sub>b</sub>=(D/2)∫<sub>A</sub>[w<sub>,xx</sub><super>2</super>+w<sub>,yy</sub><super>2</super>+2νw<sub>,xx</sub>w<sub>,yy</sub>+2(1−ν)w<sub>,xy</sub><super>2</super>]dA",
            "(2-7)",
        )
    )
    story.append(P("2.4 預應力的二階作功", H2))
    story.append(
        P(
            "板受面內壓縮後若產生小側向斜率，弧長增量的二階項為 "
            "<font name='ArialU'>(dw/dx)<super>2</super>/2</font>。死壓縮力沿斜率造成的端縮短作正功，"
            "所以在總勢能中以負號出現。對一般中面力張量，幾何勢能為："
        )
    )
    story.extend(
        eq(
            "Π<sub>g</sub>=−(1/2)∫<sub>A</sub>[N<sub>x</sub>w<sub>,x</sub><super>2</super>+N<sub>y</sub>w<sub>,y</sub><super>2</super>+2N<sub>xy</sub>w<sub>,x</sub>w<sub>,y</sub>]dA",
            "(2-8)",
        )
    )
    story.append(P("2.5 變分、分部積分與控制方程", H2))
    story.append(
        P(
            "先對彎曲能取變分。把每一項寫開，不先省略混合導數："
        )
    )
    story.extend(
        eq(
            "δU<sub>b</sub>=D∫<sub>A</sub>[w<sub>,xx</sub>δw<sub>,xx</sub>+w<sub>,yy</sub>δw<sub>,yy</sub>+νw<sub>,yy</sub>δw<sub>,xx</sub>+νw<sub>,xx</sub>δw<sub>,yy</sub>+2(1−ν)w<sub>,xy</sub>δw<sub>,xy</sub>]dA",
            "(2-9)",
        )
    )
    story.append(
        P(
            "各項對 <font name='ArialU'>x</font>、<font name='ArialU'>y</font> 分部積分兩次。"
            "內域係數依序為 <font name='ArialU'>w<sub>,xxxx</sub></font>、"
            "<font name='ArialU'>w<sub>,yyyy</sub></font>、"
            "<font name='ArialU'>2νw<sub>,xxyy</sub></font> 與 "
            "<font name='ArialU'>2(1−ν)w<sub>,xxyy</sub></font>。混合項相加後泊松比消去："
        )
    )
    story.extend(
        eq(
            "δU<sub>b</sub>|<sub>內域</sub>=D∫<sub>A</sub>[w<sub>,xxxx</sub>+2w<sub>,xxyy</sub>+w<sub>,yyyy</sub>]δw dA=D∫<sub>A</sub>∇<super>4</super>w δw dA",
            "(2-10)",
        )
    )
    story.append(
        P(
            "再對幾何勢能取變分。以常值中面力為例，一次分部積分後："
        )
    )
    story.extend(
        eq(
            "δΠ<sub>g</sub>|<sub>內域</sub>=∫<sub>A</sub>[N<sub>x</sub>w<sub>,xx</sub>+2N<sub>xy</sub>w<sub>,xy</sub>+N<sub>y</sub>w<sub>,yy</sub>]δw dA",
            "(2-11)",
        )
    )
    story.append(
        P(
            "令任意內域 <font name='ArialU'>δw</font> 的係數為零，即得壓縮為正號約定下的薄板線性屈曲方程："
        )
    )
    story.extend(
        eq(
            "D∇<super>4</super>w+N<sub>x</sub>w<sub>,xx</sub>+2N<sub>xy</sub>w<sub>,xy</sub>+N<sub>y</sub>w<sub>,yy</sub>=0",
            "(2-12)",
        )
    )
    story.append(
        P(
            "在直線簡支邊，運動邊界條件是 <font name='ArialU'>w=0</font>，自然邊界條件是法向彎矩 "
            "<font name='ArialU'>M<sub>n</sub>=0</font>。例如在 <font name='ArialU'>x=0,a</font>："
        )
    )
    story.extend(eq("w=0，　M<sub>x</sub>=−D(w<sub>,xx</sub>+νw<sub>,yy</sub>)=0", "(2-13)"))
    story.append(
        P(
            "因為 <font name='ArialU'>w</font> 沿該邊恆為零，沿邊切向微分給 "
            "<font name='ArialU'>w<sub>,yy</sub>=0</font>，故簡化為 "
            "<font name='ArialU'>w=w<sub>,xx</sub>=0</font>。同理，"
            "<font name='ArialU'>y=0,b</font> 上有 <font name='ArialU'>w=w<sub>,yy</sub>=0</font>。"
        )
    )

    # Section 3
    story.append(PageBreak())
    story.append(P("3. 四邊簡支矩形板的解析屈曲", H1))
    story.append(PlateSchematic())
    story.append(P("圖 3-1　單向均勻壓縮之四邊簡支矩形板，壓縮膜力 N<sub>x</sub> 為每單位邊長的合力。", CAPTION))
    story.append(P("3.1 Navier 模態與單向壓縮", H2))
    story.append(
        P(
            "令 <font name='ArialU'>N<sub>x</sub>=N&gt;0</font>，"
            "<font name='ArialU'>N<sub>y</sub>=N<sub>xy</sub>=0</font>。"
            "同時滿足四邊簡支條件的單一雙正弦模態為："
        )
    )
    story.extend(eq("w=W sin(mπx/a) sin(nπy/b)，　m,n=1,2,3,…", "(3-1)"))
    story.append(
        P(
            "定義 <font name='ArialU'>α=mπ/a</font>、<font name='ArialU'>β=nπ/b</font>。逐項微分："
        )
    )
    story.extend(eq("w<sub>,xx</sub>=−α<super>2</super>w，　w<sub>,yy</sub>=−β<super>2</super>w", "(3-2)"))
    story.extend(
        eq(
            "w<sub>,xxxx</sub>=α<super>4</super>w，　w<sub>,xxyy</sub>=α<super>2</super>β<super>2</super>w，　w<sub>,yyyy</sub>=β<super>4</super>w",
            "(3-3)",
        )
    )
    story.extend(eq("∇<super>4</super>w=(α<super>2</super>+β<super>2</super>)<super>2</super>w", "(3-4)"))
    story.append(P("代入控制方程 (2-12)："))
    story.extend(
        eq(
            "[D(α<super>2</super>+β<super>2</super>)<super>2</super>−Nα<super>2</super>]W sin(αx)sin(βy)=0",
            "(3-5)",
        )
    )
    story.append(
        P(
            "非平凡解要求 <font name='ArialU'>W≠0</font>，且正弦函數不在整個區域恆為零，因此中括號必須為零："
        )
    )
    story.extend(
        eq(
            "N<sub>mn</sub>=D(α<super>2</super>+β<super>2</super>)<super>2</super>/α<super>2</super>",
            "(3-6)",
        )
    )
    story.extend(
        eq(
            "N<sub>mn</sub>=(π<super>2</super>D/b<super>2</super>)[mb/a+n<super>2</super>a/(mb)]<super>2</super>　（一般 n）",
            "(3-7)",
        )
    )
    story.append(
        P(
            "固定 <font name='ArialU'>m</font> 時，<font name='ArialU'>n</font> 越大，"
            "<font name='ArialU'>β</font> 越大而臨界力單調增加，所以第一屈曲模態必有 "
            "<font name='ArialU'>n=1</font>。於是："
        )
    )
    story.extend(
        eq(
            "N<sub>m</sub>=k<sub>m</sub>π<super>2</super>D/b<super>2</super>，　k<sub>m</sub>=[mb/a+a/(mb)]<super>2</super>",
            "(3-8)",
        )
    )
    story.extend(
        eq(
            "σ<sub>cr</sub>=N<sub>cr</sub>/h=kπ<super>2</super>E/[12(1−ν<super>2</super>)]·(h/b)<super>2</super>",
            "(3-9)",
        )
    )
    story.append(P("3.2 以能量法逐項驗證", H2))
    story.append(
        P(
            "同一結果可直接由二次勢能得到。對 (3-1) 積分，利用 "
            "<font name='ArialU'>∫<sub>0</sub><super>a</super>sin<super>2</super>(mπx/a)dx=a/2</font> "
            "與餘弦平方的同一結果："
        )
    )
    story.extend(eq("∫<sub>A</sub>w<super>2</super>dA=abW<super>2</super>/4", "(3-10a)"))
    story.extend(eq("∫<sub>A</sub>w<sub>,x</sub><super>2</super>dA=α<super>2</super>abW<super>2</super>/4", "(3-10b)"))
    story.extend(
        eq(
            "∫<sub>A</sub>{w<sub>,xx</sub><super>2</super>,w<sub>,yy</sub><super>2</super>,w<sub>,xx</sub>w<sub>,yy</sub>,w<sub>,xy</sub><super>2</super>}dA=(abW<super>2</super>/4){α<super>4</super>,β<super>4</super>,α<super>2</super>β<super>2</super>,α<super>2</super>β<super>2</super>}",
            "(3-10c)",
        )
    )
    story.append(
        P(
            "代回 (2-7)，混合項係數為 "
            "<font name='ArialU'>2ν+2(1−ν)=2</font>，所以："
        )
    )
    story.extend(eq("U<sub>b</sub>=(DabW<super>2</super>/8)(α<super>2</super>+β<super>2</super>)<super>2</super>", "(3-11)"))
    story.extend(eq("Π<sub>g</sub>=−NabW<super>2</super>α<super>2</super>/8", "(3-12)"))
    story.extend(
        eq(
            "Π<sub>2</sub>=(abW<super>2</super>/8)[D(α<super>2</super>+β<super>2</super>)<super>2</super>−Nα<super>2</super>]",
            "(3-13)",
        )
    )
    story.append(
        P(
            "中性狀態下，任意無限小非零 <font name='ArialU'>W</font> 的二次係數為零，"
            "立即重得 (3-6)。這也說明解析微分方程法與 Rayleigh 商法是同一個二次變分的兩種表示。"
        )
    )
    story.append(P("3.3 半波數選擇與模態切換", H2))
    story.append(
        P(
            "令長寬比 <font name='ArialU'>r=a/b</font>，則 "
            "<font name='ArialU'>k<sub>m</sub>=(m/r+r/m)<super>2</super></font>。"
            "若暫把 <font name='ArialU'>m</font> 當連續變數，令 "
            "<font name='ArialU'>s=m<super>2</super></font>："
        )
    )
    story.extend(eq("k(s)=s/r<super>2</super>+2+r<super>2</super>/s", "(3-14)"))
    story.extend(eq("dk/ds=1/r<super>2</super>−r<super>2</super>/s<super>2</super>=0", "(3-15)"))
    story.extend(eq("s=r<super>2</super> ⇒ m=r ⇒ k<sub>min,continuous</sub>=4", "(3-16)"))
    story.append(
        P(
            "實際 <font name='ArialU'>m</font> 必須為正整數，所以計算相鄰整數並取最小值。"
            "從 <font name='ArialU'>m</font> 切換到 <font name='ArialU'>m+1</font> 的長寬比由兩個係數相等決定。"
            "因兩邊均為正，可先開平方："
        )
    )
    story.extend(eq("m/r+r/m=(m+1)/r+r/(m+1)", "(3-17)"))
    story.extend(eq("−1/r+r/[m(m+1)]=0", "(3-18)"))
    story.extend(eq("r<super>2</super>=m(m+1) ⇒ a/b=√[m(m+1)]", "(3-19)"))
    story.append(
        make_table(
            ["模態切換", "a/b 臨界值", "物理解讀"],
            [
                ["m=1 → 2", "√2 = 1.414", "板長超過此值後，兩個 x 向半波較有利"],
                ["m=2 → 3", "√6 = 2.449", "再增加一個半波可降低彎曲／幾何能比"],
                ["m=3 → 4", "√12 = 3.464", "長板逐漸被分割為近似方形屈曲胞格"],
            ],
            widths=[34 * mm, 42 * mm, CONTENT_W - 76 * mm],
        )
    )
    story.extend(source("[B06 | §9.2 | PDF p.270-272] 原書以雙正弦級數、能量與半波切換曲線推導相同結果；[B07 | §3.12 | PDF p.152-155] 由控制方程與簡支邊界得到模態式。"))

    story.append(P("3.4 雙向壓縮的互制式", H2))
    story.append(
        P(
            "若 <font name='ArialU'>N<sub>x</sub></font>、<font name='ArialU'>N<sub>y</sub></font> "
            "皆為均勻壓縮，且沒有剪力，將相同模態代入 (2-12)："
        )
    )
    story.extend(
        eq(
            "D(α<super>2</super>+β<super>2</super>)<super>2</super>−N<sub>x</sub>α<super>2</super>−N<sub>y</sub>β<super>2</super>=0",
            "(3-20)",
        )
    )
    story.extend(
        eq(
            "N<sub>x</sub>α<super>2</super>+N<sub>y</sub>β<super>2</super>=D(α<super>2</super>+β<super>2</super>)<super>2</super>",
            "(3-21)",
        )
    )
    story.append(
        P(
            "沿比例載重路徑 <font name='ArialU'>N<sub>y</sub>=ρN<sub>x</sub></font>，每一個 "
            "<font name='ArialU'>(m,n)</font> 模態的臨界值為："
        )
    )
    story.extend(
        eq(
            "N<sub>x,mn</sub>=D(α<super>2</super>+β<super>2</super>)<super>2</super>/(α<super>2</super>+ρβ<super>2</super>)",
            "(3-22)",
        )
    )
    story.append(
        P(
            "必須對所有正整數 <font name='ArialU'>m,n</font> 取最小值。特別地，方板 "
            "<font name='ArialU'>a=b</font> 在等雙向壓縮 "
            "<font name='ArialU'>N<sub>x</sub>=N<sub>y</sub>=N</font> 下，第一模態 "
            "<font name='ArialU'>m=n=1</font>："
        )
    )
    story.extend(eq("N<sub>cr</sub>=2π<super>2</super>D/a<super>2</super>", "(3-23)"))
    story.append(
        P(
            "同一方板在單向壓縮時為 <font name='ArialU'>4π<super>2</super>D/a<super>2</super></font>，"
            "因此等雙向壓縮下每一方向允許的臨界膜力恰為單向值的一半。"
        )
    )

    story.append(P("3.5 純剪切為何必須耦合多個模態", H2))
    story.append(
        P(
            "純剪切時控制方程含 <font name='ArialU'>2N<sub>xy</sub>w<sub>,xy</sub></font>。"
            "單一雙正弦的混合導數是餘弦乘餘弦，並不與原雙正弦成比例；"
            "而且其單模態幾何能積分為零。因此不能用單一項直接求剪切屈曲。"
        )
    )
    story.extend(
        eq(
            "w=Σ<sub>m=1</sub><super>M</super>Σ<sub>n=1</sub><super>M</super>a<sub>mn</sub>φ<sub>mn</sub>，　φ<sub>mn</sub>=sin(mπx/a)sin(nπy/b)",
            "(3-24)",
        )
    )
    story.append(
        P(
            "將展開式代入二次勢能，利用正交性，彎曲矩陣與單向壓縮矩陣為對角矩陣："
        )
    )
    story.extend(
        eq(
            "K<sup>b</sup><sub>mn,mn</sub>=(Dab/4)(α<sub>m</sub><super>2</super>+β<sub>n</sub><super>2</super>)<super>2</super>",
            "(3-25a)",
        )
    )
    story.extend(
        eq(
            "K<sup>x</sup><sub>mn,mn</sub>=(ab/4)α<sub>m</sub><super>2</super>，　K<sup>y</sup><sub>mn,mn</sub>=(ab/4)β<sub>n</sub><super>2</super>",
            "(3-25b)",
        )
    )
    story.append(
        P(
            "剪切耦合矩陣需要兩個交叉積分。先計算一維積分；只有波數奇偶性相反時非零："
        )
    )
    story.extend(
        eq(
            "∫<sub>0</sub><super>a</super>cos(mπx/a)sin(pπx/a)dx=2ap/[π(p<super>2</super>−m<super>2</super>)]",
            "(3-26)",
        )
    )
    story.append(P("上式適用於 <font name='ArialU'>m+p</font> 為奇數；若為偶數，積分為零。組合 x、y 兩向後："))
    story.extend(
        eq(
            "G<sup>xy</sup><sub>mn,pq</sub>=∫<sub>A</sub>(φ<sub>mn,x</sub>φ<sub>pq,y</sub>+φ<sub>mn,y</sub>φ<sub>pq,x</sub>)dA",
            "(3-27)",
        )
    )
    story.extend(
        eq(
            "G<sup>xy</sup><sub>mn,pq</sub>=8mnpq/[(p<super>2</super>−m<super>2</super>)(n<super>2</super>−q<super>2</super>)]",
            "(3-28)",
        )
    )
    story.append(
        P(
            "式 (3-28) 只有 <font name='ArialU'>m,p</font> 與 <font name='ArialU'>n,q</font> "
            "各自奇偶相反時成立，否則為零。最後得到截斷 Galerkin 特徵值問題："
        )
    )
    story.extend(
        eq(
            "[K<sup>b</sup>−N<sub>x</sub>K<sup>x</sup>−N<sub>y</sub>K<sup>y</sup>−N<sub>xy</sub>G<sup>xy</sup>]a=0",
            "(3-29)",
        )
    )
    story.append(
        P(
            "這個矩陣式已完整說明純剪切板的數學機制：剪切不降低單一模態自己的對角剛度，"
            "而是透過奇偶不同的模態耦合，使整體二次型失去正定性。"
        )
    )

    # Section 4 shell
    story.append(PageBreak())
    story.append(P("4. 圓柱殼與球殼的經典線性屈曲", H1))
    story.append(CylinderSchematic())
    story.append(P("圖 4-1　軸向均勻壓縮圓柱殼；x 為軸向，y=Rθ 為展開後的圓周弧長。", CAPTION))
    story.append(P("4.1 圓柱殼的淺殼運動學", H2))
    story.append(
        P(
            "對薄、長、曲率緩變的圓柱殼，Donnell 型淺殼運動學保留周向曲率 "
            "<font name='ArialU'>1/R</font>。法向位移向外為正，則中面膜應變可寫為："
        )
    )
    story.extend(eq("ε<sub>x</sub>=u<sub>,x</sub>+(1/2)w<sub>,x</sub><super>2</super>", "(4-1a)"))
    story.extend(eq("ε<sub>y</sub>=v<sub>,y</sub>+w/R+(1/2)w<sub>,y</sub><super>2</super>", "(4-1b)"))
    story.extend(eq("γ<sub>xy</sub>=u<sub>,y</sub>+v<sub>,x</sub>+w<sub>,x</sub>w<sub>,y</sub>", "(4-1c)"))
    story.append(
        P(
            "彎曲曲率仍近似為 <font name='ArialU'>{−w<sub>,xx</sub>,−w<sub>,yy</sub>,−2w<sub>,xy</sub>}</font>。"
            "與平板相比，唯一決定性的新線性項是周向應變中的 <font name='ArialU'>w/R</font>；"
            "它使徑向位移必然伴隨膜伸縮，也正是殼的曲率剛化來源。"
        )
    )
    story.append(P("4.2 Airy 應力函數與相容方程", H2))
    story.append(
        P(
            "令屈曲擾動所引起的增量膜力為張力正號 "
            "<font name='ArialU'>n<sub>x</sub>,n<sub>y</sub>,n<sub>xy</sub></font>。"
            "引入 Airy 應力函數 <font name='ArialU'>Φ</font>："
        )
    )
    story.extend(
        eq(
            "n<sub>x</sub>=Φ<sub>,yy</sub>，　n<sub>y</sub>=Φ<sub>,xx</sub>，　n<sub>xy</sub>=−Φ<sub>,xy</sub>",
            "(4-2)",
        )
    )
    story.append(
        P(
            "此定義自動滿足無面內體力時的平衡 "
            "<font name='ArialU'>n<sub>x,x</sub>+n<sub>xy,y</sub>=0</font> 與 "
            "<font name='ArialU'>n<sub>xy,x</sub>+n<sub>y,y</sub>=0</font>。"
            "線性平面應力反算式為："
        )
    )
    story.extend(eq("ε<sub>x</sub>=(n<sub>x</sub>−νn<sub>y</sub>)/(Eh)", "(4-3a)"))
    story.extend(eq("ε<sub>y</sub>=(n<sub>y</sub>−νn<sub>x</sub>)/(Eh)", "(4-3b)"))
    story.extend(eq("γ<sub>xy</sub>=2(1+ν)n<sub>xy</sub>/(Eh)", "(4-3c)"))
    story.append(
        P(
            "對 (4-1) 的線性部分取相容組合。位移 <font name='ArialU'>u,v</font> 的交叉導數彼此抵消，只留下曲率項："
        )
    )
    story.extend(
        eq(
            "ε<sub>x,yy</sub>+ε<sub>y,xx</sub>−γ<sub>xy,xy</sub>=w<sub>,xx</sub>/R",
            "(4-4)",
        )
    )
    story.append(
        P(
            "將 (4-2) 與 (4-3) 逐項代入左側："
        )
    )
    story.extend(
        eq(
            "[Φ<sub>,yyyy</sub>−νΦ<sub>,xxyy</sub>+Φ<sub>,xxxx</sub>−νΦ<sub>,xxyy</sub>+2(1+ν)Φ<sub>,xxyy</sub>]/(Eh)=w<sub>,xx</sub>/R",
            "(4-5)",
        )
    )
    story.append(
        P(
            "混合導數係數為 <font name='ArialU'>−ν−ν+2(1+ν)=2</font>，因此："
        )
    )
    story.extend(eq("∇<super>4</super>Φ=(Eh/R)w<sub>,xx</sub>", "(4-6)"))
    story.append(P("4.3 軸壓圓柱殼的兩個線性方程", H2))
    story.append(
        P(
            "令屈曲前軸向壓縮膜力為 <font name='ArialU'>N&gt;0</font>。法向增量平衡包含三項："
            "板彎曲、增量周向膜力因曲率產生的法向恢復力，以及軸向預壓力乘上二階斜率。"
        )
    )
    story.extend(
        eq(
            "D∇<super>4</super>w+(1/R)Φ<sub>,xx</sub>+Nw<sub>,xx</sub>=0",
            "(4-7)",
        )
    )
    story.append(
        P(
            "式 (4-6) 與 (4-7) 形成軸壓圓柱殼的線性屈曲聯立方程。取滿足軸向簡支與圓周週期性的模態："
        )
    )
    story.extend(eq("w=W sin(αx)cos(βy)，　Φ=F sin(αx)cos(βy)", "(4-8)"))
    story.extend(eq("α=mπ/L，　β=n/R，　q<super>2</super>=α<super>2</super>+β<super>2</super>", "(4-9)"))
    story.append(P("先代入相容方程 (4-6)："))
    story.extend(eq("q<super>4</super>F=−(Eh/R)α<super>2</super>W", "(4-10)"))
    story.extend(eq("F=−Ehα<super>2</super>W/(Rq<super>4</super>)", "(4-11)"))
    story.append(P("再計算 <font name='ArialU'>Φ<sub>,xx</sub>=−α<super>2</super>Φ</font>，其振幅為："))
    story.extend(eq("−α<super>2</super>F=Ehα<super>4</super>W/(Rq<super>4</super>)", "(4-12)"))
    story.append(P("代入法向平衡 (4-7)，消去非零振幅 <font name='ArialU'>W</font>："))
    story.extend(
        eq(
            "Dq<super>4</super>+Ehα<super>4</super>/(R<super>2</super>q<super>4</super>)−Nα<super>2</super>=0",
            "(4-13)",
        )
    )
    story.extend(
        eq(
            "N(α,β)=Dq<super>4</super>/α<super>2</super>+Ehα<super>2</super>/(R<super>2</super>q<super>4</super>)",
            "(4-14)",
        )
    )
    story.append(P("4.4 對波數完整最小化", H2))
    story.append(
        P(
            "定義正量 <font name='ArialU'>X=q<super>4</super>/α<super>2</super></font>，則第二項可改寫為 "
            "<font name='ArialU'>Eh/(R<super>2</super>X)</font>："
        )
    )
    story.extend(eq("N(X)=DX+Eh/(R<super>2</super>X)", "(4-15)"))
    story.extend(eq("dN/dX=D−Eh/(R<super>2</super>X<super>2</super>)=0", "(4-16)"))
    story.extend(eq("X<sub>*</sub>=√[Eh/(DR<super>2</super>)]", "(4-17)"))
    story.append(
        P(
            "二階導數 <font name='ArialU'>d<super>2</super>N/dX<super>2</super>=2Eh/(R<super>2</super>X<super>3</super>)&gt;0</font>，"
            "故此駐點確為最小值。代回："
        )
    )
    story.extend(eq("N<sub>cr</sub>=2√(DEh)/R", "(4-18)"))
    story.append(P("再代入 <font name='ArialU'>D=Eh<super>3</super>/[12(1−ν<super>2</super>)]</font>："))
    story.extend(
        eq(
            "N<sub>cr</sub>=Eh<super>2</super>/[R√(3(1−ν<super>2</super>))]",
            "(4-19)",
        )
    )
    story.extend(
        eq(
            "σ<sub>cr</sub>=N<sub>cr</sub>/h=E(h/R)/√[3(1−ν<super>2</super>)]",
            "(4-20)",
        )
    )
    story.append(
        P(
            "最佳波數不唯一，而滿足："
        )
    )
    story.extend(
        eq(
            "(α<super>2</super>+β<super>2</super>)/α=[12(1−ν<super>2</super>)]<super>1/4</super>/√(Rh)",
            "(4-21)",
        )
    )
    story.append(
        P(
            "因此理想 Donnell 理論存在一族近乎等臨界的短波模態。有限長度、端部拘束、較完整殼理論與離散整數 "
            "<font name='ArialU'>m,n</font> 會解除此退化。這也是圓柱殼特徵值常成群接近的重要原因。"
        )
    )
    story.extend(source("[B06 | §11.1-11.4 | PDF p.347-361] 軸壓圓柱殼理論、模態與實驗落差；[B07 | §3.17 | PDF p.211-230] 圓柱殼能量、線性方程、後屈曲與缺陷敏感性。"))

    story.append(P("4.5 外壓完整球殼", H2))
    story.append(
        P(
            "對半徑 <font name='ArialU'>R</font> 的淺球殼，兩個主曲率均為 "
            "<font name='ArialU'>1/R</font>。局部平面波的兩個線性方程可寫為："
        )
    )
    story.extend(eq("D∇<super>4</super>w+(1/R)∇<super>2</super>Φ+N∇<super>2</super>w=0", "(4-22)"))
    story.extend(eq("∇<super>4</super>Φ=(Eh/R)∇<super>2</super>w", "(4-23)"))
    story.append(
        P(
            "取 <font name='ArialU'>w=W exp(i k·x)</font>、"
            "<font name='ArialU'>Φ=F exp(i k·x)</font>，且 "
            "<font name='ArialU'>q=|k|</font>。則 "
            "<font name='ArialU'>∇<super>2</super>→−q<super>2</super></font>、"
            "<font name='ArialU'>∇<super>4</super>→q<super>4</super></font>。"
        )
    )
    story.extend(eq("q<super>4</super>F=−(Eh/R)q<super>2</super>W ⇒ F=−EhW/(Rq<super>2</super>)", "(4-24)"))
    story.extend(eq("Dq<super>4</super>+Eh/R<super>2</super>−Nq<super>2</super>=0", "(4-25)"))
    story.extend(eq("N(q)=Dq<super>2</super>+Eh/(R<super>2</super>q<super>2</super>)", "(4-26)"))
    story.append(
        P(
            "令 <font name='ArialU'>Y=q<super>2</super></font>，最小化過程與 (4-15) 完全相同，所以 "
            "<font name='ArialU'>N<sub>cr</sub>=2√(DEh)/R</font>。完整球殼承受均勻外壓 "
            "<font name='ArialU'>p</font> 時，膜理論給每一主方向壓縮膜力 "
            "<font name='ArialU'>N=pR/2</font>。故："
        )
    )
    story.extend(
        eq(
            "p<sub>cr</sub>=2N<sub>cr</sub>/R=2E(h/R)<super>2</super>/√[3(1−ν<super>2</super>)]",
            "(4-27)",
        )
    )
    story.extend(source("[B06 | §11.13 | PDF p.397-406] 均勻壓縮球殼；[B07 | §3.16 | PDF p.192-210] 一般殼理論下的外壓球殼屈曲。"))

    story.append(P("4.6 為何殼的經典值常嚴重高估", H2))
    story.append(
        P(
            "平板的第一分岔後通常仍能藉由中面拉伸建立正的後屈曲承載力；理想軸壓圓柱殼則可出現負斜率、"
            "不穩定的後屈曲路徑。只要初始幾何含有與臨界模態相近的微小分量，結構便可能在理想特徵值之前"
            "偏離基本路徑並達到極限點。"
        )
    )
    story.append(
        KeepTogether(
            [
                P(
                    "<b>工程解讀：</b>式 (4-20) 與 (4-27) 是完美幾何、線彈性、理想邊界的分岔值。"
                    "它們適合用來驗證元素、網格與單位，也適合決定缺陷形狀；不宜直接當成未折減的設計強度。"
                    "實務必須依適用規範採 knock-down factor，或使用量測／製造公差定義幾何缺陷後做幾何非線性分析。",
                    WARNING,
                )
            ]
        )
    )

    # Section 5 FE
    story.append(P("5. 從連續二次變分到有限元素特徵值", H1))
    story.append(P("5.1 離散平衡與切線剛度", H2))
    story.append(
        P(
            "令節點位移向量為 <font name='ArialU'>d</font>，內力為 "
            "<font name='ArialU'>f<sub>int</sub>(d)</font>，參考外力為 "
            "<font name='ArialU'>f̄</font>。平衡殘差："
        )
    )
    story.extend(eq("r(d,λ)=f<sub>int</sub>(d)−λf̄=0", "(5-1)"))
    story.append(
        P(
            "在屈曲前平衡點 <font name='ArialU'>(d<sub>0</sub>,λ)</font> 加入無限小擾動 "
            "<font name='ArialU'>εδd</font>，對殘差作一階 Taylor 展開："
        )
    )
    story.extend(
        eq(
            "r(d<sub>0</sub>+εδd,λ)=r(d<sub>0</sub>,λ)+ε[∂f<sub>int</sub>/∂d]<sub>d0</sub>δd+O(ε<super>2</super>)",
            "(5-2)",
        )
    )
    story.append(P("第一項因原狀態平衡而為零。若同一載重下存在另一個無限接近的平衡分支，則非零擾動必須滿足："))
    story.extend(eq("K<sub>T</sub>δd=0，　K<sub>T</sub>=∂f<sub>int</sub>/∂d", "(5-3)"))
    story.append(P("5.2 材料剛度與幾何剛度的分解", H2))
    story.append(
        P(
            "在小屈曲前位移梯度、線彈性、比例載重下，切線剛度分為："
        )
    )
    story.extend(eq("K<sub>T</sub>=K<sub>M</sub>+K<sub>σ</sub>(σ<super>0</super>)", "(5-4)"))
    story.append(
        P(
            "其中 <font name='ArialU'>K<sub>M</sub>=∫B<super>T</super>DB dV</font> 是材料／彈性剛度；"
            "<font name='ArialU'>K<sub>σ</sub></font> 是由屈曲前應力產生的初應力剛度。"
            "若應力採張力為正，壓縮應力使相關方向的 <font name='ArialU'>K<sub>σ</sub></font> 為負。"
            "由單位參考載重得到 <font name='ArialU'>σ<super>0</super>=λσ<sup>ref</sup></font>，因此："
        )
    )
    story.extend(eq("[K<sub>M</sub>+λK<sub>σ,ref</sub>]φ=0", "(5-5)"))
    story.append(
        P(
            "有些程式把壓縮削弱項另定義成正矩陣 "
            "<font name='ArialU'>K<sub>G</sub>=−K<sub>σ,ref</sub></font>，便寫成："
        )
    )
    story.extend(eq("K<sub>M</sub>φ=λK<sub>G</sub>φ", "(5-6)"))
    story.append(
        P(
            "兩種寫法完全等價；最常見的錯誤是把求解器的應力正號與理論中『壓縮為正』的 "
            "<font name='ArialU'>N</font> 混用，導致正負特徵值顛倒。"
        )
    )
    story.append(P("5.3 板元素幾何剛度的直接來源", H2))
    story.append(
        P(
            "令橫向位移插值 <font name='ArialU'>w=N<sub>w</sub>d</font>，斜率矩陣為："
        )
    )
    story.extend(
        eq(
            "{w<sub>,x</sub>,w<sub>,y</sub>}<super>T</super>=B<sub>g</sub>d，　B<sub>g</sub>=[[N<sub>1,x</sub>,…,N<sub>n,x</sub>],[N<sub>1,y</sub>,…,N<sub>n,y</sub>]]",
            "(5-7)",
        )
    )
    story.append(
        P(
            "把 (2-8) 寫成矩陣式，令壓縮正號膜力矩陣 "
            "<font name='ArialU'>𝓝=[[N<sub>x</sub>,N<sub>xy</sub>],[N<sub>xy</sub>,N<sub>y</sub>]]</font>："
        )
    )
    story.extend(
        eq(
            "Π<sub>g,e</sub>=−(1/2)d<super>T</super>[∫<sub>Ae</sub>B<sub>g</sub><super>T</super>𝓝B<sub>g</sub>dA]d",
            "(5-8)",
        )
    )
    story.extend(
        eq(
            "K<sub>g,e</sub>=∫<sub>Ae</sub>B<sub>g</sub><super>T</super>𝓝B<sub>g</sub>dA，　K<sub>T,e</sub>=K<sub>b,e</sub>−K<sub>g,e</sub>",
            "(5-9)",
        )
    )
    story.append(
        P(
            "曲殼元素還會有局部基底、膜-彎耦合、轉角自由度與曲率項，但其核心仍是同一件事："
            "預應力對擾動斜率的二階作功形成幾何剛度。"
        )
    )
    story.append(P("5.4 Rayleigh 商與第一特徵值", H2))
    story.append(
        P(
            "由 (5-5) 左乘 <font name='ArialU'>φ<super>T</super></font>："
        )
    )
    story.extend(
        eq(
            "φ<super>T</super>K<sub>M</sub>φ+λφ<super>T</super>K<sub>σ,ref</sub>φ=0",
            "(5-10)",
        )
    )
    story.extend(
        eq(
            "λ(φ)=−[φ<super>T</super>K<sub>M</sub>φ]/[φ<super>T</super>K<sub>σ,ref</sub>φ]",
            "(5-11)",
        )
    )
    story.append(
        P(
            "壓縮模態下分母為負，因此 <font name='ArialU'>λ</font> 為正。"
            "在可容許離散空間中使此比值最小的 <font name='ArialU'>φ</font> 給第一屈曲倍率；"
            "這正是第 3 節能量法在有限維空間中的版本。"
        )
    )
    story.append(P("5.5 實際計算流程與驗證門檻", H2))
    story.append(
        make_table(
            ["步驟", "計算內容", "必做檢查"],
            [
                ["1", "建立幾何、厚度、材料、局部座標與邊界", "剛體模態是否完全排除；簡支是否誤鎖轉角"],
                ["2", "以參考載重 f̄ 做線性屈曲前靜力分析", "反力總和、膜力方向與單位；是否已有顯著彎曲"],
                ["3", "由參考應力組裝 K<sub>σ,ref</sub>", "壓縮區對應負初應力剛度；積分與厚度一致"],
                ["4", "解最低數個 (K<sub>M</sub>+λK<sub>σ,ref</sub>)φ=0", "過濾剛體、鑽孔、零能與局部數值模態"],
                ["5", "網格收斂與解析基準比對", "每一屈曲半波至少約 6-10 個低階元素；加密後 λ、波數穩定"],
                ["6", "以模態生成受控初始缺陷並做幾何非線性分析", "缺陷振幅、符號、材料非線性及載重控制方法有依據"],
            ],
            widths=[15 * mm, 82 * mm, CONTENT_W - 97 * mm],
        )
    )
    story.extend(source("[B04 | §3.5 | PDF p.119-121] K<sub>0</sub>+λK<sub>NL</sub><sup>e</sup> 的線性特徵值式；[B04 | §4.4 | PDF p.147-152] 切線剛度失去正定性、分岔與分支切換。"))

    # Section 6 examples
    story.append(PageBreak())
    story.append(P("6. 完整例題", H1))
    story.append(P("例題 1：單向壓縮鋼矩形板", H2))
    story.append(
        P(
            "<b>已知：</b><font name='ArialU'>a=1200 mm</font>、<font name='ArialU'>b=600 mm</font>、"
            "<font name='ArialU'>h=6 mm</font>、<font name='ArialU'>E=210000 MPa</font>、"
            "<font name='ArialU'>ν=0.30</font>，四邊簡支，沿 x 方向均勻壓縮。"
            "求第一臨界膜力、臨界應力、總邊力與半波數。"
        )
    )
    story.append(P("<b>步驟 1：彎曲剛度。</b>"))
    story.extend(
        eq(
            "D=210000×6<super>3</super>/[12(1−0.3<super>2</super>)]=4.153846×10<super>6</super> N·mm",
            "(E1-1)",
        )
    )
    story.append(P("<b>步驟 2：長寬比與候選半波。</b>"))
    story.extend(eq("r=a/b=1200/600=2", "(E1-2)"))
    story.append(
        P(
            "連續最佳值為 <font name='ArialU'>m=r=2</font>，恰為整數。仍列出相鄰候選以核對："
        )
    )
    story.append(
        make_table(
            ["m", "k<sub>m</sub>=(m/r+r/m)<super>2</super>", "N<sub>m</sub> (N/mm)", "σ<sub>m</sub> (MPa)"],
            [
                ["1", "6.2500", "711.750", "118.625"],
                ["2", "4.0000", "455.520", "75.920"],
                ["3", "4.6944", "534.604", "89.101"],
            ],
            widths=[18 * mm, 63 * mm, 49 * mm, CONTENT_W - 130 * mm],
        )
    )
    story.append(P("<b>步驟 3：第一臨界值。</b>"))
    story.extend(
        eq(
            "N<sub>cr</sub>=4π<super>2</super>D/b<super>2</super>=455.520 N/mm",
            "(E1-3)",
        )
    )
    story.extend(eq("σ<sub>cr</sub>=N<sub>cr</sub>/h=455.520/6=75.920 MPa", "(E1-4)"))
    story.extend(eq("P<sub>cr</sub>=N<sub>cr</sub>b=455.520×600=273.312 kN", "(E1-5)"))
    story.append(
        P(
            "<b>答案：</b>第一模態為 <font name='ArialU'>(m,n)=(2,1)</font>；x 方向有兩個半波，"
            "每一半波長 <font name='ArialU'>a/m=600 mm</font>，恰等於板寬。"
        )
    )

    story.append(P("例題 2：等雙向壓縮鋁方板", H2))
    story.append(
        P(
            "<b>已知：</b><font name='ArialU'>a=b=400 mm</font>、<font name='ArialU'>h=2 mm</font>、"
            "<font name='ArialU'>E=70000 MPa</font>、<font name='ArialU'>ν=0.33</font>，"
            "四邊簡支，<font name='ArialU'>N<sub>x</sub>=N<sub>y</sub>=N</font>。"
        )
    )
    story.extend(
        eq(
            "D=70000×2<super>3</super>/[12(1−0.33<super>2</super>)]=52369.730 N·mm",
            "(E2-1)",
        )
    )
    story.append(P("方板第一模態取 <font name='ArialU'>m=n=1</font>，由 (3-23)："))
    story.extend(
        eq(
            "N<sub>cr</sub>=2π<super>2</super>D/a<super>2</super>=6.4609 N/mm",
            "(E2-2)",
        )
    )
    story.extend(eq("σ<sub>cr</sub>=N<sub>cr</sub>/h=3.2304 MPa", "(E2-3)"))
    story.append(
        P(
            "若只有 x 向壓縮，同一方板為 <font name='ArialU'>4π<super>2</super>D/a<super>2</super>=12.9217 N/mm</font>。"
            "所以等雙向壓縮使每方向的臨界膜力減半。"
        )
    )

    story.append(P("例題 3：四邊簡支方板純剪切的 Galerkin 收斂", H2))
    story.append(
        P(
            "令方板邊長為 <font name='ArialU'>L</font>，定義剪切屈曲係數 "
            "<font name='ArialU'>k<sub>s</sub>=N<sub>xy,cr</sub>L<super>2</super>/(π<super>2</super>D)</font>。"
            "將 (3-29) 的模態截斷為 <font name='ArialU'>1≤m,n≤M</font>。"
        )
    )
    story.append(P("<b>先做兩模態手算：</b>取 <font name='ArialU'>(1,1)</font> 與 <font name='ArialU'>(2,2)</font>。"))
    story.extend(eq("K<sub>11</sub>=Dπ<super>4</super>/L<super>2</super>，　K<sub>22</sub>=16Dπ<super>4</super>/L<super>2</super>", "(E3-1)"))
    story.extend(eq("G<sup>xy</sup><sub>11,22</sub>=8·1·1·2·2/[(4−1)(1−4)]=−32/9", "(E3-2)"))
    story.extend(
        eq(
            "det[[K<sub>11</sub>,−N<sub>xy</sub>G<sub>12</sub>],[−N<sub>xy</sub>G<sub>12</sub>,K<sub>22</sub>]]=0",
            "(E3-3)",
        )
    )
    story.extend(
        eq(
            "N<sub>xy,cr</sub>=√(K<sub>11</sub>K<sub>22</sub>)/|G<sub>12</sub>|=(9/8)π<super>4</super>D/L<super>2</super>",
            "(E3-4)",
        )
    )
    story.extend(eq("k<sub>s</sub>=(9/8)π<super>2</super>=11.1033", "(E3-5)"))
    story.append(
        P(
            "兩模態是可容許 Ritz 子空間，因此給上界。增加模態後："
        )
    )
    story.append(
        make_table(
            ["截斷 M", "自由係數數 M<super>2</super>", "k<sub>s</sub>", "相對 M=16"],
            [
                ["2", "4", "11.1033", "+19.08%"],
                ["3", "9", "9.4218", "+1.04%"],
                ["4", "16", "9.4044", "+0.86%"],
                ["5", "25", "9.3428", "+0.19%"],
                ["8", "64", "9.3283", "+0.04%"],
                ["12", "144", "9.3251", "+0.005%"],
                ["16", "256", "9.3247", "基準"],
            ],
            widths=[33 * mm, 42 * mm, 42 * mm, CONTENT_W - 117 * mm],
        )
    )
    story.append(
        P(
            "<b>結論：</b>純剪切需要模態耦合；單一雙正弦項甚至會給零剪切幾何能，"
            "而足夠大的 Navier 子空間收斂至 <font name='ArialU'>k<sub>s</sub>≈9.325</font>。"
        )
    )

    story.append(P("例題 4：軸壓鋁圓柱殼", H2))
    story.append(
        P(
            "<b>已知：</b><font name='ArialU'>R=500 mm</font>、<font name='ArialU'>L=1000 mm</font>、"
            "<font name='ArialU'>h=1 mm</font>、<font name='ArialU'>E=70000 MPa</font>、"
            "<font name='ArialU'>ν=0.33</font>。求理想經典臨界應力、總軸力與一個代表性軸對稱波數。"
        )
    )
    story.extend(
        eq(
            "σ<sub>cr</sub>=70000(1/500)/√[3(1−0.33<super>2</super>)]=85.626 MPa",
            "(E4-1)",
        )
    )
    story.extend(eq("N<sub>cr</sub>=σ<sub>cr</sub>h=85.626 N/mm", "(E4-2)"))
    story.extend(
        eq(
            "P<sub>cr</sub>=2πRN<sub>cr</sub>=2π×500×85.626=269.00 kN",
            "(E4-3)",
        )
    )
    story.append(
        P(
            "取代表性的軸對稱模態 <font name='ArialU'>β=0</font>。由 (4-21)，此時 "
            "<font name='ArialU'>α=[12(1−ν<super>2</super>)]<super>1/4</super>/√(Rh)</font>："
        )
    )
    story.extend(eq("α=0.080871 mm<super>−1</super>，　λ<sub>x,wave</sub>=2π/α=77.694 mm", "(E4-4)"))
    story.extend(eq("m≈αL/π=25.742 ⇒ 取 m=26", "(E4-5)"))
    story.append(
        P(
            "把離散 <font name='ArialU'>m=26</font> 代回 (4-14) 得 "
            "<font name='ArialU'>σ≈85.643 MPa</font>，與連續最小值只差約 0.02%。"
            "實際殼的第一模態可能為非軸對稱且高度依賴邊界與缺陷。"
        )
    )

    story.append(P("例題 5：同一球殼的理想外壓", H2))
    story.append(
        P(
            "沿用 <font name='ArialU'>R=500 mm</font>、<font name='ArialU'>h=1 mm</font>、"
            "<font name='ArialU'>E=70000 MPa</font>、<font name='ArialU'>ν=0.33</font>，"
            "由 (4-27)："
        )
    )
    story.extend(
        eq(
            "p<sub>cr</sub>=2×70000×(1/500)<super>2</super>/√[3(1−0.33<super>2</super>)]=0.34250 MPa",
            "(E5-1)",
        )
    )
    story.append(
        P(
            "膜力核對：<font name='ArialU'>N=pR/2=0.34250×500/2=85.626 N/mm</font>，"
            "正好等於例題 4 的經典臨界膜力。這不是巧合，而是兩者最小化後皆得到 "
            "<font name='ArialU'>2√(DEh)/R</font>。"
        )
    )

    story.append(P("例題 6：二自由度廣義特徵值手算", H2))
    story.append(
        P(
            "為了檢查有限元素求解器的符號，假設材料剛度與『壓縮削弱正矩陣』為："
        )
    )
    story.extend(eq("K<sub>M</sub>=[[12,−2],[−2,6]]，　K<sub>G</sub>=[[1,0.2],[0.2,0.5]]", "(E6-1)"))
    story.append(P("採 <font name='ArialU'>det(K<sub>M</sub>−λK<sub>G</sub>)=0</font>："))
    story.extend(
        eq(
            "(12−λ)(6−0.5λ)−(−2−0.2λ)<super>2</super>=0",
            "(E6-2)",
        )
    )
    story.extend(eq("0.46λ<super>2</super>−12.8λ+68=0", "(E6-3)"))
    story.extend(eq("λ=[12.8±√(12.8<super>2</super>−4×0.46×68)]/(2×0.46)", "(E6-4)"))
    story.extend(eq("λ<sub>1</sub>=7.1494，　λ<sub>2</sub>=20.6767", "(E6-5)"))
    story.append(
        P(
            "若參考載重為 10 kN，第一理想屈曲載重為 "
            "<font name='ArialU'>71.494 kN</font>。若程式回傳負值，先確認它使用的是 "
            "<font name='ArialU'>K<sub>M</sub>+λK<sub>σ</sub></font> 還是 "
            "<font name='ArialU'>K<sub>M</sub>−λK<sub>G</sub></font> 的正號慣例。"
        )
    )

    # Section 7
    story.append(P("7. 驗證、常見錯誤與適用界線", H1))
    story.append(P("7.1 三層驗證", H2))
    story.append(
        make_table(
            ["層級", "應做的驗證", "通過標準"],
            [
                ["解析層", "方板單向壓縮、等雙向壓縮、純剪切級數；圓柱／球殼經典值", "量綱正確；長寬比、h/R 趨勢正確；最低波數合理"],
                ["離散層", "網格加密、元素階次、積分法、局部座標、邊界敏感性", "最低數個 λ 與模態穩定；沒有零能／鑽孔假模態"],
                ["物理層", "幾何缺陷、材料屈服、殘餘應力、端部拘束與載重引入", "非線性極限載重不被誤稱為理想 eigenvalue；結果可對照試驗／規範"],
            ],
            widths=[26 * mm, 78 * mm, CONTENT_W - 104 * mm],
        )
    )
    story.append(P("7.2 常見錯誤清單", H2))
    for item in [
        "<b>把 N 當成應力：</b>板殼控制方程中的 N 是厚度積分後的膜力，量綱為 N/mm；應力為 σ=N/h。",
        "<b>忽略整數波數：</b>連續最小化只給下界與趨勢；有限 a、b、L、R 必須搜尋整數 m、n。",
        "<b>簡支條件設錯：</b>解析 Kirchhoff 板的簡支是 w=0、M<sub>n</sub>=0，不等於把所有轉角鎖死。",
        "<b>單模態求純剪切：</b>單一雙正弦的剪切幾何能為零；必須使用耦合級數或有限元素。",
        "<b>預應力場錯誤：</b>幾何剛度必須由屈曲前平衡應力組裝；不要用未平衡、單位錯誤或局部方向錯誤的應力。",
        "<b>只看第一個數字：</b>重複或接近特徵值時，任何線性組合都可能被求解器回傳；應檢查模態子空間。",
        "<b>殼網格太粗：</b>軸壓圓柱殼波長約為 O(√Rh)；元素尺寸必須能解析短波，而非只依整體尺寸分網。",
        "<b>把 eigenvalue 當設計強度：</b>薄殼對缺陷極敏感；理想分岔值通常是上限，不是直接容許值。",
        "<b>忽略載重型式：</b>本講義假設死載重。跟隨力可能導致非對稱切線矩陣，能量與正定性判據需重新處理。",
        "<b>高階特徵值過度解讀：</b>高模態可能超出線性屈曲前假設，亦可能是離散假象；必須以網格與物理尺度篩選。",
    ]:
        story.append(bullet(item))
    story.append(P("7.3 公式的快速量綱檢查", H2))
    story.append(
        make_table(
            ["式子", "量綱推導", "結果"],
            [
                ["D=Eh<super>3</super>/12(1−ν<super>2</super>)", "(N/mm<super>2</super>)·mm<super>3</super>", "N·mm"],
                ["N<sub>plate</sub>~D/b<super>2</super>", "(N·mm)/mm<super>2</super>", "N/mm"],
                ["σ<sub>plate</sub>~E(h/b)<super>2</super>", "(N/mm<super>2</super>)·1", "MPa"],
                ["N<sub>cyl</sub>~Eh<super>2</super>/R", "(N/mm<super>2</super>)·mm<super>2</super>/mm", "N/mm"],
                ["p<sub>sphere</sub>~E(h/R)<super>2</super>", "(N/mm<super>2</super>)·1", "MPa"],
            ],
            widths=[62 * mm, 70 * mm, CONTENT_W - 132 * mm],
        )
    )

    # References
    story.append(P("8. 書籍來源與閱讀定位", H1))
    story.append(
        P(
            "以下頁碼均為工作區 PDF 閱讀器中的一基底實體頁碼。公式、邊界與符號已依原頁核對；"
            "本講義為重新組織的推導與例題，不是原書逐字翻譯。"
        )
    )
    story.append(
        make_table(
            ["代碼", "書籍", "本講義使用範圍"],
            [
                [
                    "B06",
                    "S. P. Timoshenko, J. M. Gere, <i>Theory of Elastic Stability</i>",
                    "Ch. 9 薄板屈曲，PDF p.268-333；Ch. 11 殼屈曲，PDF p.347-406。",
                ],
                [
                    "B07",
                    "W. T. Koiter / A. M. A. van der Heijden (ed.), <i>W. T. Koiter’s Elastic Stability of Solids and Structures</i>",
                    "§3.12 平面內受載板，PDF p.147-167；§3.16 球殼，p.192-210；§3.17 圓柱殼，p.211-230。",
                ],
                [
                    "B04",
                    "R. de Borst, M. A. Crisfield et al., <i>Non-Linear Finite Element Analysis of Solids and Structures</i>, 2nd ed.",
                    "§3.5 線性屈曲，PDF p.119-121；§4.4 穩定、唯一性與分岔，PDF p.147-152。",
                ],
            ],
            widths=[15 * mm, 88 * mm, CONTENT_W - 103 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        P(
            "<b>最終概念鏈：</b>運動學假設 → 非線性應變中的斜率平方 → 二次變分 → 彎曲剛度與預應力幾何能 → "
            "中性平衡微分方程 → 邊界條件與模態 → 臨界載重最小化 → 有限元素材料／幾何剛度 → "
            "廣義特徵值 → 以缺陷敏感的非線性分析判斷真實承載力。",
            CALLOUT,
        )
    )
    return story


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BucklingDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="Plate / Shell Buckling 完整數學推導與例題",
        author="Codex",
        subject="板殼線性屈曲、能量法、解析解與有限元素特徵值",
    )
    doc.multiBuild(add_story())
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
