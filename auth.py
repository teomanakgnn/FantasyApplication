import streamlit as st
from services.database import db
import re
import base64
import os
from datetime import datetime, timedelta

# --- YARDIMCI FONKSİYONLAR ---

def get_img_as_base64(file_path):
    """Yerel resim dosyasını base64 string'e çevirir."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        # Eğer logo dosyası bulunamazsa boş döner veya varsayılan bir ikon konabilir.
        print(f"Uyarı: {file_path} bulunamadı.")
        return None

def is_valid_email(email):
    """Email formatı doğrulama"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def check_authentication():
    """Kullanıcının giriş yapıp yapmadığını kontrol eder (Senkronizasyon Düzeltildi)"""
    if st.session_state.get('authenticated'):
        return True
    
    # app.py ile AYNI key olmalı: "nba_cookies"
    from extra_streamlit_components import CookieManager
    cookie_manager = CookieManager(key="nba_cookies")
    
    # Iframe içinde çerezlerin gelmesi bazen zaman alır
    token = cookie_manager.get('hooplife_auth_token')

    if token:
        user = db.validate_session(token)
        if user:
            st.session_state.user = user
            st.session_state.session_token = token
            st.session_state.authenticated = True
            return True
            
    return False

def logout():
    """Kullanıcı çıkış işlemi"""
    if 'session_token' in st.session_state:
        db.logout_session(st.session_state.session_token)
    
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.session_token = None
    st.rerun()

# --- ARAYÜZ FONKSİYONU ---

def render_auth_page():
    """Login ve Register sayfası - Koyu Tema ve Özel Logo"""
    
    # Üst kısım (Geri butonu)
    col1, col2, col3 = st.columns([1, 10, 1])
    with col1:
        if st.button("⬅️", help="Back to Home"):
            st.session_state.page = "home"
            st.rerun()

    # --- CSS: TAMAMEN KOYU TEMA ---
    st.markdown("""
        <style>
        /* Genel Arkaplan */
        .block-container {
            padding-top: 0.5rem;
            padding-bottom: 2rem;
        }
        
        /* Kart Tasarımı - KOYU RENK */
        .auth-card {
            background-color: #1a1c24 !important; /* Koyu Arka Plan */
            border: 1px solid #2d2d2d;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            max-width: 500px;
            margin: 0 auto;
        }
        
        /* Metin Renkleri - Koyu kart üzerinde açık renk yazı */
        .auth-card h1, .auth-card h2 { color: #ececf1 !important; }
        .auth-card p, .auth-card div, .brand-header p { color: #9ca3af !important; }

        /* Başlıklar */
        .brand-header {
            text-align: center;
            margin-bottom: 1.5rem;
            margin-top: 0;
            padding-top: 0;
        }

        /* Logo Alanı Stili */
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 0.3rem;
            margin-top: 0;
            padding-top: 0;
        }
        .logo-img {
            max-width: 300px !important; /* Logo boyutu daha da küçültüldü */
            width: 300px !important;
            height: auto;
            display: block;
        }

        /* Tab Etiketleri (Giriş Yap / Kayıt Ol) */
        div[data-testid="stTabs"] button {
            color: #9ca3af !important; /* Pasif tab rengi */
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #ececf1 !important; /* Aktif tab rengi */
            border-bottom-color: #1D428A !important;
        }

        /* Plan Kartları - Koyu Tema */
        .plan-container {
            border: 1px solid #2d2d2d;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1.5rem;
            text-align: center;
            background-color: #262730; /* Daha koyu gri */
            transition: all 0.3s ease;
        }
        .plan-container:hover {
            border-color: #1D428A;
            transform: translateY(-2px);
            background-color: #2d2d2d;
        }
        .plan-title {
            font-weight: 700;
            font-size: 1.1rem;
            color: #ececf1 !important;
            display: block;
            margin-bottom: 0.5rem;
        }
        .feature-text {
            font-size: 0.85rem;
            color: #9ca3af !important;
            line-height: 1.5;
        }
        .coming-soon-badge {
            background-color: #374151; /* Koyu gri */
            color: #FBBF24 !important; /* Sarı metin */
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.6rem;
            font-weight: bold;
            text-transform: uppercase;
            margin-left: 5px;
        }
        
        /* Input Alanlarını Zorla Koyu Yap */
        input[type="text"], input[type="password"] {
            background-color: #262730 !important; /* Koyu input zemini */
            color: #ececf1 !important; /* Açık renk yazı */
            border: 1px solid #4b5563 !important;
        }
        /* Checkbox metni */
        .stCheckbox label {
            color: #9ca3af !important;
        }
        
        /* Buton İyileştirmeleri */
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            font-weight: 600;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
            background-color: #1D428A !important; /* NBA Mavisi Buton */
            color: white !important;
            border: none !important;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #163a7a !important; /* Hover rengi */
            transform: scale(1.01);
        }
        </style>
    """, unsafe_allow_html=True)



    # 1. LOGO VE HEADER ALANI
    logo_path = "HoopLifeNBA_logo.png" # Dosya adı
    logo_b64 = get_img_as_base64(logo_path)

    # Eğer logo dosyası varsa göster, yoksa varsayılan bir ikon göster
    if logo_b64:
        img_tag = f'<img src="data:image/png;base64,{logo_b64}" class="logo-img" alt="HoopLife NBA Logo">'
    else:
        # Dosya bulunamazsa yedek ikon (isteğe bağlı kaldırılabilir)
        img_tag = '<img src="https://cdn-icons-png.flaticon.com/512/33/33736.png" class="logo-img" style="opacity:0.5" alt="Default Logo">'
        st.warning(f"Logo dosyası ({logo_path}) bulunamadı. Lütfen auth.py ile aynı dizine ekleyin.")

    st.markdown(f"""
        <div class="logo-container">
            {img_tag}
        </div>
        <div class="brand-header">
            <p style="margin-top: 0; padding-top: 0;">Your ultimate fantasy basketball companion.</p>
        </div>
    """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2 = st.tabs(["Sign In", "Create Account"])

    # ==================== LOGIN TAB ====================
    with tab1:
        st.write("")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            col_rem, col_empty = st.columns([1.5, 1])
            with col_rem:
                remember_me = st.checkbox("Remember me", value=True)
            
            st.write("")
            submit = st.form_submit_button("Sign In", use_container_width=True)
            
# ... (Login submit bloğu içinde)
            if submit:
                if not username or not password:
                    st.error("Please enter your credentials.")
                else:
                    user = db.verify_user(username, password)
                    if user:
                        token = db.create_session(user['id'])
                        if token:
                            # Session State'i doldur
                            st.session_state.user = user
                            st.session_state.session_token = token
                            st.session_state.authenticated = True
                            
                            # --- BENİ HATIRLA MANTIĞI ---
                        if remember_me:
                            # app.py ile AYNI key
                            from extra_streamlit_components import CookieManager
                            cookie_manager = CookieManager(key="nba_cookies")
                            cookie_manager.set(
                                'hooplife_auth_token', 
                                token, 
                                expires_at=datetime.now() + timedelta(days=30)
                            )
                            
                            st.session_state.page = "home"
                            st.rerun()
                        else:
                            st.error("Connection error. Please try again.")
                    else:
                        st.error("Incorrect username or password.")

    # ==================== REGISTER TAB ====================
    with tab2:
        st.write("")
        
        c1, c2 = st.columns(2)
        with c1:
            # Starter Plan Kartı - Koyu mod
            st.markdown("""
                <div class="plan-container">
                    <span class="plan-title">Starter</span>
                    <div class="feature-text">✓ Live Scores</div>
                    <div class="feature-text">✓ Basic Stats</div>
                    <div class="feature-text">✓ Free Forever</div>
                </div>
            """, unsafe_allow_html=True)
            
        with c2:
            # Pro Plan Kartı - Koyu mod (hafif degrade)
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
                        st.success("Account created! Please switch to Sign In tab.")
                        st.balloons()
                    else:
                        st.error(f"Error: {message}")

    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("""
        <div style="text-align: center; margin-top: 1rem; color: #6b7280; font-size: 0.8rem;">
            © 2024 HoopLife NBA. All rights reserved.
        </div>
    """, unsafe_allow_html=True)