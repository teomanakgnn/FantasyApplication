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

import threading
import time

import bcrypt
import psycopg2
from psycopg2 import errors as pg_errors
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

import config

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
_PRIVATE_USER_FIELDS = {"password_hash", "reset_token", "reset_token_expires",
                        "reset_token_hash"}


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
        self._pool = None
        self._pool_lock = threading.Lock()
        self._schema_ready = False
        self._win_tables_ready = False
        self._unavailable_reason = None
        self._last_failure = 0.0

    # ==================== BAGLANTI ====================

    def _credentials(self):
        """Sirlari okur. Tanimli degilse None doner (ekrana hata basmaz)."""
        host = config.get("DB_HOST")
        if not host:
            self._unavailable_reason = "missing_secrets"
            print("DB connection skipped: DB_HOST is not set")
            return None
        return {
            "host": host,
            "dbname": config.get("DB_NAME"),
            "user": config.get("DB_USER"),
            "password": config.get("DB_PASSWORD"),
            "port": int(config.get("DB_PORT", 5432) or 5432),
        }

    def _ensure_pool(self):
        """
        Baglanti havuzu. Web sunucusu istekleri paralel isliyor; tek bir
        paylasilan baglanti istekleri birbirinin transaction'ina
        karistirirdi. Havuz her istege kendi baglantisini verir.
        """
        if self._pool is not None:
            return self._pool
        # Veritabani ulasilamazken her istekte 10 saniyelik baglanti
        # denemesi yapmayalim: basarisiz denemeden sonra 30 saniye bekle.
        if time.time() - self._last_failure < 30:
            return None
        with self._pool_lock:
            if self._pool is not None:
                return self._pool
            creds = self._credentials()
            if not creds:
                return None
            try:
                self._pool = ThreadedConnectionPool(
                    1, 10, sslmode="require", connect_timeout=10,
                    keepalives=1, keepalives_idle=30, keepalives_interval=10,
                    keepalives_count=3, **creds)
            except Exception as exc:
                self._unavailable_reason = str(exc)
                self._last_failure = time.time()
                print(f"DB connection failed: {exc.__class__.__name__}: {exc}")
                return None
        self._ensure_schema()
        return self._pool

    def get_connection(self):
        """Geriye donuk uyumluluk: havuz kurulabiliyor mu."""
        return self._ensure_pool()

    @property
    def available(self):
        """Veritabani kullanilabilir mi? Ekrana hata basmadan kontrol eder."""
        return self._ensure_pool() is not None

    @property
    def unavailable_reason(self):
        return self._unavailable_reason

    def _run(self, sql, params=None, fetch=None, _retry=True):
        """
        Tek sorgu calistirir.

        fetch: None (sadece calistir), "one", "all", "value",
        "rowcount" (etkilenen satir sayisi -- sahiplik kontrollu
        silme/guncellemelerde "hicbir sey eslesmedi"yi ayirt etmek icin).
        Baglanti kopmussa bir kez yeni baglantiyla tekrar dener; Neon
        bosta kalan baglantilari kapattigi icin bu sart.
        """
        pool = self._ensure_pool()
        if pool is None:
            return None
        try:
            conn = pool.getconn()
        except Exception as exc:
            self._unavailable_reason = str(exc)
            return None
        broken = False
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
            # Baglanti dusmus: havuzdan at, bir kez yenisiyle dene
            broken = True
            if _retry:
                pool.putconn(conn, close=True)
                conn = None
                return self._run(sql, params, fetch, _retry=False)
            return None
        except pg_errors.UniqueViolation:
            conn.rollback()
            raise
        except Exception as exc:
            print(f"DB error: {exc.__class__.__name__}: {exc}")
            try:
                conn.rollback()
            except Exception:
                broken = True
            return None
        finally:
            if conn is not None:
                try:
                    pool.putconn(conn, close=broken or conn.closed)
                except Exception:
                    pass

    def close(self):
        if self._pool is not None:
            self._pool.closeall()
        self._pool = None

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
            # Sifre sifirlama: yalnizca anahtarin ozeti ve son gecerlilik saklanir.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_hash TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP",
            # Tercih yazimi ON CONFLICT (user_id) kullaniyor; bu kural olmadan
            # her kayit hata veriyordu ve spoiler ayari hic saklanamiyordu.
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_preferences_user ON user_preferences (user_id)",
            # Giris denemesi hiz siniri
            """CREATE TABLE IF NOT EXISTS login_attempts (
                   id SERIAL PRIMARY KEY,
                   username TEXT NOT NULL,
                   ip_address TEXT,
                   success BOOLEAN NOT NULL DEFAULT FALSE,
                   attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
               )""",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts (username, attempted_at)",
            # Trivia gecmisi ve serisi. Bu iki tablo hic olusturulmamisti;
            # yazma sessizce basarisiz oluyor, seri hep 0 kaliyordu.
            """CREATE TABLE IF NOT EXISTS user_trivia_history (
                   user_id INTEGER NOT NULL,
                   played_date DATE NOT NULL,
                   correct BOOLEAN,
                   PRIMARY KEY (user_id, played_date)
               )""",
            """CREATE TABLE IF NOT EXISTS user_trivia_streak (
                   user_id INTEGER PRIMARY KEY,
                   streak INTEGER NOT NULL DEFAULT 0,
                   last_played DATE
               )""",
            "ALTER TABLE user_trivia_streak ADD COLUMN IF NOT EXISTS last_played DATE",
            # Suren mock draftlar: sunucu yeniden baslayinca (her yayinda)
            # kullanicinin yarim draft'i kaybolmasin diye her hamlede yaziliyor.
            """CREATE TABLE IF NOT EXISTS live_drafts (
                   id TEXT PRIMARY KEY,
                   owner TEXT NOT NULL,
                   state JSONB NOT NULL,
                   saved_id INTEGER,
                   updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
               )""",
            "CREATE INDEX IF NOT EXISTS idx_live_drafts_updated ON live_drafts (updated_at)",
            # Gunluk gizemli oyuncu: gunun cevabi ilk istekte secilip yaziliyor;
            # kadro gun icinde degisse de herkes ayni oyuncuyu tahmin eder.
            """CREATE TABLE IF NOT EXISTS daily_player (
                   game_date DATE PRIMARY KEY,
                   player_id TEXT NOT NULL,
                   data JSONB NOT NULL
               )""",
            # Kayit kaynagi (utm/ref) ve Pro kodlari
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS signup_source TEXT",
            """CREATE TABLE IF NOT EXISTS promo_codes (
                   code TEXT PRIMARY KEY,
                   pro_days INTEGER NOT NULL DEFAULT 30,
                   max_uses INTEGER NOT NULL DEFAULT 100,
                   uses INTEGER NOT NULL DEFAULT 0,
                   note TEXT,
                   created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
               )""",
            """CREATE TABLE IF NOT EXISTS promo_redemptions (
                   code TEXT NOT NULL,
                   user_id INTEGER NOT NULL,
                   redeemed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   PRIMARY KEY (code, user_id)
               )""",
            # Kayitli mock draftlar (eskiden ilk kayitta tembel olusturuluyordu)
            """CREATE TABLE IF NOT EXISTS mock_drafts (
                   id SERIAL PRIMARY KEY,
                   user_id INTEGER NOT NULL,
                   name TEXT NOT NULL,
                   state JSONB NOT NULL,
                   grade TEXT,
                   complete BOOLEAN DEFAULT FALSE,
                   format TEXT,
                   team_count INTEGER,
                   rounds INTEGER,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )""",
        ]
        pool = self._pool
        if pool is None:
            return
        conn = pool.getconn()
        try:
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
        finally:
            pool.putconn(conn)
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
        pool = self._ensure_pool()
        if pool is None:
            return False, "Service is temporarily unavailable. Try again shortly."
        try:
            conn = pool.getconn()
        except Exception:
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
        finally:
            pool.putconn(conn)

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

    # ==================== SIFRE SIFIRLAMA ====================

    RESET_MINUTES = 60

    def create_password_reset(self, email):
        """
        E-postaya ait hesap varsa tek kullanimlik sifirlama anahtari uretir.

        Returns:
            (kullanici, ham anahtar) ya da (None, None). Anahtarin yalnizca
            ozeti saklanir; veritabanini goren biri linki uretemez.
        """
        email = (email or "").strip().lower()
        if not EMAIL_RE.match(email):
            return None, None
        row = self._run("SELECT * FROM users WHERE LOWER(email) = %s", (email,), fetch="one")
        if not row:
            return None, None
        raw = secrets.token_urlsafe(32)
        self._run("UPDATE users SET reset_token_hash = %s, reset_token_expires = "
                  "CURRENT_TIMESTAMP + %s * INTERVAL '1 minute' WHERE id = %s",
                  (_hash_token(raw), self.RESET_MINUTES, row["id"]))
        return _public_user(row), raw

    def reset_token_valid(self, raw):
        if not raw:
            return False
        return bool(self._run(
            "SELECT 1 FROM users WHERE reset_token_hash = %s AND reset_token_expires > CURRENT_TIMESTAMP",
            (_hash_token(raw),), fetch="value"))

    def reset_password(self, raw, new_password):
        if len(new_password or "") < MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        row = self._run(
            "SELECT id FROM users WHERE reset_token_hash = %s AND reset_token_expires > CURRENT_TIMESTAMP",
            (_hash_token(raw or ""),), fetch="one")
        if not row:
            return False, "This reset link has expired or was already used. Ask for a new one."
        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        done = self._run("UPDATE users SET password_hash = %s, reset_token_hash = NULL, "
                         "reset_token_expires = NULL WHERE id = %s", (new_hash, row["id"]))
        if not done:
            return False, "Could not update the password. Try again."
        # Eski oturumlar duser: sifreyi baskasi biliyorsa artik giremez.
        self._run("DELETE FROM sessions WHERE user_id = %s", (row["id"],))
        return True, "Password updated. Sign in with your new password."

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
                      "mock_drafts", "user_trivia_history", "user_trivia_streak",
                      "season_win_picks", "promo_redemptions"):
            if self._run("SELECT to_regclass(%s)", ("public." + table,), fetch="value"):
                self._run("DELETE FROM %s WHERE user_id = %%s" % table, (user_id,))
        # Suren mock draftlar kullanici kimligine degil sahip anahtarina bagli
        self._run("DELETE FROM live_drafts WHERE owner = %s", (f"u{user_id}",))
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
        """
        Bugunun sorusu.

        Once bugune yazilmis soru aranir. Yoksa (yeni soru girilmediyse)
        butun sorular arasindan gunun sirasina gore biri secilir: herkes
        ayni gun ayni soruyu gorur ve sorular hic tukenmez.
        """
        columns = ("id, question, option_a, option_b, option_c, option_d, "
                   "correct_option, explanation")
        today = self._run(f"SELECT {columns} FROM trivia_questions "
                          "WHERE game_date = CURRENT_DATE LIMIT 1", fetch="one")
        if today:
            return today
        return self._run(
            f"SELECT {columns} FROM trivia_questions ORDER BY id "
            "OFFSET (CURRENT_DATE - DATE '2026-01-01') % "
            "GREATEST((SELECT COUNT(*) FROM trivia_questions), 1) LIMIT 1",
            fetch="one")

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

    def mark_user_trivia_played(self, user_id, correct=True):
        """
        Gunu isaretler ve seriyi gunceller.

        Dogru cevap seriyi bir artirir (dun de oynandiysa), yanlis cevap
        sifirlar. Eski surum ekranda "seriniz sifirlandi" yazip seriyi
        yine de artiriyordu.
        """
        played = self._run(
            "INSERT INTO user_trivia_history (user_id, played_date, correct) "
            "VALUES (%s, CURRENT_DATE, %s) ON CONFLICT (user_id, played_date) DO NOTHING",
            (user_id, bool(correct)), fetch="rowcount")
        if not played:
            return False
        if correct:
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
        else:
            self._run(
                "INSERT INTO user_trivia_streak (user_id, streak, last_played) "
                "VALUES (%s, 0, CURRENT_DATE) "
                "ON CONFLICT (user_id) DO UPDATE SET streak = 0, last_played = CURRENT_DATE",
                (user_id,))
        return True

    # ==================== GUNLUK GIZEMLI OYUNCU ====================

    def get_daily_player(self, day):
        row = self._run("SELECT player_id, data FROM daily_player WHERE game_date = %s",
                        (day,), fetch="one")
        return row

    def set_daily_player(self, day, player_id, data):
        """Ilk yazan kazanir; ayni gun icin ikinci secim yok sayilir."""
        self._run("INSERT INTO daily_player (game_date, player_id, data) VALUES (%s, %s, %s) "
                  "ON CONFLICT (game_date) DO NOTHING",
                  (day, str(player_id), json.dumps(data)))
        return self.get_daily_player(day)

    def recent_daily_player_ids(self, day, days=120):
        rows = self._run("SELECT player_id FROM daily_player "
                         "WHERE game_date < %s AND game_date >= %s - %s::int",
                         (day, day, days), fetch="all")
        return {r["player_id"] for r in rows or []}

    # ==================== KAYNAK / PRO KODLARI ====================

    def set_signup_source(self, user_id, source):
        return bool(self._run("UPDATE users SET signup_source = %s "
                              "WHERE id = %s AND signup_source IS NULL",
                              ((source or "")[:120], user_id)))

    def signup_sources(self, days=30):
        """Son N gunde kaynak basina kayit sayisi (yonetici paneli)."""
        return self._run(
            "SELECT COALESCE(NULLIF(signup_source, ''), 'direct') AS source, COUNT(*) AS n "
            "FROM users WHERE created_at >= NOW() - %s * INTERVAL '1 day' "
            "GROUP BY 1 ORDER BY n DESC", (days,), fetch="all") or []

    def signup_totals(self):
        return self._run(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') AS day, "
            "COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 day') AS week "
            "FROM users", fetch="one") or {}

    def create_promo_code(self, code, pro_days, max_uses, note=""):
        try:
            return bool(self._run(
                "INSERT INTO promo_codes (code, pro_days, max_uses, note) VALUES (%s, %s, %s, %s)",
                (code.upper(), int(pro_days), int(max_uses), note[:200])))
        except pg_errors.UniqueViolation:
            return False

    def list_promo_codes(self):
        return self._run("SELECT code, pro_days, max_uses, uses, note, created_at "
                         "FROM promo_codes ORDER BY created_at DESC LIMIT 50", fetch="all") or []

    def redeem_promo_code(self, user_id, code):
        """
        Kodu kullanir ve Pro'yu acar. (ok, mesaj) doner.
        Kullanim sayaci tek bir kosullu UPDATE ile artiyor: ayni anda iki
        kisi son hakki kullanmaya calissa da sinir asilmiyor.
        """
        code = (code or "").strip().upper()
        if not code:
            return False, "Enter a code."
        row = self._run("SELECT pro_days FROM promo_codes WHERE code = %s", (code,), fetch="one")
        if not row:
            return False, "That code does not exist."
        try:
            added = self._run("INSERT INTO promo_redemptions (code, user_id) VALUES (%s, %s)",
                              (code, user_id))
        except pg_errors.UniqueViolation:
            return False, "You have already used this code."
        if not added:
            return False, "Could not use the code right now. Try again."
        taken = self._run("UPDATE promo_codes SET uses = uses + 1 "
                          "WHERE code = %s AND uses < max_uses", (code,), fetch="rowcount")
        if not taken:
            self._run("DELETE FROM promo_redemptions WHERE code = %s AND user_id = %s",
                      (code, user_id))
            return False, "This code has been used up."
        days = int(row["pro_days"])
        # Zaten Pro olana sure eklenir, kisaltilmaz
        plan, expires = self.get_plan(user_id)
        if plan == PLAN_PRO and expires is None:
            return True, "You already have Pro with no end date."
        start = expires if (plan == PLAN_PRO and expires and expires > datetime.now()) else datetime.now()
        self._run("UPDATE users SET plan = %s, plan_expires_at = %s WHERE id = %s",
                  (PLAN_PRO, start + timedelta(days=days), user_id))
        return True, f"Pro unlocked for {days} days."

    # ==================== KAYITLI MOCK DRAFTLAR ====================

    def ensure_draft_table(self):
        """Tablo sema adiminda olusuyor; eski surumlerden kalan tabloya eksik sutunlari ekler."""
        for sql in ("ALTER TABLE mock_drafts ADD COLUMN IF NOT EXISTS format TEXT",
                    "ALTER TABLE mock_drafts ADD COLUMN IF NOT EXISTS team_count INTEGER",
                    "ALTER TABLE mock_drafts ADD COLUMN IF NOT EXISTS rounds INTEGER"):
            self._run(sql)
        return True

    def saved_draft_count(self, user_id):
        return int(self._run("SELECT COUNT(*) FROM mock_drafts WHERE user_id = %s",
                             (user_id,), fetch="value") or 0)

    def save_mock_draft(self, user_id, name, state_blob, grade=None, draft_id=None):
        """
        Draftin kaydi. Liste ekraninin gosterdigi ozet alanlar (format,
        takim sayisi, tur, bitti mi) ayri sutunlarda tutuluyor; eskiden
        yalnizca JSON'a yaziliyordu ve liste ekrani bu alanlari
        bulamayip cokuyordu.
        """
        meta = (state_blob.get("format"), state_blob.get("team_count"),
                state_blob.get("rounds"), bool(state_blob.get("complete")))
        if draft_id:
            updated = self._run(
                "UPDATE mock_drafts SET name = %s, state = %s, grade = %s, format = %s, "
                "team_count = %s, rounds = %s, complete = %s, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s",
                (name, json.dumps(state_blob), grade, *meta, draft_id, user_id),
                fetch="rowcount")
            return draft_id if updated else None
        return self._run(
            "INSERT INTO mock_drafts (user_id, name, state, grade, format, team_count, "
            "rounds, complete) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, name, json.dumps(state_blob), grade, *meta), fetch="value")

    def list_mock_drafts(self, user_id, limit=25):
        return self._run(
            "SELECT id, name, grade, complete, format, team_count, rounds, "
            "created_at, updated_at "
            "FROM mock_drafts WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
            (user_id, limit), fetch="all") or []

    # ==================== SUREN MOCK DRAFTLAR ====================

    def save_live_draft(self, draft_id, owner, state_blob, saved_id=None):
        return bool(self._run(
            "INSERT INTO live_drafts (id, owner, state, saved_id, updated_at) "
            "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, "
            "saved_id = EXCLUDED.saved_id, updated_at = CURRENT_TIMESTAMP",
            (draft_id, owner, json.dumps(state_blob), saved_id)))

    def load_live_draft(self, draft_id, owner):
        row = self._run("SELECT state, saved_id FROM live_drafts WHERE id = %s AND owner = %s",
                        (draft_id, owner), fetch="one")
        if not row:
            return None
        state = row["state"]
        if isinstance(state, str):
            state = json.loads(state)
        return state, row.get("saved_id")

    def purge_live_drafts(self, days=3):
        return self._run("DELETE FROM live_drafts WHERE updated_at < CURRENT_TIMESTAMP - %s * INTERVAL '1 day'",
                         (days,), fetch="rowcount")

    def load_mock_draft(self, user_id, draft_id):
        return self._run("SELECT * FROM mock_drafts WHERE id = %s AND user_id = %s",
                         (draft_id, user_id), fetch="one")

    def delete_mock_draft(self, user_id, draft_id):
        affected = self._run("DELETE FROM mock_drafts WHERE id = %s AND user_id = %s",
                             (draft_id, user_id), fetch="rowcount")
        return bool(affected)


    # ==================== ALT/UST TAHMINI ====================

    def ensure_win_pick_tables(self):
        """
        Iki tablo: dondurulmus baremler ve kullanici tahminleri.

        Baremler ayri bir tabloda tutuluyor cunku yarismanin adil olmasi
        icin cizginin donmasi sart: model her gun yeniden hesaplansa,
        erken tahmin eden ile gec tahmin eden farkli bareme oynamis olur.
        Bir sezon icin bir kez yazilir, sonra hep oradan okunur.

        Surec basina bir kez calisir. Her cagrida calistirmak dort DDL
        gidis-donusu demekti ve altindaki asil sorguyu golgede birakiyordu:
        olculdu, basit bir SELECT 1.5 saniye suruyordu, bunun ~1.4'u bu
        kontroldu.
        """
        if self._win_tables_ready:
            return True

        lines = self._run(
            """CREATE TABLE IF NOT EXISTS season_win_lines (
                   season INTEGER NOT NULL,
                   team TEXT NOT NULL,
                   team_name TEXT NOT NULL,
                   line NUMERIC(4,1) NOT NULL,
                   projected NUMERIC(4,1),
                   frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   PRIMARY KEY (season, team)
               )""")
        # Konferans ve gecen sezon rekoru sonradan eklendi. Bunlar cizgiyi
        # degistirmeyen gosterim alanlari ama burada durmalari sart: yoksa
        # sayfa her acilista sadece bu iki alan icin butun draft tablosunu
        # (16MB) yeniden cekmek zorunda kaliyor.
        self._run("ALTER TABLE season_win_lines ADD COLUMN IF NOT EXISTS conf TEXT")
        self._run("ALTER TABLE season_win_lines "
                  "ADD COLUMN IF NOT EXISTS last_wins NUMERIC(4,1)")
        # Vegas oranlari (ust / alt). Model cizgisinden Vegas'a gecildiginde
        # eklendi; model satirlarinda bos.
        self._run("ALTER TABLE season_win_lines ADD COLUMN IF NOT EXISTS over_odds INTEGER")
        self._run("ALTER TABLE season_win_lines ADD COLUMN IF NOT EXISTS under_odds INTEGER")
        self._win_tables_ready = bool(lines)
        picks = self._run(
            """CREATE TABLE IF NOT EXISTS season_win_picks (
                   user_id INTEGER NOT NULL,
                   season INTEGER NOT NULL,
                   team TEXT NOT NULL,
                   pick TEXT NOT NULL CHECK (pick IN ('over', 'under')),
                   line NUMERIC(4,1) NOT NULL,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   PRIMARY KEY (user_id, season, team)
               )""")
        return bool(lines and picks)

    def win_lines_frozen(self, season):
        """Bu sezonun baremleri daha once dondurulmus mu?"""
        self.ensure_win_pick_tables()
        return int(self._run("SELECT COUNT(*) FROM season_win_lines WHERE season = %s",
                             (season,), fetch="value") or 0) > 0

    def freeze_win_lines(self, season, rows):
        """
        Baremleri bir kez yazar. Zaten varsa hicbir seye dokunmaz.

        rows: [{team, team_name, line, projected}, ...]
        """
        self.ensure_win_pick_tables()
        if self.win_lines_frozen(season):
            return False
        for row in rows:
            self._run(
                "INSERT INTO season_win_lines "
                "(season, team, team_name, line, projected, conf, last_wins, "
                " over_odds, under_odds) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (season, team) DO NOTHING",
                (season, row["team"], row["team_name"], row["line"],
                 row.get("projected"), row.get("conf"), row.get("last_wins"),
                 row.get("over_odds"), row.get("under_odds")))
        return True

    def replace_win_lines(self, season, lines):
        """
        Dondurulmus cizgileri yenileriyle degistirir (model -> Vegas).

        lines: {team: (line, over_odds, under_odds)}

        Mevcut tahminler korunabildigi kadar korunur. 45.5 ustu diyen biri
        43.5 ustunu de zaten demis oluyor; o tahmin yeni cizgiye tasinir.
        Yeni cizginin ima etmedigi tahmin (45.5 ustu -> 47.5) silinir:
        kullanici adina bir karar uydurulmuyor, yeniden secmesi gerekiyor.

        Returns:
            Silinen tahmin sayisi, basarisizsa None.
        """
        self.ensure_win_pick_tables()
        cleared = 0
        for team, (line, over_odds, under_odds) in lines.items():
            done = self._run(
                "UPDATE season_win_lines SET line = %s, over_odds = %s, "
                "under_odds = %s, frozen_at = CURRENT_TIMESTAMP "
                "WHERE season = %s AND team = %s",
                (line, over_odds, under_odds, season, team))
            if not done:
                return None
            self._run(
                "UPDATE season_win_picks SET line = %s, updated_at = CURRENT_TIMESTAMP "
                "WHERE season = %s AND team = %s AND line <> %s AND "
                "((pick = 'over' AND line >= %s) OR (pick = 'under' AND line <= %s))",
                (line, season, team, line, line, line))
            cleared += int(self._run(
                "DELETE FROM season_win_picks "
                "WHERE season = %s AND team = %s AND line <> %s",
                (season, team, line), fetch="rowcount") or 0)
        return cleared

    def backfill_win_line_details(self, season, rows):
        """
        Dondurulmus satirlara konferans/gecen sezon bilgisini ekler.

        Cizgiye dokunmaz - yalnizca gosterim alanlarini doldurur, ve bir kez
        doldurulduktan sonra model bir daha hic calistirilmaz.
        """
        self.ensure_win_pick_tables()
        for row in rows:
            self._run(
                "UPDATE season_win_lines SET conf = %s, last_wins = %s "
                "WHERE season = %s AND team = %s AND conf IS NULL",
                (row.get("conf"), row.get("last_wins"), season, row["team"]))
        return True

    def get_win_lines(self, season):
        self.ensure_win_pick_tables()
        return self._run(
            "SELECT team, team_name, line, projected, conf, last_wins, "
            "over_odds, under_odds, frozen_at "
            "FROM season_win_lines WHERE season = %s ORDER BY line DESC",
            (season,), fetch="all") or []

    def save_win_pick(self, user_id, season, team, pick, line):
        """Tahmini yazar veya degistirir (son teslim tarihine kadar)."""
        self.ensure_win_pick_tables()
        return bool(self._run(
            "INSERT INTO season_win_picks (user_id, season, team, pick, line) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, season, team) DO UPDATE SET "
            "pick = EXCLUDED.pick, updated_at = CURRENT_TIMESTAMP",
            (user_id, season, team, pick, line)))

    def clear_win_pick(self, user_id, season, team):
        self.ensure_win_pick_tables()
        return bool(self._run(
            "DELETE FROM season_win_picks WHERE user_id = %s AND season = %s AND team = %s",
            (user_id, season, team), fetch="rowcount"))

    def get_win_picks(self, user_id, season):
        """{team: pick} seklinde kullanicinin tahminleri."""
        self.ensure_win_pick_tables()
        rows = self._run(
            "SELECT team, pick FROM season_win_picks WHERE user_id = %s AND season = %s",
            (user_id, season), fetch="all") or []
        return {row["team"]: row["pick"] for row in rows}

    def win_pick_counts(self, season):
        """Her takimda kac kisi ust, kac kisi alt demis (kalabalik gorunsun)."""
        self.ensure_win_pick_tables()
        rows = self._run(
            "SELECT team, pick, COUNT(*) AS n FROM season_win_picks "
            "WHERE season = %s GROUP BY team, pick", (season,), fetch="all") or []
        out = {}
        for row in rows:
            out.setdefault(row["team"], {"over": 0, "under": 0})[row["pick"]] = int(row["n"])
        return out


db = Database()
