# -*- coding: utf-8 -*-
"""
系統設定檔。
"""
from pathlib import Path

# ── 目標區域 ──────────────────────────────────────────
# 內政部實價登錄縣市代碼：彰化縣 = n
COUNTY_PREFIX = "n"
TARGET_TOWNS = ["溪湖鎮", "埔心鄉", "埤頭鄉", "埔鹽鄉", "秀水鄉"]

# ── 路徑 ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT_DIR / "state"
OUTPUT_DIR = ROOT_DIR / "output"
FONT_DIR = ROOT_DIR / "fonts"

SEEN_IDS_PATH = STATE_DIR / "seen_ids.json"
META_PATH = STATE_DIR / "meta.json"
HISTORY_PATH = STATE_DIR / "history.csv"

FONT_REGULAR = FONT_DIR / "NotoSansTC-Regular.ttf"
FONT_BOLD = FONT_DIR / "NotoSansTC-Bold.ttf"

# ── 分析參數 ──────────────────────────────────────────
# 與近 12 個月同鄉鎮、同使用分區類別中位數相比，超過此比例標記為【推估】偏離
DEVIATION_THRESHOLD = 0.30
TREND_MONTHS = 12
MIN_SAMPLE_FOR_MEDIAN = 3  # 樣本數不足時不判斷偏離

# ── 內政部開放資料 ────────────────────────────────────
DOWNLOAD_BASE_URL = "https://plvr.land.moi.gov.tw/DownloadSeason"
DOWNLOAD_TIMEOUT = 60
DOWNLOAD_RETRIES = 4
DOWNLOAD_RETRY_WAIT_BASE = 5  # 秒，遞增等待

# ── 免責聲明 ──────────────────────────────────────────
DISCLAIMER = (
    "本報告內容為內政部實價登錄公開資料之整理與行情分析，"
    "非「不動產估價師法」所稱之估價報告，亦非正式鑑價文件，"
    "僅供參考，實際交易應以買賣雙方協議及專業估價為準。"
)
