# app/core/error_handler.py  (fix: UnicodeEncodeError trên Windows)
"""
Global exception handler cho Finance AI.

Thay đổi so với phiên bản cũ:
  - Thêm _safe_str() để loại bỏ emoji/ký tự không encode được trước khi
    ghi log và hiển thị QMessageBox — fix UnicodeEncodeError trên Windows
  - Timestamp dùng datetime.now() thay vì stat().st_mtime
  - Log file tự động rotate khi > 5MB
  - Tích hợp với logging module
"""

import sys
import traceback
import logging
import unicodedata
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

# ── Cấu hình đường dẫn log ────────────────────────────────────────────────────
LOG_DIR  = Path("data")
LOG_FILE = LOG_DIR / "error.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ── Helper: chuyển chuỗi về ASCII-safe cho Windows locale ────────────────────
def _safe_str(text: str, max_len: int = 500) -> str:
    """
    Loại bỏ ký tự không encode được bằng locale mặc định của Windows
    (cp1252, gbk...). Thay thế emoji và ký tự đặc biệt bằng '?'.
    Dùng cho QMessageBox và print() — KHÔNG dùng cho file log (log dùng UTF-8).
    """
    if not isinstance(text, str):
        text = str(text)
    # Cắt độ dài trước
    text = text[:max_len]
    # Thử encode bằng locale hiện tại; thay ký tự lỗi bằng '?'
    try:
        locale_enc = sys.stdout.encoding or "utf-8"
    except Exception:
        locale_enc = "utf-8"
    return text.encode(locale_enc, errors="replace").decode(locale_enc, errors="replace")


# ── Cấu hình logging module ───────────────────────────────────────────────────
def _setup_logging():
    logger = logging.getLogger("finance_ai")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # File handler — luôn UTF-8 để giữ nguyên emoji trong log file
        try:
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter(
                fmt="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            logger.addHandler(fh)
        except OSError:
            pass

        # Console handler — dùng errors="replace" để không crash trên Windows
        try:
            import io
            stream = io.TextIOWrapper(
                sys.stderr.buffer if hasattr(sys.stderr, "buffer") else sys.stderr,
                encoding="utf-8",
                errors="replace"
            )
        except Exception:
            stream = sys.stderr

        ch = logging.StreamHandler(stream)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(fmt="[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(ch)

    return logger


app_logger = _setup_logging()


# ── Rotate log nếu quá lớn ────────────────────────────────────────────────────
def _rotate_log_if_needed(max_size_mb: int = 5) -> None:
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > max_size_mb * 1024 * 1024:
            backup = LOG_FILE.with_suffix(".log.bak")
            LOG_FILE.rename(backup)
            app_logger.info(f"Log file rotated -> {backup.name}")
    except OSError:
        pass


# ── Lấy thông tin user hiện tại ───────────────────────────────────────────────
def _get_current_user_info() -> str:
    try:
        from user_session import session
        if session.is_logged_in:
            return f"User: {session.username} ({session.role})"
        return "User: chua dang nhap"
    except Exception:
        return "User: khong xac dinh"


# ── Global exception handler ──────────────────────────────────────────────────
def setup_global_handler(app) -> None:
    """
    Đăng ký global exception handler.
    Gọi một lần trong main() trước khi show window.
    """
    _rotate_log_if_needed()

    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        # Format traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_str   = "".join(tb_lines)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_info = _get_current_user_info()

        log_entry = (
            f"\n{'=' * 60}\n"
            f"Timestamp : {timestamp}\n"
            f"{user_info}\n"
            f"Exception : {exc_type.__name__}: {exc_value}\n"
            f"{'=' * 60}\n"
            f"{tb_str}"
        )

        # Ghi file — luôn UTF-8 (giữ nguyên emoji, ký tự đặc biệt)
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(log_entry)
        except OSError as write_err:
            # Không thể ghi file thì bỏ qua, không crash thêm
            pass

        # Ghi qua logging module
        try:
            app_logger.error(
                f"Unhandled exception: {exc_type.__name__}: {exc_value}",
                exc_info=(exc_type, exc_value, exc_tb)
            )
        except Exception:
            pass

        # Hiển thị QMessageBox — dùng _safe_str() để tránh UnicodeEncodeError
        # khi Qt nội bộ chuyển string sang Windows API
        safe_exc_name = _safe_str(exc_type.__name__, 100)
        safe_msg      = _safe_str(str(exc_value), 300)
        safe_log_path = _safe_str(str(LOG_FILE.absolute()), 200)

        try:
            QMessageBox.critical(
                None,
                "Loi khong mong muon",
                f"Da xay ra loi khong mong muon.\n\n"
                f"Loai loi : {safe_exc_name}\n"
                f"Chi tiet  : {safe_msg}\n\n"
                f"Log da luu tai:\n{safe_log_path}\n\n"
                f"Vui long chup man hinh nay va bao cao neu loi lap lai."
            )
        except Exception:
            # Nếu Qt dialog cũng lỗi, print ra console (đã redirect sang UTF-8)
            try:
                print(log_entry)
            except Exception:
                pass

    sys.excepthook = handle_exception
    app_logger.info(
        f"Finance AI khoi dong - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
