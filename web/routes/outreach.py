"""Yonetici: davet e-postalari gonderme paneli ve abonelikten cikma sayfasi."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse

import config
from services import mailer, outreach
from services.database import db
from web.core import current_user, login_required, redirect, render

router = APIRouter()


def _admin(request):
    user = current_user(request)
    return user if user and user.get("username") in config.ADMIN_USERNAMES else None


def _page(request, **context):
    context.setdefault("subject", outreach.DEFAULT_SUBJECT)
    context.setdefault("body", outreach.DEFAULT_BODY)
    context.setdefault("code", "HOOPFRIENDS")
    context.setdefault("recipients", "")
    context.setdefault("resend", False)
    return render(request, "admin_outreach.html", active="account",
                  sender=config.OUTREACH_FROM, reply_to=config.OUTREACH_REPLY_TO,
                  sent_today=db.outreach_sent_today(), daily_limit=config.OUTREACH_DAILY_LIMIT,
                  max_per_send=outreach.MAX_PER_SEND, history=db.outreach_recent(),
                  email_signups=db.outreach_signups(), mail_ready=mailer.enabled(), **context)


@router.get("/admin/outreach")
def outreach_page(request: Request):
    gate = login_required(request)
    if gate:
        return gate
    if not _admin(request):
        return redirect("/account", "Admins only.", "error")
    return _page(request)


def _plan(people, resend):
    """Kime gidecek, kim neden atlanacak."""
    history = db.outreach_status([p["email"] for p in people])
    send, skipped = [], []
    for p in people:
        past = history.get(p["email"])
        if past and past["status"] == "unsubscribed":
            skipped.append((p, "unsubscribed"))
        elif past and past["status"] == "sent" and not resend:
            skipped.append((p, "already emailed"))
        else:
            send.append(p)
    return send, skipped


@router.post("/admin/outreach")
def outreach_send(request: Request, action: str = Form("preview"), recipients: str = Form(""),
                  subject: str = Form(""), body: str = Form(""), code: str = Form(""),
                  resend: str = Form(None)):
    admin = _admin(request)
    if not admin:
        return redirect("/account", "Admins only.", "error")
    subject = subject.strip()[:150] or outreach.DEFAULT_SUBJECT
    body = body.strip() or outreach.DEFAULT_BODY
    code = "".join(ch for ch in code.upper() if ch.isalnum() or ch in "-_")[:32]
    form = {"recipients": recipients, "subject": subject, "body": body, "code": code,
            "resend": bool(resend)}

    if action == "test":
        me = {"email": admin["email"], "name": admin.get("username") or ""}
        ok, error = mailer.send_batch([outreach.message(me, subject, body, code)])
        if ok:
            return _page(request, notice=f"Test email sent to {me['email']}.", **form)
        return _page(request, error=f"Test email failed: {error}", **form)

    people, bad = outreach.parse_recipients(recipients)
    send, skipped = _plan(people, bool(resend))
    if not people:
        return _page(request, error="Add at least one email address.", bad=bad, **form)
    if len(send) > outreach.MAX_PER_SEND:
        return _page(request, error=f"At most {outreach.MAX_PER_SEND} people per send. Split the list.",
                     bad=bad, **form)
    left = config.OUTREACH_DAILY_LIMIT - db.outreach_sent_today()
    if len(send) > left:
        return _page(request, error=f"Today's limit leaves room for {max(0, left)} more emails. "
                                    "Send the rest tomorrow.", bad=bad, **form)

    if action != "send":
        preview = outreach.render(send[0] if send else people[0], subject, body, code)
        return _page(request, preview=preview, to_send=send, skipped=skipped, bad=bad, **form)

    if not send:
        return _page(request, error="Nobody left to email in this list.", skipped=skipped, bad=bad, **form)
    ok, error = mailer.send_batch([outreach.message(p, subject, body, code) for p in send])
    for p in send:
        db.outreach_record(p["email"], p["name"], ok, error)
    if not ok:
        return _page(request, error=f"Sending failed: {error}", bad=bad, **form)
    form["recipients"] = ""
    return _page(request, notice=f"Sent to {len(send)} people."
                 + (f" Skipped {len(skipped)}." if skipped else ""), skipped=skipped, bad=bad, **form)


# ==================== ZIYARETCILER ====================

def _flag(iso):
    iso = (iso or "").upper()
    if len(iso) != 2 or not iso.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in iso)


@router.get("/admin/visitors")
def visitors_page(request: Request, days: int = 7):
    gate = login_required(request)
    if gate:
        return gate
    if not _admin(request):
        return redirect("/account", "Admins only.", "error")
    days = days if days in (1, 7, 30, 90) else 7
    report = db.visitor_report(days)
    for row in report["countries"]:
        row["flag"] = _flag(row.get("iso"))
    total = sum(r["visitors"] for r in report["countries"]) or 1
    for row in report["countries"]:
        row["share"] = round(100 * row["visitors"] / total)
    return render(request, "admin_visitors.html", active="account", days=days, r=report)


# ==================== ABONELIKTEN CIKMA ====================

@router.get("/unsubscribe")
def unsubscribe_page(request: Request, e: str = "", t: str = ""):
    email = outreach.verify_unsubscribe(e, t)
    return render(request, "unsubscribe.html", email=email, e=e, t=t, done=False)


@router.post("/unsubscribe")
def unsubscribe(request: Request, e: str = "", t: str = ""):
    """
    Hem sayfadaki buton hem de e-posta istemcilerinin tek tikla cikma
    istegi (List-Unsubscribe-Post) buraya gelir.
    """
    email = outreach.verify_unsubscribe(e, t)
    if not email:
        return PlainTextResponse("Invalid link.", status_code=400)
    db.outreach_unsubscribe(email)
    return render(request, "unsubscribe.html", email=email, e=e, t=t, done=True)
