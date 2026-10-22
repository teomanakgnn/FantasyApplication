"""Giris, kayit, cikis."""
import html
import time
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Form, Request

import config
from services import mailer
from services.database import LOGIN_WINDOW_MINUTES, db
from web.core import (CODE_COOKIE, INVITE_COOKIE, SIGNUP_COOKIE, SOURCE_COOKIE, clear_session_cookie, client_ip,
                      current_user, forget_user_cache, redirect, render, set_session_cookie)

router = APIRouter()
REFERRAL_DAYS = 30


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
def register_page(request: Request, next: str = "/"):
    if current_user(request):
        return redirect(_safe_next(next))
    code = request.query_params.get("code") or request.cookies.get(CODE_COOKIE) or ""
    return render(request, "login.html", mode="register", next=_safe_next(next), form={"code": code[:32]},
                  turnstile=config.TURNSTILE_SITE_KEY)


@router.post("/register")
def register(request: Request, username: str = Form(""), email: str = Form(""),
             password: str = Form(""), password2: str = Form(""), terms: str = Form(None),
             code: str = Form(""), next: str = Form("/"),
             turnstile_token: str = Form("", alias="cf-turnstile-response")):
    form = {"username": username, "email": email, "code": code}
    target = _safe_next(next)

    def fail(message, code=400):
        return render(request, "login.html", mode="register", next=target, form=form,
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
    return _finish_signup(request, user, session, target, code)


def _finish_signup(request, user, session, target, code=""):
    """Yeni hesap (form ya da Google): kaynak, davet kodu, arkadas daveti, oturum."""
    source = request.cookies.get(SOURCE_COOKIE)
    if source:
        db.set_signup_source(user["id"], source)
    message = f"Welcome to HoopLife, {user['username']}."
    code = (code or request.cookies.get(CODE_COOKIE) or "").strip()
    if code:
        redeemed, note = db.redeem_promo_code(user["id"], code)
        message += " " + (note if redeemed else f"The invite code did not work: {note}")
    # Arkadas daveti: iki tarafa da 30 gun Pro
    inviter = db.user_by_invite(request.cookies.get(INVITE_COOKIE))
    if inviter and inviter["id"] != user["id"] and db.set_referred_by(user["id"], inviter["id"]):
        db.extend_pro(user["id"], REFERRAL_DAYS)
        db.extend_pro(inviter["id"], REFERRAL_DAYS)
        forget_user_cache()
        message += f" You and {inviter['username']} both got {REFERRAL_DAYS} days of Pro."
    response = redirect(target, message)
    response.delete_cookie(INVITE_COOKIE, path="/")
    response.delete_cookie(CODE_COOKIE, path="/")
    response.set_cookie(SIGNUP_COOKIE, "1", max_age=600, httponly=True,
                        secure=config.PRODUCTION, samesite="lax", path="/")
    if session:
        set_session_cookie(response, session["token"], remember=True)
    return response


# ==================== GOOGLE ILE GIRIS ====================

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
GSTATE_COOKIE = "hl_gstate"


def _google_redirect_uri():
    return config.SITE_URL.rstrip("/") + "/auth/google/callback"


@router.get("/auth/google")
def google_start(request: Request, next: str = "/"):
    if not (config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET):
        return redirect("/login", "Google sign-in is not available yet.", "error")
    import secrets
    from urllib.parse import urlencode

    from fastapi.responses import RedirectResponse
    state = secrets.token_urlsafe(24)
    params = {"client_id": config.GOOGLE_CLIENT_ID, "redirect_uri": _google_redirect_uri(), "response_type": "code",
              "scope": "openid email profile", "state": state, "prompt": "select_account"}
    response = RedirectResponse(f"{GOOGLE_AUTH}?{urlencode(params)}", 303)
    # Donuste ayni tarayici mi? (CSRF) + nereye donulecek
    response.set_cookie(GSTATE_COOKIE, f"{state}|{_safe_next(next)}", max_age=600, httponly=True,
                        secure=config.PRODUCTION, samesite="lax", path="/")
    return response


def _google_username(info):
    """Google adindan gecerli ve bos bir kullanici adi: 'Teoman Akgun' -> 'TeomanA', doluysa sayi eklenir."""
    import re
    import secrets
    import unicodedata
    raw = info.get("name") or (info.get("email") or "player").split("@")[0]
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    parts = [re.sub(r"[^A-Za-z0-9]", "", w) for w in raw.split()]
    parts = [w for w in parts if w]
    base = (parts[0] + (parts[1][:1] if len(parts) > 1 else "")) if parts else "player"
    base = (base if len(base) >= 3 else base + "fan")[:24]
    if not db.username_taken(base):
        return base
    for _ in range(8):
        name = f"{base}{secrets.randbelow(9000) + 100}"
        if not db.username_taken(name):
            return name
    return f"player{secrets.token_hex(4)}"


@router.get("/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    import hmac
    import secrets
    saved = request.cookies.get(GSTATE_COOKIE) or ""
    saved_state, _, target = saved.partition("|")
    target = _safe_next(target)

    def fail(message):
        response = redirect("/login" + (f"?next={target}" if target != "/" else ""), message, "error")
        response.delete_cookie(GSTATE_COOKIE, path="/")
        return response

    if error:
        return fail("Google sign-in was cancelled.")
    if not code or not saved_state or not hmac.compare_digest(state, saved_state):
        return fail("Google sign-in expired. Try again.")
    if not db.available:
        return fail("Sign-in is unavailable right now. Try again shortly.")
    try:
        tok = requests.post(GOOGLE_TOKEN, timeout=10, data={
            "code": code, "client_id": config.GOOGLE_CLIENT_ID, "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": _google_redirect_uri(), "grant_type": "authorization_code"}).json()
        info = requests.get(GOOGLE_USERINFO, timeout=10,
                            headers={"Authorization": f"Bearer {tok['access_token']}"}).json()
    except Exception as exc:
        print(f"google sign-in failed: {exc}")
        return fail("Could not reach Google. Try again.")
    sub_id, email = info.get("sub"), (info.get("email") or "").strip().lower()
    if not sub_id or not email or not info.get("email_verified"):
        return fail("Your Google account has no verified email.")

    created = False
    user = db.user_by_google(sub_id)
    if not user:
        user = db.user_by_email(email)
        if user:
            # Ayni e-postayla acilmis hesap: Google dogruladigi icin baglanir
            if user.get("google_sub") and user["google_sub"] != str(sub_id):
                return fail("That email is linked to another Google account.")
            db.set_google_sub(user["id"], sub_id)
        else:
            ok, message = db.create_user(_google_username(info), email, secrets.token_urlsafe(24))
            if not ok:
                return fail(message)
            user = db.user_by_email(email)
            db.set_google_sub(user["id"], sub_id)
            created = True
    session = db.create_session(user["id"], browser_id="web", ip_address=client_ip(request),
                                user_agent=request.headers.get("user-agent", "")[:300])
    if created:
        response = _finish_signup(request, user, session, target)
    else:
        response = redirect(target, f"Welcome back, {user['username']}.")
        if session:
            set_session_cookie(response, session["token"], remember=True)
    response.delete_cookie(GSTATE_COOKIE, path="/")
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
