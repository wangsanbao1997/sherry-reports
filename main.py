# -*- coding: utf-8 -*-
"""
實價登錄監測快報 v2 主程式。

流程：
1. 下載本季＋上季資料（跳過假 200／尚未發布的季度）
2. 解析出目標五鄉鎮交易
3. 與 seen_ids 比對，找出新增交易
4. 寫入歷史庫（供中位數與趨勢分析）
5. 分析：中位數偏離判斷（依使用分區分開統計）
6. 產出趨勢圖、PDF 報告、手機版 HTML 報告
7. 選用：AI 行情觀察摘要
8. 寄信（無新增時依設定決定是否寄「系統正常」通知）
9. 更新狀態（seen_ids、meta）
"""
from __future__ import annotations

import datetime as dt
import os
import sys

from lvr import config, download, parse, store, analyze, charts, report_pdf, report_html, ai_summary, mailer


def run() -> None:
    today = dt.date.today().isoformat()
    send_empty = os.environ.get("SEND_EMPTY", "true").lower() == "true"

    print(f"[main] 開始執行，日期 {today}")

    # 1. 下載
    fetched = download.fetch_all()
    if not fetched:
        print("[main] 本季與上季皆無法取得資料，本次略過（不視為錯誤，可能尚未發布）")
        return

    latest_build = max(payload["build_time"] for payload in fetched.values())

    # 2. 解析
    all_records = parse.parse_all(fetched)
    print(f"[main] 共解析出 {len(all_records)} 筆目標鄉鎮交易（含已比對過的）")

    # 3. 比對新增
    seen = store.load_seen_ids()
    first_run = len(seen) == 0
    new_records = [r for r in all_records if r.rec_id not in seen]

    build_times = {s: p["build_time"] for s, p in fetched.items()}

    if first_run:
        print("[main] 首次執行：以目前資料建立基準，全部視為新增")

    # 4. 歷史庫先寫入（含本次新增），趨勢與中位數基準才會即時
    history_before = store.load_history()
    store.append_history(new_records)

    summary = {
        "total": len(new_records),
        "by_town": {t: sum(1 for r in new_records if r.town == t)
                    for t in config.TARGET_TOWNS},
        "special": sum(1 for r in new_records if r.is_special),
        "build_time": latest_build,
        "report_date": today,
    }

    # 5. 無新增：更新狀態後視設定寄通知
    if not new_records:
        _finalize(seen, all_records, build_times)
        print("[main] 本次無新增交易")
        if send_empty:
            mailer.send_report(
                f"【實價登錄】{today} 無新增交易",
                f"系統運作正常。資料建置時間 {latest_build}，"
                "本期五鄉鎮無新增交易紀錄。",
            )
        return

    # 6. 分析（偏離判斷用「本次之前」的歷史當基準，避免自己跟自己比）
    assessments = analyze.assess(new_records, history_before)

    # 7. 每鄉鎮獨立成交量／金額趨勢圖（用含本次的完整歷史）
    full_history = store.load_history()
    town_charts = charts.town_volume_charts(full_history, config.OUTPUT_DIR)

    # 8. AI 行情觀察（選用）
    ai_text = ai_summary.generate(assessments, summary)

    # 9. 報告
    pdf_path = report_pdf.build_pdf(
        assessments, summary, town_charts, ai_text,
        config.OUTPUT_DIR / f"實價登錄日報_{today}.pdf",
        is_first_run=first_run)
    html_path = report_html.build_html(
        assessments, summary, town_charts, ai_text, config.OUTPUT_DIR)

    # 10. 寄信
    flagged = sum(1 for a in assessments if a.flag.startswith("【推估】"))
    body = (f"本期新增 {summary['total']} 筆交易"
            f"（{'、'.join(f'{t} {n} 筆' for t, n in summary['by_town'].items() if n)}）。\n"
            f"其中 {flagged} 筆價格明顯偏離區域中位數，已於報告標記。\n\n"
            f"附件：PDF 報告（列印用）、HTML 報告（手機開啟，可轉傳客戶）。\n"
            f"資料建置時間：{latest_build}\n\n{config.DISCLAIMER}")
    if first_run:
        body = "【首次執行】以下為基準清單，之後僅通知新增部分。\n\n" + body
    mailer.send_report(
        f"【實價登錄】{today} 新增 {summary['total']} 筆"
        + (f"｜{flagged} 筆價格異常" if flagged else ""),
        body, [pdf_path, html_path])

    # 11. 更新狀態
    _finalize(seen, all_records, build_times)


def _finalize(seen: set, all_records: list, build_times: dict) -> None:
    seen.update(r.rec_id for r in all_records)
    store.save_seen_ids(seen)
    store.save_meta({
        "build_times": build_times,
        "last_run": dt.datetime.now().isoformat(timespec="seconds"),
    })
    print("[main] 狀態已更新。")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:  # noqa: BLE001
        mailer.send_failure_alert(e)
        print(f"[main] 執行失敗：{e}", file=sys.stderr)
        raise
