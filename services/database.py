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
        """PostgreSQL bağlantısı oluştur"""
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
        """Generic query execution helper"""
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
            print(f"Login error: {e}")
            return None
    
    def create_session(self, user_id, browser_id=None, ip_address=None, user_agent=None):
        """Yeni session oluştur (browser_id ile) ve dictionary döndür"""
        conn = self.get_connection()
        if not conn:
            print("❌ Database connection failed")
            return None
        
        try:
            # Token ve Session ID oluştur
            session_token = secrets.token_urlsafe(32)
            session_id = str(uuid.uuid4()) # Benzersiz Session ID
            expires_at = datetime.now() + timedelta(days=30)
            
            cursor = conn.cursor()
            
            # session_id sütununu da INSERT işlemine ekliyoruz
            cursor.execute(
                """INSERT INTO sessions (user_id, session_token, session_id, browser_id, ip_address, user_agent, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING session_token""",
                (user_id, session_token, session_id, browser_id, ip_address, user_agent, expires_at)
            )
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                # Last login güncelle
                cursor.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                    (user_id,)
                )
                conn.commit()
                cursor.close()
                
                print(f"✅ Session created for user_id: {user_id}")
                
                # ARTIK SÖZLÜK DÖNDÜRÜYORUZ (Hatanın çözümü)
                return {
                    'token': session_token,
                    'session_id': session_id
                }
            
            cursor.close()
            return None
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Session create error: {e}")
            return None
    
    def validate_session(self, session_token, browser_id=None):
        """Session token'ı doğrula (browser_id ile)"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Browser ID kontrolü ile
            if browser_id:
                cursor.execute(
                    """SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                              CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                       FROM users u
                       JOIN sessions s ON u.id = s.user_id
                       WHERE s.session_token = %s 
                       AND s.browser_id = %s
                       AND s.expires_at > CURRENT_TIMESTAMP""",
                    (session_token, browser_id)
                )
            else:
                # Fallback (eski sistem uyumluluğu için)
                cursor.execute(
                    """SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                              CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                       FROM users u
                       JOIN sessions s ON u.id = s.user_id
                       WHERE s.session_token = %s 
                       AND s.expires_at > CURRENT_TIMESTAMP""",
                    (session_token,)
                )
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            
            return None
            
        except Exception as e:
            print(f"❌ Session validation error: {e}")
            return None
    
    def logout_session(self, session_token, browser_id=None):
        """Session'ı sonlandır"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            if browser_id:
                # Sadece bu browser'ın session'ını sil
                cursor.execute(
                    "DELETE FROM sessions WHERE session_token = %s AND browser_id = %s",
                    (session_token, browser_id)
                )
            else:
                # Token'a ait tüm session'ları sil
                cursor.execute(
                    "DELETE FROM sessions WHERE session_token = %s",
                    (session_token,)
                )
            
            conn.commit()
            cursor.close()
            print(f"✅ Session logged out")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Logout error: {e}")
            return False
    
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
    
 # DATABASE HELPER METHODS
# services/database.py dosyanıza bu metodları ekleyin

    def validate_session_by_token(self, token):
        """
        Token ile session'ı doğrula
        Returns: user dict or None
        """
        try:
            c = self.conn.cursor()
            
            # Session tablosundan token'ı bul
            c.execute('''
                SELECT s.user_id, s.expires_at, u.username, u.email, u.is_pro
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.is_active = 1
            ''', (token,))
            
            result = c.fetchone()
            
            if not result:
                return None
            
            user_id, expires_at, username, email, is_pro = result
            
            # Süre kontrolü
            from datetime import datetime
            expiry = datetime.fromisoformat(expires_at)
            
            if datetime.now() > expiry:
                # Session süresi dolmuş
                c.execute('UPDATE sessions SET is_active = 0 WHERE token = ?', (token,))
                self.conn.commit()
                return None
            
            return {
                'id': user_id,
                'username': username,
                'email': email,
                'is_pro': bool(is_pro)
            }
            
        except Exception as e:
            print(f"❌ validate_session_by_token error: {e}")
            return None


    def get_user_by_id(self, user_id):
        """
        User ID ile kullanıcı bilgilerini getir
        Returns: user dict or None
        """
        try:
            c = self.conn.cursor()
            
            c.execute('''
                SELECT id, username, email, is_pro, created_at
                FROM users
                WHERE id = ?
            ''', (user_id,))
            
            result = c.fetchone()
            
            if not result:
                return None
            
            user_id, username, email, is_pro, created_at = result
            
            return {
                'id': user_id,
                'username': username,
                'email': email,
                'is_pro': bool(is_pro),
                'created_at': created_at
            }
            
        except Exception as e:
            print(f"❌ get_user_by_id error: {e}")
            return None


    def cleanup_expired_sessions(self):
        """
        Süresi dolmuş session'ları temizle
        Cron job ile günlük çalıştırılmalı
        """
        try:
            c = self.conn.cursor()
            
            from datetime import datetime
            now = datetime.now().isoformat()
            
            # Süresi dolmuş session'ları pasif yap
            c.execute('''
                UPDATE sessions
                SET is_active = 0
                WHERE expires_at < ? AND is_active = 1
            ''', (now,))
            
            deleted_count = c.rowcount
            self.conn.commit()
            
            print(f"🧹 Cleaned up {deleted_count} expired sessions")
            return deleted_count
            
        except Exception as e:
            print(f"❌ cleanup_expired_sessions error: {e}")
            return 0


    def get_user_active_sessions(self, user_id):
        """
        Kullanıcının aktif session'larını listele
        Multi-device kullanımı için
        """
        try:
            c = self.conn.cursor()
            
            c.execute('''
                SELECT token, created_at, expires_at, browser_id, ip_address, user_agent
                FROM sessions
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
            ''', (user_id,))
            
            results = c.fetchall()
            
            sessions = []
            for row in results:
                sessions.append({
                    'token': row[0],
                    'created_at': row[1],
                    'expires_at': row[2],
                    'browser_id': row[3],
                    'ip_address': row[4],
                    'user_agent': row[5]
                })
            
            return sessions
            
        except Exception as e:
            print(f"❌ get_user_active_sessions error: {e}")
            return []


    def revoke_session(self, token):
        """
        Belirli bir session'ı iptal et
        Güvenlik için (örn: cihaz kaybı)
        """
        try:
            c = self.conn.cursor()
            
            c.execute('''
                UPDATE sessions
                SET is_active = 0
                WHERE token = ?
            ''', (token,))
            
            self.conn.commit()
            
            if c.rowcount > 0:
                print(f"✅ Session revoked: {token[:10]}...")
                return True
            else:
                print(f"⚠️ Session not found: {token[:10]}...")
                return False
                
        except Exception as e:
            print(f"❌ revoke_session error: {e}")
            return False


    def revoke_all_user_sessions(self, user_id, except_token=None):
        """
        Kullanıcının tüm session'larını iptal et
        Güvenlik için (örn: şifre değişimi sonrası)
        
        except_token: Bu token hariç tüm session'ları iptal et (mevcut session korunsun)
        """
        try:
            c = self.conn.cursor()
            
            if except_token:
                c.execute('''
                    UPDATE sessions
                    SET is_active = 0
                    WHERE user_id = ? AND token != ? AND is_active = 1
                ''', (user_id, except_token))
            else:
                c.execute('''
                    UPDATE sessions
                    SET is_active = 0
                    WHERE user_id = ? AND is_active = 1
                ''', (user_id,))
            
            revoked_count = c.rowcount
            self.conn.commit()
            
            print(f"🔒 Revoked {revoked_count} sessions for user {user_id}")
            return revoked_count
            
        except Exception as e:
            print(f"❌ revoke_all_user_sessions error: {e}")
            return 0


    # BONUS: Session Statistics
    def get_session_stats(self):
        """
        Genel session istatistikleri
        Admin dashboard için
        """
        try:
            c = self.conn.cursor()
            
            # Toplam aktif session
            c.execute('SELECT COUNT(*) FROM sessions WHERE is_active = 1')
            active_sessions = c.fetchone()[0]
            
            # Benzersiz aktif kullanıcı
            c.execute('SELECT COUNT(DISTINCT user_id) FROM sessions WHERE is_active = 1')
            active_users = c.fetchone()[0]
            
            # Bugün oluşturulan session
            from datetime import datetime, timedelta
            today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
            
            c.execute('SELECT COUNT(*) FROM sessions WHERE created_at >= ?', (today_start,))
            today_sessions = c.fetchone()[0]
            
            # Süresi dolmuş session (henüz temizlenmemiş)
            now = datetime.now().isoformat()
            c.execute('SELECT COUNT(*) FROM sessions WHERE expires_at < ? AND is_active = 1', (now,))
            expired_sessions = c.fetchone()[0]
            
            return {
                'active_sessions': active_sessions,
                'active_users': active_users,
                'today_sessions': today_sessions,
                'expired_sessions': expired_sessions
            }
            
        except Exception as e:
            print(f"❌ get_session_stats error: {e}")
            return None
 
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
        
    # ==================== DAILY TRIVIA ====================
    
    def get_daily_trivia(self):
        """Bugünün trivia sorusunu getir"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM trivia_questions WHERE game_date = %s",
                (datetime.now().date(),)
            )
            question = cursor.fetchone()
            cursor.close()
            return dict(question) if question else None
        except Exception as e:
            st.error(f"Trivia error: {e}")
            return None

    def get_user_streak(self, user_id):
        """Kullanıcının mevcut serisini getir"""
        conn = self.get_connection()
        if not conn:
            return 0
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_streak FROM users WHERE id = %s", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result and result[0] is not None else 0
        except Exception as e:
            return 0

    def mark_user_trivia_played(self, user_id):
        """Kullanıcının bugün trivia oynadığını işaretle ve STREAK hesapla"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # 1. Önce kullanıcının son oynama tarihini ve mevcut serisini al
            cursor.execute("SELECT last_trivia_date, current_streak FROM users WHERE id = %s", (user_id,))
            result = cursor.fetchone()
            
            last_date = result[0]
            current_streak = result[1] if result[1] is not None else 0
            
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            
            new_streak = 1 # Varsayılan: Zincir kırıldı veya yeni başladı
            
            if last_date == today:
                # Zaten bugün oynanmış (Hata önlemi)
                new_streak = current_streak
            elif last_date == yesterday:
                # Dün oynamış, seriyi artır!
                new_streak = current_streak + 1
            else:
                # Dün oynamamış, seri 1'e döner
                new_streak = 1
            
            # 2. Veritabanını güncelle
            cursor.execute(
                "UPDATE users SET last_trivia_date = %s, current_streak = %s WHERE id = %s",
                (today, new_streak, user_id)
            )
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            st.error(f"Streak update error: {e}")
            return False
            
    def check_user_played_trivia_today(self, user_id):
        """Kullanıcı bugün trivia oynadı mı?"""
        conn = self.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_trivia_date FROM users WHERE id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0] == datetime.now().date():
                return True
            return False
        except Exception as e:
            return False
        
    def get_score_display_preference(self, user_id):
        """Kullanıcının skor gösterim tercihini getir"""
        conn = self.get_connection()
        if not conn:
            return 'full'
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT score_display_mode FROM user_preferences WHERE user_id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result and result.get('score_display_mode'):
                return result['score_display_mode']
            return 'full'  # Default
        except Exception as e:
            print(f"Error getting score display preference: {e}")
            return 'full'

    def update_score_display_preference(self, user_id, mode):
        """Kullanıcının skor gösterim tercihini güncelle"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Önce user_preferences kaydı var mı kontrol et
            cursor.execute(
                "SELECT id FROM user_preferences WHERE user_id = %s",
                (user_id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                # Güncelle
                cursor.execute(
                    "UPDATE user_preferences SET score_display_mode = %s, updated_at = %s WHERE user_id = %s",
                    (mode, datetime.now(), user_id)
                )
            else:
                # Yeni kayıt oluştur
                cursor.execute(
                    """INSERT INTO user_preferences (user_id, score_display_mode) 
                    VALUES (%s, %s)""",
                    (user_id, mode)
                )
            
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error updating score display preference: {e}")
            return False
    
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
        
    def validate_session_by_id(self, session_id, browser_id=None):
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if browser_id:
                cursor.execute(
                    """SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                            CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_id = %s 
                    AND s.browser_id = %s
                    AND s.expires_at > CURRENT_TIMESTAMP""",
                    (session_id, browser_id)
                )
            else:
                cursor.execute(
                    """SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                            CASE WHEN u.username = 'admin' THEN true ELSE false END as is_pro
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_id = %s 
                    AND s.expires_at > CURRENT_TIMESTAMP""",
                    (session_id,)
                )
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            
            return None
            
        except Exception as e:
            print(f"❌ Session ID validation error: {e}")
            return None    


    def logout_session_by_id(self, session_id, browser_id=None):
        """Session ID ile session'ı sonlandır"""
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
                cursor.execute(
                    "DELETE FROM sessions WHERE session_id = %s",
                    (session_id,)
                )
            
            conn.commit()
            cursor.close()
            print(f"✅ Session logged out by ID")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Logout error: {e}")
            return False
# Singleton instance
db = Database()