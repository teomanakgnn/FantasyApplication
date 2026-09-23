"""
Pro uyelik kapisi.

Eskiden her sayfa kendi kilit ekranini kendi metniyle ciziyordu
("This is a PRO feature.", "Watchlist is a PRO feature.") ve ucretsiz
kullanici bazi sayfalarda hicbir sey goremiyordu. Burasi tek kaynak:
neyin ucretsiz oldugunu, neyin sinirli oldugunu ve kilit ekraninin
nasil gorunecegini tanimlar.
"""
import streamlit as st

from services.database import FREE_SAVED_DRAFT_LIMIT, FREE_WATCHLIST_LIMIT

# Yukseltme akisi yok: Pro'yu simdilik yonetici eliyle veriyoruz.
UPGRADE_NOTE = "Pro is currently invite-only while we finish the season rollout."

PRO_FEATURES = [
    ("Unlimited watchlist",
     f"Free accounts track up to {FREE_WATCHLIST_LIMIT} players."),
    ("Player trends",
     "Rolling form, usage shifts and rumour tracking."),
    ("Punt build analysis",
     "Category punt builds in the trade analyzer."),
    ("Unlimited saved mock drafts",
     f"Free accounts keep {FREE_SAVED_DRAFT_LIMIT} saved drafts."),
    ("CSV export",
     "Download any table you can see."),
]


def is_pro(user=None):
    """Kullanici gecerli bir Pro plana sahip mi?"""
    user = user if user is not None else st.session_state.get("user")
    return bool(user and user.get("is_pro"))


def plan_label(user=None):
    user = user if user is not None else st.session_state.get("user")
    if not user:
        return "Guest"
    return "Pro" if user.get("is_pro") else "Free"


def _lock_panel(title, body, show_upgrade=True):
    st.markdown(
        f"""
        <div class="pro-lock">
            <div class="pro-lock-tag">PRO</div>
            <div class="pro-lock-title">{title}</div>
            <div class="pro-lock-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if show_upgrade:
        st.caption(UPGRADE_NOTE)


def require_pro(feature, description="", stop=True):
    """
    Pro gerektiren bir sayfanin basinda cagrilir.

    Pro ise True doner. Degilse kilit ekranini cizer ve (stop=True ise)
    sayfayi durdurur.
    """
    if is_pro():
        return True

    signed_in = bool(st.session_state.get("user"))
    if signed_in:
        _lock_panel(feature, description or "This section is part of Pro.")
    else:
        _lock_panel(feature,
                    description or "Sign in with a Pro account to open this section.",
                    show_upgrade=False)

    col1, col2 = st.columns(2)
    with col1:
        label = "Account" if signed_in else "Sign in"
        if st.button(label, width="stretch", type="primary", key=f"pro_cta_{feature}"):
            st.session_state.page = "account" if signed_in else "login"
            st.rerun()
    with col2:
        if st.button("Back to home", width="stretch", key=f"pro_home_{feature}"):
            st.session_state.page = "home"
            st.rerun()
    if stop:
        st.stop()
    return False


def within_limit(current, limit, user=None):
    """Ucretsiz plan siniri asilmis mi? Pro'da sinir yok."""
    if is_pro(user):
        return True
    return current < limit


def limit_notice(current, limit, noun):
    """Sinira yaklasan ucretsiz kullaniciya kisa bir not."""
    if is_pro():
        return
    left = max(0, limit - current)
    if left == 0:
        st.warning(f"Free accounts hold {limit} {noun}. Remove one to add another, "
                   "or switch to Pro for unlimited.")
    elif left <= 3:
        st.caption(f"{left} of {limit} {noun} slots left on the free plan.")


def inject_pro_css():
    """Kilit ekraninin stili. Tek yerde durur ki her sayfada ayni gorunsun."""
    st.markdown(
        """
        <style>
        .pro-lock {
            border: 1px solid rgba(255,255,255,.10);
            background: rgba(255,255,255,.035);
            border-radius: 16px;
            padding: 20px 18px;
            margin: 6px 0 14px;
        }
        .pro-lock-tag {
            display: inline-block;
            font-size: 10px; font-weight: 800; letter-spacing: 1.4px;
            padding: 3px 9px; border-radius: 999px;
            background: rgba(251,191,36,.16); color: #FBBF24;
            margin-bottom: 10px;
        }
        .pro-lock-title {
            font-size: 1.15rem; font-weight: 800; letter-spacing: -.3px;
            margin-bottom: 6px;
        }
        .pro-lock-body { font-size: .9rem; color: #8C99B2; line-height: 1.5; }
        .plan-chip {
            display: inline-block; font-size: 10px; font-weight: 800;
            letter-spacing: 1px; padding: 3px 9px; border-radius: 999px;
        }
        .plan-chip.pro  { background: rgba(251,191,36,.16); color: #FBBF24; }
        .plan-chip.free { background: rgba(255,255,255,.07); color: #93A1BC; }
        /* Kenar cubugundaki kimlik karti (eskiden mor gradyanli kutuydu) */
        .side-user {
            border: 1px solid rgba(255,255,255,.09);
            background: rgba(255,255,255,.03);
            border-radius: 12px; padding: 12px 13px; margin-bottom: 10px;
        }
        .side-user-name { font-size: .98rem; font-weight: 800; letter-spacing: -.2px; }
        .side-user-mail {
            font-size: .76rem; color: #8C99B2; margin: 2px 0 8px;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
