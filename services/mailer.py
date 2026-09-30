"""
E-posta gonderimi (Resend).

RESEND_API_KEY tanimli degilse hicbir sey gonderilmez ve False doner;
uygulama e-posta olmadan da calisir (sifre sifirlama ekrani bunu
kullaniciya soyler).
"""
import threading
import time

import requests

import config

API = "https://api.resend.com/emails"


def enabled():
    return bool(config.RESEND_API_KEY)


def reset_enabled():
    """Sifre sifirlama e-postasi gonderilebilir mi (alan adi dogrulandi mi)?"""
    return enabled() and config.PASSWORD_RESET_EMAIL


def send(to, subject, html, text=None, sender=None):
    if not enabled():
        print(f"email skipped (no RESEND_API_KEY): {subject}")
        return False
    try:
        resp = requests.post(API, timeout=15, headers={
            "Authorization": f"Bearer {config.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }, json={"from": sender or config.MAIL_FROM, "to": [to], "subject": subject,
                 "html": html, **({"text": text} if text else {})})
        if resp.status_code >= 300:
            print(f"email failed {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as exc:
        print(f"email failed: {exc}")
        return False


# ==================== HATA BILDIRIMI ====================

_last_alert = {}
_ALERT_GAP = 15 * 60   # ayni hata icin en fazla 15 dakikada bir e-posta


def alert(title, detail):
    """
    Sunucu hatasini yoneticiye e-postayla bildirir.

    Ayni hata art arda tekrarlarsa gelen kutusu dolmasin diye ayni
    baslik 15 dakikada bir gonderilir. Istek beklemesin diye arka planda.
    """
    if not (enabled() and config.ALERT_EMAIL):
        return
    now = time.time()
    if now - _last_alert.get(title, 0) < _ALERT_GAP:
        return
    _last_alert[title] = now
    body = (f"<p><b>{_esc(title)}</b></p><pre style='white-space:pre-wrap;font-size:12px'>"
            f"{_esc(detail[-6000:])}</pre><p>HoopLife NBA - app.hooplifenba.com</p>")
    threading.Thread(target=send, args=(config.ALERT_EMAIL, f"[HoopLife] {title[:120]}", body),
                     kwargs={"sender": config.ALERT_FROM}, daemon=True).start()


def _esc(value):
    import html
    return html.escape(str(value))
