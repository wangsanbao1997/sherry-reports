# -*- coding: utf-8 -*-
"""
下載內政部實價登錄季度資料（ZIP）。

資料每旬（1、11、21 日）發布最新季度。季度未發布時，
伺服器可能回傳 HTTP 200 但內容是 HTML 錯誤頁（假 200），
因此一律以 ZIP magic bytes 判斷成功與否，不能只看狀態碼。
"""
from __future__ import annotations

import datetime as dt
import io
import time
import zipfile

import requests

from . import config


def current_and_previous_seasons() -> list[str]:
    """
    回傳「本季」與「上季」的季度代碼（如 115S3），
    同時抓兩季以涵蓋補登記交易（買賣完成後補登記可能晚於當季）。
    """
    today = dt.date.today()
    roc_year = today.year - 1911
    season = (today.month - 1) // 3 + 1

    seasons = []
    y, s = roc_year, season
    for _ in range(2):
        seasons.append(f"{y}S{s}")
        s -= 1
        if s == 0:
            s = 4
            y -= 1
    return seasons


def _is_valid_zip(content: bytes) -> bool:
    return content[:2] == b"PK"


def download_season(season: str) -> bytes | None:
    """
    下載指定季度的 ZIP bytes。若該季尚未發布（假 200 或 404），回傳 None。
    """
    url = f"{config.DOWNLOAD_BASE_URL}?season={season}&type=zip&fileName=lvr_landcsv.zip"
    last_err = None
    for attempt in range(1, config.DOWNLOAD_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=config.DOWNLOAD_TIMEOUT)
            if resp.status_code == 200 and _is_valid_zip(resp.content):
                return resp.content
            if resp.status_code == 404:
                return None
            last_err = f"HTTP {resp.status_code}，內容非有效 ZIP（可能尚未發布）"
        except requests.RequestException as e:
            last_err = str(e)

        wait = config.DOWNLOAD_RETRY_WAIT_BASE * attempt
        print(f"[download] {season} 第 {attempt} 次嘗試失敗：{last_err}，{wait}s 後重試")
        time.sleep(wait)

    print(f"[download] {season} 已達重試上限，略過（{last_err}）")
    return None


def extract_build_time(zip_bytes: bytes) -> str:
    """從 ZIP 內檔案的最新時間戳判斷資料建置時間，作為新鮮度依據。"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        latest = max(zf.infolist(), key=lambda i: i.date_time)
        return dt.datetime(*latest.date_time).isoformat(timespec="minutes")


def extract_csv_files(zip_bytes: bytes, county_prefix: str) -> dict[str, bytes]:
    """
    從季度 ZIP 中取出指定縣市的「主表」CSV：
    n_lvr_land_a.csv（買賣）、n_lvr_land_b.csv（預售屋）。
    不含 c（租賃，暫不分析）及 _build/_land/_park 附屬明細檔。
    """
    results = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            lower = name.lower()
            if lower in (f"{county_prefix}_lvr_land_a.csv", f"{county_prefix}_lvr_land_b.csv"):
                results[name] = zf.read(name)
    return results


def fetch_all() -> dict[str, dict[str, bytes]]:
    """
    抓取本季＋上季所有目標縣市 CSV。
    回傳 {season: {filename: csv_bytes}}，跳過尚未發布的季度。
    """
    out = {}
    for season in current_and_previous_seasons():
        zip_bytes = download_season(season)
        if zip_bytes is None:
            print(f"[download] {season} 尚未發布或無法取得，略過")
            continue
        build_time = extract_build_time(zip_bytes)
        csvs = extract_csv_files(zip_bytes, config.COUNTY_PREFIX)
        if not csvs:
            print(f"[download] {season} 找不到縣市 {config.COUNTY_PREFIX} 的 CSV")
            continue
        out[season] = {"build_time": build_time, "files": csvs}
        print(f"[download] {season} 取得 {len(csvs)} 個檔案，建置時間 {build_time}")
    return out
