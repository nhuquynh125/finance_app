# app/data/repositories.py  (cập nhật: validate() chặt hơn)
"""
Thay đổi so với phiên bản cũ:
  - TransactionModel.validate(): thêm kiểm tra amount tối đa,
    ngày không được trong tương lai quá 1 năm, ngày không quá cũ,
    description quá dài
  - BudgetModel.validate(): thêm kiểm tra limit_amount tối đa
  - Không thay đổi gì khác — toàn bộ logic DB giữ nguyên
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Generator, Optional

from app.data.models import _get_current_db_path


# ── Connection context manager ────────────────────────────────────────────────

class DBContext:
    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "DBContext":
        self.conn = sqlite3.connect(str(_get_current_db_path()))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is None:
            return False
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
            self.conn = None
        return False

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        assert self.conn is not None, "DBContext not entered"
        return self.conn.execute(sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.execute(sql, params).fetchall()]

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        row = self.execute(sql, params).fetchone()
        return dict(row) if row else None


@contextmanager
def db_session() -> Generator[DBContext, None, None]:
    ctx = DBContext()
    ctx.__enter__()
    try:
        yield ctx
        ctx.conn.commit()
    except Exception:
        ctx.conn.rollback()
        raise
    finally:
        if ctx.conn:
            ctx.conn.close()


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class TransactionModel:
    account_id: int
    amount: float
    type_: str                      # "income" | "expense"
    description: str
    date: str                       # "YYYY-MM-DD"
    category_id: Optional[int] = None
    note: str = ""
    id: Optional[int] = None
    is_anomaly: int = 0
    created_at: Optional[str] = None

    # Giới hạn hợp lý cho ứng dụng quản lý tài chính cá nhân VN
    MAX_AMOUNT      = 10_000_000_000    # 10 tỷ đồng
    MAX_DESC_LENGTH = 200
    MAX_NOTE_LENGTH = 500

    def validate(self) -> list[str]:
        """
        Trả về list lỗi. Rỗng = hợp lệ.
        Kiểm tra đầy đủ: amount, type, date, description, note.
        """
        errors: list[str] = []

        # ── Số tiền ───────────────────────────────────────────────────────────
        if self.amount <= 0:
            errors.append("Số tiền phải lớn hơn 0")
        elif self.amount > self.MAX_AMOUNT:
            errors.append(
                f"Số tiền vượt quá giới hạn cho phép "
                f"({self.MAX_AMOUNT:,.0f}đ)".replace(",", ".")
            )

        # ── Loại giao dịch ────────────────────────────────────────────────────
        if self.type_ not in ("income", "expense"):
            errors.append("Loại phải là 'income' hoặc 'expense'")

        # ── Ngày ──────────────────────────────────────────────────────────────
        try:
            dt = datetime.strptime(self.date, "%Y-%m-%d")
            now = datetime.now()

            # Không cho nhập ngày tương lai quá 1 năm
            if dt > now + timedelta(days=365):
                errors.append("Ngày không được vượt quá 1 năm trong tương lai")

            # Không cho nhập ngày quá xa quá khứ (> 50 năm)
            if dt.year < (now.year - 50):
                errors.append("Ngày quá xa trong quá khứ (trên 50 năm)")

        except ValueError:
            errors.append("Ngày không đúng định dạng YYYY-MM-DD")

        # ── Mô tả ─────────────────────────────────────────────────────────────
        if not self.description.strip():
            errors.append("Mô tả không được để trống")
        elif len(self.description) > self.MAX_DESC_LENGTH:
            errors.append(
                f"Mô tả không được quá {self.MAX_DESC_LENGTH} ký tự "
                f"(hiện tại: {len(self.description)})"
            )

        # ── Ghi chú (tùy chọn nhưng giới hạn độ dài) ─────────────────────────
        if self.note and len(self.note) > self.MAX_NOTE_LENGTH:
            errors.append(f"Ghi chú không được quá {self.MAX_NOTE_LENGTH} ký tự")

        # ── account_id ────────────────────────────────────────────────────────
        if not isinstance(self.account_id, int) or self.account_id <= 0:
            errors.append("Tài khoản không hợp lệ")

        return errors


@dataclass
class BudgetModel:
    category_id: int
    limit_amount: float
    month: str
    spent_amount: float = 0.0
    alert_threshold: float = 0.8
    id: Optional[int] = None

    MAX_BUDGET = 10_000_000_000  # 10 tỷ

    def validate(self) -> list[str]:
        errors: list[str] = []

        if self.limit_amount <= 0:
            errors.append("Ngân sách phải lớn hơn 0")
        elif self.limit_amount > self.MAX_BUDGET:
            errors.append(
                f"Ngân sách vượt quá giới hạn ({self.MAX_BUDGET:,.0f}đ)".replace(",", ".")
            )

        if not (0.1 <= self.alert_threshold <= 1.0):
            errors.append("Ngưỡng cảnh báo phải từ 10% đến 100%")

        # Kiểm tra định dạng tháng
        try:
            datetime.strptime(self.month + "-01", "%Y-%m-%d")
        except ValueError:
            errors.append("Tháng không đúng định dạng YYYY-MM")

        return errors

    @property
    def pct(self) -> int:
        return min(100, int(self.spent_amount / (self.limit_amount or 1) * 100))

    @property
    def status(self) -> str:
        if self.pct >= 100:
            return "over"
        if self.pct >= int(self.alert_threshold * 100):
            return "warning"
        return "ok"


@dataclass
class UserProfileModel:
    username: str
    full_name: str
    color: str = "#378ADD"
    currency: str = "VND"
    id: Optional[int] = None


# ── TransactionRepo ───────────────────────────────────────────────────────────

class TransactionRepo:
    """CRUD + query cho bảng transactions."""

    def get_by_month(self, month: str, account_id: Optional[int] = None,
                     limit: int = 500) -> list[dict]:
        sql = """
            SELECT t.*, c.name as category_name, c.color,
                   a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts   a ON t.account_id  = a.id
            WHERE strftime('%Y-%m', t.date) = ?
        """
        params: list[Any] = [month]
        if account_id:
            sql += " AND t.account_id = ?"
            params.append(account_id)
        sql += " ORDER BY t.date DESC, t.id DESC LIMIT ?"
        params.append(limit)
        with db_session() as db:
            return db.fetchall(sql, tuple(params))

    def get_monthly_summary(self, month: str) -> dict:
        with db_session() as db:
            row = db.fetchone("""
                SELECT
                    COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0) as total_income,
                    COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as total_expense,
                    COUNT(*) as total_count
                FROM transactions
                WHERE strftime('%Y-%m', date) = ?
            """, (month,))
            return row or {"total_income": 0, "total_expense": 0, "total_count": 0}

    def add(self, model: TransactionModel) -> int:
        """Thêm giao dịch, cập nhật số dư tài khoản. Trả về id mới."""
        errors = model.validate()
        if errors:
            raise ValueError("; ".join(errors))
        with db_session() as db:
            cur = db.execute("""
                INSERT INTO transactions
                    (account_id, category_id, amount, type, description, date, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (model.account_id, model.category_id, model.amount,
                  model.type_, model.description, model.date, model.note))
            tx_id = cur.lastrowid
            delta = model.amount if model.type_ == "income" else -model.amount
            db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?",
                       (delta, model.account_id))
            return tx_id

    def update(self, tx_id: int, model: TransactionModel) -> None:
        errors = model.validate()
        if errors:
            raise ValueError("; ".join(errors))
        with db_session() as db:
            old = db.fetchone("SELECT * FROM transactions WHERE id=?", (tx_id,))
            if old:
                revert = -old["amount"] if old["type"] == "income" else old["amount"]
                db.execute("UPDATE accounts SET balance=balance+? WHERE id=?",
                           (revert, old["account_id"]))
            db.execute("""
                UPDATE transactions
                SET account_id=?, category_id=?, amount=?, type=?,
                    description=?, date=?, note=?
                WHERE id=?
            """, (model.account_id, model.category_id, model.amount, model.type_,
                  model.description, model.date, model.note, tx_id))
            delta = model.amount if model.type_ == "income" else -model.amount
            db.execute("UPDATE accounts SET balance=balance+? WHERE id=?",
                       (delta, model.account_id))

    def delete(self, tx_id: int) -> None:
        with db_session() as db:
            tx = db.fetchone("SELECT * FROM transactions WHERE id=?", (tx_id,))
            if tx:
                delta = -tx["amount"] if tx["type"] == "income" else tx["amount"]
                db.execute("UPDATE accounts SET balance=balance+? WHERE id=?",
                           (delta, tx["account_id"]))
                db.execute("DELETE FROM transactions WHERE id=?", (tx_id,))

    def get_category_monthly(self, month: str) -> list[dict]:
        with db_session() as db:
            return db.fetchall("""
                SELECT c.name, c.color, SUM(t.amount) as total
                FROM transactions t JOIN categories c ON t.category_id=c.id
                WHERE t.type='expense' AND strftime('%Y-%m',t.date)=?
                GROUP BY c.id ORDER BY total DESC
            """, (month,))

    def get_history_6months(self) -> list[dict]:
        with db_session() as db:
            return db.fetchall("""
                SELECT strftime('%Y-%m', date) as month,
                       SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) as income,
                       SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
                FROM transactions
                GROUP BY month ORDER BY month DESC LIMIT 6
            """)


# ── CategoryRepo ──────────────────────────────────────────────────────────────

class CategoryRepo:
    def get_all(self, type_: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM categories"
        params: tuple = ()
        if type_:
            sql += " WHERE type=?"
            params = (type_,)
        sql += " ORDER BY name"
        with db_session() as db:
            return db.fetchall(sql, params)

    def get_color_map(self) -> dict[str, str]:
        with db_session() as db:
            rows = db.fetchall("SELECT name, color FROM categories")
            return {r["name"]: r["color"] for r in rows}

    def find_by_name(self, name: str) -> Optional[dict]:
        with db_session() as db:
            return db.fetchone(
                "SELECT * FROM categories WHERE name=?", (name,))


# ── AccountRepo ───────────────────────────────────────────────────────────────

class AccountRepo:
    def get_all(self) -> list[dict]:
        with db_session() as db:
            return db.fetchall("SELECT * FROM accounts ORDER BY name")

    def get_total_balance(self) -> float:
        with db_session() as db:
            row = db.fetchone(
                "SELECT COALESCE(SUM(balance),0) as total FROM accounts")
            return row["total"] if row else 0.0


# ── BudgetRepo ────────────────────────────────────────────────────────────────

class BudgetRepo:
    def get_by_month(self, month: str) -> list[dict]:
        with db_session() as db:
            return db.fetchall("""
                SELECT b.*, c.name as cat_name, c.color
                FROM budgets b JOIN categories c ON b.category_id=c.id
                WHERE b.month=?
                ORDER BY b.limit_amount DESC
            """, (month,))

    def upsert(self, model: BudgetModel) -> None:
        errors = model.validate()
        if errors:
            raise ValueError("; ".join(errors))
        with db_session() as db:
            existing = db.fetchone(
                "SELECT id FROM budgets WHERE category_id=? AND month=?",
                (model.category_id, model.month)
            )
            if existing:
                db.execute(
                    "UPDATE budgets SET limit_amount=?, alert_threshold=? WHERE id=?",
                    (model.limit_amount, model.alert_threshold, existing["id"])
                )
            else:
                db.execute("""
                    INSERT INTO budgets
                        (category_id, limit_amount, spent_amount, month, alert_threshold)
                    VALUES (?, ?, 0, ?, ?)
                """, (model.category_id, model.limit_amount,
                      model.month, model.alert_threshold))

    def delete(self, budget_id: int) -> None:
        with db_session() as db:
            db.execute("DELETE FROM budgets WHERE id=?", (budget_id,))

    def sync_spent(self, month: str) -> None:
        """Đồng bộ spent_amount từ transactions thực tế."""
        with db_session() as db:
            rows = db.fetchall("""
                SELECT category_id, SUM(amount) as spent
                FROM transactions
                WHERE type='expense' AND strftime('%Y-%m', date)=?
                GROUP BY category_id
            """, (month,))
            for r in rows:
                db.execute(
                    "UPDATE budgets SET spent_amount=? WHERE category_id=? AND month=?",
                    (r["spent"], r["category_id"], month)
                )


# ── UserProfileRepo ───────────────────────────────────────────────────────────

class UserProfileRepo:
    def ensure_table(self) -> None:
        with db_session() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    username  TEXT NOT NULL UNIQUE,
                    full_name TEXT DEFAULT '',
                    color     TEXT DEFAULT '#378ADD',
                    currency  TEXT DEFAULT 'VND',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS user_shared_data (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user  TEXT NOT NULL,
                    shared_with TEXT NOT NULL,
                    permission  TEXT DEFAULT 'read',
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(owner_user, shared_with)
                )
            """)

    def get_all(self) -> list[dict]:
        with db_session() as db:
            return db.fetchall(
                "SELECT * FROM user_profiles ORDER BY full_name")

    def upsert(self, model: UserProfileModel) -> None:
        with db_session() as db:
            existing = db.fetchone(
                "SELECT id FROM user_profiles WHERE username=?",
                (model.username,)
            )
            if existing:
                db.execute(
                    "UPDATE user_profiles SET full_name=?, color=?, currency=? WHERE username=?",
                    (model.full_name, model.color, model.currency, model.username)
                )
            else:
                db.execute(
                    "INSERT INTO user_profiles (username, full_name, color, currency) "
                    "VALUES (?,?,?,?)",
                    (model.username, model.full_name, model.color, model.currency)
                )

    def get(self, username: str) -> Optional[dict]:
        with db_session() as db:
            return db.fetchone(
                "SELECT * FROM user_profiles WHERE username=?", (username,))

    def share_data(self, owner: str, shared_with: str,
                   permission: str = "read") -> None:
        with db_session() as db:
            db.execute("""
                INSERT OR REPLACE INTO user_shared_data
                    (owner_user, shared_with, permission)
                VALUES (?, ?, ?)
            """, (owner, shared_with, permission))

    def get_shared_users(self, owner: str) -> list[dict]:
        with db_session() as db:
            return db.fetchall(
                "SELECT * FROM user_shared_data WHERE owner_user=?", (owner,))
