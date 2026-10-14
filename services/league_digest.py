"""
My League e-posta uyarilari.

Gunde bir kez (15:00 UTC; ABD'de maclar ve kadro kilidinden once) e-posta
uyarisi acik her ESPN ligi icin uyarilar hesaplanir. Daha once gonderilen
uyari tekrar gitmez (league_alert_log), yeni bir sey yoksa e-posta yok.

Zamanlayici uygulamanin icindeki bir is parcacigi: tek sunucu calistigi icin
yeterli. Yeniden baslatma ayni saatte olursa tekrar calisir ama kayit
tablosu ayni uyariyi ikinci kez gondermez.
"""
import html
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

import config
from services import mailer
from services.database import db

RUN_HOUR_UTC = 15


def run_once():
    """Bekleyen uyarilari gonderir. (gonderilen e-posta, uyari) sayisi doner."""
    from services import league_insights as li
    by_user = defaultdict(list)
    for row in db.alert_digest_targets():
        by_user[(row["user_id"], row["email"], row["username"])].append(row)
    mails = alerts_sent = 0
    for (user_id, email, username), leagues in by_user.items():
        sections, keys = [], []
        for lg in leagues:
            try:
                r = li.build(int(lg["league_ref"]), lg["team_id"])
            except Exception as exc:
                print(f"digest: league {lg['league_ref']} failed: {exc}")
                continue
            items = r.get("alerts") or []
            fresh_keys = db.unsent_alert_keys(user_id, [f"{lg['id']}:{a['key']}" for a in items])
            fresh = [a for a in items if f"{lg['id']}:{a['key']}" in fresh_keys]
            if fresh:
                sections.append((lg, r, fresh))
                keys += [f"{lg['id']}:{a['key']}" for a in fresh]
        if not sections:
            continue
        if mailer.send(email, _subject(sections), _html(username, sections), text=_text(sections)):
            db.log_alerts(user_id, keys)
            mails += 1
            alerts_sent += len(keys)
    return mails, alerts_sent


def _subject(sections):
    n = sum(len(f) for _, _, f in sections)
    first = sections[0][2][0]["text"]
    return f"HoopLife: {n} thing{'s' if n != 1 else ''} to check - {first[:60]}{'…' if len(first) > 60 else ''}"


def _html(username, sections):
    base = config.SITE_URL.rstrip("/")
    color = {"bad": "#D0112B", "warn": "#B7791F", "good": "#1E9E5A"}
    parts = [f"<p>Hi {html.escape(username or '')},</p><p>Here is what changed in your leagues:</p>"]
    for lg, r, fresh in sections:
        me = r.get("me") or {}
        parts.append(f"<h3 style='margin:18px 0 6px'>{html.escape(r['name'])} "
                     f"<span style='color:#777;font-weight:400'>· {html.escape(me.get('name', ''))}</span></h3>")
        for a in fresh:
            parts.append(f"<p style='margin:6px 0;padding:8px 10px;border-left:3px solid {color[a['level']]};"
                         f"background:#f6f6f6'>{html.escape(a['text'])}</p>")
        parts.append(f"<p><a href='{base}/league/my/{lg['id']}'>Open {html.escape(r['name'])} on HoopLife</a></p>")
    parts.append(f"<p style='color:#777;font-size:12px;margin-top:24px'>You get this because email alerts are on "
                 f"for these leagues. Turn them off on <a href='{base}/league'>My Leagues</a>.</p>")
    return f"<div style='font-family:Arial,sans-serif;font-size:15px;line-height:1.5;color:#111'>{''.join(parts)}</div>"


def _text(sections):
    base = config.SITE_URL.rstrip("/")
    lines = []
    for lg, r, fresh in sections:
        lines.append(r["name"])
        lines += [f"- {a['text']}" for a in fresh]
        lines.append(f"{base}/league/my/{lg['id']}\n")
    lines.append(f"Turn alerts off: {base}/league")
    return "\n".join(lines)


def _loop():
    last = None
    while True:
        now = datetime.now(timezone.utc)
        if now.hour == RUN_HOUR_UTC and last != now.date():
            last = now.date()
            try:
                print("league digest:", run_once())
            except Exception as exc:
                print(f"league digest failed: {exc}")
        time.sleep(600)


def start():
    if not (mailer.enabled() and db.available):
        return
    threading.Thread(target=_loop, daemon=True, name="league-digest").start()
