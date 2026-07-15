# -*- coding: utf-8 -*-
"""
產出「每鄉鎮各自獨立」的成交件數趨勢圖：
- 土地成交件數折線圖
- 房屋成交件數折線圖
X 軸固定為「前三個完整月份」（例如當前為 7 月 → 顯示 4、5、6 月，不含當月）。
五個鄉鎮共 10 張圖，彼此不混畫在同一張圖上。輸出為 JPG。
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from . import config
from .parse import Record

TOWN_COLOR = "#0B5B52"
ORANGE = "#FB8919"

_font_name = None


def _register_fonts() -> str:
    global _font_name
    if _font_name:
        return _font_name
    name = "Noto Sans TC"
    for path in (config.FONT_REGULAR, config.FONT_BOLD):
        if Path(path).exists():
            font_manager.fontManager.addfont(str(path))
            name = font_manager.FontProperties(fname=str(path)).get_name()
    plt.rcParams["font.family"] = name
    plt.rcParams["axes.unicode_minus"] = False
    _font_name = name
    return name


def _last_three_full_months_roc() -> list[str]:
    """
    回傳「前三個完整月份」的民國年月標籤，不含當月。
    例如當前為 115/07 → ['115/04', '115/05', '115/06']。
    """
    today = dt.date.today()
    y, m = today.year - 1911, today.month
    months = []
    for offset in (3, 2, 1):  # 前三、前二、前一個月，時間由舊到新
        total = y * 12 + (m - 1) - offset
        yy, mm = divmod(total, 12)
        months.append(f"{yy}/{mm + 1:02d}")
    return months


def _extract_roc_yyyymm(trade_date: str) -> str | None:
    digits = "".join(c for c in trade_date if c.isdigit())
    if len(digits) < 5:
        return None
    year = digits[:3] if len(digits) >= 7 else digits[:-4]
    month = digits[-4:-2]
    try:
        int(year)
        int(month)
    except ValueError:
        return None
    return f"{year}/{month}"


def _count_by_month(records: list[Record], town: str, months: list[str], land: bool) -> list[int]:
    """
    統計指定鄉鎮、在固定 months 各月份的成交件數。
    land=True 只算土地交易；land=False 只算房屋（含建物）交易。
    """
    counts: dict[str, int] = defaultdict(int)
    for r in records:
        if r.town != town:
            continue
        if land and not r.is_land_only:
            continue
        if not land and r.is_land_only:
            continue
        ym = _extract_roc_yyyymm(r.trade_date)
        if ym in months:
            counts[ym] += 1
    return [counts.get(m, 0) for m in months]


def _plot_count_line(months: list[str], counts: list[int], title: str, out_path: Path) -> Path | None:
    """畫固定三個月的成交件數折線圖（字體放大版）。"""
    if not any(counts):
        print(f"[charts] {out_path.stem}：三個月皆無交易，略過繪圖")
        return None

    _register_fonts()
    fig, ax = plt.subplots(figsize=(6.6, 3.8), dpi=150)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    ax.plot(months, counts, marker="o", color=TOWN_COLOR, linewidth=3, markersize=9,
            markerfacecolor=ORANGE, markeredgecolor=TOWN_COLOR, markeredgewidth=1.5)

    # 資料標籤（放大）
    for x, y in zip(months, counts):
        ax.annotate(f"{y}", (x, y), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=15,
                    fontweight="bold", color=TOWN_COLOR)

    ax.set_title(title, fontsize=17, fontweight="bold", pad=14, color="#0B5B52")
    ax.set_ylabel("成交件數", fontsize=13)
    ax.set_ylim(0, max(counts) + max(2, max(counts) * 0.3))
    ax.grid(True, alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=12)
    # 只顯示整數刻度
    from matplotlib.ticker import MaxNLocator
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="jpg", pil_kwargs={"quality": 92})
    plt.close(fig)
    return out_path


def town_volume_charts(
    records: list[Record], out_dir: Path
) -> dict[str, tuple[Path | None, Path | None]]:
    """
    為每個鄉鎮各自產出「土地成交件數」與「房屋成交件數」兩張獨立折線圖。
    X 軸固定為前三個完整月份。
    回傳 {鄉鎮: (土地件數圖路徑, 房屋件數圖路徑)}，全無交易時對應路徑為 None。
    """
    months = _last_three_full_months_roc()
    print(f"[charts] 統計月份區間（前三個完整月）：{months}")

    result = {}
    for town in config.TARGET_TOWNS:
        land_counts = _count_by_month(records, town, months, land=True)
        house_counts = _count_by_month(records, town, months, land=False)

        land_path = _plot_count_line(
            months, land_counts, f"{town}｜土地成交件數", out_dir / f"vol_land_{town}.jpg",
        )
        house_path = _plot_count_line(
            months, house_counts, f"{town}｜房屋成交件數", out_dir / f"vol_house_{town}.jpg",
        )
        result[town] = (land_path, house_path)
        print(f"[charts] {town}：土地圖 {'✓' if land_path else '✗'}，房屋圖 {'✓' if house_path else '✗'}")
    return result
