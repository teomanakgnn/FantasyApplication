import streamlit as st
from services.database import db
import re
import base64
import os
from datetime import datetime, timedelta
import pickle
import hashlib
import uuid

# --- BROWSER ID FONKSİYONLARI ---

def get_browser_id():
    """Tarayıcı için kalıcı benzersiz ID (tüm sekmeler için aynı)"""
    # İlk olarak session_state'te kontrol et
    if 'browser_id' in st.session_state and st.session_state.browser_id:
        return st.session_state.browser_id
    
    # Cookie'den almaya çalış (app.py'deki JavaScript tarafından set edilmiş)
    try:
        # Streamlit context'inden cookie'leri al
        if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
            cookies = st.context.cookies
            if 'hooplife_browser_id' in cookies:
                browser_id = cookies['hooplife_browser_id']
                st.session_state.browser_id = browser_id
                print(f"✅ Browser ID loaded from cookie: {browser_id[:16]}...")
                return browser_id
    except Exception as e:
        print(f"⚠️ Could not read browser_id from cookie: {e}")
    
    # Session'da yoksa yeni oluştur
    new_id = f'browser_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}'
    st.session_state.browser_id = new_id
    print(f"🆕 New browser ID created: {new_id[:16]}...")
    
    return new_id

def get_client_info():
    """İstemci bilgilerini topla"""
    try:
        # Streamlit'ten IP almaya çalış (production'da çalışır)
        headers = st.context.headers if hasattr(st, 'context') else {}
        ip_address = headers.get('X-Forwarded-For', headers.get('Remote-Addr', 'unknown'))
        user_agent = headers.get('User-Agent', 'unknown')
    except:
        ip_address = 'unknown'
        user_agent = 'unknown'
    
    return {
        'ip_address': ip_address,
        'user_agent': user_agent,
        'browser_id': get_browser_id()
    }

# --- TOKEN SAKLAMA FONKSİYONLARI ---

def get_token_file_path(username, browser_id):
    """Token dosyasının yolunu döndür - Her kullanıcı + browser için benzersiz"""
    home_dir = os.path.expanduser("~")
    token_dir = os.path.join(home_dir, ".hooplife")
    
    if not os.path.exists(token_dir):
        try:
            os.makedirs(token_dir)
        except:
            token_dir = os.path.join("/tmp", ".hooplife")
            if not os.path.exists(token_dir):
                os.makedirs(token_dir)
    
    # Username + browser_id kombinasyonu ile benzersiz dosya
    safe_username = hashlib.md5(username.encode()).hexdigest()[:16]
    safe_browser = hashlib.md5(browser_id.encode()).hexdigest()[:8]
    filename = f"auth_token_{safe_username}_{safe_browser}.pkl"
    
    return os.path.join(token_dir, filename)

def save_token_to_file(token, username, browser_id):
    """Token'ı kullanıcı + browser'a özel dosyaya kaydet"""
    try:
        token_data = {
            'token': token,
            'username': username,
            'browser_id': browser_id,
            'expiry': (datetime.now() + timedelta(days=30)).isoformat(),
            'saved_at': datetime.now().isoformat()
        }
        
        file_path = get_token_file_path(username, browser_id)
        
        with open(file_path, 'wb') as f:
            pickle.dump(token_data, f)
        
        print(f"✅ Token saved: {username} (browser: {browser_id[:8]}...)")
        return True
    except Exception as e:
        print(f"❌ Token save error: {e}")
        return False

def load_token_from_file(browser_id):
    """Bu browser için kaydedilmiş token'ı yükle"""
    try:
        home_dir = os.path.expanduser("~")
        token_dir = os.path.join(home_dir, ".hooplife")
        
        if not os.path.exists(token_dir):
            return None
        
        import glob
        # Bu browser_id'ye ait dosyaları bul
        safe_browser = hashlib.md5(browser_id.encode()).hexdigest()[:8]
        pattern = os.path.join(token_dir, f"auth_token_*_{safe_browser}.pkl")
        token_files = glob.glob(pattern)
        
        for file_path in token_files:
            try:
                with open(file_path, 'rb') as f:
                    token_data = pickle.load(f)
                
                # Browser ID kontrolü
                if token_data.get('browser_id') != browser_id:
                    continue
                
                # Expiry kontrolü
                expiry = datetime.fromisoformat(token_data['expiry'])
                if datetime.now() > expiry:
                    os.remove(file_path)
                    print(f"🗑️ Expired token deleted: {token_data.get('username')}")
                    continue
                
                # Token'ı database'de doğrula
                user = db.validate_session(token_data['token'], browser_id)
                
                if user and user['username'] == token_data['username']:
                    print(f"✅ File token loaded: {user['username']}")
                    return token_data
                else:
                    # Geçersiz token, dosyayı sil
                    os.remove(file_path)
                    print(f"🗑️ Invalid token deleted: {token_data.get('username')}")
                    
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

def delete_token_file(username, browser_id):
    """Kullanıcı + browser'a özel token dosyasını sil"""
    try:
        file_path = get_token_file_path(username, browser_id)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ Token deleted: {username}")
            return True
    except Exception as e:
        print(f"❌ Token delete error: {e}")
    return False

def cleanup_expired_tokens():
    """Süresi dolmuş tüm token dosyalarını temizle"""
    try:
        home_dir = os.path.expanduser("~")
        token_dir = os.path.join(home_dir, ".hooplife")
        
        if not os.path.exists(token_dir):
            return
        
        import glob
        token_files = glob.glob(os.path.join(token_dir, "auth_token_*.pkl"))
        
        cleaned = 0
        for file_path in token_files:
            try:
                with open(file_path, 'rb') as f:
                    token_data = pickle.load(f)
                
                expiry = datetime.fromisoformat(token_data['expiry'])
                if datetime.now() > expiry:
                    os.remove(file_path)
                    cleaned += 1
            except:
                try:
                    os.remove(file_path)
                    cleaned += 1
                except:
                    pass
        
        if cleaned > 0:
            print(f"🧹 Cleaned {cleaned} expired token(s)")
            
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

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

# auth.py - check_authentication fonksiyonunu değiştir

def check_authentication(all_cookies):
    """Kullanıcının giriş yapıp yapmadığını kontrol eder - IFRAME UYUMLU"""
    
    # Browser ID'yi al
    browser_id = None
    if all_cookies and 'hooplife_browser_id' in all_cookies:
        browser_id = all_cookies['hooplife_browser_id']
        st.session_state.browser_id = browser_id
    else:
        browser_id = get_browser_id()
    
    # 1. Session State'te varsa (sayfa yenilenmemiş)
    if st.session_state.get('authenticated') and st.session_state.get('user'):
        session_id = st.session_state.get('session_id')
        
        if session_id:
            # Session ID ile doğrula
            user = db.validate_session_by_id(session_id, browser_id)
            
            if user:
                st.session_state.user = user
                return True
            else:
                # Session süresi dolmuş
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.session_id = None
    
    # 2. URL Query Parameter'dan session_id kontrol et (iframe için)
    query_params = st.query_params
    if 'session_id' in query_params:
        session_id = query_params['session_id']
        
        user = db.validate_session_by_id(session_id, browser_id)
        
        if user:
            st.session_state.user = user
            st.session_state.session_id = session_id
            st.session_state.authenticated = True
            print(f"✅ Query param login: {user['username']}")
            return True
    
    # 3. Cookie'den token yükle (normal kullanım)
    if all_cookies:
        cookie_token = all_cookies.get('hooplife_auth_token')
        if cookie_token:
            user = db.validate_session(cookie_token, browser_id)
            
            if user:
                st.session_state.user = user
                st.session_state.session_token = cookie_token
                st.session_state.authenticated = True
                print(f"✅ Cookie login: {user['username']}")
                return True
    
    # 4. Dosyadan token yükle
    token_data = load_token_from_file(browser_id)
    
    if token_data:
        user = db.validate_session(token_data['token'], browser_id)
        
        if user:
            st.session_state.user = user
            st.session_state.session_token = token_data['token']
            st.session_state.authenticated = True
            print(f"✅ File login: {user['username']}")
            return True
        else:
            delete_token_file(token_data['username'], browser_id)
    
    return False

def logout():
    """Kullanıcı çıkış işlemi"""
    browser_id = get_browser_id()
    current_user = st.session_state.get('user')
    session_id = st.session_state.get('session_id')
    
    # Database session'ı iptal et
    if session_id:
        db.logout_session_by_id(session_id, browser_id)
    elif 'session_token' in st.session_state:
        db.logout_session(st.session_state.session_token, browser_id)
    
    # Token dosyasını sil
    if current_user:
        delete_token_file(current_user['username'], browser_id)
    
    # Session state temizle
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.session_token = None
    st.session_state.session_id = None
    
    if 'file_token_checked' in st.session_state:
        del st.session_state.file_token_checked
    
    # iframe içindeyse parent'a bildir
    is_embedded = st.query_params.get("embed") == "true"
    if is_embedded:
        st.markdown("""
            <script>
                window.parent.postMessage({
                    type: 'hooplife_logout'
                }, '*');
                localStorage.removeItem('hooplife_session_id');
                localStorage.removeItem('hooplife_username');
            </script>
        """, unsafe_allow_html=True)
    
    st.rerun()

# --- ARAYÜZ FONKSİYONU ---

def render_auth_page():
    """Login ve Register sayfası"""
    
    # Üst kısım (Geri butonu)
    col1, col2, col3 = st.columns([1, 10, 1])
    with col1:
        if st.button("⬅️", help="Back to Home"):
            st.session_state.page = "home"
            st.rerun()

    # CSS
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
        
# auth.py - render_auth_page fonksiyonunda LOGIN TAB kısmını değiştir

# auth.py içinde render_auth_page fonksiyonu, "Sign In" butonu mantığı

        if submit:
            if not username or not password:
                st.error("Please enter your credentials.")
            else:
                user = db.verify_user(username, password)
                if user:
                    # Client bilgilerini al
                    client_info = get_client_info()
                    
                    # Session oluştur (session_id döner)
                    session_data = db.create_session(
                        user['id'], 
                        browser_id=client_info['browser_id'],
                        ip_address=client_info['ip_address'],
                        user_agent=client_info['user_agent']
                    )
                    
                    if session_data:
                        # Session State'i doldur
                        st.session_state.user = user
                        st.session_state.session_token = session_data['token']
                        st.session_state.session_id = session_data['session_id']
                        st.session_state.authenticated = True
                        
                        # file_token_checked'i sıfırla
                        if 'file_token_checked' in st.session_state:
                            del st.session_state['file_token_checked']
                        
                        # ---------------------------------------------------------
                        # DÜZELTME BAŞLANGICI: COOKIE VE LOCALSTORAGE YAZMA
                        # ---------------------------------------------------------
                        
                        # JavaScript ile Token'ı Tarayıcıya Kaydet
                        # Bu kısım app.py'deki "LocalStorage'dan Cookie'ye aktar" script'i ile uyumlu çalışır.
                        
                        js_code = f"""
                            <script>
                                // 1. Token verisini hazırla
                                const authData = {{
                                    token: "{session_data['token']}",
                                    expiry: new Date(new Date().getTime() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 Gün
                                    username: "{user['username']}"
                                }};

                                // 2. LocalStorage'a kaydet (Kalıcı hafıza)
                                localStorage.setItem('hooplife_auth_data', JSON.stringify(authData));
                                localStorage.setItem('hooplife_username', "{user['username']}");

                                // 3. Cookie'yi manuel olarak da set et (Anlık erişim için)
                                document.cookie = "hooplife_auth_token={session_data['token']}; max-age=2592000; path=/; SameSite=Lax";
                                
                                console.log('✅ Token saved to Browser (Cookie & LS)');
                            </script>
                        """
                        st.markdown(js_code, unsafe_allow_html=True)

                        if remember_me:
                            # Opsiyonel: Sunucu tarafında da yedek olarak dosyaya yazabilirsiniz (Eski kodunuz)
                            save_token_to_file(
                                session_data['token'], 
                                user['username'], 
                                client_info['browser_id']
                            )
                            st.success(f"✅ Welcome back, {user['username']}!")
                        else:
                            # Beni hatırla seçili değilse LocalStorage'ı temizleyen JS (Sadece session süresince kalsın)
                            st.markdown("""
                                <script>
                                    localStorage.removeItem('hooplife_auth_data');
                                </script>
                            """, unsafe_allow_html=True)
                            st.success(f"✅ Welcome, {user['username']}!")

                        # ---------------------------------------------------------
                        # DÜZELTME BİTİŞİ
                        # ---------------------------------------------------------

                        # IFRAME içindeyse parent'a session_id gönder
                        is_embedded = st.query_params.get("embed") == "true"
                        if is_embedded:
                            st.markdown(f"""
                                <script>
                                    window.parent.postMessage({{
                                        type: 'hooplife_session',
                                        session_id: '{session_data["session_id"]}',
                                        username: '{user["username"]}'
                                    }}, '*');
                                </script>
                            """, unsafe_allow_html=True)
                        
                        # Otomatik yönlendirme
                        import time
                        time.sleep(1)
                        
                        st.session_state.page = "home"
                        st.rerun()
                        
                    else:
                        st.error("Connection error. Please try again.")
                else:
                    st.error("Invalid username or password.")

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