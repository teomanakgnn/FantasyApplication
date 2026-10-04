"""Giris, kayit, cikis."""
import html
import time
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Form, Request

import config
from services import mailer
from services.database import LOGIN_WINDOW_MINUTES, db
from web.core import (CODE_COOKIE, SIGNUP_COOKIE, SOURCE_COOKIE, clear_session_cookie, client_ip,
                      current_user, forget_user_cache, redirect, render, set_session_cookie)

router = APIRouter()


def _safe_next(target):
    """Giristen sonra yalnizca bu sitenin bir sayfasina donulur."""
    if not target:
        return "/"
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


@router.get("/login")
def login_page(request: Request, next: str = "/"):
    if current_user(request):
        return redirect(_safe_next(next))
    return render(request, "login.html", mode="login", next=_safe_next(next), form={})


@router.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form(""),
          remember: str = Form(None), next: str = Form("/")):
    target = _safe_next(next)
    form = {"username": username}
    if not username.strip() or not password:
        return render(request, "login.html", mode="login", next=target, form=form,
                      error="Enter your username and password.", status_code=400)
    if not db.available:
        return render(request, "login.html", mode="login", next=target, form=form,
                      error="Sign-in is unavailable right now. Try again shortly.",
                      status_code=503)
    ip = client_ip(request)
    user = db.verify_user(username.strip(), password, ip_address=ip)
    if user == "locked":
        return render(request, "login.html", mode="login", next=target, form=form,
                      error=f"Too many failed attempts. Try again in {LOGIN_WINDOW_MINUTES} minutes.",
                      status_code=429)
    if not user:
        return render(request, "login.html", mode="login", next=target, form=form,
                      error="Incorrect username or password.", status_code=401)
    session = db.create_session(user["id"], browser_id="web", ip_address=ip,
                                user_agent=request.headers.get("user-agent", "")[:300])
    if not session:
        return render(request, "login.html", mode="login", next=target, form=form,
                      error="Could not start a session. Try again.", status_code=500)
    response = redirect(target, f"Welcome back, {user['username']}.")
    set_session_cookie(response, session["token"], remember=bool(remember))
    return response


def _turnstile_ok(request, token):
    """
    Kayit formundaki bot dogrulamasi (Cloudflare Turnstile).

    Anahtar tanimli degilse dogrulama kapali sayilir. Cloudflare'e
    ulasilamazsa kayit engellenmez: gercek kullaniciyi disarida birakmak,
    arada bir botu iceri almaktan daha kotu.
    """
    if not config.TURNSTILE_SECRET_KEY:
        return True
    if not token:
        return False
    try:
        resp = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                             data={"secret": config.TURNSTILE_SECRET_KEY, "response": token,
                                   "remoteip": client_ip(request)}, timeout=8)
        return bool(resp.json().get("success"))
    except Exception as exc:
        print(f"turnstile check failed: {exc}")
        return True


@router.get("/register")
def register_page(request: Request):
    if current_user(request):
        return redirect("/")
    code = request.query_params.get("code") or request.cookies.get(CODE_COOKIE) or ""
    return render(request, "login.html", mode="register", next="/", form={"code": code[:32]},
                  turnstile=config.TURNSTILE_SITE_KEY)


@router.post("/register")
def register(request: Request, username: str = Form(""), email: str = Form(""),
             password: str = Form(""), password2: str = Form(""), terms: str = Form(None),
             code: str = Form(""),
             turnstile_token: str = Form("", alias="cf-turnstile-response")):
    form = {"username": username, "email": email, "code": code}

    def fail(message, code=400):
        return render(request, "login.html", mode="register", next="/", form=form,
                      error=message, status_code=code, turnstile=config.TURNSTILE_SITE_KEY)

    if not _turnstile_ok(request, turnstile_token):
        return fail("Please confirm you are not a robot and try again.")

    if not all([username.strip(), email.strip(), password, password2]):
        return fail("Fill in every field.")
    if password != password2:
        return fail("The two passwords do not match.")
    if not terms:
        return fail("Accept the terms to continue.")
    valid, message = db.validate_registration(username, email, password)
    if not valid:
        return fail(message)
    if not db.available:
        return fail("Registration is unavailable right now. Try again shortly.", 503)
    ok, message = db.create_user(username, email, password)
    if not ok:
        return fail(message)

    # Hesap acilinca dogrudan giris: eskiden "simdi Sign In sekmesine gec"
    # deniyordu ve kullanici her seyi ikinci kez yaziyordu.
    user = db.verify_user(username.strip(), password, ip_address=client_ip(request))
    if not user or user == "locked":
        return redirect("/login", "Account created. Sign in to continue.")
    session = db.create_session(user["id"], browser_id="web", ip_address=client_ip(request),
                                user_agent=request.headers.get("user-agent", "")[:300])
    source = request.cookies.get(SOURCE_COOKIE)
    if source:
        db.set_signup_source(user["id"], source)
    message = f"Welcome to HoopLife, {user['username']}."
    code = (code or request.cookies.get(CODE_COOKIE) or "").strip()
    if code:
        redeemed, note = db.redeem_promo_code(user["id"], code)
        message += " " + (note if redeemed else f"The invite code did not work: {note}")
    response = redirect("/", message)
    response.delete_cookie(CODE_COOKIE, path="/")
    response.set_cookie(SIGNUP_COOKIE, "1", max_age=600, httponly=True,
                        secure=config.PRODUCTION, samesite="lax", path="/")
    if session:
        set_session_cookie(response, session["token"], remember=True)
    return response


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get("hl_session")
    if token:
        db.logout_session(token)
        forget_user_cache(token)
    response = redirect("/", "You are signed out.")
    clear_session_cookie(response)
    return response


# ==================== SIFRE SIFIRLAMA ====================

_reset_hits = {}


def _throttled(key, limit, window=3600):
    now = time.time()
    hits = [t for t in _reset_hits.get(key, []) if now - t < window]
    if len(hits) >= limit:
        _reset_hits[key] = hits
        return True
    hits.append(now)
    _reset_hits[key] = hits
    return False


@router.get("/forgot-password")
def forgot_page(request: Request):
    return render(request, "password.html", mode="forgot", mail_ready=mailer.reset_enabled())


@router.post("/forgot-password")
def forgot(request: Request, email: str = Form("")):
    email = email.strip().lower()
    # Hesap olsun olmasin ayni cevap: kimin kayitli oldugu buradan ogrenilemez.
    done = render(request, "password.html", mode="sent", email=email)
    if not mailer.reset_enabled():
        return render(request, "password.html", mode="forgot", mail_ready=False,
                      error="Password reset by email is not available yet.")
    if _throttled(f"ip:{client_ip(request)}", 8) or _throttled(f"mail:{email}", 3):
        return done
    user, raw = db.create_password_reset(email)
    if user and raw:
        link = f"{config.SITE_URL.rstrip('/')}/reset-password?token={raw}"
        name = html.escape(user.get("username") or "")
        mailer.send(
            user["email"], "Reset your HoopLife NBA password",
            f"<p>Hi {name},</p><p>Someone asked to reset the password for your HoopLife NBA "
            f"account. The link works for 60 minutes and only once:</p>"
            f"<p><a href=\"{link}\" style=\"background:#D0112B;color:#fff;padding:10px 16px;"
            f"border-radius:8px;text-decoration:none;font-weight:600\">Choose a new password</a></p>"
            f"<p>If you did not ask for this, ignore this email - your password stays the same.</p>",
            text=f"Reset your HoopLife NBA password (valid 60 minutes): {link}")
    return done


@router.get("/reset-password")
def reset_page(request: Request, token: str = ""):
    return render(request, "password.html", mode="reset", token=token,
                  valid=db.reset_token_valid(token))


@router.post("/reset-password")
def reset(request: Request, token: str = Form(""), password: str = Form(""),
          password2: str = Form("")):
    if password != password2:
        return render(request, "password.html", mode="reset", token=token, valid=True,
                      error="The two passwords do not match.")
    ok, message = db.reset_password(token, password)
    if not ok:
        return render(request, "password.html", mode="reset", token=token,
                      valid=db.reset_token_valid(token), error=message)
    forget_user_cache()
    response = redirect("/login", message)
    clear_session_cookie(response)
    return response
