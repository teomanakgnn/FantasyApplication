import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from datetime import datetime, timedelta
import bcrypt
import secrets

class Database:
    def __init__(self):
        self.conn = None
        
    def get_connection(self):
        """PostgreSQL bağlantısı oluştur"""
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(
                    host=st.secrets.get("DB_HOST"),
                    database=st.secrets.get("DB_NAME"),
                    user=st.secrets.get("DB_USER"),
                    password=st.secrets.get("DB_PASSWORD"),
                    port=st.secrets.get("DB_PORT", 5432),
                    sslmode='require'  # Bulut bağlantıları için bunu ekleyin
                )
            except Exception as e:
                st.error(f"Database connection error: {e}")
                return None
        return self.conn
    
    def close(self):
        """Bağlantıyı kapat"""
        if self.conn and not self.conn.closed:
            self.conn.close()
    
    # ==================== USER AUTHENTICATION ====================
    
    def create_user(self, username, email, password):
        """Yeni kullanıcı oluştur"""
        conn = self.get_connection()
        if not conn:
            return False, "Database connection failed"
        
        try:
            cursor = conn.cursor()
            
            # Password hash
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            cursor.execute(
                """INSERT INTO users (username, email, password_hash) 
                   VALUES (%s, %s, %s) RETURNING id""",
                (username, email, password_hash)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()
            
            # Create default preferences
            cursor.execute(
                """INSERT INTO user_preferences (user_id, default_weights) 
                   VALUES (%s, %s)""",
                (user_id, '{"pts": 1, "reb": 1.2, "ast": 1.5, "stl": 3, "blk": 3, "to": -1}')
            )
            conn.commit()
            cursor.close()
            
            return True, "User created successfully"
        except psycopg2.IntegrityError as e:
            conn.rollback()
            if 'username' in str(e):
                return False, "Username already exists"
            elif 'email' in str(e):
                return False, "Email already exists"
            return False, "Registration failed"
        except Exception as e:
            conn.rollback()
            return False, f"Error: {str(e)}"
    
    def verify_user(self, username, password):
        """Kullanıcı doğrulama"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM users WHERE username = %s",
                (username,)
            )
            user = cursor.fetchone()
            cursor.close()
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                # Update last login
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET last_login = %s WHERE id = %s",
                    (datetime.now(), user['id'])
                )
                conn.commit()
                cursor.close()
                return dict(user)
            return None
        except Exception as e:
            st.error(f"Login error: {e}")
            return None
    
    def create_session(self, user_id):
        """Oturum oluştur"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(days=7)
            
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO sessions (user_id, session_token, expires_at)
                   VALUES (%s, %s, %s) RETURNING session_token""",
                (user_id, token, expires_at)
            )
            conn.commit()
            cursor.close()
            return token
        except Exception as e:
            st.error(f"Session creation error: {e}")
            return None
    
    def validate_session(self, token):
        """Oturum doğrula"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """SELECT u.* FROM users u
                   JOIN sessions s ON u.id = s.user_id
                   WHERE s.session_token = %s AND s.expires_at > %s""",
                (token, datetime.now())
            )
            user = cursor.fetchone()
            cursor.close()
            return dict(user) if user else None
        except Exception as e:
            return None
    
    def logout_session(self, token):
        """Oturumu sonlandır"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_token = %s", (token,))
            conn.commit()
            cursor.close()
        except Exception as e:
            pass
    
    # ==================== USER PREFERENCES ====================
    
    def get_user_preferences(self, user_id):
        """Kullanıcı tercihlerini getir"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM user_preferences WHERE user_id = %s",
                (user_id,)
            )
            prefs = cursor.fetchone()
            cursor.close()
            return dict(prefs) if prefs else None
        except Exception as e:
            return None
    
    def update_preferences(self, user_id, favorite_teams=None, favorite_players=None, weights=None):
        """Tercihleri güncelle"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if favorite_teams is not None:
                updates.append("favorite_teams = %s")
                params.append(favorite_teams)
            if favorite_players is not None:
                updates.append("favorite_players = %s")
                params.append(favorite_players)
            if weights is not None:
                updates.append("default_weights = %s")
                params.append(weights)
            
            if updates:
                updates.append("updated_at = %s")
                params.append(datetime.now())
                params.append(user_id)
                
                query = f"UPDATE user_preferences SET {', '.join(updates)} WHERE user_id = %s"
                cursor.execute(query, params)
                conn.commit()
            
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False
    
    # ==================== WATCHLIST (PRO FEATURE) ====================
    
    def add_to_watchlist(self, user_id, player_name, notes=""):
        """Watchlist'e oyuncu ekle"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO watchlists (user_id, player_name, notes)
                   VALUES (%s, %s, %s)""",
                (user_id, player_name, notes)
            )
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False
    
    def get_watchlist(self, user_id):
        """Kullanıcının watchlist'ini getir"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM watchlists WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            watchlist = cursor.fetchall()
            cursor.close()
            return [dict(item) for item in watchlist]
        except Exception as e:
            return []
    
    def remove_from_watchlist(self, watchlist_id):
        """Watchlist'ten oyuncu sil"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlists WHERE id = %s", (watchlist_id,))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False
    
    def update_watchlist_notes(self, watchlist_id, notes):
        """Watchlist notlarını güncelle"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE watchlists SET notes = %s WHERE id = %s",
                (notes, watchlist_id)
            )
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False

# Singleton instance
db = Database()