# -*- coding: utf-8 -*-
"""
產出 PDF 報告：橫式明細表，深綠＋橘色視覺風格（頁首橫幅、統計膠囊、
深綠表頭配橘色分隔線），並附一頁獨立的量價趨勢圖表頁。
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Table, TableStyle, Paragraph, Spacer, Image, PageBreak, NextPageTemplate,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

from . import config
from .analyze import Assessment

FONT_NAME = "NotoTC"
FONT_BOLD_NAME = "NotoTC-Bold"

# ── 品牌色（沿用目標樣式：深綠＋橘色）──────────────
GREEN = colors.HexColor("#0B5B52")
ORANGE = colors.HexColor("#FB8919")
ORANGE_BG = colors.HexColor("#FDEBD8")
ORANGE_BORDER = colors.HexColor("#FBDCAF")
TEXT_DARK = colors.HexColor("#374B47")
TEXT_LIGHT = colors.HexColor("#E7F2EF")
TEXT_MUTED = colors.HexColor("#A9C9C3")
ROW_ALT = colors.HexColor("#F4F8F7")
GRID_LINE = colors.HexColor("#E3ECE9")
FOOTNOTE_COLOR = colors.HexColor("#6B7D78")

HEADER_HEIGHT = 30 * mm  # 頁首橫幅高度（畫布層滿版色塊）

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(config.FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, str(config.FONT_BOLD)))
    _fonts_registered = True


def _make_header_painter(page_w, page_h, title_text, subtitle_text, right_lines):
    """回傳一個 onPage callback，在畫布層畫出滿版到頁面邊緣的深綠色頁首橫幅。"""
    def _paint(canvas, doc):
        canvas.saveState()
        top_y = page_h - HEADER_HEIGHT
        canvas.setFillColor(GREEN)
        canvas.rect(0, top_y, page_w, HEADER_HEIGHT, fill=1, stroke=0)
        canvas.setFillColor(ORANGE)
        canvas.rect(0, top_y - 1.6 * mm, page_w, 1.6 * mm, fill=1, stroke=0)

        margin = 14 * mm
        # 左側：eyebrow + 標題 + 副標
        canvas.setFillColor(ORANGE)
        canvas.setFont(FONT_BOLD_NAME, 9.5)
        canvas.drawString(margin, page_h - 10 * mm, "實價登錄　·　日報")

        canvas.setFillColor(colors.white)
        canvas.setFont(FONT_BOLD_NAME, 18)
        canvas.drawString(margin, page_h - 17 * mm, title_text)

        canvas.setFillColor(TEXT_LIGHT)
        canvas.setFont(FONT_NAME, 9)
        canvas.drawString(margin, page_h - 23 * mm, subtitle_text)

        # 右側：多行資訊，靠右對齊
        right_x = page_w - margin
        canvas.setFont(FONT_NAME, 9)
        y = page_h - 10 * mm
        for line, color in right_lines:
            canvas.setFillColor(color)
            canvas.drawRightString(right_x, y, line)
            y -= 4.6 * mm

        canvas.restoreState()
    return _paint


def _money_wan(yuan: float) -> str:
    """元 → 萬元，取整數並加千分位。"""
    return f"{yuan / 10000:,.0f}"


def _unit_price_wan_ping(unit_price_ping_yuan: float) -> str:
    """元/坪 → 萬元/坪，取兩位小數。"""
    if unit_price_ping_yuan <= 0:
        return "—"
    return f"{unit_price_ping_yuan / 10000:.2f}"


def _trade_kind(r) -> str:
    return "預售屋" if r.building_type == "預售屋" else "買賣"


def _trade_target(r) -> str:
    if r.is_land_only:
        return "土地"
    if r.area_ping > 0 and r.building_type:
        return "房地(土地+建物)"
    return r.building_type or "房地"


def build_pdf(
    assessments: list[Assessment],
    summary: dict,
    town_charts: dict[str, tuple[Path, Path]] | None,
    ai_text: str | None,
    out_path: Path,
    is_first_run: bool = False,
) -> Path:
    """
    town_charts: {鄉鎮: (土地件數圖路徑, 房屋件數圖路徑)}，放在獨立圖表頁，
                 每個鄉鎮各自兩張圖、不與其他鄉鎮混畫。
    """
    _register_fonts()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = landscape(A4)
    margin = 14 * mm
    content_w = page_w - 2 * margin

    subtitle = "首次執行：建立基準，列出本期全部交易" if is_first_run else "新增交易通知"
    right_lines = [
        (f"報表日期：{summary['report_date']}", colors.white),
        (f"鎖定區域：{'、'.join(config.TARGET_TOWNS)}", TEXT_LIGHT),
        ("資料來源：內政部不動產交易實價查詢服務網", TEXT_MUTED),
    ]
    chart_right_lines = [
        ("前三個完整月份　·　每鄉鎮獨立呈現", colors.white),
    ]

    main_painter = _make_header_painter(page_w, page_h, "實價登錄新增交易日報", subtitle, right_lines)
    chart_painter = _make_header_painter(page_w, page_h, "五鄉鎮土地／房屋成交件數趨勢", "", chart_right_lines)

    frame_top = page_h - HEADER_HEIGHT - 6 * mm
    frame = Frame(margin, 12 * mm, content_w, frame_top - 12 * mm, id="main_frame",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    chart_frame = Frame(margin, 12 * mm, content_w, frame_top - 12 * mm, id="chart_frame",
                         leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc = BaseDocTemplate(
        str(out_path), pagesize=landscape(A4),
        leftMargin=margin, rightMargin=margin, topMargin=0, bottomMargin=12 * mm,
    )
    doc.addPageTemplates([
        PageTemplate(id="main", frames=[frame], onPage=main_painter),
        PageTemplate(id="chart", frames=[chart_frame], onPage=chart_painter),
    ])

    # ── 樣式 ──────────────────────────────
    h2_style = ParagraphStyle(
        "h2", fontName=FONT_BOLD_NAME, fontSize=13,
        textColor=GREEN, spaceBefore=10, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "body", fontName=FONT_NAME, fontSize=9, textColor=TEXT_DARK,
        leading=14, alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        "cell", fontName=FONT_NAME, fontSize=7.6, leading=10,
        textColor=TEXT_DARK,
    )
    disclaimer_style = ParagraphStyle(
        "disclaimer", fontName=FONT_NAME, fontSize=7, leading=10.5,
        textColor=FOOTNOTE_COLOR, spaceBefore=10,
    )
    badge_style = ParagraphStyle(
        "badge", fontName=FONT_BOLD_NAME, fontSize=9.5,
        textColor=colors.white, alignment=1,
    )
    town_badge_style = ParagraphStyle(
        "town_badge", fontName=FONT_NAME, fontSize=8.8,
        textColor=GREEN, alignment=1,
    )

    elements = []

    # ── 統計膠囊列（總筆數＋各鄉鎮筆數）──────────────
    total_badge = Table(
        [[Paragraph(f"本次新增共 {summary['total']} 筆", badge_style)]],
        colWidths=[36 * mm], rowHeights=[8 * mm],
    )
    total_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))

    badge_cells = [total_badge]
    for t in config.TARGET_TOWNS:
        n = summary["by_town"].get(t, 0)
        if not n:
            continue
        txt = f"{t} <font color='#FB8919'><b>{n}</b></font> 筆"
        badge = Table(
            [[Paragraph(txt, town_badge_style)]],
            colWidths=[28 * mm], rowHeights=[7.5 * mm],
        )
        badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ORANGE_BG),
            ("BOX", (0, 0), (-1, -1), 0.6, ORANGE_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROUNDEDCORNERS", [10, 10, 10, 10]),
        ]))
        badge_cells.append(badge)

    badge_row = Table(
        [badge_cells],
        colWidths=[36 * mm] + [28 * mm] * (len(badge_cells) - 1),
    )
    badge_row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(badge_row)
    elements.append(Spacer(1, 10))

    # ── 明細表 ──────────────────────────────
    header = ["鄉鎮", "類別", "交易標的", "地段 / 門牌", "交易日期",
               "總價(萬)", "單價(萬/坪)", "土地(坪)", "建物(坪)", "使用分區", "建物型態"]
    table_data = [header]

    for a in assessments:
        r = a.record
        note = ""
        if r.is_special:
            note = "備註：親友、員工、共有人或其他特殊關係間之交易"
        elif a.flag.startswith("【推估】"):
            note = f"備註：{a.flag}"

        address_html = r.address
        if note:
            address_html += f"<br/><font color='#FB8919' size=6.3>{note}</font>"
        address_cell = Paragraph(address_html, cell_style)

        table_data.append([
            Paragraph(f"<b>{r.town}</b>", ParagraphStyle("t", parent=cell_style, textColor=GREEN)),
            r.town and _trade_kind(r),
            _trade_target(r),
            address_cell,
            r.trade_date,
            Paragraph(f"<b>{_money_wan(r.total_price)}</b>",
                      ParagraphStyle("p", parent=cell_style, textColor=GREEN, alignment=TA_RIGHT)),
            _unit_price_wan_ping(r.unit_price_ping),
            f"{r.land_area_ping:.2f}" if r.land_area_ping else "-",
            f"{r.building_area_ping:.2f}" if r.building_area_ping else "-",
            r.zone_use or "其他",
            r.building_type or "其他",
        ])

    col_widths = [16*mm, 13*mm, 24*mm, 78*mm, 16*mm, 15*mm, 17*mm, 14*mm, 14*mm, 26*mm, 30*mm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD_NAME),
        ("FONTSIZE", (0, 0), (-1, 0), 8.2),
        ("FONTSIZE", (0, 1), (-1, -1), 7.6),
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, 0), 1.6, ORANGE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRID_LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (5, 0), (8, -1), "RIGHT"),
        ("ALIGN", (5, 0), (8, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
        else:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.white))
    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    footnote = (
        "單價已依申報資料換算為 萬元/坪（1 坪 = 3.3058 平方公尺）；車位價格未拆算。"
        "實際交易條件請以謄本與買賣契約為準。"
    )
    elements.append(Paragraph(footnote, disclaimer_style))

    if ai_text:
        elements.append(Paragraph("行情觀察（AI 輔助生成，僅供參考）", h2_style))
        elements.append(Paragraph(ai_text, body_style))

    elements.append(Paragraph(config.DISCLAIMER, disclaimer_style))

    # ── 圖表頁（獨立一頁，每鄉鎮各自兩張圖，不混畫）──────────────
    if town_charts:
        elements.append(NextPageTemplate("chart"))
        elements.append(PageBreak())

        img_w = 128 * mm
        img_h = 60 * mm
        rows = []
        for town in config.TARGET_TOWNS:
            charts_pair = town_charts.get(town)
            if not charts_pair:
                continue
            count_path, amount_path = charts_pair
            row_cells = []
            for p in (count_path, amount_path):
                if p and Path(p).exists():
                    row_cells.append(Image(str(p), width=img_w, height=img_h))
                else:
                    row_cells.append(Paragraph(f"{town}｜資料不足，暫無圖表", body_style))
            rows.append(row_cells)

        if rows:
            chart_table = Table(rows, colWidths=[img_w + 4*mm, img_w + 4*mm])
            chart_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            elements.append(chart_table)

    doc.build(elements)
    print(f"[report_pdf] PDF 已輸出：{out_path}")
    return out_path
