"""
Veritabani katmani (Neon/Postgres).

Onceki surumdeki sorunlar ve cozumleri:

* ``is_pro`` dort ayri sorguda ``username = 'admin'`` diye sabit kodluydu.
  Artik ``users.plan`` sutunu var; Pro uyelik verinin kendisinde tutuluyor
  ve suresi dolabiliyor.
* Tek bir baglanti acik tutuluyordu. Neon bosta kalan baglantilari kapatir,
  bu da rastgele "connection already closed" hatalari demekti. Artik her
  sorgu kopmus baglantiyi bir kez yeniden kuruyor.
* Oturum anahtarlari veritabaninda duz metindi; veritabanini goren biri
  dogrudan oturum caliyordu. Artik yalnizca SHA-256 ozeti saklaniyor.
* ``verify_user`` kullanicinin parola ozetini de dondurup ``session_state``
  icine tasiyordu. Artik disariya yalnizca guvenli alanlar cikiyor.
* Izleme listesi islemleri yalniz satir kimligi aliyordu; baska bir
  kullanicinin satirini silmek mumkundu. Artik sahiplik sart.
* Giris denemelerinde hiz siniri yoktu.
* Sirlar tanimli degilse Streamlit ekrana yerel dosya yollarini basan
  kirmizi bir kutu koyuyordu. Artik katman sessizce devre disi kaliyor.
"""
import hashlib
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta

import bcrypt
import psycopg2
import streamlit as st
from psycopg2 import errors as pg_errors
from psycopg2.extras import RealDictCursor

# ==================== PLANLAR ====================

PLAN_FREE = "free"
PLAN_PRO = "pro"
VALID_PLANS = (PLAN_FREE, PLAN_PRO)

# Ucretsiz planin sinirlari. Pro'da sinirsiz.
FREE_WATCHLIST_LIMIT = 10
FREE_SAVED_DRAFT_LIMIT = 2

# Giris denemesi hiz siniri
LOGIN_WINDOW_MINUTES = 15
LOGIN_MAX_FAILURES = 8

SESSION_DAYS = 30

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MIN_PASSWORD_LENGTH = 8

# Kullanicidan gizlenecek alanlar (parola ozeti disariya cikmamali)
_PRIVATE_USER_FIELDS = {"password_hash", "reset_token", "reset_token_expires"}


def _hash_token(raw):
    """Oturum anahtarinin veritabaninda saklanan ozeti."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _public_user(row):
    """Veritabani satirini disariya verilebilir bir sozluge cevirir."""
    if not row:
        return None
    user = {k: v for k, v in dict(row).items() if k not in _PRIVATE_USER_FIELDS}
    plan = (user.get("plan") or PLAN_FREE).lower()
    expires = user.get("plan_expires_at")
    active = plan == PLAN_PRO and (expires is None or expires > datetime.now())
    user["plan"] = plan
    user["is_pro"] = bool(active)
    return user


class Database:
    """Uygulamanin tek veritabani giris noktasi."""

    def __init__(self):
        self._conn = None
        self._schema_ready = False
        self._unavailable_reason = None

    # ==================== BAGLANTI ====================

    def _credentials(self):
        """Sirlari okur. Tanimli degilse None doner (ekrana hata basmaz)."""
        try:
            return {
                "host": st.secrets["DB_HOST"],
                "dbname": st.secrets["DB_NAME"],
                "user": st.secrets["DB_USER"],
                "password": st.secrets["DB_PASSWORD"],
                "port": st.secrets.get("DB_PORT", 5432),
            }
        except Exception:
            self._unavailable_reason = "missing_secrets"
            return None

    def _open(self):
        creds = self._credentials()
        if not creds:
            return None
        try:
            conn = psycopg2.connect(sslmode="require", connect_timeout=10, **creds)
            conn.autocommit = False
            return conn
        except Exception as exc:
            self._unavailable_reason = str(exc)
            return None

    def get_connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = self._open()
            if self._conn is not None:
                self._ensure_schema()
        return self._conn

    @property
    def available(self):
        """Veritabani kullanilabilir mi? Ekrana hata basmadan kontrol eder."""
        return self.get_connection() is not None

    @property
    def unavailable_reason(self):
        return self._unavailable_reason

    def _run(self, sql, params=None, fetch=None, _retry=True):
        """
        Tek sorgu calistirir.

        fetch: None (sadece calistir), "one", "all", "value",
        "rowcount" (etkilenen satir sayisi -- sahiplik kontrollu
        silme/guncellemelerde "hicbir sey eslesmedi"yi ayirt etmek icin).
        Baglanti kopmussa bir kez yeniden baglanip tekrar dener; Neon
        bosta kalan baglantilari kapattigi icin bu sart.
        """
        conn = self.get_connection()
        if conn is None:
            return None
        try:
            factory = RealDictCursor if fetch in ("one", "all") else None
            with conn.cursor(cursor_factory=factory) as cur:
                # params bos tuple ise psycopg2 yine bicimlendirme
                # yapiyor ve SQL icindeki duz '%' (LIKE kaliplari)
                # patliyor. Parametresiz sorguda None gecilmeli.
                cur.execute(sql, params if params else None)
                if fetch == "one":
                    row = cur.fetchone()
                    result = dict(row) if row else None
                elif fetch == "all":
                    result = [dict(r) for r in cur.fetchall()]
                elif fetch == "value":
                    row = cur.fetchone()
                    result = row[0] if row else None
                elif fetch == "rowcount":
                    result = cur.rowcount
                else:
                    result = True
            conn.commit()
            return result
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # Baglanti dusmus: bir kez yeniden kur ve tekrar dene
            try:
                if self._conn and not self._conn.closed:
                    self._conn.close()
            except Exception:
                pass
            self._conn = None
            if _retry:
                return self._run(sql, params, fetch, _retry=False)
            return None
        except pg_errors.UniqueViolation:
            conn.rollback()
            raise
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return None

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
        self._conn = None

    # ==================== SEMA ====================

    def _ensure_schema(self):
        """
        Eksik sutun/tablolari tamamlar. Her adim tekrar calistirilabilir,
        yani uygulama her acildiginda guvenle cagrilabilir.
        """
        if self._schema_ready:
            return
        steps = [
            # Plan sistemi: Pro uyelik artik veride
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            # Oturum anahtarlari artik ozetleniyor
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS token_hash TEXT",
            "CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions (token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists (user_id)",
            # Giris denemesi hiz siniri
            """CREATE TABLE IF NOT EXISTS login_attempts (
                   id SERIAL PRIMARY KEY,
                   username TEXT NOT NULL,
                   ip_address TEXT,
                   success BOOLEAN NOT NULL DEFAULT FALSE,
                   attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
               )""",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts (username, attempted_at)",
            # Seri tablosunda gun bilgisi yoksa seri artirilamiyor
            "ALTER TABLE user_trivia_streak ADD COLUMN IF NOT EXISTS last_played DATE",
        ]
        conn = self._conn
        if conn is None:
            return
        for sql in steps:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            except Exception:
                # Tablo henuz yoksa veya yetki yoksa sessizce gec;
                # uygulamanin acilisini engellememeli.
                try:
                    conn.rollback()
                except Exception:
                    pass
        self._schema_ready = True

    # ==================== KAYIT / GIRIS ====================

    @staticmethod
    def validate_registration(username, email, password):
        """Kayit alanlarini dogrular. (ok, mesaj) doner."""
        username = (username or "").strip()
        email = (email or "").strip().lower()
        if not USERNAME_RE.match(username):
            return False, ("Username must be 3-32 characters and can contain "
                           "letters, numbers, dot, underscore or hyphen.")
        if not EMAIL_RE.match(email):
            return False, "Enter a valid email address."
        if len(password or "") < MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        return True, ""

    def create_user(self, username, email, password):
        ok, message = self.validate_registration(username, email, password)
        if not ok:
            return False, message

        username = username.strip()
        email = email.strip().lower()
        conn = self.get_connection()
        if conn is None:
            return False, "Service is temporarily unavailable. Try again shortly."

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            # Kullanici ve tercihleri TEK islemde olusuyor; eskiden iki ayri
            # commit vardi ve ikincisi patlayinca tercihsiz kullanici kaliyordu.
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                if cur.fetchone():
                    conn.rollback()
                    return False, "That username is taken."
                cur.execute("SELECT 1 FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
                if cur.fetchone():
                    conn.rollback()
                    return False, "That email is already registered."
                cur.execute(
                    "INSERT INTO users (username, email, password_hash, plan) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (username, email, password_hash, PLAN_FREE),
                )
                user_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO user_preferences (user_id, default_weights) VALUES (%s, %s)",
                    (user_id, json.dumps({"pts": 1, "reb": 1.2, "ast": 1.5,
                                          "stl": 3, "blk": 3, "to": -1})),
                )
            conn.commit()
            return True, "Account created."
        except pg_errors.UniqueViolation:
            conn.rollback()
            return False, "That username or email is already registered."
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return False, "Could not create the account. Try again."

    def _recent_failures(self, username):
        count = self._run(
            "SELECT COUNT(*) FROM login_attempts "
            "WHERE LOWER(username) = LOWER(%s) AND success = FALSE "
            "AND attempted_at > CURRENT_TIMESTAMP - INTERVAL '%s minutes'",
            (username, LOGIN_WINDOW_MINUTES),
            fetch="value",
        )
        return int(count or 0)

    def _record_attempt(self, username, success, ip_address=None):
        self._run(
            "INSERT INTO login_attempts (username, ip_address, success) VALUES (%s, %s, %s)",
            (username, ip_address, success),
        )

    def verify_user(self, username, password, ip_address=None):
        """
        Kullaniciyi dogrular.

        Basarisiz denemeler sayilir; kisa surede cok deneme olursa hesap
        gecici olarak kilitlenir. Donen sozlukte parola ozeti YOKTUR.
        """
        username = (username or "").strip()
        if not username or not password:
            return None
        if self.get_connection() is None:
            return None

        if self._recent_failures(username) >= LOGIN_MAX_FAILURES:
            return "locked"

        row = self._run(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)",
            (username, username),
            fetch="one",
        )
        stored = (row or {}).get("password_hash")
        ok = False
        if stored:
            try:
                ok = bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except ValueError:
                ok = False

        self._record_attempt(username, ok, ip_address)
        if not ok:
            return None

        self._run("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (row["id"],))
        return _public_user(row)

    def change_password(self, user_id, current_password, new_password):
        if len(new_password or "") < MIN_PASSWORD_LENGTH:
            return False, f"New password must be at least {MIN_PASSWORD_LENGTH} characters."
        row = self._run("SELECT password_hash FROM users WHERE id = %s", (user_id,), fetch="one")
        if not row:
            return False, "Account not found."
        try:
            if not bcrypt.checkpw(current_password.encode("utf-8"),
                                  row["password_hash"].encode("utf-8")):
                return False, "Current password is incorrect."
        except ValueError:
            return False, "Current password is incorrect."

        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        if self._run("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id)):
            # Parola degisince diger cihazlardaki oturumlar dusmeli
            self._run("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            return True, "Password updated. Other devices have been signed out."
        return False, "Could not update the password."

    def update_email(self, user_id, email):
        email = (email or "").strip().lower()
        if not EMAIL_RE.match(email):
            return False, "Enter a valid email address."
        taken = self._run(
            "SELECT 1 FROM users WHERE LOWER(email) = LOWER(%s) AND id <> %s",
            (email, user_id), fetch="value")
        if taken:
            return False, "That email is already registered."
        if self._run("UPDATE users SET email = %s WHERE id = %s", (email, user_id)):
            return True, "Email updated."
        return False, "Could not update the email."

    def delete_account(self, user_id):
        """
        Hesabi ve bagli tum kayitlari siler.

        Bagli tablolar tek tek siliniyor: hepsi tek islemde yapilinca
        henuz olusturulmamis bir tablo (ornegin mock_drafts) butun
        islemi dusuruyor ve hesap silinemiyordu.
        """
        if self.get_connection() is None:
            return False
        for table in ("sessions", "watchlists", "user_preferences",
                      "mock_drafts", "user_trivia_history", "user_trivia_streak"):
            if self._run("SELECT to_regclass(%s)", ("public." + table,), fetch="value"):
                self._run("DELETE FROM %s WHERE user_id = %%s" % table, (user_id,))
        affected = self._run("DELETE FROM users WHERE id = %s", (user_id,), fetch="rowcount")
        return bool(affected)

    # ==================== PLAN ====================

    def set_plan(self, user_id, plan, days=None):
        """Kullanicinin planini ayarlar. days=None ise suresiz."""
        plan = (plan or PLAN_FREE).lower()
        if plan not in VALID_PLANS:
            return False
        expires = datetime.now() + timedelta(days=days) if days else None
        return bool(self._run(
            "UPDATE users SET plan = %s, plan_expires_at = %s WHERE id = %s",
            (plan, expires, user_id)))

    def get_plan(self, user_id):
        row = self._run("SELECT plan, plan_expires_at FROM users WHERE id = %s",
                        (user_id,), fetch="one")
        if not row:
            return PLAN_FREE, None
        return (row.get("plan") or PLAN_FREE).lower(), row.get("plan_expires_at")

    # ==================== OTURUMLAR ====================

    def create_session(self, user_id, browser_id=None, ip_address=None, user_agent=None):
        raw_token = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=SESSION_DAYS)
        ok = self._run(
            """INSERT INTO sessions
               (user_id, session_token, token_hash, session_id, browser_id,
                ip_address, user_agent, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            # session_token sutunu NOT NULL olabilir; ozetini yaziyoruz ki
            # duz anahtar hicbir yerde saklanmasin.
            (user_id, _hash_token(raw_token), _hash_token(raw_token), session_id,
             browser_id, ip_address, user_agent, expires_at),
        )
        if not ok:
            return None
        self._run("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
        return {"token": raw_token, "session_id": session_id}

    def _user_for_session(self, where_sql, params):
        row = self._run(
            "SELECT u.* FROM users u JOIN sessions s ON u.id = s.user_id "
            "WHERE %s AND s.expires_at > CURRENT_TIMESTAMP "
            "ORDER BY s.created_at DESC LIMIT 1" % where_sql,
            params, fetch="one")
        return _public_user(row)

    def validate_session_by_token(self, token):
        if not token:
            return None
        user = self._user_for_session("s.token_hash = %s", (_hash_token(token),))
        if user:
            return user
        # Gecis donemi: ozetleme oncesi acilmis oturumlar duz anahtarla
        # duruyor. Bulursak ozete yukseltip kullaniciyi disari atmiyoruz.
        legacy = self._user_for_session("s.session_token = %s", (token,))
        if legacy:
            self._run("UPDATE sessions SET token_hash = %s, session_token = %s "
                      "WHERE session_token = %s",
                      (_hash_token(token), _hash_token(token), token))
        return legacy

    def validate_session(self, session_token, browser_id=None):
        return self.validate_session_by_token(session_token)

    def validate_session_by_id(self, session_id, browser_id=None):
        if not session_id:
            return None
        return self._user_for_session("s.session_id = %s", (session_id,))

    def validate_session_by_fingerprint(self, fingerprint):
        if not fingerprint:
            return None
        return self._user_for_session("s.device_fingerprint = %s", (fingerprint,))

    def update_session_fingerprint(self, session_token, fingerprint_hash):
        if not session_token:
            return False
        return bool(self._run(
            "UPDATE sessions SET device_fingerprint = %s WHERE token_hash = %s",
            (fingerprint_hash, _hash_token(session_token))))

    def logout_session(self, session_token, browser_id=None):
        if not session_token:
            return False
        return bool(self._run(
            "DELETE FROM sessions WHERE token_hash = %s OR session_token = %s",
            (_hash_token(session_token), session_token)))

    def logout_session_by_id(self, session_id, browser_id=None):
        if not session_id:
            return False
        return bool(self._run("DELETE FROM sessions WHERE session_id = %s", (session_id,)))

    def list_sessions(self, user_id):
        """Hesap ayarlarinda gosterilen aktif cihazlar."""
        return self._run(
            "SELECT session_id, ip_address, user_agent, created_at, expires_at "
            "FROM sessions WHERE user_id = %s AND expires_at > CURRENT_TIMESTAMP "
            "ORDER BY created_at DESC",
            (user_id,), fetch="all") or []

    def logout_other_sessions(self, user_id, keep_token):
        return bool(self._run(
            "DELETE FROM sessions WHERE user_id = %s AND token_hash <> %s",
            (user_id, _hash_token(keep_token or ""))))

    def purge_expired_sessions(self):
        return bool(self._run("DELETE FROM sessions WHERE expires_at <= CURRENT_TIMESTAMP"))

    def get_user_by_id(self, user_id):
        return _public_user(self._run("SELECT * FROM users WHERE id = %s",
                                      (user_id,), fetch="one"))

    # ==================== TERCIHLER ====================

    def get_user_preferences(self, user_id):
        return self._run("SELECT * FROM user_preferences WHERE user_id = %s",
                         (user_id,), fetch="one")

    def update_preferences(self, user_id, favorite_teams=None, favorite_players=None, weights=None):
        sets, params = [], []
        for column, value in (("favorite_teams", favorite_teams),
                              ("favorite_players", favorite_players),
                              ("default_weights", weights)):
            if value is not None:
                sets.append("%s = %%s" % column)
                params.append(value)
        if not sets:
            return True
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        return bool(self._run(
            "UPDATE user_preferences SET %s WHERE user_id = %%s" % ", ".join(sets), params))

    def get_score_display_preference(self, user_id):
        value = self._run("SELECT score_display_mode FROM user_preferences WHERE user_id = %s",
                          (user_id,), fetch="value")
        return value or "full"

    def update_score_display_preference(self, user_id, mode):
        return bool(self._run(
            "INSERT INTO user_preferences (user_id, score_display_mode) VALUES (%s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET score_display_mode = EXCLUDED.score_display_mode, "
            "updated_at = CURRENT_TIMESTAMP",
            (user_id, mode)))

    # ==================== IZLEME LISTESI ====================

    def watchlist_count(self, user_id):
        return int(self._run("SELECT COUNT(*) FROM watchlists WHERE user_id = %s",
                             (user_id,), fetch="value") or 0)

    def add_to_watchlist(self, user_id, player_name, notes=""):
        return bool(self._run(
            "INSERT INTO watchlists (user_id, player_name, notes) VALUES (%s, %s, %s)",
            (user_id, player_name, notes)))

    def get_watchlist(self, user_id):
        return self._run(
            "SELECT * FROM watchlists WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,), fetch="all") or []

    def remove_from_watchlist(self, watchlist_id, user_id=None):
        """
        Sahiplik sart: eskiden yalnizca satir kimligi isteniyordu ve
        baska bir kullanicinin satiri silinebiliyordu.
        """
        if user_id is None:
            return False
        affected = self._run("DELETE FROM watchlists WHERE id = %s AND user_id = %s",
                             (watchlist_id, user_id), fetch="rowcount")
        return bool(affected)

    def update_watchlist_notes(self, watchlist_id, notes, user_id=None):
        if user_id is None:
            return False
        affected = self._run(
            "UPDATE watchlists SET notes = %s WHERE id = %s AND user_id = %s",
            (notes, watchlist_id, user_id), fetch="rowcount")
        return bool(affected)

    def clear_watchlist(self, user_id):
        return bool(self._run("DELETE FROM watchlists WHERE user_id = %s", (user_id,)))

    # ==================== GUNLUK TRIVIA ====================

    def get_daily_trivia(self):
        """Bugunun sorusu. Tablo gun basina tek soru tutuyor."""
        return self._run(
            "SELECT id, question, option_a, option_b, option_c, option_d, "
            "correct_option, explanation FROM trivia_questions "
            "WHERE date = CURRENT_DATE LIMIT 1", fetch="one")

    def get_user_streak(self, user_id):
        """Kac gundur ust uste oynandigi. Cagiranlar tam sayi bekliyor."""
        value = self._run("SELECT streak FROM user_trivia_streak WHERE user_id = %s",
                          (user_id,), fetch="value")
        return int(value or 0)

    def check_user_played_trivia_today(self, user_id):
        return bool(self._run(
            "SELECT 1 FROM user_trivia_history "
            "WHERE user_id = %s AND played_date = CURRENT_DATE",
            (user_id,), fetch="value"))

    def mark_user_trivia_played(self, user_id):
        """
        Gunu isaretler ve seriyi gunceller. Eskiden seri hicbir yerde
        artmiyordu: yalnizca gecmise satir ekleniyordu, bu yuzden
        "Current streak" hep 0 goruluyordu.
        """
        played = self._run(
            "INSERT INTO user_trivia_history (user_id, played_date) "
            "VALUES (%s, CURRENT_DATE) ON CONFLICT (user_id, played_date) DO NOTHING",
            (user_id,))
        if played is None:
            return False
        self._run(
            "INSERT INTO user_trivia_streak (user_id, streak, last_played) "
            "VALUES (%s, 1, CURRENT_DATE) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "streak = CASE "
            "  WHEN user_trivia_streak.last_played = CURRENT_DATE THEN user_trivia_streak.streak "
            "  WHEN user_trivia_streak.last_played = CURRENT_DATE - 1 THEN user_trivia_streak.streak + 1 "
            "  ELSE 1 END, "
            "last_played = CURRENT_DATE",
            (user_id,))
        return True

    # ==================== KAYITLI MOCK DRAFTLAR ====================

    def ensure_draft_table(self):
        return bool(self._run(
            """CREATE TABLE IF NOT EXISTS mock_drafts (
                   id SERIAL PRIMARY KEY,
                   user_id INTEGER NOT NULL,
                   name TEXT NOT NULL,
                   state JSONB NOT NULL,
                   grade TEXT,
                   complete BOOLEAN DEFAULT FALSE,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )"""))

    def saved_draft_count(self, user_id):
        return int(self._run("SELECT COUNT(*) FROM mock_drafts WHERE user_id = %s",
                             (user_id,), fetch="value") or 0)

    def save_mock_draft(self, user_id, name, state_blob, grade=None, draft_id=None):
        self.ensure_draft_table()
        if draft_id:
            return bool(self._run(
                "UPDATE mock_drafts SET name = %s, state = %s, grade = %s, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s",
                (name, json.dumps(state_blob), grade, draft_id, user_id)))
        return self._run(
            "INSERT INTO mock_drafts (user_id, name, state, grade) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, name, json.dumps(state_blob), grade), fetch="value")

    def list_mock_drafts(self, user_id, limit=25):
        return self._run(
            "SELECT id, name, grade, complete, created_at, updated_at "
            "FROM mock_drafts WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
            (user_id, limit), fetch="all") or []

    def load_mock_draft(self, user_id, draft_id):
        return self._run("SELECT * FROM mock_drafts WHERE id = %s AND user_id = %s",
                         (draft_id, user_id), fetch="one")

    def delete_mock_draft(self, user_id, draft_id):
        affected = self._run("DELETE FROM mock_drafts WHERE id = %s AND user_id = %s",
                             (draft_id, user_id), fetch="rowcount")
        return bool(affected)


db = Database()
