# -*- coding: utf-8 -*-
"""
選用：呼叫 Anthropic API 產出行情觀察摘要文字。
未設定 ANTHROPIC_API_KEY 時直接略過（回傳 None），不影響主流程。

依法規避免使用「估價」用語，並在輸出中明確標示需人工審核。
"""
from __future__ import annotations

import os

from .analyze import Assessment

SYSTEM_PROMPT = """你是一位協助房仲彙整市場資訊的助手。根據提供的交易評估資料，
寫一段 150-220 字的「行情觀察」，語氣專業、平實、不誇大。

嚴格規則：
- 絕對不要使用「估價」「鑑價」「行情價」等具法律意涵的詞彙，一律用「行情觀察」「交易資訊」代替
- 只描述資料呈現的客觀現象（如：某鄉鎮本期交易件數、與歷史中位數的差異），不做投資建議
- 不預測未來房價走勢
- 標記為【推估】的交易，用詞要保留（如「觀察到」「可能與」），不要斷言
- 結尾提醒讀者：本段落為 AI 輔助生成之觀察，正式判斷仍應以實際看屋與專業意見為準
"""


def generate(assessments: list[Assessment], summary: dict) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ai_summary] 未設定 ANTHROPIC_API_KEY，略過 AI 摘要")
        return None

    try:
        import anthropic
    except ImportError:
        print("[ai_summary] anthropic 套件未安裝，略過")
        return None

    lines = []
    for a in assessments[:30]:
        r = a.record
        lines.append(
            f"{r.town}｜{r.building_type}｜{r.trade_date}｜"
            f"{r.unit_price_ping:.0f}元/坪｜{a.flag}"
        )
    data_text = "\n".join(lines)

    user_prompt = (
        f"本期新增交易 {summary['total']} 筆，"
        f"分布：{summary['by_town']}。\n\n交易明細：\n{data_text}\n\n"
        "請依規則寫一段行情觀察。"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return text.strip() or None
    except Exception as e:  # noqa: BLE001
        print(f"[ai_summary] API 呼叫失敗，略過：{e}")
        return None
