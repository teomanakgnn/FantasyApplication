"""
Hesap ayarlari.

Kullanicinin kendi verisini yonetebilecegi tek yer: profil, parola,
eposta, aktif cihazlar, gosterim tercihleri ve hesap silme. Daha once
bunlarin hicbiri arayuzde yoktu; parola degistirmek veya oturum kapatmak
icin veritabanina elle dokunmak gerekiyordu.
"""
from datetime import datetime

import streamlit as st

from utils.text import esc
from components.pro import PRO_FEATURES, UPGRADE_NOTE, inject_pro_css, plan_label
from services.database import (FREE_SAVED_DRAFT_LIMIT, FREE_WATCHLIST_LIMIT,
                               PLAN_FREE, PLAN_PRO, db)

ADMIN_USERNAMES = {"admin"}


def _short_agent(agent):
    """Uzun user-agent metnini okunur bir cihaz adina indirger."""
    if not agent:
        return "Unknown device"
    agent = str(agent)
    if "iPhone" in agent:
        base = "iPhone"
    elif "iPad" in agent:
        base = "iPad"
    elif "Android" in agent:
        base = "Android"
    elif "Macintosh" in agent or "Mac OS" in agent:
        base = "Mac"
    elif "Windows" in agent:
        base = "Windows"
    elif "Linux" in agent:
        base = "Linux"
    else:
        base = "Browser"
    for name in ("Edg", "Chrome", "Firefox", "Safari"):
        if name in agent:
            return f"{base} · {'Edge' if name == 'Edg' else name}"
    return base


def _fmt_date(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    return str(value)[:10]


def _profile(user):
    plan = plan_label(user)
    chip = "pro" if user.get("is_pro") else "free"
    st.markdown(
        f"""
        <div class="acct-card">
            <div class="acct-name">{esc(user.get('username'))}</div>
            <div class="acct-mail">{esc(user.get('email'))}</div>
            <div style="margin-top:10px;">
                <span class="plan-chip {chip}">{plan.upper()}</span>
                <span class="acct-meta">Member since {_fmt_date(user.get('created_at'))}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    expires = user.get("plan_expires_at")
    if user.get("is_pro") and expires:
        st.caption(f"Pro access runs until {_fmt_date(expires)}.")


def _plan_section(user):
    st.subheader("Plan")
    if user.get("is_pro"):
        st.write("You have Pro. Everything below is unlocked.")
    else:
        st.write("You are on the free plan. Pro adds:")
    for name, detail in PRO_FEATURES:
        st.markdown(f"**{name}** — {detail}")
    if not user.get("is_pro"):
        st.caption(UPGRADE_NOTE)


def _usage(user):
    st.subheader("Usage")
    watch = db.watchlist_count(user["id"])
    drafts = db.saved_draft_count(user["id"])
    pro = user.get("is_pro")
    col1, col2 = st.columns(2)
    col1.metric("Watchlist",
                f"{watch}" if pro else f"{watch} / {FREE_WATCHLIST_LIMIT}")
    col2.metric("Saved mock drafts",
                f"{drafts}" if pro else f"{drafts} / {FREE_SAVED_DRAFT_LIMIT}")


def _security(user):
    st.subheader("Password")
    with st.form("change_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        again = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password", type="primary", width="stretch"):
            if new != again:
                st.error("The two new passwords do not match.")
            else:
                ok, message = db.change_password(user["id"], current, new)
                (st.success if ok else st.error)(message)
                if ok:
                    st.session_state.pop("session_token", None)
                    st.session_state.authenticated = False
                    st.session_state.pop("user", None)
                    st.info("Sign in again with your new password.")

    st.subheader("Email")
    with st.form("change_email"):
        email = st.text_input("Email address", value=user.get("email", ""))
        if st.form_submit_button("Update email", width="stretch"):
            ok, message = db.update_email(user["id"], email)
            if ok:
                st.session_state.user = db.get_user_by_id(user["id"])
            (st.success if ok else st.error)(message)


def _sessions(user):
    st.subheader("Signed-in devices")
    sessions = db.list_sessions(user["id"])
    if not sessions:
        st.caption("No other active sessions.")
        return
    for item in sessions:
        st.markdown(
            f"""
            <div class="acct-row">
                <div>
                    <div class="acct-row-main">{esc(_short_agent(item.get('user_agent')))}</div>
                    <div class="acct-row-sub">{esc(item.get('ip_address'), 'unknown IP')}
                        · signed in {_fmt_date(item.get('created_at'))}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if st.button("Sign out other devices", width="stretch"):
        db.logout_other_sessions(user["id"], st.session_state.get("session_token"))
        st.success("Other devices have been signed out.")
        st.rerun()


def _preferences(user):
    st.subheader("Display")
    current = db.get_score_display_preference(user["id"])
    options = {"full": "Show final scores", "hidden": "Hide scores until I tap"}
    keys = list(options)
    choice = st.radio(
        "Game scores",
        keys,
        index=keys.index(current) if current in keys else 0,
        format_func=lambda k: options[k],
        horizontal=True,
    )
    if choice != current:
        db.update_score_display_preference(user["id"], choice)
        st.toast("Display preference saved.")


def _admin(user):
    """Pro simdilik elle veriliyor; bu panel yalnizca yoneticide gorunur."""
    if user.get("username") not in ADMIN_USERNAMES:
        return
    st.subheader("Grant Pro")
    st.caption("Admin only. Pro has no self-serve upgrade yet.")
    with st.form("grant_pro"):
        target = st.text_input("Username")
        col1, col2 = st.columns(2)
        with col1:
            days = st.number_input("Days (0 = no expiry)", min_value=0, max_value=3650,
                                   value=365, step=30)
        with col2:
            plan = st.selectbox("Plan", [PLAN_PRO, PLAN_FREE])
        if st.form_submit_button("Apply", type="primary", width="stretch"):
            row = db._run("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)",
                          (target.strip(),), fetch="one")
            if not row:
                st.error("No user with that username.")
            elif db.set_plan(row["id"], plan, days=int(days) or None):
                st.success(f"{target} is now on the {plan} plan.")
            else:
                st.error("Could not update that account.")


def _danger(user):
    st.subheader("Delete account")
    st.caption("This removes your account, watchlist, saved drafts and sessions. "
               "It cannot be undone.")
    confirm = st.text_input("Type your username to confirm", key="delete_confirm")
    if st.button("Delete my account", width="stretch"):
        if confirm.strip() != user.get("username"):
            st.error("The username does not match.")
        elif db.delete_account(user["id"]):
            for key in ("authenticated", "user", "session_token"):
                st.session_state.pop(key, None)
            st.session_state.page = "home"
            st.success("Your account has been deleted.")
            st.rerun()
        else:
            st.error("Could not delete the account. Try again.")


def _css():
    st.markdown(
        """
        <style>
        .acct-card {
            border: 1px solid rgba(255,255,255,.10);
            background: rgba(255,255,255,.035);
            border-radius: 16px; padding: 16px 18px; margin-bottom: 4px;
        }
        .acct-name { font-size: 1.3rem; font-weight: 800; letter-spacing: -.4px; }
        .acct-mail { font-size: .88rem; color: #8C99B2; margin-top: 2px; }
        .acct-meta { font-size: .78rem; color: #6B7893; margin-left: 8px; }
        .acct-row {
            border: 1px solid rgba(255,255,255,.07);
            border-radius: 12px; padding: 10px 12px; margin-bottom: 6px;
            background: rgba(255,255,255,.02);
        }
        .acct-row-main { font-size: .9rem; font-weight: 700; }
        .acct-row-sub { font-size: .76rem; color: #6B7893; margin-top: 2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_account_page():
    user = st.session_state.get("user")
    if not user:
        st.warning("Sign in to manage your account.")
        if st.button("Sign in", type="primary"):
            st.session_state.page = "login"
            st.rerun()
        return

    # Plan/eposta gibi alanlar baska bir cihazda degismis olabilir
    fresh = db.get_user_by_id(user["id"])
    if fresh:
        user = fresh
        st.session_state.user = fresh

    inject_pro_css()
    _css()
    st.title("Account")
    _profile(user)

    tab_plan, tab_security, tab_devices, tab_settings = st.tabs(
        ["Plan", "Security", "Devices", "Settings"])
    with tab_plan:
        _plan_section(user)
        _usage(user)
    with tab_security:
        _security(user)
    with tab_devices:
        _sessions(user)
    with tab_settings:
        _preferences(user)
        _admin(user)
        st.divider()
        _danger(user)
