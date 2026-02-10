import streamlit as st
from services.database import db
import re
import base64
import os
from datetime import datetime, timedelta
import json
import time
import streamlit.components.v1 as components
import hashlib


def handle_login(username, password, remember_me=True, fingerprint_hash=None):
    """Login işlemi - LocalStorage + URL param tabanlı"""
    user = db.verify_user(username, password)

    if not user:
        return False, "Invalid credentials"

    # Session oluştur
    client_info = get_client_info()
    session_data = db.create_session(
        user['id'],
        browser_id=client_info.get('browser_id', 'default'),
        ip_address=client_info.get('ip_address', 'unknown'),
        user_agent=client_info.get('user_agent', 'unknown')
    )

    if not session_data:
        return False, "Session creation failed"
    
    # Store fingerprint in the session if provided
    if fingerprint_hash and session_data.get('token'):
        try:
            db.update_session_fingerprint(session_data['token'], fingerprint_hash)
        except Exception as e:
            print(f"⚠️ Could not store fingerprint: {e}")
            # Continue anyway - fingerprint is optional

    # Session state'e kaydet
    st.session_state.authenticated = True
    st.session_state.user = user
    st.session_state.session_token = session_data['token']

    if remember_me:
        # LocalStorage'a kaydet ve URL param ile yenile
        auth_data = {
            'token': session_data['token'],
            'username': user['username'],
            'user_id': user['id'],
            'expiry': (datetime.now() + timedelta(days=30)).isoformat()
        }
        st.components.v1.html(f"""
        <script>
            (function() {{
                try {{
                    localStorage.setItem('hooplife_auth_data', JSON.stringify({json.dumps(auth_data)}));
                    console.log('✅ Session saved to localStorage');
                }} catch(e) {{
                    console.error('❌ localStorage save failed:', e);
                }}

                // URL param ekleyerek yenile - Streamlit token'ı yakalasın
                const url = new URL(window.parent.location.href);
                url.searchParams.set('auth_token', '{session_data['token']}');
                url.searchParams.set('auth_user', '{user['username']}');
                window.parent.location.href = url.toString();
            }})();
        </script>
        """, height=0)
        # JS yönlendiriyor, Python rerun yapmıyor
        return True, "Login successful. Redirecting..."
    else:
        # Remember me kapalı: sadece session state, URL temiz
        st.session_state.page = "home"
        st.rerun()
        return True, "Login successful"

def get_fingerprint_component():
    """Görünmez bir JS bileşeni ile cihaz özelliklerini toplar"""
    # Bu bileşen Streamlit session_state'e veri döndürür
    fingerprint_js = """
    <script>
        const fpData = {
            ua: navigator.userAgent,
            res: window.screen.width + "x" + window.screen.height,
            tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
            mem: navigator.deviceMemory || 0,
            lang: navigator.language
        };
        const fpHash = btoa(JSON.stringify(fpData)); // Basit bir encode
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: fpHash
        }, '*');
    </script>
    """
    # Streamlit'in html bileşeni veriyi yakalamak için bazen yetersiz kalabilir, 
    # bu yüzden bu veriyi bir query param olarak veya direkt döndürerek kullanacağız.
    return components.html(fingerprint_js, height=0)


def check_authentication_enhanced(fingerprint_hash=None):
    """
    Check if user is authenticated via session state, URL params, or fingerprint.
    
    Args:
        fingerprint_hash: Optional device fingerprint hash for automatic login
    """
    # 1. Zaten giriş yapılmışsa
    if st.session_state.get('authenticated'):
        return True

    # 2. URL parametrelerinden token kontrolü
    query_params = st.query_params
    if 'auth_token' in query_params:
        token = query_params['auth_token']
        user = db.validate_session_by_token(token)
        if user:
            st.session_state.authenticated = True
            st.session_state.user = user
            st.session_state.session_token = token
            return True

    # 3. Parmak izi gelmişse ve session yoksa DB'den kontrol et
    if fingerprint_hash:
        user = db.validate_session_by_fingerprint(fingerprint_hash)
        if user:
            st.session_state.authenticated = True
            st.session_state.user = user
            return True
    
    return False


def inject_auth_bridge():
    """
    LocalStorage'dan token'ı okur ve Python tarafına URL üzerinden güvenli bir şekilde paslar.
    Döngüye girmemesi için session_state kontrolü ekliyoruz.
    """
    if st.session_state.get('authenticated') or st.session_state.get('bridge_fired'):
        return

    st.components.v1.html("""
    <script>
        (function() {
            try {
                const data = localStorage.getItem('hooplife_auth_data');
                if (!data) return;
                
                const auth = JSON.parse(data);
                const now = new Date();
                
                if (new Date(auth.expiry) > now && auth.token) {
                    const url = new URL(window.parent.location.href);
                    // Sadece token yoksa ekle ve yenile
                    if (url.searchParams.get('auth_token') !== auth.token) {
                        url.searchParams.set('auth_token', auth.token);
                        url.searchParams.set('auth_user', auth.username);
                        window.parent.location.href = url.toString();
                    }
                }
            } catch (e) { console.error("Auth Bridge Error", e); }
        })();
    </script>
    """, height=0)
    st.session_state.bridge_fired = True


def logout_enhanced():
    """Logout - session state + LocalStorage + URL temizle"""

    # Database session'ı iptal et
    if 'session_token' in st.session_state:
        try:
            db.logout_session(st.session_state.session_token, 'default')
        except Exception as e:
            print(f"⚠️ DB logout error: {e}")

    # Session state temizle
    for key in ['authenticated', 'user', 'session_token']:
        st.session_state.pop(key, None)

    # LocalStorage + URL temizle, login sayfasına yönlendir
    st.components.v1.html("""
    <script>
        (function() {
            try {
                localStorage.removeItem('hooplife_auth_data');
                console.log('🗑️ localStorage cleared');
            } catch(e) {}

            try {
                sessionStorage.removeItem('auth_redirect_count');
            } catch(e) {}

            // URL'deki token parametrelerini temizleyip yenile
            const url = new URL(window.parent.location.href);
            url.searchParams.delete('auth_token');
            url.searchParams.delete('auth_user');
            window.parent.location.href = url.toString();
        })();
    </script>
    """, height=0)

    return True


def get_client_info():
    """İstemci bilgilerini al"""
    try:
        headers = st.context.headers if hasattr(st, 'context') else {}
        return {
            'ip_address': headers.get('X-Forwarded-For', 'unknown'),
            'user_agent': headers.get('User-Agent', 'streamlit-client'),
            'browser_id': 'default'
        }
    except Exception:
        return {
            'ip_address': 'unknown',
            'user_agent': 'unknown',
            'browser_id': 'default'
        }


def is_valid_email(email):
    """Email formatı doğrulama"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def render_auth_page_enhanced():
    """Login ve Register sayfası"""

    col1, col2, col3 = st.columns([1, 10, 1])
    with col1:
        if st.button("⬅️", help="Back to Home"):
            st.session_state.page = "home"
            st.rerun()

    st.markdown("""
        <style>
        .block-container { padding-top: 0.5rem; padding-bottom: 2rem; }
        .auth-card {
            background-color: #1a1c24 !important;
            border: 1px solid #2d2d2d;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
            max-width: 500px;
            margin: 0 auto;
        }
        .brand-header { text-align: center; margin-bottom: 1.5rem; }
        .logo-container { display: flex; justify-content: center; align-items: center; margin-bottom: 0.3rem; }
        .logo-img { max-width: 300px !important; width: 300px !important; height: auto; display: block; }
        div[data-testid="stTabs"] button { color: #9ca3af !important; }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #ececf1 !important;
            border-bottom-color: #1D428A !important;
        }
        .plan-container {
            border: 1px solid #2d2d2d;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1.5rem;
            text-align: center;
            background-color: #262730;
        }
        .plan-title { font-weight: 700; font-size: 1.1rem; color: #ececf1 !important; display: block; margin-bottom: 0.5rem; }
        .feature-text { font-size: 0.85rem; color: #9ca3af !important; line-height: 1.5; }
        .coming-soon-badge {
            background-color: #374151;
            color: #FBBF24 !important;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.6rem;
            font-weight: bold;
            text-transform: uppercase;
            margin-left: 5px;
        }
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            font-weight: 600;
            background-color: #1D428A !important;
            color: white !important;
            border: none !important;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #163a7a !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Logo
    def get_img_as_base64(file_path):
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except FileNotFoundError:
            return None

    logo_b64 = get_img_as_base64("HoopLifeNBA_logo.png")
    img_tag = (
        f'<img src="data:image/png;base64,{logo_b64}" class="logo-img" alt="HoopLife NBA Logo">'
        if logo_b64
        else '<img src="https://cdn-icons-png.flaticon.com/512/33/33736.png" class="logo-img" style="opacity:0.5" alt="Default Logo">'
    )

    st.markdown(f"""
        <div class="logo-container">{img_tag}</div>
        <div class="brand-header">
            <p style="margin-top:0;">Your ultimate fantasy basketball companion.</p>
        </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Sign In", "Create Account"])

    # ==================== LOGIN TAB ====================
    with tab1:
        st.write("")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            col_rem, _ = st.columns([1.5, 1])
            with col_rem:
                remember_me = st.checkbox("Remember me", value=True)
            st.write("")
            submit = st.form_submit_button("Sign In", use_container_width=True)

        if submit:
            if not username or not password:
                st.error("Please enter your credentials.")
            else:
                with st.spinner("Logging in..."):
                    # Get fingerprint hash from session state if available
                    fingerprint_hash = st.session_state.get('fingerprint_hash')
                    success, message = handle_login(username, password, remember_me, fingerprint_hash)

                if success:
                    st.success(f"✅ Welcome back, {username}!")
                    # remember_me=True ise JS yönlendiriyor, rerun gerekmez.
                    # remember_me=False ise handle_login içinde rerun yapıldı.
                else:
                    st.error(f"❌ {message}")

    # ==================== REGISTER TAB ====================
    with tab2:
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
                <div class="plan-container">
                    <span class="plan-title">Starter</span>
                    <div class="feature-text">✓ Live Scores</div>
                    <div class="feature-text">✓ Basic Stats</div>
                    <div class="feature-text">✓ Free Forever</div>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("""
                <div class="plan-container" style="background: linear-gradient(145deg, #262730 0%, #2d2d2d 100%);">
                    <span class="plan-title">Pro <span class="coming-soon-badge">SOON</span></span>
                    <div class="feature-text">★ Advanced Analytics</div>
                    <div class="feature-text">★ AI Predictions</div>
                    <div class="feature-text">★ Export Data</div>
                </div>
            """, unsafe_allow_html=True)

        with st.form("register_form", clear_on_submit=True):
            reg_username = st.text_input("Username", placeholder="Choose a username")
            reg_email = st.text_input("Email", placeholder="name@example.com")
            p1, p2 = st.columns(2)
            with p1:
                reg_password = st.text_input("Password", type="password")
            with p2:
                reg_password2 = st.text_input("Confirm", type="password")
            terms = st.checkbox("I agree to the Terms of Service")
            st.markdown("---")
            submit_reg = st.form_submit_button("Create Free Account", use_container_width=True)

            if submit_reg:
                errors = []
                if not all([reg_username, reg_email, reg_password, reg_password2]):
                    errors.append("All fields are required")
                elif len(reg_username) < 3:
                    errors.append("Username too short (min 3 chars)")
                elif not is_valid_email(reg_email):
                    errors.append("Invalid email format")
                elif len(reg_password) < 6:
                    errors.append("Password too short (min 6 chars)")
                elif reg_password != reg_password2:
                    errors.append("Passwords do not match")
                elif not terms:
                    errors.append("Please accept the terms")

                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    success, message = db.create_user(reg_username, reg_email, reg_password)
                    if success:
                        st.success("✅ Account created! Please switch to Sign In tab.")
                        st.balloons()
                    else:
                        st.error(f"❌ {message}")

    st.markdown("""
        <div style="text-align:center; margin-top:1rem; color:#6b7280; font-size:0.8rem;">
            © 2024 HoopLife NBA. All rights reserved.
        </div>
    """, unsafe_allow_html=True)


__all__ = [
    'check_authentication_enhanced',
    'handle_login',
    'logout_enhanced',
    'inject_auth_bridge',
    'is_valid_email',
    'render_auth_page_enhanced'
]