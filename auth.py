import streamlit as st
from services.database import db
import re
import base64
import os
from datetime import datetime, timedelta
import pickle
import hashlib

# --- TOKEN SAKLAMA FONKSİYONLARI ---

def get_token_file_path(username=None):
    """Token dosyasının yolunu döndür - Her kullanıcı için benzersiz"""
    home_dir = os.path.expanduser("~")
    token_dir = os.path.join(home_dir, ".hooplife")
    
    if not os.path.exists(token_dir):
        try:
            os.makedirs(token_dir)
        except:
            token_dir = os.path.join("/tmp", ".hooplife")
            if not os.path.exists(token_dir):
                os.makedirs(token_dir)
    
    # 🔥 DÜZELTME: Her kullanıcı için benzersiz dosya
    if username:
        # Username'i hash'le (güvenli dosya adı için)
        safe_username = hashlib.md5(username.encode()).hexdigest()[:16]
        filename = f"auth_token_{safe_username}.pkl"
    else:
        # Fallback: Browser-specific token
        import streamlit as st
        # Session ID yerine browser fingerprint kullan
        browser_id = st.session_state.get('browser_id', 'guest')
        filename = f"auth_token_{browser_id}.pkl"
    
    return os.path.join(token_dir, filename)

def save_token_to_file(token, username):
    """Token'ı kullanıcıya özel dosyaya kaydet"""
    try:
        token_data = {
            'token': token,
            'username': username,
            'expiry': (datetime.now() + timedelta(days=30)).isoformat(),
            'saved_at': datetime.now().isoformat()
        }
        
        # 🔥 USERNAME parametresini ekle
        file_path = get_token_file_path(username)
        
        with open(file_path, 'wb') as f:
            pickle.dump(token_data, f)
        
        print(f"✅ Token saved for user: {username} → {file_path}")
        return True
    except Exception as e:
        print(f"❌ Token save error: {e}")
        return False

def load_token_from_file():
    """Tüm kullanıcı token dosyalarını tara ve geçerli olanı döndür"""
    try:
        home_dir = os.path.expanduser("~")
        token_dir = os.path.join(home_dir, ".hooplife")
        
        if not os.path.exists(token_dir):
            return None
        
        # 🔥 Tüm token dosyalarını kontrol et
        import glob
        token_files = glob.glob(os.path.join(token_dir, "auth_token_*.pkl"))
        
        for file_path in token_files:
            try:
                with open(file_path, 'rb') as f:
                    token_data = pickle.load(f)
                
                # Expiry kontrolü
                expiry = datetime.fromisoformat(token_data['expiry'])
                if datetime.now() > expiry:
                    os.remove(file_path)
                    continue
                
                # Geçerli token bulundu
                print(f"✅ Valid token found: {token_data['username']}")
                return token_data
                
            except Exception as e:
                print(f"⚠️ Corrupt token file: {file_path} → {e}")
                try:
                    os.remove(file_path)
                except:
                    pass
        
        return None
        
    except Exception as e:
        print(f"❌ Token load error: {e}")
        return None

def delete_token_file(username=None):
    """Kullanıcıya özel token dosyasını sil"""
    try:
        if username:
            # Belirli kullanıcının token'ını sil
            file_path = get_token_file_path(username)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Token deleted for: {username}")
                return True
        else:
            # Mevcut kullanıcının token'ını sil (session'dan al)
            current_user = st.session_state.get('user')
            if current_user:
                file_path = get_token_file_path(current_user['username'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"🗑️ Token deleted for current user")
                    return True
    except Exception as e:
        print(f"❌ Token delete error: {e}")
    return False
# --- AUTHENTICATION FONKSİYONLARI ---

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

def check_authentication(all_cookies):
    """Kullanıcının giriş yapıp yapmadığını kontrol eder"""
    
    # 1. Session'da zaten varsa
    if st.session_state.get('authenticated'):
        return True
    
    # 2. Dosyadan token yükle (sadece bir kez)
    if 'file_token_checked' not in st.session_state:
        st.session_state.file_token_checked = True
        
        token_data = load_token_from_file()
        
        if token_data:
            # Token'ı database'de doğrula
            user = db.validate_session(token_data['token'])
            
            if user:
                # Token geçerli, otomatik login
                st.session_state.user = user
                st.session_state.session_token = token_data['token']
                st.session_state.authenticated = True
                
                print(f"✅ Otomatik login: {user['username']}")
                return True
            else:
                # Token geçersiz, dosyayı sil
                delete_token_file()
    
    # 3. Cookie fallback (eski sistem)
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
    # Database session'ı iptal et
    if 'session_token' in st.session_state:
        db.logout_session(st.session_state.session_token)
    
    # 🔥 Kullanıcıya özel token dosyasını sil
    current_user = st.session_state.get('user')
    if current_user:
        delete_token_file(current_user['username'])
    
    # Session state temizle
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.session_token = None
    
    if 'file_token_checked' in st.session_state:
        del st.session_state.file_token_checked
    
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

    # CSS (aynı kalacak)
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
        
        # FORM DIŞINDA
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
                        
                        # 🔥 BENİ HATIRLA - DOSYAYA KAYDET
                        if remember_me:
                            success = save_token_to_file(token, user['username'])
                            if success:
                                st.success("✅ Giriş başarılı! 30 gün boyunca oturum açık kalacak.")
                            else:
                                st.warning("✅ Giriş başarılı! (Ancak 'Beni Hatırla' kaydedilemedi)")
                        else:
                            st.success("✅ Giriş başarılı!")
                        
                        # Otomatik yönlendirme
                        import time
                        time.sleep(1.5)
                        
                        st.session_state.page = "home"
                        st.rerun()
                        
                    else:
                        st.error("Bağlantı hatası. Lütfen tekrar deneyin.")
                else:
                    st.error("Kullanıcı adı veya şifre hatalı.")

    # ==================== REGISTER TAB (aynı kalacak) ====================
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
