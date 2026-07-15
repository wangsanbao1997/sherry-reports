# -*- coding: utf-8 -*-
"""
產出手機版單檔 HTML 報告：深綠＋橘色視覺風格，大字卡片，可直接轉傳長輩客戶。
加上 noindex 及隨機檔名，避免被搜尋引擎收錄或被外部人任意瀏覽。
"""
from __future__ import annotations

import base64
import secrets
from pathlib import Path

from . import config
from .analyze import Assessment

CARD_TEMPLATE = """
<div class="card">
  <div class="card-top">
    <span class="town">{town}｜{trade_kind}</span>
    <span class="flag {flag_class}">{flag}</span>
  </div>
  <div class="price">{total_price} <span class="unit">萬元</span></div>
  <div class="meta">{address}</div>
  <div class="meta">{trade_date}｜{land_ping}｜{building_ping}｜{unit_price} 萬/坪</div>
</div>
"""


def _flag_class(flag: str) -> str:
    if flag.startswith("【推估】"):
        return "flag-deviation"
    if flag.startswith("【假設】"):
        return "flag-assumption"
    return "flag-normal"


def _img_to_base64(path: Path | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("ascii")


def build_html(
    assessments: list[Assessment],
    summary: dict,
    town_charts: dict[str, tuple[Path | None, Path | None]] | None,
    ai_text: str | None,
    out_dir: Path,
) -> Path:
    cards = []
    for a in assessments:
        r = a.record
        cards.append(CARD_TEMPLATE.format(
            town=r.town,
            trade_kind=("預售屋" if r.building_type == "預售屋" else "買賣"),
            flag_class=_flag_class(a.flag),
            flag=a.flag,
            total_price=f"{r.total_price/10000:,.0f}",
            address=r.address,
            trade_date=r.trade_date,
            land_ping=f"土地 {r.land_area_ping:.1f}坪" if r.land_area_ping else "土地 —",
            building_ping=f"建物 {r.building_area_ping:.1f}坪" if r.building_area_ping else "建物 —",
            unit_price=f"{r.unit_price_ping/10000:.2f}" if r.unit_price_ping else "—",
        ))
    cards_html = "\n".join(cards)

    town_badges = "".join(
        f'<span class="town-badge">{t} <b>{n}</b> 筆</span>'
        for t, n in summary["by_town"].items() if n
    )

    chart_sections = []
    if town_charts:
        for town in config.TARGET_TOWNS:
            pair = town_charts.get(town)
            if not pair:
                continue
            count_path, amount_path = pair
            imgs = []
            for p, label in ((count_path, "土地成交件數"), (amount_path, "房屋成交件數")):
                b64 = _img_to_base64(p)
                if b64:
                    imgs.append(f'<img class="chart" src="data:image/jpeg;base64,{b64}" alt="{town}{label}">')
            if imgs:
                chart_sections.append(
                    f'<div class="chart-town-label">{town}</div>' + "".join(imgs)
                )
    charts_html = "\n".join(chart_sections)

    ai_html = (
        f'<div class="ai-box"><div class="ai-label">行情觀察（AI 輔助生成，僅供參考）</div>'
        f'<div class="ai-text">{ai_text}</div></div>'
        if ai_text else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>實價登錄日報</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Noto Sans TC', -apple-system, sans-serif;
    background: #F4F8F7; color: #374B47; padding-bottom: 40px;
  }}
  .header {{
    background: #0B5B52; color: #fff; padding: 28px 20px 24px;
    border-bottom: 5px solid #FB8919;
  }}
  .header .eyebrow {{
    color: #FB8919; font-size: 11px; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; margin-bottom: 6px;
  }}
  .header h1 {{ font-size: 21px; font-weight: 900; margin-bottom: 8px; }}
  .header .sub {{ font-size: 12.5px; color: #CFE3DF; line-height: 1.7; }}
  .header .sub strong {{ color: #fff; }}
  .badges {{ padding: 16px 20px 4px; display: flex; flex-wrap: wrap; gap: 8px; }}
  .total-badge {{
    background: #0B5B52; color: #fff; font-size: 13px; font-weight: 700;
    padding: 6px 14px; border-radius: 20px;
  }}
  .town-badge {{
    background: #FDEBD8; color: #0B5B52; font-size: 12.5px; font-weight: 600;
    padding: 5px 12px; border-radius: 20px; border: 1px solid #FBDCAF;
  }}
  .town-badge b {{ color: #FB8919; font-weight: 800; }}
  .section-label {{
    font-size: 14px; color: #0B5B52; font-weight: 700;
    margin: 22px 20px 10px; padding-bottom: 6px; border-bottom: 2px solid #FB8919;
  }}
  .chart-town-label {{ font-size: 13px; color: #0B5B52; font-weight: 700; margin: 16px 20px 6px; }}
  .chart {{
    width: calc(100% - 40px); margin: 0 20px 10px; border-radius: 10px;
    border: 1px solid #E3ECE9; background: #fff; display: block;
  }}
  .ai-box {{
    background: #FDEBD8; border: 1px solid #FBDCAF; border-radius: 12px;
    padding: 16px; margin: 16px 20px;
  }}
  .ai-label {{ font-size: 12px; color: #0B5B52; margin-bottom: 8px; font-weight: 700; }}
  .ai-text {{ font-size: 14px; line-height: 1.9; color: #374B47; }}
  .card {{
    background: #fff; border: 1px solid #E3ECE9; border-left: 4px solid #0B5B52;
    border-radius: 10px; padding: 16px 18px; margin: 0 20px 12px;
  }}
  .card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
  .town {{ font-size: 14.5px; font-weight: 700; color: #0B5B52; }}
  .flag {{ font-size: 10.5px; padding: 3px 10px; border-radius: 20px; }}
  .flag-normal {{ background: #E3F0EC; color: #0B5B52; }}
  .flag-deviation {{ background: #FDEBD8; color: #FB8919; }}
  .flag-assumption {{ background: #ECECEC; color: #8A8A8A; }}
  .price {{ font-size: 23px; font-weight: 800; color: #0B5B52; margin-bottom: 8px; }}
  .price .unit {{ font-size: 12.5px; color: #8AA39D; font-weight: 500; }}
  .meta {{ font-size: 12px; color: #6B7D78; margin-bottom: 2px; line-height: 1.6; }}
  .disclaimer {{
    margin: 24px 20px 0; font-size: 10.5px; line-height: 1.8;
    color: #8AA39D; padding-top: 14px; border-top: 1px solid #E3ECE9;
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="eyebrow">實價登錄 · 日報</div>
    <h1>實價登錄新增交易日報</h1>
    <div class="sub">
      報表日期：<strong>{summary['report_date']}</strong><br>
      鎖定區域：{'、'.join(config.TARGET_TOWNS)}<br>
      資料來源：內政部不動產交易實價查詢服務網
    </div>
  </div>
  <div class="badges">
    <span class="total-badge">本次新增共 {summary['total']} 筆</span>
    {town_badges}
  </div>
  {ai_html}
  <div class="section-label">新增交易明細</div>
  {cards_html}
  <div class="section-label">五鄉鎮土地／房屋成交件數趨勢（前三個完整月份）</div>
  {charts_html}
  <div class="disclaimer">
    單價已依申報資料換算為萬元/坪（1 坪 = 3.3058 平方公尺）；車位價格未拆算。實際交易條件請以謄本與買賣契約為準。<br><br>
    {config.DISCLAIMER}
  </div>
</body>
</html>
"""

    out_dir.mkdir(parents=True, exist_ok=True)
    random_name = f"report_{secrets.token_hex(6)}.html"
    out_path = out_dir / random_name
    out_path.write_text(html, encoding="utf-8")
    print(f"[report_html] HTML 已輸出：{out_path}")
    return out_path
