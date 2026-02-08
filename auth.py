import streamlit as st
from services.database import db
import re
import base64
import os
from datetime import datetime, timedelta
import pickle
import hashlib
import uuid
import json
import time

# --- ÇOKLU KATMANLI KALICILIK SİSTEMİ ---

class PersistentAuthManager:
    """
    3 Katmanlı Kalıcılık Sistemi:
    1. LocalStorage (JavaScript - En hızlı)
    2. URL Query Params (Sayfa yenileme için)
    3. File System (Tarayıcı değişse bile)
    """
    
    def __init__(self):
        self.storage_dir = self._get_storage_dir()
        
    def _get_storage_dir(self):
        """Streamlit Cloud uyumlu storage dizini"""
        # Streamlit Cloud'da SADECE /tmp kullanılabilir
        storage_dir = "/tmp/.hooplife_auth"
        
        try:
            os.makedirs(storage_dir, mode=0o700, exist_ok=True)
            
            # Test yazma izni
            test_file = os.path.join(storage_dir, ".test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
            return storage_dir
            
        except Exception as e:
            # Hata durumunda session-only mode
            print(f"⚠️ Storage unavailable, using session-only mode: {e}")
            return None  # Session state kullanılacak
        
    def generate_device_fingerprint(self):
        """Tarayıcı + cihaz kombinasyonu için benzersiz ID"""
        # Session state'te varsa kullan
        if 'device_fingerprint' in st.session_state:
            return st.session_state.device_fingerprint
        
        # Yoksa oluştur
        timestamp = str(datetime.now().timestamp())
        random_part = uuid.uuid4().hex[:12]
        fingerprint = f"device_{hashlib.sha256(f'{timestamp}{random_part}'.encode()).hexdigest()[:16]}"
        
        st.session_state.device_fingerprint = fingerprint
        return fingerprint
    
    def save_persistent_session(self, user_id, username, session_token, remember_me=True):
        """Kalıcı oturum kaydet - 3 katmanlı"""
        device_id = self.generate_device_fingerprint()
        
        session_data = {
            'user_id': user_id,
            'username': username,
            'session_token': session_token,
            'device_id': device_id,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=30)).isoformat(),
            'remember_me': remember_me
        }
        
        # 1. Session State (Immediate)
        st.session_state.persistent_auth = session_data
        st.session_state.authenticated = True
        st.session_state.user = {'id': user_id, 'username': username}
        st.session_state.session_token = session_token
        
        # 2. File System (Long-term)
        if remember_me:
            self._save_to_file(device_id, session_data)
        
        # 3. Return data for JavaScript storage
        return {
            'device_id': device_id,
            'session_token': session_token,
            'username': username,
            'expires_at': session_data['expires_at']
        }
    
    def _save_to_file(self, device_id, session_data):
        """Dosyaya güvenli şekilde kaydet - Cloud safe"""
        if not self.storage_dir:  # ← Eklendi
            return False  # Storage yoksa skip et
            
        try:
            filename = f"auth_{hashlib.md5(device_id.encode()).hexdigest()}.pkl"
            filepath = os.path.join(self.storage_dir, filename)
            
            with open(filepath, 'wb') as f:
                pickle.dump(session_data, f)
            
            os.chmod(filepath, 0o600)
            print(f"✅ Auth saved to file: {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ File save error (non-critical): {e}")
            return False  # Hata olsa da devam et
    
    def load_persistent_session(self):
        """Kalıcı oturumu yükle - 3 katmandan ara"""
        
        # 1. Session State kontrolü (en hızlı)
        if 'persistent_auth' in st.session_state:
            session_data = st.session_state.persistent_auth
            if self._is_valid_session(session_data):
                print("✅ Loaded from session state")
                return session_data
        
        # 2. URL Query Params kontrolü
        query_session = self._load_from_query_params()
        if query_session:
            print("✅ Loaded from URL params")
            st.session_state.persistent_auth = query_session
            return query_session
        
        # 3. File System kontrolü
        device_id = self.generate_device_fingerprint()
        file_session = self._load_from_file(device_id)
        if file_session:
            print("✅ Loaded from file")
            st.session_state.persistent_auth = file_session
            return file_session
        
        # 4. JavaScript LocalStorage'dan gelecek veri (sayfa ilk yüklemede)
        # Bu component ile handle ediliyor
        
        return None
    
    def _load_from_query_params(self):
        """URL'den session yükle"""
        try:
            params = st.query_params
            
            if 'auth_token' in params and 'auth_user' in params:
                token = params['auth_token']
                username = params['auth_user']
                
                # Database'de doğrula
                user = db.validate_session_by_token(token)
                if user and user['username'] == username:
                    return {
                        'user_id': user['id'],
                        'username': username,
                        'session_token': token,
                        'device_id': self.generate_device_fingerprint(),
                        'loaded_from': 'url_params'
                    }
        except Exception as e:
            print(f"⚠️ URL load error: {e}")
        
        return None
    
    def _load_from_file(self, device_id):
        """Dosyadan session yükle"""
        try:
            filename = f"auth_{hashlib.md5(device_id.encode()).hexdigest()}.pkl"
            filepath = os.path.join(self.storage_dir, filename)
            
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'rb') as f:
                session_data = pickle.load(f)
            
            if not self._is_valid_session(session_data):
                os.remove(filepath)
                print(f"🗑️ Expired session file deleted")
                return None
            
            # Database'de doğrula
            user = db.validate_session_by_token(session_data['session_token'])
            if user:
                session_data['user_id'] = user['id']
                return session_data
            else:
                os.remove(filepath)
                return None
                
        except Exception as e:
            print(f"❌ File load error: {e}")
            return None
    
    def _is_valid_session(self, session_data):
        """Session geçerliliğini kontrol et"""
        if not session_data or not isinstance(session_data, dict):
            return False
        
        try:
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            return datetime.now() < expires_at
        except:
            return False
    
    def clear_session(self, device_id=None):
        """Tüm katmanlardan session'ı temizle"""
        if device_id is None:
            device_id = st.session_state.get('device_fingerprint')
        
        # Session state temizle
        for key in ['persistent_auth', 'authenticated', 'user', 'session_token']:
            if key in st.session_state:
                del st.session_state[key]
        
        # Dosyayı sil
        if device_id:
            try:
                filename = f"auth_{hashlib.md5(device_id.encode()).hexdigest()}.pkl"
                filepath = os.path.join(self.storage_dir, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"🗑️ Session file deleted")
            except Exception as e:
                print(f"⚠️ File delete error: {e}")
        
        return True


# Global instance
auth_manager = PersistentAuthManager()


# --- JAVASCRIPT KÖPRÜSÜ ---

def inject_auth_bridge():
    """
    LocalStorage ve Python arasında köprü kurar
    Sayfa yüklendiğinde LocalStorage'dan veriyi alır ve Python'a gönderir
    """
    
    bridge_html = """
    <div id="auth-bridge" style="display:none;"></div>
    <script>
        (function() {
            'use strict';
            
            const STORAGE_KEY = 'hooplife_persistent_auth';
            const bridge = document.getElementById('auth-bridge');
            
            // LocalStorage'dan veri oku
            function loadFromStorage() {
                try {
                    const stored = localStorage.getItem(STORAGE_KEY);
                    if (!stored) {
                        console.log('📭 No stored auth found');
                        return null;
                    }
                    
                    const data = JSON.parse(stored);
                    const expiresAt = new Date(data.expires_at);
                    
                    if (new Date() > expiresAt) {
                        console.log('⏰ Stored auth expired');
                        localStorage.removeItem(STORAGE_KEY);
                        return null;
                    }
                    
                    console.log('✅ Valid auth found:', data.username);
                    return data;
                    
                } catch(e) {
                    console.error('❌ Storage read error:', e);
                    localStorage.removeItem(STORAGE_KEY);
                    return null;
                }
            }
            
            // URL'ye session ekle ve yenile (sayfa yenileme sonrası otomatik giriş)
            function restoreSession(data) {
                const url = new URL(window.location.href);
                const currentToken = url.searchParams.get('auth_token');
                
                // Zaten URL'de doğru token varsa, yenileme yapma
                if (currentToken === data.session_token) {
                    console.log('✅ Session already in URL');
                    return;
                }
                
                // URL'ye ekle ve yenile
                url.searchParams.set('auth_token', data.session_token);
                url.searchParams.set('auth_user', data.username);
                
                console.log('🔄 Restoring session...');
                
                // Sadece bir kez yenile
                if (!sessionStorage.getItem('auth_restored')) {
                    sessionStorage.setItem('auth_restored', 'true');
                    window.location.href = url.toString();
                }
            }
            
            // LocalStorage'a kaydet (Login'den sonra çağrılacak)
            window.saveAuthToStorage = function(authData) {
                try {
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(authData));
                    console.log('💾 Auth saved to storage');
                    return true;
                } catch(e) {
                    console.error('❌ Storage save error:', e);
                    return false;
                }
            };
            
            // LocalStorage'dan temizle (Logout'tan sonra çağrılacak)
            window.clearAuthStorage = function() {
                localStorage.removeItem(STORAGE_KEY);
                sessionStorage.removeItem('auth_restored');
                console.log('🗑️ Auth cleared from storage');
            };
            
            // Sayfa yüklendiğinde çalıştır
            const storedAuth = loadFromStorage();
            if (storedAuth) {
                bridge.setAttribute('data-auth', JSON.stringify(storedAuth));
                restoreSession(storedAuth);
            } else {
                bridge.setAttribute('data-auth', 'null');
            }
            
        })();
    </script>
    """
    
    st.components.v1.html(bridge_html, height=0)


# --- GÜNCELLENMİŞ CHECK_AUTHENTICATION ---

def check_authentication_enhanced():
    """Geliştirilmiş authentication - URL + LocalStorage"""
    
    # 1. Session state kontrolü (en hızlı)
    if st.session_state.get('authenticated'):
        return True
    
    # 2. URL'den token kontrolü
    try:
        params = st.query_params
        
        if 'auth_token' in params and 'auth_user' in params:
            token = params['auth_token']
            username = params['auth_user']
            
            # Database'de doğrula
            user = db.validate_session_by_token(token)
            
            if user and user['username'] == username:
                # Session state'e yükle
                st.session_state.authenticated = True
                st.session_state.user = user
                st.session_state.session_token = token
                print(f"✅ Auto-login from URL: {username}")
                return True
    except Exception as e:
        print(f"⚠️ URL auth failed: {e}")
    
    # 3. JavaScript LocalStorage bridge
    inject_auth_bridge()
    
    return False


# --- GÜNCELLENMİŞ LOGIN FONKSIYONU ---

def handle_login(username, password, remember_me=True):
    """Login işlemi - kalıcılık desteği ile"""
    
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
    
    # Session state'e kaydet
    st.session_state.authenticated = True
    st.session_state.user = user
    st.session_state.session_token = session_data['token']
    
    # Remember me için URL'ye token ekle
    if remember_me:
        auth_data = {
            'session_token': session_data['token'],
            'username': user['username'],
            'user_id': user['id'],
            'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
        }
        
        # JavaScript ile LocalStorage + URL update
        save_html = f"""
        <script>
            (function() {{
                const authData = {json.dumps(auth_data)};
                
                // 1. LocalStorage'a kaydet
                localStorage.setItem('hooplife_persistent_auth', JSON.stringify(authData));
                console.log('💾 Auth saved to LocalStorage');
                
                // 2. URL'ye ekle
                const url = new URL(window.location.href);
                url.searchParams.set('auth_token', authData.session_token);
                url.searchParams.set('auth_user', authData.username);
                
                // 3. Sayfayı yenile
                setTimeout(() => {{
                    window.top.location.href = url.toString();
                }}, 500);
            }})();
        </script>
        """
        
        st.components.v1.html(save_html, height=0)
    else:
        # Remember me kapalıysa sadece session
        st.rerun()
    
    return True, "Login successful"


# --- GÜNCELLENMİŞ LOGOUT FONKSIYONU ---

def logout_enhanced():
    """Logout - tüm katmanları temizle"""
    
    device_id = st.session_state.get('device_fingerprint')
    
    # Database session'ı iptal et
    if 'session_token' in st.session_state:
        db.logout_session(st.session_state.session_token, device_id or 'default')
    
    # Tüm katmanları temizle
    auth_manager.clear_session(device_id)
    
    # JavaScript'ten temizle
    st.components.v1.html("""
        <script>
            if (window.clearAuthStorage) {
                window.clearAuthStorage();
            }
            
            // URL'yi temizle
            const url = new URL(window.location.href);
            url.searchParams.delete('auth_token');
            url.searchParams.delete('auth_user');
            url.searchParams.delete('page');
            
            setTimeout(() => {
                window.top.location.href = url.toString();
            }, 300);
        </script>
    """, height=0)
    
    return True


# --- HELPER FUNCTIONS ---

def get_client_info():
    """İstemci bilgilerini al"""
    try:
        headers = st.context.headers if hasattr(st, 'context') else {}
        return {
            'ip_address': headers.get('X-Forwarded-For', 'unknown'),
            'user_agent': headers.get('User-Agent', 'streamlit-client'),
            'browser_id': auth_manager.generate_device_fingerprint()
        }
    except:
        return {
            'ip_address': 'unknown',
            'user_agent': 'unknown',
            'browser_id': auth_manager.generate_device_fingerprint()
        }


def is_valid_email(email):
    """Email formatı doğrulama"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# --- RENDER AUTH PAGE WITH ENHANCED SYSTEM ---

def render_auth_page_enhanced():
    """Login ve Register sayfası - Geliştirilmiş kalıcılık ile"""
    
    # Geri butonu
    col1, col2, col3 = st.columns([1, 10, 1])
    with col1:
        if st.button("⬅️", help="Back to Home"):
            st.session_state.page = "home"
            st.rerun()

    # CSS (orijinal tasarım korunuyor)
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
    def get_img_as_base64(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except FileNotFoundError:
            print(f"Warning: {file_path} not found")
            return None

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
        
        if submit:
            if not username or not password:
                st.error("Please enter your credentials.")
            else:
                success, message = handle_login(username, password, remember_me)
                
                if success:
                    st.success(f"✅ Welcome back, {username}!")
                    st.info("🔄 Redirecting...")
                    
                    # Auto-redirect kodu zaten handle_login içinde
                    st.rerun()
                    
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
        <div style="text-align: center; margin-top: 1rem; color: #6b7280; font-size: 0.8rem;">
            © 2024 HoopLife NBA. All rights reserved.
        </div>
    """, unsafe_allow_html=True)


# --- EXPORT EDİLECEK FONKSİYONLAR ---
__all__ = [
    'check_authentication_enhanced',
    'handle_login',
    'logout_enhanced',
    'auth_manager',
    'is_valid_email',
    'render_auth_page_enhanced'
]