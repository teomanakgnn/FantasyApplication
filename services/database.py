import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from datetime import datetime, timedelta
import bcrypt
import uuid
import secrets

class Database:
    def __init__(self):
        self.conn = None
        
    def get_connection(self):
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(
                    host=st.secrets.get("DB_HOST"),
                    database=st.secrets.get("DB_NAME"),
                    user=st.secrets.get("DB_USER"),
                    password=st.secrets.get("DB_PASSWORD"),
                    port=st.secrets.get("DB_PORT", 5432),
                    sslmode='require'
                )
            except Exception as e:
                st.error(f"Database connection error: {e}")
                return None
        return self.conn
    
    def execute_query(self, query, params=None, fetch=False):
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
                cursor.close()
                return [dict(row) for row in result] if result else []
            else:
                conn.commit()
                cursor.close()
                return True
        except Exception as e:
            conn.rollback()
            print(f"Query error: {e}")
            return None
    
    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
    
    # ==================== USER AUTHENTICATION ====================
    
    def create_user(self, username, email, password):
        conn = self.get_connection()
        if not conn:
            return False, "Database connection failed"
        try:
            cursor = conn.cursor()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, email, password_hash)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()
            cursor.execute(
                "INSERT INTO user_preferences (user_id, default_weights) VALUES (%s, %s)",
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
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (datetime.now(), user['id']))
                conn.commit()
                cursor.close()
                return dict(user)
            return None
        except Exception as e:
            print(f"Login error: {e}")
            return None
    
    def create_session(self, user_id, browser_id=None, ip_address=None, user_agent=None):
        conn = self.get_connection()
        if not conn:
            print("❌ Database connection failed")
            return None
        try:
            session_token = secrets.token_urlsafe(32)
            session_id = str(uuid.uuid4())
            expires_at = datetime.now() + timedelta(days=30)
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO sessions (user_id, session_token, session_id, browser_id, ip_address, user_agent, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING session_token""",
                (user_id, session_token, session_id, browser_id, ip_address, user_agent, expires_at)
            )
            result = cursor.fetchone()
            conn.commit()
            if result:
                cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
                conn.commit()
                cursor.close()
                print(f"✅ Session created for user_id: {user_id}")
                return {'token': session_token, 'session_id': session_id}
            cursor.close()
            return None
        except Exception as e:
            conn.rollback()
            print(f"❌ Session create error: {e}")
            return None
    
    def update_session_fingerprint(self, session_token, fingerprint_hash):
        """Update a session with device fingerprint"""
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET device_fingerprint = %s WHERE session_token = %s",
                (fingerprint_hash, session_token)
            )
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Update fingerprint error: {e}")
            return False
        
    def validate_session_by_fingerprint(self, fingerprint):
        """Cihaz parmak izi ile aktif ve süresi dolmamış oturumu bulur"""
        conn = self.get_connection()
        if not conn: 
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT u.*, 
                    CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                FROM users u
                JOIN sessions s ON u.id = s.user_id
                WHERE s.device_fingerprint = %s 
                AND s.expires_at > CURRENT_TIMESTAMP
                ORDER BY s.created_at DESC LIMIT 1
            """, (fingerprint,))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else None
        except Exception as e:
            print(f"Fingerprint Validation Error: {e}")
            return None

    # ==================== SESSION VALIDATION ====================

    def validate_session_by_token(self, token):
        conn = self.get_connection()
        if not conn: 
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT u.*, 
                CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                FROM users u
                JOIN sessions s ON u.id = s.user_id
                WHERE s.session_token = %s 
                AND s.expires_at > CURRENT_TIMESTAMP
            """, (token,))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else None
        except Exception as e:
            print(f"Token Validation Error: {e}")
            return None

    def validate_session(self, session_token, browser_id=None):
        """session_token ile doğrula (isteğe bağlı browser_id)"""
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if browser_id:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                        CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_token = %s AND s.browser_id = %s
                    AND s.expires_at > CURRENT_TIMESTAMP
                """, (session_token, browser_id))
            else:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                        CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_token = %s
                    AND s.expires_at > CURRENT_TIMESTAMP
                """, (session_token,))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else None
        except Exception as e:
            print(f"❌ Session validation error: {e}")
            return None

    def validate_session_by_id(self, session_id, browser_id=None):
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if browser_id:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                        CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_id = %s AND s.browser_id = %s
                    AND s.expires_at > CURRENT_TIMESTAMP
                """, (session_id, browser_id))
            else:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                        CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_id = %s
                    AND s.expires_at > CURRENT_TIMESTAMP
                """, (session_id,))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else None
        except Exception as e:
            print(f"❌ Session ID validation error: {e}")
            return None

    def logout_session(self, session_token, browser_id=None):
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            if browser_id:
                cursor.execute(
                    "DELETE FROM sessions WHERE session_token = %s AND browser_id = %s",
                    (session_token, browser_id)
                )
            else:
                cursor.execute("DELETE FROM sessions WHERE session_token = %s", (session_token,))
            conn.commit()
            cursor.close()
            print("✅ Session logged out")
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Logout error: {e}")
            return False

    def logout_session_by_id(self, session_id, browser_id=None):
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            if browser_id:
                cursor.execute(
                    "DELETE FROM sessions WHERE session_id = %s AND browser_id = %s",
                    (session_id, browser_id)
                )
            else:
                cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Logout error: {e}")
            return False

    # ==================== USER PREFERENCES ====================
    
    def get_user_preferences(self, user_id):
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM user_preferences WHERE user_id = %s", (user_id,))
            prefs = cursor.fetchone()
            cursor.close()
            return dict(prefs) if prefs else None
        except Exception as e:
            return None
    
    def update_preferences(self, user_id, favorite_teams=None, favorite_players=None, weights=None):
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
                cursor.execute(f"UPDATE user_preferences SET {', '.join(updates)} WHERE user_id = %s", params)
                conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False

    def get_score_display_preference(self, user_id):
        conn = self.get_connection()
        if not conn:
            return 'full'
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT score_display_mode FROM user_preferences WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            if result and result.get('score_display_mode'):
                return result['score_display_mode']
            return 'full'
        except Exception as e:
            return 'full'

    def update_score_display_preference(self, user_id, mode):
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user_preferences WHERE user_id = %s", (user_id,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute(
                    "UPDATE user_preferences SET score_display_mode = %s, updated_at = %s WHERE user_id = %s",
                    (mode, datetime.now(), user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO user_preferences (user_id, score_display_mode) VALUES (%s, %s)",
                    (user_id, mode)
                )
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False

    # ==================== WATCHLIST ====================
    
    def add_to_watchlist(self, user_id, player_name, notes=""):
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlists (user_id, player_name, notes) VALUES (%s, %s, %s)",
                (user_id, player_name, notes)
            )
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False
    
    def get_watchlist(self, user_id):
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
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE watchlists SET notes = %s WHERE id = %s", (notes, watchlist_id))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            return False

    # ==================== DAILY TRIVIA ====================
    
    def get_daily_trivia(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            today = datetime.now().date()
            cursor.execute("""
                SELECT id, question, option_a, option_b, option_c, option_d,
                    correct_option, explanation
                FROM trivia_questions WHERE date = %s LIMIT 1
            """, (today,))
            row = cursor.fetchone()
            cursor.close()
            conn.commit()
            if row:
                return {
                    'id': row[0], 'question': row[1],
                    'option_a': row[2], 'option_b': row[3],
                    'option_c': row[4], 'option_d': row[5],
                    'correct_option': row[6], 'explanation': row[7]
                }
            return None
        except Exception as e:
            print(f"❌ Trivia fetch error: {e}")
            try: 
                conn.rollback()
            except: 
                pass
            return None

    def get_user_streak(self, user_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT streak FROM user_trivia_streak WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.commit()
            return row[0] if row else 0
        except Exception as e:
            print(f"❌ Get streak error: {e}")
            return 0

    def mark_user_trivia_played(self, user_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            today = datetime.now().date()
            cursor.execute("""
                INSERT INTO user_trivia_history (user_id, played_date)
                VALUES (%s, %s)
                ON CONFLICT (user_id, played_date) DO NOTHING
            """, (user_id, today))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ Mark trivia error: {e}")
            try: 
                conn.rollback()
            except: 
                pass
            return False

    def check_user_played_trivia_today(self, user_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            today = datetime.now().date()
            cursor.execute("""
                SELECT COUNT(*) FROM user_trivia_history
                WHERE user_id = %s AND played_date = %s
            """, (user_id, today))
            count = cursor.fetchone()[0]
            cursor.close()
            conn.commit()
            return count > 0
        except Exception as e:
            print(f"❌ Check trivia error: {e}")
            return False

    # ==================== USER ====================

    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            if result:
                user = dict(result)
                user['is_pro'] = (user.get('username') == 'admin')
                return user
            return None
        except Exception as e:
            print(f"❌ get_user_by_id error: {e}")
            return None


# Singleton instance
db = Database()