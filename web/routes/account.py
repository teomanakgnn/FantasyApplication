"""Hesap ayarlari: profil, plan, parola, eposta, cihazlar, gorunum, silme."""
from datetime import datetime

from fastapi import APIRouter, Form, Request

import config
from web.plans import PRO_FEATURES, UPGRADE_NOTE
from services.database import (FREE_SAVED_DRAFT_LIMIT, FREE_WATCHLIST_LIMIT,
                               PLAN_FREE, PLAN_PRO, db)
from web.core import (clear_session_cookie, current_user, forget_user_cache,
                      login_required, redirect, render)

router = APIRouter()


def _device(agent):
    """Uzun user-agent metnini okunur bir cihaz adina indirger."""
    agent = str(agent or "")
    base = "Browser"
    for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                      ("Macintosh", "Mac"), ("Windows", "Windows"), ("Linux", "Linux")):
        if key in agent:
            base = name
            break
    for key, name in (("Edg", "Edge"), ("Chrome", "Chrome"), ("Firefox", "Firefox"),
                      ("Safari", "Safari")):
        if key in agent:
            return f"{base} · {name}"
    return base


@router.get("/account")
def account(request: Request):
    gate = login_required(request)
    if gate:
        return gate
    user = current_user(request)
    sessions = db.list_sessions(user["id"])
    for s in sessions:
        s["device"] = _device(s.get("user_agent"))
    return render(
        request, "account.html", active="account",
        features=PRO_FEATURES, upgrade_note=UPGRADE_NOTE,
        watch_count=db.watchlist_count(user["id"]),
        draft_count=db.saved_draft_count(user["id"]),
        watch_limit=FREE_WATCHLIST_LIMIT, draft_limit=FREE_SAVED_DRAFT_LIMIT,
        sessions=sessions, display=db.get_score_display_preference(user["id"]),
        is_admin=user.get("username") in config.ADMIN_USERNAMES,
        plans=(PLAN_PRO, PLAN_FREE), now=datetime.now())


@router.post("/account/password")
def change_password(request: Request, current: str = Form(""), new: str = Form(""),
                    again: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect("/login")
    if new != again:
        return redirect("/account#security", "The two new passwords do not match.", "error")
    ok, message = db.change_password(user["id"], current, new)
    if not ok:
        return redirect("/account#security", message, "error")
    forget_user_cache()
    response = redirect("/login", "Password updated. Sign in with your new password.")
    clear_session_cookie(response)
    return response


@router.post("/account/email")
def change_email(request: Request, email: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect("/login")
    ok, message = db.update_email(user["id"], email)
    if ok:
        forget_user_cache(request.cookies.get("hl_session"))
    return redirect("/account#security", message, "ok" if ok else "error")


@router.post("/account/sessions")
def sign_out_others(request: Request):
    user = current_user(request)
    if not user:
        return redirect("/login")
    db.logout_other_sessions(user["id"], request.cookies.get("hl_session"))
    forget_user_cache()
    return redirect("/account#devices", "Other devices have been signed out.")


@router.post("/account/display")
def display(request: Request, mode: str = Form("full")):
    user = current_user(request)
    if not user:
        return redirect("/login")
    mode = "spoiler_protected" if mode == "spoiler_protected" else "full"
    if not db.update_score_display_preference(user["id"], mode):
        return redirect("/account#display", "Could not save that preference. Try again.", "error")
    return redirect("/account#display", "Display preference saved.")


@router.post("/account/grant")
def grant(request: Request, username: str = Form(""), days: int = Form(365),
          plan: str = Form(PLAN_PRO)):
    user = current_user(request)
    if not user or user.get("username") not in config.ADMIN_USERNAMES:
        return redirect("/account", "Admins only.", "error")
    row = db._run("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)",
                  (username.strip(),), fetch="one")
    if not row:
        return redirect("/account#admin", "No user with that username.", "error")
    if db.set_plan(row["id"], plan, days=int(days) or None):
        forget_user_cache()
        return redirect("/account#admin", f"{username} is now on the {plan} plan.")
    return redirect("/account#admin", "Could not update that account.", "error")


@router.post("/account/delete")
def delete(request: Request, confirm: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect("/login")
    if confirm.strip() != user.get("username"):
        return redirect("/account#delete", "The username does not match.", "error")
    if not db.delete_account(user["id"]):
        return redirect("/account#delete", "Could not delete the account. Try again.", "error")
    forget_user_cache()
    response = redirect("/", "Your account has been deleted.")
    clear_session_cookie(response)
    return response
