# -*- coding: utf-8 -*-
"""
分析模組：
1. 依「使用分區類別」分開統計中位數（避免農地／建地混算失真）
2. 每筆新增交易與同鄉鎮、同分區類別的近 12 月中位數比對，超過門檻標記【推估】偏離
3. 產出月度趨勢資料供繪圖使用
"""
from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass

from . import config
from .parse import Record


def _zone_category(zone_use: str) -> str:
    """
    將使用分區粗分為「住宅」「商業」「農地」「其他」四類，
    避免農地與建地混算中位數造成失真（曾實測混算導致建地被誤標 +633%）。
    """
    if any(k in zone_use for k in ["住宅", "住"]):
        return "住宅"
    if any(k in zone_use for k in ["商業", "商"]):
        return "商業"
    if any(k in zone_use for k in ["農業", "農牧", "農"]):
        return "農地"
    return "其他"


@dataclass
class Assessment:
    record: Record
    category: str
    median_unit_price: float | None
    deviation_pct: float | None
    flag: str  # "【事實】" 或 "【推估】偏離 +xx%" 或 "【假設】樣本不足未判斷"


def _median_unit_price(history: list[Record], town: str, category: str) -> tuple[float | None, int]:
    """回傳 (中位數元/坪, 樣本數)。排除非常規交易與土地/建物面積為 0 的異常值。"""
    prices = [
        r.unit_price_ping for r in history
        if r.town == town
        and _zone_category(r.zone_use) == category
        and not r.is_special
        and r.unit_price_ping > 0
    ]
    if len(prices) < config.MIN_SAMPLE_FOR_MEDIAN:
        return None, len(prices)
    return statistics.median(prices), len(prices)


def assess(new_records: list[Record], history: list[Record]) -> list[Assessment]:
    """對每筆新增交易做偏離評估，基準為「本次之前」的歷史資料。"""
    results = []
    for r in new_records:
        category = _zone_category(r.zone_use)

        if r.is_special:
            results.append(Assessment(
                record=r, category=category, median_unit_price=None,
                deviation_pct=None, flag="【假設】非常規交易（親友／拍賣等），不納入行情比對",
            ))
            continue

        median, sample_n = _median_unit_price(history, r.town, category)
        if median is None or r.unit_price_ping <= 0:
            results.append(Assessment(
                record=r, category=category, median_unit_price=median,
                deviation_pct=None,
                flag=f"【假設】樣本不足（{sample_n} 筆），未進行行情比對",
            ))
            continue

        deviation = (r.unit_price_ping - median) / median
        if abs(deviation) >= config.DEVIATION_THRESHOLD:
            sign = "+" if deviation > 0 else ""
            flag = f"【推估】偏離區域中位數 {sign}{deviation*100:.0f}%"
        else:
            flag = "【事實】價格落於區域正常區間"

        results.append(Assessment(
            record=r, category=category, median_unit_price=median,
            deviation_pct=deviation, flag=flag,
        ))
    return results


def monthly_trend(history: list[Record]) -> dict[str, list[tuple[str, float]]]:
    """
    依鄉鎮回傳近 TREND_MONTHS 個月的月均單價趨勢：
    {town: [(民國年月, 平均元/坪), ...]}
    """
    cutoff_roc_yyyymm = _months_ago_roc(config.TREND_MONTHS)

    by_town_month: dict[str, dict[str, list[float]]] = {}
    for r in history:
        if r.is_special or r.unit_price_ping <= 0:
            continue
        ym = _extract_roc_yyyymm(r.trade_date)
        if ym is None or ym < cutoff_roc_yyyymm:
            continue
        by_town_month.setdefault(r.town, {}).setdefault(ym, []).append(r.unit_price_ping)

    trend = {}
    for town, month_map in by_town_month.items():
        series = sorted(
            (ym, round(statistics.mean(prices), 0))
            for ym, prices in month_map.items()
        )
        trend[town] = series
    return trend


def _extract_roc_yyyymm(trade_date: str) -> str | None:
    """交易年月日格式如 1140715（民國114年7月15日）→ '114/07'"""
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


def _months_ago_roc(n_months: int) -> str:
    today = dt.date.today()
    y, m = today.year - 1911, today.month
    total = y * 12 + (m - 1) - n_months
    y2, m2 = divmod(total, 12)
    return f"{y2}/{m2+1:02d}"
