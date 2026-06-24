# auth_manager.py

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from user_session import session


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate số điện thoại Việt Nam.
    Hợp lệ: 10 chữ số, bắt đầu bằng 0.
    Trả về (ok, message_or_normalized).
    """
    import re
    digits = re.sub(r"[\s\-\.]", "", phone.strip())
    if not digits:
        return False, "Số điện thoại không được để trống."
    if not digits.isdigit():
        return False, "Số điện thoại chỉ được chứa chữ số."
    if len(digits) != 10:
        return False, "Số điện thoại phải có đúng 10 chữ số."
    if not digits.startswith("0"):
        return False, "Số điện thoại phải bắt đầu bằng 0."
    return True, digits


def _get_auth_db_path() -> Path:
    """Đường dẫn database xác thực dùng chung (không per-user)."""
    return session.auth_db_path


def _auth_conn() -> sqlite3.Connection:
    """Mở connection tới auth.db."""
    path = _get_auth_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Session file (remember me) ────────────────────────────────────────────────

def _session_file() -> Path:
    """File lưu phiên đăng nhập — đặt trong data/shared/"""
    try:
        return session.auth_db_path.parent / "session.json"
    except Exception:
        return Path("data") / "shared" / "session.json"


# ── AuthManager ───────────────────────────────────────────────────────────────

class AuthManager:

    def __init__(self):
        self._ensure_users_table()

    # ── Public API ────────────────────────────────────────────────────────

    def login(self, phone: str, password: str,
              remember: bool = False) -> dict:
        """
        Xác thực bằng SĐT và thiết lập session.
        Trả về {'success': bool, 'message': str, 'user': dict | None}
        """
        ok, phone_normalized = _validate_phone(phone)
        if not ok:
            return {"success": False, "message": phone_normalized, "user": None}

        conn = _auth_conn()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE phone=? AND is_active=1",
                (phone_normalized,)
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return {"success": False,
                    "message": "Số điện thoại chưa được đăng ký.",
                    "user": None}

        expected = _hash_password(password, row["salt"])
        if expected != row["password_hash"]:
            return {"success": False,
                    "message": "Mật khẩu không đúng. Vui lòng thử lại.",
                    "user": None}

        # Cập nhật last_login
        conn = _auth_conn()
        try:
            conn.execute(
                "UPDATE users SET last_login=? WHERE phone=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phone_normalized)
            )
            conn.commit()
        finally:
            conn.close()

        user = {
            "id":        row["id"],
            "phone":     row["phone"],
            "full_name": row["full_name"] or row["phone"],
            "role":      row["role"],
        }

        # Thiết lập session — quan trọng: phải gọi trước init_database
        session.set_user(user)

        # Khởi tạo DB riêng cho user này nếu chưa có
        from app.data.models import init_database
        init_database()

        if remember:
            self._save_session(phone_normalized)
        else:
            self._clear_session()

        return {"success": True, "message": "Đăng nhập thành công.", "user": user}

    def register(self, password: str,
                 full_name: str = "", phone: str = "") -> dict:
        """
        Tạo tài khoản mới. Khóa chính là SĐT.
        Trả về {'success': bool, 'message': str}
        """
        if len(password) < 6:
            return {"success": False,
                    "message": "Mật khẩu phải có ít nhất 6 ký tự."}

        # Validate & chuẩn hóa SĐT
        if not phone or not phone.strip():
            return {"success": False,
                    "message": "Số điện thoại là thông tin bắt buộc."}
        ok, phone_result = _validate_phone(phone)
        if not ok:
            return {"success": False, "message": phone_result}
        phone_normalized = phone_result   # chuỗi 10 chữ số đã chuẩn hóa

        if not full_name or not full_name.strip():
            return {"success": False, "message": "Họ và tên không được để trống."}

        conn = _auth_conn()
        try:
            # Kiểm tra SĐT trùng
            existing_phone = conn.execute(
                "SELECT id FROM users WHERE phone=?", (phone_normalized,)
            ).fetchone()
            if existing_phone:
                return {"success": False,
                        "message": "Số điện thoại này đã được đăng ký với tài khoản khác."}

            salt = secrets.token_hex(16)
            pw_hash = _hash_password(password, salt)

            conn.execute("""
                INSERT INTO users (password_hash, salt, full_name, phone, role)
                VALUES (?, ?, ?, ?, 'user')
            """, (pw_hash, salt, full_name.strip(), phone_normalized))
            conn.commit()
        finally:
            conn.close()

        # Tạo thư mục và DB cho user mới ngay khi đăng ký
        _tmp_user = {"phone": phone_normalized, "full_name": full_name.strip(), "role": "user"}
        session.set_user(_tmp_user)
        from app.data.models import init_database
        init_database()
        session.clear()

        return {"success": True, "message": "Tạo tài khoản thành công!"}

    def reset_password(self, phone: str, new_password: str) -> dict:
        """Đặt lại mật khẩu cho user theo SĐT."""
        ok, phone_normalized = _validate_phone(phone)
        if not ok:
            return {"success": False, "message": phone_normalized}

        conn = _auth_conn()
        try:
            row = conn.execute(
                "SELECT id FROM users WHERE phone=? AND is_active=1",
                (phone_normalized,)
            ).fetchone()
            if not row:
                return {"success": False,
                        "message": "Số điện thoại không tồn tại hoặc tài khoản đã bị khóa."}

            salt = secrets.token_hex(16)
            pw_hash = _hash_password(new_password, salt)
            conn.execute(
                "UPDATE users SET password_hash=?, salt=? WHERE phone=?",
                (pw_hash, salt, phone_normalized)
            )
            conn.commit()
        finally:
            conn.close()
        return {"success": True, "message": "Đặt lại mật khẩu thành công."}

    def get_remembered_user(self) -> str | None:
        """Trả về phone đã lưu phiên, hoặc None."""
        sf = _session_file()
        if not sf.exists():
            return None
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            return data.get("phone")
        except Exception:
            return None

    def logout(self) -> None:
        """Xóa phiên đăng nhập và reset DB connection."""
        self._clear_session()
        # Reset DatabaseManager singleton để user kế tiếp bắt đầu fresh
        from app.data.models import DatabaseManager
        DatabaseManager.reset()
        session.clear()

    def find_user_by_phone(self, phone: str) -> dict | None:
        """Tìm người dùng theo số điện thoại."""
        ok, phone_normalized = _validate_phone(phone)
        if not ok:
            return None
        conn = _auth_conn()
        try:
            row = conn.execute(
                "SELECT id, full_name, phone FROM users WHERE phone=? AND is_active=1",
                (phone_normalized,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_users(self) -> list:
        """Trả danh sách user (admin only)."""
        conn = _auth_conn()
        try:
            rows = conn.execute(
                "SELECT id, full_name, phone, role, last_login, is_active "
                "FROM users ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Internal ──────────────────────────────────────────────────────────

    def _ensure_users_table(self):
        """Đảm bảo bảng users tồn tại trong auth.db với phone là khóa chính định danh."""
        conn = _auth_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    password_hash TEXT    NOT NULL,
                    salt          TEXT    NOT NULL,
                    full_name     TEXT    DEFAULT '',
                    phone         TEXT    NOT NULL UNIQUE,
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
                pass  # cột đã tồn tại
            # Đảm bảo có UNIQUE index cho phone
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
                pw_hash = _hash_password("admin123", salt)
                conn.execute("""
                    INSERT INTO users (password_hash, salt, full_name, phone, role)
                    VALUES (?, ?, 'Quản trị viên', '0000000000', 'admin')
                """, (pw_hash, salt))
            conn.commit()
        finally:
            conn.close()

    def _save_session(self, phone: str):
        sf = _session_file()
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(
            json.dumps({"phone": phone}, ensure_ascii=False),
            encoding="utf-8"
        )

    def _clear_session(self):
        sf = _session_file()
        if sf.exists():
            try:
                sf.unlink()
            except Exception:
                pass