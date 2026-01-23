import streamlit as st
from services.database import db
import re

def is_valid_email(email):
    """Email validation regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def render_auth_page():
    """Login ve Register sayfası - Profesyonel Tasarım"""
    
    # Sayfa düzeni için üst kısım
    col1, col2, col3 = st.columns([1, 10, 1])
    with col1:
        if st.button("⬅️", help="Back to Home"):
            st.session_state.page = "home"
            st.rerun()

    # --- MODERN VE PROFESYONEL CSS ---
    st.markdown("""
        <style>
        /* Genel Arkaplan ve Fontlar */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Kart Tasarımı (Auth Container) */
        .auth-card {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
            max-width: 500px;
            margin: 0 auto;
        }
        
        /* Dark Mode Uyumluluğu */
        @media (prefers-color-scheme: dark) {
            .auth-card {
                background-color: #1a1c24;
                border-color: #2d2d2d;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            }
            h1, h2, h3, p { color: #ececf1 !important; }
            .feature-text { color: #9ca3af !important; }
        }

        /* Başlıklar */
        .brand-header {
            text-align: center;
            margin-bottom: 2.5rem;
        }
        .brand-header h1 {
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 800;
            font-size: 2.2rem;
            margin: 0;
            background: -webkit-linear-gradient(45deg, #1D428A, #C8102E); /* NBA Renkleri */
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .brand-header p {
            color: #6b7280;
            font-size: 1rem;
            margin-top: 0.5rem;
        }

        /* Plan Kartları */
        .plan-container {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        .plan-container:hover {
            border-color: #1D428A;
            transform: translateY(-2px);
        }
        .plan-title {
            font-weight: 700;
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
            display: block;
        }
        .coming-soon-badge {
            background-color: #FFF3CD;
            color: #856404;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            vertical-align: middle;
            margin-left: 8px;
        }
        .feature-text {
            font-size: 0.9rem;
            color: #4b5563;
            line-height: 1.6;
        }
        
        /* Buton İyileştirmeleri */
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            font-weight: 600;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            transform: scale(1.01);
        }
        </style>
    """, unsafe_allow_html=True)

    # --- ANA KAPSAYICI ---
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)

    # Header
    st.markdown("""
        <div class="brand-header">
            <h1>🏀 NBA Dashboard</h1>
            <p>Your ultimate fantasy basketball companion.</p>
        </div>
    """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2 = st.tabs(["Sign In", "Create Account"])

    # ==================== LOGIN TAB ====================
    with tab1:
        st.write("") # Spacer
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            col_rem, col_empty = st.columns([1.5, 1])
            with col_rem:
                remember_me = st.checkbox("Remember me", value=True)
            
            st.write("") # Spacer
            submit = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            
            if submit:
                if not username or not password:
                    st.error("Please enter your credentials.")
                else:
                    user = db.verify_user(username, password)
                    if user:
                        token = db.create_session(user['id'])
                        if token:
                            st.session_state.user = user
                            st.session_state.session_token = token
                            st.session_state.authenticated = True
                            st.session_state.page = "home"
                            st.toast(f"Welcome back, {user['username']}!", icon="👋")
                            st.rerun()
                        else:
                            st.error("Connection error. Please try again.")
                    else:
                        st.error("Incorrect username or password.")

    # ==================== REGISTER TAB ====================
    with tab2:
        st.write("")
        
        # Karşılaştırma Alanı - Sadeleştirilmiş
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
                <div class="plan-container" style="background: linear-gradient(145deg, rgba(255,255,255,1) 0%, rgba(249,250,251,1) 100%);">
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
            submit_reg = st.form_submit_button("Create Free Account", use_container_width=True, type="primary")
            
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
    
    # Alt bilgi
    st.markdown("""
        <div style="text-align: center; margin-top: 1rem; color: #9ca3af; font-size: 0.8rem;">
            © 2024 NBA Dashboard. All rights reserved.
        </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# EKSİK OLAN FONKSİYONLAR BURAYA EKLENDİ
# ---------------------------------------------------------

def check_authentication():
    """Check if user is authenticated"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'session_token' in st.session_state and not st.session_state.authenticated:
        user = db.validate_session(st.session_state.session_token)
        if user:
            st.session_state.user = user
            st.session_state.authenticated = True
        else:
            st.session_state.authenticated = False
    
    return st.session_state.authenticated

def logout():
    """Logout user"""
    if 'session_token' in st.session_state:
        db.logout_session(st.session_state.session_token)
    
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.session_token = None
    st.rerun()