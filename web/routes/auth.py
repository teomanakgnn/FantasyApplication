"""Giris, kayit, cikis."""
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request

from services.database import LOGIN_WINDOW_MINUTES, db
from web.core import (clear_session_cookie, client_ip, current_user,
                      forget_user_cache, redirect, render, set_session_cookie)

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


@router.get("/register")
def register_page(request: Request):
    if current_user(request):
        return redirect("/")
    return render(request, "login.html", mode="register", next="/", form={})


@router.post("/register")
def register(request: Request, username: str = Form(""), email: str = Form(""),
             password: str = Form(""), password2: str = Form(""), terms: str = Form(None)):
    form = {"username": username, "email": email}

    def fail(message, code=400):
        return render(request, "login.html", mode="register", next="/", form=form,
                      error=message, status_code=code)

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
    response = redirect("/", f"Welcome to HoopLife, {user['username']}.")
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
