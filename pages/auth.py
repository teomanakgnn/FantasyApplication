import streamlit as st
from services.database import db
import re

def is_valid_email(email):
    """Email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def render_auth_page():
    """Login ve Register sayfası"""
    
    # Back to home button at top
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    
    # Custom CSS
    st.markdown("""
        <style>
        .auth-container {
            max-width: 450px;
            margin: 0 auto;
            padding: 2rem;
        }
        .auth-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .auth-header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        .pro-badge {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.3rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            display: inline-block;
            margin-top: 0.5rem;
        }
        .feature-list {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1.5rem 0;
        }
        .feature-item {
            display: flex;
            align-items: center;
            margin: 0.8rem 0;
            font-size: 0.95rem;
        }
        .feature-item::before {
            content: "✓";
            color: #10b981;
            font-weight: bold;
            margin-right: 0.8rem;
            font-size: 1.2rem;
        }
        @media (prefers-color-scheme: dark) {
            .feature-list { background-color: #1e1e1e; }
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="auth-header">
            <h1>🏀 NBA Dashboard</h1>
            <p style="color: #6b7280; font-size: 1.1rem;">Your Fantasy Basketball Companion</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    # ==================== LOGIN TAB ====================
    with tab1:
        st.markdown("### Welcome Back")
        
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                remember_me = st.checkbox("Remember me")
            
            submit = st.form_submit_button("Login", use_container_width=True, type="primary")
            
            if submit:
                if not username or not password:
                    st.error("Please fill in all fields")
                else:
                    user = db.verify_user(username, password)
                    if user:
                        # Create session
                        token = db.create_session(user['id'])
                        if token:
                            st.session_state.user = user
                            st.session_state.session_token = token
                            st.session_state.authenticated = True
                            st.session_state.page = "home"  # Ana sayfaya dön
                            st.success(f"Welcome back, {user['username']}!")
                            st.rerun()
                        else:
                            st.error("Failed to create session")
                    else:
                        st.error("Invalid username or password")
        
        st.markdown("---")
        st.caption("Don't have an account? Register above")
    
    # ==================== REGISTER TAB ====================
    with tab2:
        st.markdown("### Create Account")
        
        # Free vs Pro features
        col_free, col_pro = st.columns(2)
        
        with col_free:
            st.markdown("**Free Features**")
            st.markdown("""
                <div class="feature-list">
                    <div class="feature-item">Live game scores</div>
                    <div class="feature-item">Box scores</div>
                    <div class="feature-item">Fantasy stats</div>
                    <div class="feature-item">Basic filters</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col_pro:
            st.markdown('<span class="pro-badge">PRO FEATURES</span>', unsafe_allow_html=True)
            st.markdown("""
                <div class="feature-list">
                    <div class="feature-item">Player watchlists</div>
                    <div class="feature-item">Trend analysis</div>
                    <div class="feature-item">Custom scoring</div>
                    <div class="feature-item">Injury alerts</div>
                    <div class="feature-item">Export data</div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        with st.form("register_form", clear_on_submit=True):
            reg_username = st.text_input("Username", placeholder="Choose a username", key="reg_user")
            reg_email = st.text_input("Email", placeholder="your@email.com", key="reg_email")
            reg_password = st.text_input("Password", type="password", placeholder="Min. 6 characters", key="reg_pass")
            reg_password2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="reg_pass2")
            
            terms = st.checkbox("I agree to Terms & Conditions")
            
            submit_reg = st.form_submit_button("Create Account", use_container_width=True, type="primary")
            
            if submit_reg:
                # Validation
                errors = []
                
                if not reg_username or not reg_email or not reg_password or not reg_password2:
                    errors.append("All fields are required")
                
                if len(reg_username) < 3:
                    errors.append("Username must be at least 3 characters")
                
                if not is_valid_email(reg_email):
                    errors.append("Invalid email format")
                
                if len(reg_password) < 6:
                    errors.append("Password must be at least 6 characters")
                
                if reg_password != reg_password2:
                    errors.append("Passwords do not match")
                
                if not terms:
                    errors.append("You must agree to Terms & Conditions")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Create user
                    success, message = db.create_user(reg_username, reg_email, reg_password)
                    if success:
                        st.success("✅ Account created successfully! You can now login.")
                        st.balloons()
                    else:
                        st.error(f"Registration failed: {message}")
    
    st.markdown('</div>', unsafe_allow_html=True)

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