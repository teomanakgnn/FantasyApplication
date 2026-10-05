"""
Davet e-postalari: yoneticinin girdigi kisilere tek tek, kisisel e-posta.

Her alici ayri bir e-posta alir (To'da yalnizca kendi adresi), adiyla
hitap edilir ve altta abonelikten cikma linki vardir. Cikan kisiye bir
daha gonderilmez; daha once gonderilmis kisiye de yonetici ozellikle
istemedikce tekrar gonderilmez. Gonderim Resend'in toplu (batch)
ucundan tek istekte yapiliyor; 15-20 kisi bir saniyede gider.

Duz metin gibi duran sade bir HTML kullaniliyor: kisisel bir mektup
gibi okunsun ve spam filtrelerine "bulten" gibi gorunmesin.
"""
import base64
import hashlib
import hmac
import html
import re

import config

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAX_PER_SEND = 50

DEFAULT_SUBJECT = "A free fantasy basketball draft tool I built"

DEFAULT_BODY = """Hi {name},

I'm Teoman, a developer from Turkey and a long-time fantasy basketball player. I built HoopLife NBA, a free set of tools for 9-cat leagues:

- a mock draft simulator against AI managers (snake or auction)
- a draft strategy page that tests punt builds from your pick slot
- a trade analyzer and a daily "guess the player" game

The core of the site is free. If you sign up with the link below, your account gets Pro (player trends, extra punt builds, unlimited saved drafts) at no cost:

{link}

The season tips off on October 20, so this is a good week to run a few mock drafts. If you try it, I'd love to hear what works and what doesn't - just reply to this email.

Thanks,
Teoman
HoopLife NBA"""


def parse_recipients(raw):
    """
    Her satirda bir kisi: "Ad, e-posta", "Ad <e-posta>", "e-posta, Ad" ya da
    yalnizca "e-posta". (kisiler, hatali satirlar) doner; ayni adres bir kez.
    """
    people, bad, seen = [], [], set()
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = EMAIL_RE.search(line)
        if not match:
            bad.append(line)
            continue
        email = match.group(0).lower()
        name = (line[:match.start()] + " " + line[match.end():])
        name = re.sub(r"[<>,;\t\"]+", " ", name).strip()
        name = re.sub(r"\s+", " ", name)[:60]
        if email in seen:
            continue
        seen.add(email)
        people.append({"email": email, "name": name})
    return people, bad


def _token(email):
    return hmac.new(config.SECRET_KEY.encode(), email.lower().encode(), hashlib.sha256).hexdigest()[:32]


def unsubscribe_url(email):
    e = base64.urlsafe_b64encode(email.lower().encode()).decode().rstrip("=")
    return f"{config.SITE_URL.rstrip('/')}/unsubscribe?e={e}&t={_token(email)}"


def verify_unsubscribe(e, t):
    """Linkteki adres ve imza dogruysa adresi doner."""
    try:
        email = base64.urlsafe_b64decode(e + "=" * (-len(e) % 4)).decode()
    except Exception:
        return None
    return email if hmac.compare_digest(_token(email), t or "") else None


def signup_link(code):
    base = config.SITE_URL.rstrip("/")
    code_part = f"code={code}&" if code else ""
    return f"{base}/register?{code_part}utm_source=email&utm_medium=outreach"


def _greeting_name(name, turkish):
    """Listede nasil yazildiysa oyle hitap edilir ("Levent", "Socrates Dergi ekibi")."""
    name = (name or "").strip()
    if name and not EMAIL_RE.search(name):
        return name
    return "" if turkish else "there"


def _is_turkish(text):
    return any(ch in text for ch in "ğışçöüĞİŞÇÖÜ")


def render(person, subject, body, code):
    """Bir kisiye gidecek konu, duz metin ve HTML."""
    link = signup_link(code)
    turkish = _is_turkish(body)
    name = _greeting_name(person.get("name"), turkish)
    text = body.replace(" {name},", f" {name}," if name else ",").replace("{name}", name)
    text = text.replace("{link}", link)
    unsub = unsubscribe_url(person["email"])
    if turkish:
        footer = ("Bu e-postayı bir kez, uygulamanın ilginizi çekebileceğini düşündüğüm için gönderdim. "
                  "Bir daha e-posta almak istemezseniz: ")
    else:
        footer = ("You're getting this one-off email because I thought you might find the app useful. "
                  "If you'd rather not hear from me again: ")
    text_full = f"{text}\n\n--\n{footer}{unsub}"

    paragraphs = []
    for block in html.escape(text).split("\n\n"):
        block = block.replace("\n", "<br>")
        block = block.replace(html.escape(link), f'<a href="{html.escape(link)}">{html.escape(link)}</a>')
        paragraphs.append(f"<p style=\"margin:0 0 14px\">{block}</p>")
    html_body = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a;max-width:560px\">"
        + "".join(paragraphs)
        + f"<p style=\"margin:24px 0 0;font-size:12px;color:#777\">{html.escape(footer)}"
          f"<a href=\"{html.escape(unsub)}\" style=\"color:#777\">{'abonelikten çık' if turkish else 'unsubscribe'}</a>.</p></div>")
    return {"subject": subject.replace("{name}", name), "text": text_full, "html": html_body,
            "unsubscribe": unsub}


def message(person, subject, body, code):
    """Resend batch icin tek mesaj."""
    r = render(person, subject, body, code)
    return {
        "from": config.OUTREACH_FROM,
        "to": [person["email"]],
        "reply_to": config.OUTREACH_REPLY_TO,
        "subject": r["subject"],
        "html": r["html"],
        "text": r["text"],
        "headers": {
            "List-Unsubscribe": f"<{r['unsubscribe']}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }
