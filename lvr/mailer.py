# -*- coding: utf-8 -*-
"""
Gmail SMTP 寄信模組。支援多收件人（逗號分隔）、附件、失敗告警信。
帳密一律從環境變數讀取，絕不寫死在程式碼中。
"""
from __future__ import annotations

import os
import smtplib
import traceback
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _recipients() -> list[str]:
    raw = os.environ.get("MAIL_TO", "")
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _send(subject: str, body: str, attachments: list[Path] | None = None) -> None:
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    to_list = _recipients()

    if not (user and password and to_list):
        print("[mailer] 缺少 GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO，無法寄信")
        return

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            continue
        with path.open("rb") as f:
            part = MIMEApplication(f.read(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, to_list, msg.as_string())
    print(f"[mailer] 已寄出：{subject} → {to_list}")


def send_report(subject: str, body: str, attachments: list[Path] | None = None) -> None:
    _send(subject, body, attachments)


def send_failure_alert(error: Exception) -> None:
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    subject = "【實價登錄快報】執行失敗警告"
    body = f"排程執行時發生錯誤，請檢查 GitHub Actions log。\n\n{tb}"
    try:
        _send(subject, body)
    except Exception as e:  # noqa: BLE001
        print(f"[mailer] 連失敗警告信都寄不出去：{e}")
