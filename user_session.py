# user_session.py
"""
Quản lý phiên đăng nhập hiện tại — singleton toàn app.

Mục đích chính:
  - Lưu user đang đăng nhập (username, full_name, role)
  - Cung cấp DB_PATH và DATA_DIR động theo từng user
  - Mỗi user có thư mục riêng: data/users/{username}/

Cách dùng:
    from user_session import session

    # Sau khi đăng nhập thành công:
    session.set_user({"username": "alice", "full_name": "Alice", "role": "user"})

    # Lấy đường dẫn DB của user hiện tại:
    db_path = session.db_path

    # Lấy thư mục data của user hiện tại:
    data_dir = session.data_dir
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


# Thư mục gốc chứa data của tất cả user
# Tương thích với config.py chuẩn của project (DATA_DIR = BASE_DIR / "data")
try:
    from config import BASE_DIR
    _BASE_DIR = Path(BASE_DIR)
except (ImportError, AttributeError):
    _BASE_DIR = Path(__file__).resolve().parent


class _UserSession:
    """
    Singleton lưu trạng thái user đang đăng nhập.
    Không import ở module-level để tránh circular import —
    dùng `from user_session import session`.
    """

    def __init__(self):
        self._user: Optional[dict] = None

    # ── Thiết lập / xóa user ──────────────────────────────────────────────

    def set_user(self, user: dict) -> None:
        """
        Gọi ngay sau khi đăng nhập thành công.
        user: {"username": ..., "full_name": ..., "role": ...}
        Tự động tạo thư mục data riêng cho user nếu chưa có.
        """
        self._user = user
        self._ensure_user_dirs()

    def clear(self) -> None:
        """Gọi khi đăng xuất."""
        self._user = None

    # ── Thông tin user ────────────────────────────────────────────────────

    @property
    def is_logged_in(self) -> bool:
        return self._user is not None

    @property
    def username(self) -> str:
        if not self._user:
            raise RuntimeError("Chưa đăng nhập — gọi session.set_user() trước")
        return self._user["username"]

    @property
    def full_name(self) -> str:
        return (self._user or {}).get("full_name", "")

    @property
    def role(self) -> str:
        return (self._user or {}).get("role", "user")

    @property
    def user_dict(self) -> Optional[dict]:
        return self._user.copy() if self._user else None

    # ── Đường dẫn per-user ────────────────────────────────────────────────

    @property
    def users_root(self) -> Path:
        """Thư mục gốc chứa data của tất cả user: data/users/"""
        return _BASE_DIR / "data" / "users"

    @property
    def data_dir(self) -> Path:
        """Thư mục data của user hiện tại: data/users/{username}/"""
        return self.users_root / self.username

    @property
    def db_path(self) -> Path:
        """Đường dẫn SQLite database của user hiện tại."""
        return self.data_dir / "finance.db"

    @property
    def settings_path(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def ai_dir(self) -> Path:
        """Thư mục lưu model AI (fine-tuned, classifier) của user."""
        return self.data_dir / "ai"

    # ── Tạo thư mục ──────────────────────────────────────────────────────

    def _ensure_user_dirs(self) -> None:
        for d in [self.data_dir, self.backups_dir, self.exports_dir, self.ai_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ── Auth DB (dùng chung, không per-user) ─────────────────────────────

    @property
    def auth_db_path(self) -> Path:
        """
        Database chứa bảng users (dùng chung cho tất cả user).
        Tách riêng khỏi finance.db của từng user.
        """
        shared = _BASE_DIR / "data" / "shared"
        shared.mkdir(parents=True, exist_ok=True)
        return shared / "auth.db"


# Singleton — import và dùng trực tiếp
session = _UserSession()
