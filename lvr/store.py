# -*- coding: utf-8 -*-
"""
狀態持久化：已比對過的交易 ID、歷史交易紀錄（供中位數與趨勢分析用）、
執行 metadata。這些檔案由 GitHub Actions 在每次執行後 commit 回 repo，
讓下次執行能接續狀態，不必每次都以「全部視為新增」寄信。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from . import config
from .parse import Record


def load_seen_ids() -> set[str]:
    if not config.SEEN_IDS_PATH.exists():
        return set()
    try:
        return set(json.loads(config.SEEN_IDS_PATH.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen_ids(ids: set[str]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.SEEN_IDS_PATH.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=0), encoding="utf-8"
    )


def load_meta() -> dict:
    if not config.META_PATH.exists():
        return {}
    try:
        return json.loads(config.META_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_meta(meta: dict) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.META_PATH.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


HISTORY_FIELDS = [
    "rec_id", "season", "town", "zone_use", "building_type",
    "trade_date", "total_price", "land_area_ping", "building_area_ping",
    "area_ping", "unit_price_ping", "address", "is_land_only", "is_special",
]


def load_history() -> list[Record]:
    if not config.HISTORY_PATH.exists():
        return []
    records = []
    with config.HISTORY_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            records.append(Record(
                rec_id=row["rec_id"],
                season=row["season"],
                town=row["town"],
                zone_use=row["zone_use"],
                building_type=row["building_type"],
                trade_date=row["trade_date"],
                total_price=float(row["total_price"] or 0),
                land_area_ping=float(row.get("land_area_ping") or 0),
                building_area_ping=float(row.get("building_area_ping") or 0),
                area_ping=float(row["area_ping"] or 0),
                unit_price_ping=float(row["unit_price_ping"] or 0),
                address=row["address"],
                is_land_only=(row["is_land_only"] == "True"),
                is_special=(row["is_special"] == "True"),
            ))
    return records


def append_history(records: list[Record]) -> None:
    if not records:
        return
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = config.HISTORY_PATH.exists()
    with config.HISTORY_PATH.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not file_exists:
            writer.writeheader()
        for r in records:
            writer.writerow({
                "rec_id": r.rec_id, "season": r.season, "town": r.town,
                "zone_use": r.zone_use, "building_type": r.building_type,
                "trade_date": r.trade_date, "total_price": r.total_price,
                "land_area_ping": r.land_area_ping, "building_area_ping": r.building_area_ping,
                "area_ping": r.area_ping, "unit_price_ping": r.unit_price_ping,
                "address": r.address, "is_land_only": r.is_land_only,
                "is_special": r.is_special,
            })
