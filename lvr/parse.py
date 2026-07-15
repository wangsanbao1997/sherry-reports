# -*- coding: utf-8 -*-
"""
解析內政部實價登錄 CSV，篩選目標鄉鎮，轉為結構化交易紀錄。

CSV 編碼為 utf-8-sig，前兩列為中文／英文欄名，資料從第 3 列開始。
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from . import config

NON_ARMS_LENGTH_KEYWORDS = ["親友", "親屬", "債務", "共有物分割", "拍賣", "法拍"]


@dataclass
class Record:
    rec_id: str
    season: str
    town: str
    zone_use: str          # 使用分區（住宅區／商業區／農業區／其他）
    building_type: str      # 建物型態
    trade_date: str         # 交易年月日（民國）
    total_price: float      # 總價（元）
    land_area_ping: float   # 土地面積（坪）
    building_area_ping: float  # 建物面積（坪，土地交易為 0）
    area_ping: float        # 計價面積（優先建物，無則土地；供單價計算與中位數分析用）
    unit_price_ping: float  # 元／坪
    address: str
    is_land_only: bool      # 是否為土地交易（無建物）
    is_special: bool        # 是否為非常規交易（親友、拍賣等）
    raw: dict = field(default_factory=dict)


def _to_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _sqm_to_ping(sqm: float) -> float:
    return sqm / 3.30579


def _detect_special(note: str, main_use: str) -> bool:
    text = f"{note} {main_use}"
    return any(kw in text for kw in NON_ARMS_LENGTH_KEYWORDS)


def parse_csv(csv_bytes: bytes, season: str, source_filename: str) -> list[Record]:
    """解析單一 CSV 檔，回傳篩選過目標鄉鎮後的交易紀錄清單。"""
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    rows = list(reader)
    if len(rows) < 2:
        return []
    # 第一列資料列其實是英文欄名列，跳過
    data_rows = rows[1:]

    is_presale = "land_b" in source_filename.lower()

    records = []
    for row in data_rows:
        address = (row.get("土地位置建物門牌") or row.get("土地位置") or "").strip()
        # 以「鄉鎮市區」欄位判斷所屬鄉鎮（最可靠）；土地交易門牌是「○○段地號」
        # 不含鄉鎮名，若改用門牌字串比對會把土地交易全部漏掉。
        town_field = (row.get("鄉鎮市區") or "").strip()
        town = next((t for t in config.TARGET_TOWNS if t == town_field), None)
        if town is None:
            # 退回用門牌字串比對（保險，處理欄位缺漏情況）
            town = next((t for t in config.TARGET_TOWNS if t in address), None)
        if town is None:
            continue

        trade_date = (row.get("交易年月日") or "").strip()
        total_price = _to_float(row.get("總價元"))
        land_area_sqm = _to_float(row.get("土地移轉總面積平方公尺"))
        building_area_sqm = _to_float(row.get("建物移轉總面積平方公尺"))

        land_area_ping = round(_sqm_to_ping(land_area_sqm), 2) if land_area_sqm > 0 else 0.0
        building_area_ping = round(_sqm_to_ping(building_area_sqm), 2) if building_area_sqm > 0 else 0.0

        area_sqm = building_area_sqm if building_area_sqm > 0 else land_area_sqm
        area_ping = round(_sqm_to_ping(area_sqm), 2) if area_sqm > 0 else 0.0
        unit_price_ping = round(total_price / area_ping, 0) if area_ping > 0 else 0.0

        zone_use = (row.get("都市土地使用分區") or row.get("非都市土地使用分區") or "其他").strip() or "其他"
        building_type = (row.get("建物型態") or ("預售屋" if is_presale else "土地")).strip()
        main_use = (row.get("主要用途") or "").strip()
        note = (row.get("備註") or "").strip()

        # 以「交易標的」欄位判斷是否為純土地交易（最準確）；
        # 欄位缺漏時退回用建物面積判斷。
        trade_subject = (row.get("交易標的") or "").strip()
        if trade_subject:
            is_land_only = (trade_subject == "土地")
        else:
            is_land_only = (building_area_sqm <= 0)

        rec_id_src = f"{season}|{address}|{trade_date}|{total_price}|{row.get('編號','')}"
        rec_id = str(abs(hash(rec_id_src)))

        records.append(Record(
            rec_id=rec_id,
            season=season,
            town=town,
            zone_use=zone_use,
            building_type=building_type,
            trade_date=trade_date,
            total_price=total_price,
            land_area_ping=land_area_ping,
            building_area_ping=building_area_ping,
            area_ping=area_ping,
            unit_price_ping=unit_price_ping,
            address=address,
            is_land_only=is_land_only,
            is_special=_detect_special(note, main_use),
            raw=row,
        ))
    return records


def parse_all(fetched: dict[str, dict]) -> list[Record]:
    """解析 download.fetch_all() 回傳的所有季度資料。"""
    all_records: list[Record] = []
    for season, payload in fetched.items():
        for filename, csv_bytes in payload["files"].items():
            recs = parse_csv(csv_bytes, season, filename)
            all_records.extend(recs)
            print(f"[parse] {season}/{filename} 解析出 {len(recs)} 筆目標鄉鎮交易")
    return all_records
