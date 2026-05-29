# models.py  (cập nhật: per-user database)
"""
DatabaseManager dùng DB path động theo user đang đăng nhập.
Mỗi user có file SQLite riêng tại: data/users/{username}/finance.db

Thay đổi so với phiên bản cũ:
  - DB_PATH không còn là hằng số — lấy động từ user_session.session.db_path
  - DatabaseManager không còn là singleton cứng —
    tự reset khi user thay đổi (đăng xuất / đăng nhập lại)
  - init_database() nhận tham số db_path để init đúng DB của user
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional


# ── Lấy DB path động theo user đang đăng nhập ────────────────────────────────

def _get_current_db_path() -> Path:
    """
    Trả về đường dẫn DB của user đang đăng nhập.
    Fallback về config.DB_PATH nếu chưa có user (tương thích ngược).
    """
    try:
        from user_session import session
        if session.is_logged_in:
            return session.db_path
    except ImportError:
        pass
    # Fallback: dùng DB_PATH từ config (tương thích với code cũ)
    try:
        from config import DB_PATH
        return Path(DB_PATH)
    except ImportError:
        return Path("data") / "finance.db"


# ── DatabaseManager — reset khi đổi user ─────────────────────────────────────

class DatabaseManager:
    """
    Singleton connection pool, reset khi user thay đổi.

    Cách hoạt động:
      - Lần đầu gọi get_connection() → mở connection tới DB của user hiện tại
      - Khi user đăng xuất/đổi → gọi DatabaseManager.reset() → đóng connection
      - User mới đăng nhập → get_connection() mở connection tới DB mới
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._conn = None
                cls._instance._current_db_path: Optional[Path] = None
        return cls._instance

    def get_connection(self):
        target_path = _get_current_db_path()

        # Nếu DB path thay đổi (đổi user) → đóng connection cũ
        if self._conn is not None and self._current_db_path != target_path:
            self._close_conn()

        if self._conn is not None:
            return self._conn

        with self._lock:
            if self._conn is None:
                self._current_db_path = target_path
                self._conn = self._open_connection(target_path)

        return self._conn

    def _open_connection(self, db_path: Path) -> sqlite3.Connection:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -8000")
        conn.execute("PRAGMA temp_store = MEMORY")
        return conn

    def _close_conn(self):
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass
        self._conn = None
        self._current_db_path = None

    def _ensure_connection(self):
        """Reconnect only when the connection is truly broken (called sparingly)."""
        try:
            self._conn.execute("SELECT 1")
        except (sqlite3.Error, AttributeError):
            with self._lock:
                self._close_conn()
                target_path = _get_current_db_path()
                self._current_db_path = target_path
                self._conn = self._open_connection(target_path)

    def __getattr__(self, name):
        """Proxy unknown attributes to the underlying sqlite3.Connection object."""
        return getattr(self.get_connection(), name)

    def __enter__(self):
        return self.get_connection()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()

    def execute_write(self, query, params=()):
        """Serialised write — acquires lock, executes, commits."""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor
            except sqlite3.Error as e:
                conn.rollback()
                raise e

    def execute_write_many(self, statements):
        """
        Execute multiple (query, params) pairs in ONE atomic transaction.
        Tránh N commits riêng lẻ → nhanh hơn đáng kể.
        """
        with self._lock:
            conn = self.get_connection()
            try:
                for query, params in statements:
                    conn.execute(query, params)
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise e

    def close(self):
        self._close_conn()

    @classmethod
    def reset(cls):
        """
        Gọi khi user đăng xuất để đóng connection và reset singleton.
        User mới đăng nhập sẽ tự mở connection mới tới DB của họ.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance._close_conn()


def get_connection():
    return DatabaseManager()


# ── Index helper ──────────────────────────────────────────────────────────────

def _create_indexes(cursor):
    """Create performance indexes that dramatically speed up filtered queries."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date)",
        "CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(type)",
        "CREATE INDEX IF NOT EXISTS idx_tx_date_type ON transactions(date, type)",
        "CREATE INDEX IF NOT EXISTS idx_tx_cat_type ON transactions(category_id, type)",
        "CREATE INDEX IF NOT EXISTS idx_budget_month ON budgets(month)",
        "CREATE INDEX IF NOT EXISTS idx_budget_cat_month ON budgets(category_id, month)",
        "CREATE INDEX IF NOT EXISTS idx_pred_month ON ai_predictions(month)",
    ]
    for sql in indexes:
        try:
            cursor.execute(sql)
        except sqlite3.Error:
            pass


# ── init_database — per-user ──────────────────────────────────────────────────

def init_database(db_path: Optional[Path] = None):
    """
    Khởi tạo database cho user hiện tại.
    db_path: override path (dùng khi test). Mặc định dùng path của user đang login.
    """
    if db_path is None:
        db_path = _get_current_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = conn.cursor()

        # Migration: thêm cột nếu chưa có
        for migration in [
            "ALTER TABLE transactions ADD COLUMN owner_username TEXT",
            "ALTER TABLE transactions ADD COLUMN is_anomaly_feedback INTEGER DEFAULT 0",
        ]:
            try:
                cursor.execute(migration)
            except sqlite3.OperationalError:
                pass  # Column already exists

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT UNIQUE NOT NULL,
                full_name       TEXT,
                color           TEXT DEFAULT '#378ADD',
                currency        TEXT DEFAULT 'VND',
                avatar_initials TEXT
            );

            CREATE TABLE IF NOT EXISTS family_groups (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                owner_username TEXT NOT NULL,
                invite_code    TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS group_members (
                group_id    INTEGER REFERENCES family_groups(id),
                username    TEXT NOT NULL,
                role        TEXT DEFAULT 'member',
                joined_at   TEXT DEFAULT (datetime('now','localtime')),
                PRIMARY KEY (group_id, username)
            );

            CREATE TABLE IF NOT EXISTS savings_goals (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                target_amount  REAL NOT NULL,
                current_amount REAL DEFAULT 0,
                target_date    TEXT,
                color          TEXT DEFAULT '#1D9E75'
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                type       TEXT NOT NULL DEFAULT 'cash',
                balance    REAL NOT NULL DEFAULT 0,
                currency   TEXT NOT NULL DEFAULT 'VND',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                type      TEXT NOT NULL,
                color     TEXT DEFAULT '#378ADD',
                icon      TEXT DEFAULT 'circle',
                parent_id INTEGER REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id           INTEGER NOT NULL REFERENCES accounts(id),
                category_id          INTEGER REFERENCES categories(id),
                amount               REAL NOT NULL,
                type                 TEXT NOT NULL,
                description          TEXT,
                date                 TEXT NOT NULL,
                note                 TEXT,
                is_anomaly           INTEGER DEFAULT 0,
                is_anomaly_feedback  INTEGER DEFAULT 0,
                owner_username       TEXT,
                created_at           TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id     INTEGER REFERENCES categories(id),
                limit_amount    REAL NOT NULL,
                spent_amount    REAL DEFAULT 0,
                month           TEXT NOT NULL,
                alert_threshold REAL DEFAULT 0.8
            );

            CREATE TABLE IF NOT EXISTS ai_predictions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id      INTEGER REFERENCES categories(id),
                predicted_amount REAL,
                month            TEXT,
                confidence       REAL,
                created_at       TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)

        _create_indexes(cursor)

        # Tạo danh mục mặc định nếu chưa có
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            default_categories = [
                ("Ăn uống",   "expense", "#E24B4A", "utensils"),
                ("Di chuyển", "expense", "#BA7517", "car"),
                ("Mua sắm",   "expense", "#7F77DD", "bag"),
                ("Giải trí",  "expense", "#D4537E", "music"),
                ("Y tế",      "expense", "#1D9E75", "heart"),
                ("Hóa đơn",   "expense", "#888780", "file"),
                ("Giáo dục",  "expense", "#378ADD", "book"),
                ("Lương",     "income",  "#1D9E75", "wallet"),
                ("Thưởng",    "income",  "#639922", "star"),
                ("Đầu tư",    "income",  "#BA7517", "chart"),
            ]
            cursor.executemany(
                "INSERT INTO categories (name, type, color, icon) VALUES (?,?,?,?)",
                default_categories
            )

        # Tạo tài khoản mặc định nếu chưa có
        cursor.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO accounts (name, type, balance) VALUES ('Tiền mặt','cash',0)"
            )

        conn.commit()
        print(f"[DB] Initialized: {db_path}")

    finally:
        conn.close()


# ── init_auth_database — dùng chung cho tất cả user ──────────────────────────

def init_auth_database():
    """
    Khởi tạo database xác thực (users table) — dùng chung, không per-user.
    Chỉ gọi một lần khi app khởi động.
    """
    try:
        from user_session import session
        auth_db_path = session.auth_db_path
    except ImportError:
        try:
            from config import DATA_DIR
            auth_db_path = Path(DATA_DIR) / "shared" / "auth.db"
        except ImportError:
            auth_db_path = Path("data") / "shared" / "auth.db"

    auth_db_path.parent.mkdir(parents=True, exist_ok=True)

    import secrets, hashlib
    conn = sqlite3.connect(str(auth_db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL,
                full_name     TEXT    DEFAULT '',
                phone         TEXT    DEFAULT '',
                role          TEXT    DEFAULT 'user',
                is_active     INTEGER DEFAULT 1,
                last_login    TEXT,
                created_at    TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        # Migration: thêm cột phone nếu DB cũ chưa có
        try:
            conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone "
                "ON users(phone) WHERE phone != ''"
            )
        except Exception:
            pass
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            salt = secrets.token_hex(16)
            pw_hash = hashlib.sha256((salt + "admin123").encode()).hexdigest()
            conn.execute("""
                INSERT INTO users (username, password_hash, salt, full_name, phone, role)
                VALUES ('admin', ?, ?, 'Quản trị viên', '', 'admin')
            """, (pw_hash, salt))
        conn.commit()
        print(f"[Auth DB] Initialized: {auth_db_path}")
    finally:
        conn.close()

    return auth_db_path