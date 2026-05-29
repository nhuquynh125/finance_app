# settings_manager.py  (cập nhật: per-user settings)
"""
Quản lý settings per-user.

Thay đổi so với phiên bản cũ:
  - SETTINGS_PATH lấy động từ user_session (data/users/{username}/settings.json)
  - ENV_PATH (.env) vẫn ở thư mục gốc (dùng chung API keys)
  - backup_database() dùng DB path của user hiện tại
  - export_database_to_excel() dùng DB path của user hiện tại
  - Cache settings tách biệt per-user (invalidate khi đổi user)
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

try:
    from config import BASE_DIR
    _BASE_DIR = Path(BASE_DIR)
except (ImportError, AttributeError):
    _BASE_DIR = Path(__file__).resolve().parent


ENV_PATH = _BASE_DIR / ".env"

DEFAULT_SETTINGS = {
    "currency": "VND",
    "date_format": "dd/MM/yyyy",
    "default_month": "current",
    "auto_refresh": True,
    "auto_classification": True,
    "anomaly_detection": True,
    "forecast_method": "auto",
    "chat_engine": "gemini",
    "window_mode": "default",
}


# ── Helpers per-user ──────────────────────────────────────────────────────────

def _get_settings_path() -> Path:
    """Đường dẫn settings.json của user hiện tại."""
    try:
        from user_session import session
        if session.is_logged_in:
            return session.settings_path
    except ImportError:
        pass
    return _BASE_DIR / "data" / "settings.json"


def _get_db_path() -> Path:
    try:
        from user_session import session
        if session.is_logged_in:
            return session.db_path
    except ImportError:
        pass
    try:
        from config import DB_PATH
        return Path(DB_PATH)
    except ImportError:
        return _BASE_DIR / "data" / "finance.db"


def _get_backups_dir() -> Path:
    try:
        from user_session import session
        if session.is_logged_in:
            return session.backups_dir
    except ImportError:
        pass
    return _BASE_DIR / "data" / "backups"


def _get_exports_dir() -> Path:
    try:
        from user_session import session
        if session.is_logged_in:
            return session.exports_dir
    except ImportError:
        pass
    return _BASE_DIR / "data" / "exports"


# ── Settings cache (per-user: key = username hoặc "__default__") ──────────────

_settings_cache: dict[str, dict] = {}


def _cache_key() -> str:
    try:
        from user_session import session
        return session.username if session.is_logged_in else "__default__"
    except Exception:
        return "__default__"


def _invalidate_cache():
    key = _cache_key()
    _settings_cache.pop(key, None)


def load_settings() -> dict:
    key = _cache_key()
    if key in _settings_cache:
        return _settings_cache[key]

    settings_path = _get_settings_path()

    if not settings_path.exists():
        merged = DEFAULT_SETTINGS.copy()
        save_settings(merged)
        _settings_cache[key] = merged
        return merged

    try:
        with settings_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}

    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    _settings_cache[key] = merged
    return merged


def save_settings(settings: dict) -> dict:
    key = _cache_key()
    settings_path = _get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS})

    with settings_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    _settings_cache[key] = merged
    return merged


def get_setting(key: str, default=None):
    return load_settings().get(key, default)


# ── .env helpers (dùng chung, không per-user) ─────────────────────────────────

_env_cache: dict | None = None


def _load_env_file() -> dict:
    global _env_cache
    if _env_cache is not None:
        return _env_cache
    result = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    _env_cache = result
    return result


def update_env_value(key: str, value: str) -> None:
    global _env_cache
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    os.environ[key] = value
    if _env_cache is not None:
        _env_cache[key] = value


def get_env_value(key: str, default: str = "") -> str:
    if key in os.environ:
        return os.environ[key]
    return _load_env_file().get(key, default)


# ── Backup / restore / export (per-user) ─────────────────────────────────────

def backup_database() -> Path:
    db_path = _get_db_path()
    backups_dir = _get_backups_dir()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backups_dir / f"finance_backup_{stamp}.db"
    shutil.copy2(db_path, target)
    return target


def restore_database(source_path: str | Path) -> Path:
    source = Path(source_path)
    db_path = _get_db_path()

    if not source.exists():
        raise FileNotFoundError(f"Backup not found: {source}")
    if source.resolve() == db_path.resolve():
        raise ValueError("Source database is already the active database.")

    backup_path = backup_database() if db_path.exists() else None

    # Đóng connection hiện tại trước khi ghi đè
    from app.data.models import DatabaseManager
    DatabaseManager.reset()

    shutil.copy2(source, db_path)
    return backup_path


def export_database_to_excel(target_path: str | Path) -> Path:
    import pandas as pd
    import sqlite3 as _sqlite3

    db_path = _get_db_path()
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    tables = [
        "accounts", "categories", "transactions",
        "budgets", "ai_predictions", "chat_history",
    ]
    conn = _sqlite3.connect(str(db_path))
    try:
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            for table in tables:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                    df.to_excel(writer, sheet_name=table[:31], index=False)
                except Exception:
                    pass
    finally:
        conn.close()
    return target


def package_status(package_names: list[str]) -> dict:
    import importlib.util
    return {
        name: importlib.util.find_spec(name) is not None
        for name in package_names
    }


# ── Dùng trong các frame cần EXPORTS_DIR ────────────────────────────────────

def get_exports_dir() -> Path:
    d = _get_exports_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d
