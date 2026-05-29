#!/usr/bin/env python3
# migrate_to_per_user_db.py
"""
Script migration: tách dữ liệu từ finance.db chung thành per-user DBs.

Chạy một lần khi nâng cấp lên hệ thống per-user:
    python migrate_to_per_user_db.py

Kết quả:
  - data/shared/auth.db          — chứa bảng users (đăng nhập)
  - data/users/{username}/finance.db — dữ liệu riêng của từng user
  - data/finance.db.bak           — backup DB cũ

Nếu DB cũ không có cột owner_username:
  - Toàn bộ dữ liệu được gán cho user 'admin' (user đầu tiên)
"""

import sqlite3
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OLD_DB   = BASE_DIR / "data" / "finance.db"
SHARED   = BASE_DIR / "data" / "shared"
USERS    = BASE_DIR / "data" / "users"


def migrate():
    if not OLD_DB.exists():
        print(f"[Migration] Không tìm thấy DB cũ: {OLD_DB}")
        print("[Migration] Không cần migration — app sẽ tự tạo DB per-user khi đăng nhập.")
        return

    print(f"[Migration] Tìm thấy DB cũ: {OLD_DB}")
    print("[Migration] Bắt đầu migration...")

    # ── 1. Backup DB cũ ──────────────────────────────────────────────────────
    backup = OLD_DB.with_suffix(".db.bak")
    shutil.copy2(OLD_DB, backup)
    print(f"[Migration] Backup: {backup}")

    old_conn = sqlite3.connect(str(OLD_DB))
    old_conn.row_factory = sqlite3.Row

    # ── 2. Lấy danh sách users từ DB cũ (nếu có bảng users) ─────────────────
    users = []
    try:
        rows = old_conn.execute(
            "SELECT username, password_hash, salt, full_name, role, is_active, last_login, created_at FROM users"
        ).fetchall()
        users = [dict(r) for r in rows]
        print(f"[Migration] Tìm thấy {len(users)} user(s): {[u['username'] for u in users]}")
    except sqlite3.OperationalError:
        print("[Migration] Không có bảng users trong DB cũ — tạo user admin mặc định")
        import secrets, hashlib
        salt = secrets.token_hex(16)
        pw_hash = hashlib.sha256((salt + "admin123").encode()).hexdigest()
        users = [{
            "username":      "admin",
            "password_hash": pw_hash,
            "salt":          salt,
            "full_name":     "Quản trị viên",
            "role":          "admin",
            "is_active":     1,
            "last_login":    None,
            "created_at":    None,
        }]

    # ── 3. Tạo auth.db ────────────────────────────────────────────────────────
    SHARED.mkdir(parents=True, exist_ok=True)
    auth_db = SHARED / "auth.db"
    auth_conn = sqlite3.connect(str(auth_db))
    auth_conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            salt          TEXT    NOT NULL,
            full_name     TEXT    DEFAULT '',
            role          TEXT    DEFAULT 'user',
            is_active     INTEGER DEFAULT 1,
            last_login    TEXT,
            created_at    TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
    for u in users:
        auth_conn.execute("""
            INSERT OR REPLACE INTO users
                (username, password_hash, salt, full_name, role, is_active, last_login, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (u["username"], u["password_hash"], u["salt"],
              u.get("full_name", ""), u.get("role", "user"),
              u.get("is_active", 1), u.get("last_login"), u.get("created_at")))
    auth_conn.commit()
    auth_conn.close()
    print(f"[Migration] Tạo auth.db: {auth_db}")

    # ── 4. Kiểm tra có cột owner_username không ───────────────────────────────
    try:
        cols = [r[1] for r in old_conn.execute("PRAGMA table_info(transactions)").fetchall()]
        has_owner = "owner_username" in cols
    except Exception:
        has_owner = False

    # ── 5. Tạo per-user DB cho từng user ─────────────────────────────────────
    for user in users:
        username = user["username"]
        user_dir = USERS / username
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "backups").mkdir(exist_ok=True)
        (user_dir / "exports").mkdir(exist_ok=True)
        (user_dir / "ai").mkdir(exist_ok=True)

        user_db = user_dir / "finance.db"
        _init_user_db(user_db)

        user_conn = sqlite3.connect(str(user_db))
        user_conn.row_factory = sqlite3.Row

        # Copy categories (dùng chung, mỗi user có bản riêng)
        try:
            cats = old_conn.execute("SELECT * FROM categories").fetchall()
            user_conn.execute("DELETE FROM categories")
            for cat in cats:
                cat = dict(cat)
                user_conn.execute("""
                    INSERT OR REPLACE INTO categories (id, name, type, color, icon, parent_id)
                    VALUES (:id, :name, :type, :color, :icon, :parent_id)
                """, cat)
        except Exception as e:
            print(f"  [!] Categories: {e}")

        # Copy accounts
        try:
            accs = old_conn.execute("SELECT * FROM accounts").fetchall()
            user_conn.execute("DELETE FROM accounts")
            for acc in accs:
                acc = dict(acc)
                user_conn.execute("""
                    INSERT OR REPLACE INTO accounts (id, name, type, balance, currency, created_at)
                    VALUES (:id, :name, :type, :balance, :currency, :created_at)
                """, acc)
        except Exception as e:
            print(f"  [!] Accounts: {e}")

        # Copy transactions — lọc theo owner_username nếu có
        try:
            if has_owner:
                txs = old_conn.execute(
                    "SELECT * FROM transactions WHERE owner_username=? OR owner_username IS NULL",
                    (username,)
                ).fetchall()
                # Gán toàn bộ NULL cho user đầu tiên (admin)
                if not txs and username == users[0]["username"]:
                    txs = old_conn.execute(
                        "SELECT * FROM transactions WHERE owner_username IS NULL"
                    ).fetchall()
            else:
                # Không có cột owner → gán tất cả cho user đầu tiên
                if username == users[0]["username"]:
                    txs = old_conn.execute("SELECT * FROM transactions").fetchall()
                else:
                    txs = []

            for tx in txs:
                tx = dict(tx)
                tx.pop("owner_username", None)
                user_conn.execute("""
                    INSERT OR REPLACE INTO transactions
                        (id, account_id, category_id, amount, type, description,
                         date, note, is_anomaly, is_anomaly_feedback, created_at)
                    VALUES (:id, :account_id, :category_id, :amount, :type, :description,
                            :date, :note, :is_anomaly, :is_anomaly_feedback, :created_at)
                """, {k: tx.get(k) for k in [
                    "id", "account_id", "category_id", "amount", "type", "description",
                    "date", "note", "is_anomaly", "is_anomaly_feedback", "created_at"
                ]})
        except Exception as e:
            print(f"  [!] Transactions: {e}")
            import traceback; traceback.print_exc()

        # Copy budgets
        try:
            budgets = old_conn.execute("SELECT * FROM budgets").fetchall()
            for b in budgets:
                b = dict(b)
                user_conn.execute("""
                    INSERT OR IGNORE INTO budgets
                        (id, category_id, limit_amount, spent_amount, month, alert_threshold)
                    VALUES (:id, :category_id, :limit_amount, :spent_amount, :month, :alert_threshold)
                """, b)
        except Exception as e:
            print(f"  [!] Budgets: {e}")

        # Copy ai_predictions
        try:
            preds = old_conn.execute("SELECT * FROM ai_predictions").fetchall()
            for p in preds:
                p = dict(p)
                user_conn.execute("""
                    INSERT OR IGNORE INTO ai_predictions
                        (id, category_id, predicted_amount, month, confidence, created_at)
                    VALUES (:id, :category_id, :predicted_amount, :month, :confidence, :created_at)
                """, p)
        except Exception as e:
            print(f"  [!] AI Predictions: {e}")

        user_conn.commit()
        user_conn.close()

        # Copy classifier model nếu có
        old_ai_dir = BASE_DIR / "data"
        for fname in ["classifier_model.pkl", "fine_tuned_model"]:
            src = old_ai_dir / fname
            dst = user_dir / "ai" / fname
            if src.exists() and not dst.exists():
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        tx_count = len([t for t in (txs if 'txs' in dir() else [])])
        print(f"[Migration] User '{username}': {tx_count} giao dịch → {user_db}")

    old_conn.close()
    print("\n[Migration] Hoàn tất!")
    print(f"  Auth DB:   {auth_db}")
    print(f"  Users dir: {USERS}")
    print(f"  Backup:    {backup}")
    print("\nBước tiếp theo:")
    print("  1. Chạy app bình thường — đăng nhập bằng tài khoản cũ")
    print("  2. Kiểm tra dữ liệu")
    print(f"  3. Xóa backup khi đã chắc chắn: {backup}")


def _init_user_db(db_path: Path):
    """Tạo schema đầy đủ cho user DB."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            type      TEXT NOT NULL,
            color     TEXT DEFAULT '#378ADD',
            icon      TEXT DEFAULT 'circle',
            parent_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            type       TEXT NOT NULL DEFAULT 'cash',
            balance    REAL NOT NULL DEFAULT 0,
            currency   TEXT NOT NULL DEFAULT 'VND',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id           INTEGER NOT NULL,
            category_id          INTEGER,
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
            category_id     INTEGER,
            limit_amount    REAL NOT NULL,
            spent_amount    REAL DEFAULT 0,
            month           TEXT NOT NULL,
            alert_threshold REAL DEFAULT 0.8
        );
        CREATE TABLE IF NOT EXISTS ai_predictions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id      INTEGER,
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
        CREATE TABLE IF NOT EXISTS savings_goals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            target_amount  REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            target_date    TEXT,
            color          TEXT DEFAULT '#1D9E75'
        );
        CREATE INDEX IF NOT EXISTS idx_tx_date     ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category_id);
        CREATE INDEX IF NOT EXISTS idx_tx_type     ON transactions(type);
        CREATE INDEX IF NOT EXISTS idx_budget_month ON budgets(month);
        CREATE INDEX IF NOT EXISTS idx_pred_month   ON ai_predictions(month);
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    migrate()
