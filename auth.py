import streamlit as st
from services.database import db
import re
import base64
import os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
import hashlib

# --- YARDIMCI FONKSİYONLAR ---

def get_img_as_base64(file_path):
    """Yerel resim dosyasını base64 string'e çevirir."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        print(f"Uyarı: {file_path} bulunamadı.")
        return None

def is_valid_email(email):
    """Email formatı doğrulama"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def save_auth_token_to_parent(token):
    """Parent window'a token gönder (iframe-safe)"""
    components.html(f"""
        <script>
            (function() {{
                const token = '{token}';
                const expiry = new Date();
                expiry.setDate(expiry.getDate() + 30); // 30 gün
                
                const authData = {{
                    token: token,
                    expiry: expiry.toISOString(),
                    savedAt: new Date().toISOString()
                }};
                
                // Parent window'un localStorage'ına kaydet
                try {{
                    window.parent.localStorage.setItem('hooplife_auth_data', JSON.stringify(authData));
                    console.log('✅ Token saved to parent localStorage');
                }} catch(e) {{
                    console.error('❌ Failed to save token:', e);
                }}
                
                // Iframe'e de kaydet (yedek)
                try {{
                    window.localStorage.setItem('hooplife_auth_data', JSON.stringify(authData));
                }} catch(e) {{
                    console.error('⚠️ Failed to save token to iframe:', e);
                }}
            }})();
        </script>
    """, height=0)

def get_auth_token_from_parent():
    """Parent window'dan token oku"""
    components.html("""
        <script>
            (function() {
                let authData = null;
                
                // Parent'tan oku
                try {
                    const data = window.parent.localStorage.getItem('hooplife_auth_data');
                    if (data) {
                        authData = JSON.parse(data);
                        
                        // Expiry kontrolü
                        const expiry = new Date(authData.expiry);
                        const now = new Date();
                        
                        if (now > expiry) {
                            // Token expired
                            window.parent.localStorage.removeItem('hooplife_auth_data');
                            window.localStorage.removeItem('hooplife_auth_data');
                            authData = null;
                            console.log('⏰ Token expired, removed');
                        } else {
                            console.log('✅ Valid token found in parent:', authData.token.substring(0, 10) + '...');
                            
                            // Token'ı Streamlit session'a kaydet
                            window.parent.streamlit_auth_token = authData.token;
                        }
                    }
                } catch(e) {
                    console.error('❌ Failed to read parent token:', e);
                }
                
                // Parent'ta yoksa iframe'den oku (yedek)
                if (!authData) {
                    try {
                        const data = window.localStorage.getItem('hooplife_auth_data');
                        if (data) {
                            authData = JSON.parse(data);
                            console.log('✅ Token found in iframe storage');
                            window.parent.streamlit_auth_token = authData.token;
                        }
                    } catch(e) {
                        console.error('❌ Failed to read iframe token:', e);
                    }
                }
            })();
        </script>
    """, height=0)

def clear_auth_token():
    """Token'ı temizle (logout)"""
    components.html("""
        <script>
            (function() {
                try {
                    window.parent.localStorage.removeItem('hooplife_auth_data');
                    window.localStorage.removeItem('hooplife_auth_data');
                    delete window.parent.streamlit_auth_token;
                    console.log('✅ Token cleared from storage');
                } catch(e) {
                    console.error('❌ Failed to clear token:', e);
                }
            })();
        </script>
    """, height=0)

def check_stored_token():
    """localStorage'dan token'ı kontrol et ve session'a kaydet"""
    result = components.html("""
        <script>
            (function() {
                // Parent'tan token al
                const token = window.parent.streamlit_auth_token;
                
                if (token) {
                    // Streamlit'e bildir (hidden input ile)
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.id = 'stored_token_value';
                    input.value = token;
                    document.body.appendChild(input);
                    
                    // Token hash'ini döndür (güvenlik için)
                    const hash = btoa(token.substring(0, 20));
                    window.parent.postMessage({
                        type: 'STREAMLIT_TOKEN_READY',
                        hash: hash
                    }, '*');
                    
                    console.log('✅ Token ready for Streamlit');
                } else {
                    console.log('ℹ️ No stored token found');
                }
            })();
        </script>
    """, height=0)
    
    return result

def check_authentication(all_cookies):
    """Kullanıcının giriş yapıp yapmadığını kontrol eder"""
    
    # 1. Session'da zaten varsa
    if st.session_state.get('authenticated'):
        return True
    
    # 2. localStorage'dan token okuma (ilk yükleme)
    if 'token_load_attempted' not in st.session_state:
        st.session_state.token_load_attempted = True
        
        # JavaScript ile token'ı oku
        token_reader = """
            <script>
                (function() {
                    console.log('🔍 Token aranıyor...');
                    
                    const data = localStorage.getItem('hooplife_auth_data');
                    
                    if (data) {
                        try {
                            const authData = JSON.parse(data);
                            const expiry = new Date(authData.expiry);
                            const now = new Date();
                            
                            if (now > expiry) {
                                // Token süresi dolmuş
                                localStorage.removeItem('hooplife_auth_data');
                                console.log('⏰ Token süresi dolmuş, silindi');
                            } else {
                                // Token geçerli
                                console.log('✅ Geçerli token bulundu');
                                console.log('Username:', authData.username);
                                console.log('Token preview:', authData.token.substring(0, 15) + '...');
                                
                                // Token'ı global değişkene kaydet
                                window.hooplife_stored_token = authData.token;
                            }
                        } catch(e) {
                            console.error('❌ Token parse hatası:', e);
                            localStorage.removeItem('hooplife_auth_data');
                        }
                    } else {
                        console.log('ℹ️ localStorage\'da token bulunamadı');
                    }
                })();
            </script>
        """
        components.html(token_reader, height=0)
        
        # JavaScript'in çalışması için kısa bekle
        import time
        time.sleep(0.5)
    
    # 3. Session state'te saklanan token'ı kontrol et
    stored_token = st.session_state.get('remember_token')
    
    if stored_token:
        user = db.validate_session(stored_token)
        if user:
            st.session_state.user = user
            st.session_state.session_token = stored_token
            st.session_state.authenticated = True
            return True
    
    # 4. Cookie fallback (eski sistem)
    if all_cookies:
        token = all_cookies.get('hooplife_auth_token')
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
    
    # localStorage'dan temizle
    components.html("""
        <script>
            localStorage.removeItem('hooplife_auth_data');
            console.log('🗑️ Token localStorage\'dan silindi');
        </script>
    """, height=0)
    
    # Session state temizle
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.session_token = None
    
    if 'remember_token' in st.session_state:
        del st.session_state.remember_token
    if 'token_load_attempted' in st.session_state:
        del st.session_state.token_load_attempted
    
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

    # CSS (aynı kalacak - değişiklik yok)
    st.markdown("""
        <style>
        .block-container {
            padding-top: 0.5rem;
            padding-bottom: 2rem;
        }
        
        .auth-card {
            background-color: #1a1c24 !important;
            border: 1px solid #2d2d2d;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            max-width: 500px;
            margin: 0 auto;
        }
        
        .auth-card h1, .auth-card h2 { color: #ececf1 !important; }
        .auth-card p, .auth-card div, .brand-header p { color: #9ca3af !important; }

        .brand-header {
            text-align: center;
            margin-bottom: 1.5rem;
            margin-top: 0;
            padding-top: 0;
        }

        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 0.3rem;
            margin-top: 0;
            padding-top: 0;
        }
        .logo-img {
            max-width: 300px !important;
            width: 300px !important;
            height: auto;
            display: block;
        }

        div[data-testid="stTabs"] button {
            color: #9ca3af !important;
        }
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
            background-color: #374151;
            color: #FBBF24 !important;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.6rem;
            font-weight: bold;
            text-transform: uppercase;
            margin-left: 5px;
        }
        
        input[type="text"], input[type="password"] {
            background-color: #262730 !important;
            color: #ececf1 !important;
            border: 1px solid #4b5563 !important;
        }
        .stCheckbox label {
            color: #9ca3af !important;
        }
        
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            font-weight: 600;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
            background-color: #1D428A !important;
            color: white !important;
            border: none !important;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #163a7a !important;
            transform: scale(1.01);
        }
        </style>
    """, unsafe_allow_html=True)

    # Logo
    logo_path = "HoopLifeNBA_logo.png"
    logo_b64 = get_img_as_base64(logo_path)

    if logo_b64:
        img_tag = f'<img src="data:image/png;base64,{logo_b64}" class="logo-img" alt="HoopLife NBA Logo">'
    else:
        img_tag = '<img src="https://cdn-icons-png.flaticon.com/512/33/33736.png" class="logo-img" style="opacity:0.5" alt="Default Logo">'

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
            
# auth.py - render_auth_page içinde LOGIN TAB - submit bloğu

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
                            
                            # 🔥 BENİ HATIRLA - Basit localStorage kaydı
                            if remember_me:
                                # Token'ı session state'e de kaydet
                                st.session_state['remember_token'] = token
                                
                                # JavaScript ile localStorage'a kaydet
                                save_token_script = f"""
                                    <script>
                                        (function() {{
                                            console.log('🔄 Token kaydetme başlıyor...');
                                            
                                            const token = '{token}';
                                            const expiry = new Date();
                                            expiry.setDate(expiry.getDate() + 30); // 30 gün sonra
                                            
                                            const authData = {{
                                                token: token,
                                                expiry: expiry.toISOString(),
                                                savedAt: new Date().toISOString(),
                                                username: '{user["username"]}'
                                            }};
                                            
                                            try {{
                                                localStorage.setItem('hooplife_auth_data', JSON.stringify(authData));
                                                console.log('✅ Token başarıyla kaydedildi!');
                                                console.log('Token preview:', token.substring(0, 15) + '...');
                                                console.log('Expiry:', authData.expiry);
                                                
                                                // Doğrulama
                                                const verify = localStorage.getItem('hooplife_auth_data');
                                                if (verify) {{
                                                    console.log('✅ Doğrulama başarılı - token localStorage\'da mevcut');
                                                }} else {{
                                                    console.error('❌ Doğrulama başarısız - token kaydedilemedi');
                                                }}
                                            }} catch(e) {{
                                                console.error('❌ Token kaydetme hatası:', e);
                                            }}
                                        }})();
                                    </script>
                                """
                                components.html(save_token_script, height=0)
                                
                                st.success("✅ Giriş başarılı! 30 gün boyunca oturum açık kalacak.")
                                
                                # JavaScript'in çalışması için bekle
                                import time
                                time.sleep(2)
                            else:
                                st.success("✅ Giriş başarılı!")
                                import time
                                time.sleep(1)
                            
                            st.session_state.page = "home"
                            st.rerun()
                        else:
                            st.error("Bağlantı hatası. Lütfen tekrar deneyin.")
                    else:
                        st.error("Kullanıcı adı veya şifre hatalı.")

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
                        st.success("Account created! Please switch to Sign In tab.")
                        st.balloons()
                    else:
                        st.error(f"Error: {message}")

    st.markdown("""
        <div style="text-align: center; margin-top: 1rem; color: #6b7280; font-size: 0.8rem;">
            © 2024 HoopLife NBA. All rights reserved.
        </div>
    """, unsafe_allow_html=True)