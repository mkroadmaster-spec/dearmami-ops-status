#!/usr/bin/env python
"""오늘의 브리핑을 Slack / 텔레그램으로 전송 (설정된 채널 모두).

  python scripts/notify.py [--date YYYY-MM-DD] [--weekly-docx]   # --weekly-docx: 주간 리포트 .docx 를 텔레그램으로 첨부
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cafe24_ops import config, pipeline  # noqa: E402
from cafe24_ops.alerts import digest  # noqa: E402
from cafe24_ops.clients import slack, telegram  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--weekly-docx", action="store_true")
    a = ap.parse_args()
    store = Store()
    d = a.date or pipeline.yesterday()
    dg = digest(store, d)
    brand = config.sources().get("brand", "")
    url = config.env("DASHBOARD_URL")

    plain = f"[{brand}] {d} 브리핑 — {dg['headline']}\n" + "\n".join(f"• {l}" for l in dg["lines"]) + (f"\n{url}" if url else "")
    print(plain)
    sent = []
    if slack.is_configured():
        sent.append(f"slack={'OK' if slack.send(plain) else '실패'}")
    if telegram.is_configured():
        tg = f"<b>[{html.escape(brand)}] {d} 브리핑 — {html.escape(dg['headline'])}</b>\n" + "\n".join(f"• {html.escape(l)}" for l in dg["lines"])
        sent.append(f"telegram={'OK' if telegram.send(tg) else '실패'}")
        if a.weekly_docx:
            from cafe24_ops import report_docx
            from cafe24_ops.etl import period_report
            data = period_report.weekly_report(store)
            ok = telegram.send_document(report_docx.build(data), f"weekly-report-{data['range']['from']}.docx", data["title"] + "\n" + data["headline"])
            sent.append(f"telegram_docx={'OK' if ok else '실패'}")
    print("\n전송:", ", ".join(sent) if sent else "(SLACK_WEBHOOK_URL / TELEGRAM_BOT_TOKEN 미설정 — 출력만)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
