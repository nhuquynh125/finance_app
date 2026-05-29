# app/core/logger.py  (file mới)
"""
Logger factory cho Finance AI.

Thay thế tất cả print() debug bằng logging chuẩn.

Cách dùng:
    from app.core.logger import get_logger

    logger = get_logger(__name__)

    logger.debug("Chi tiết debug")
    logger.info("Thông tin bình thường")
    logger.warning("Cảnh báo")
    logger.error("Lỗi", exc_info=True)   # exc_info=True để log traceback
    logger.critical("Lỗi nghiêm trọng")

Cấu hình:
    - Log file: data/app.log (tự tạo)
    - Console: chỉ WARNING trở lên (không spam khi chạy bình thường)
    - File: INFO trở lên
    - Rotate khi > 5MB
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

# Thư mục log
_LOG_DIR  = Path("data")
_LOG_FILE = _LOG_DIR / "app.log"


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """
    Lấy logger với tên cho trước.
    Tự động cấu hình handler nếu chưa có.

    Args:
        name: thường dùng __name__ của module

    Returns:
        logging.Logger đã cấu hình
    """
    logger = logging.getLogger(name)

    # Tránh thêm handler nhiều lần
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    _ensure_log_dir()

    # ── File handler: RotatingFileHandler (tự rotate khi > 5MB) ──────────────
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE,
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=3,              # giữ tối đa 3 file backup
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        pass  # Không crash nếu không ghi được file log

    # ── Console handler: chỉ WARNING+ để không spam terminal ─────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        fmt="[%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(console_handler)

    # Không propagate lên root logger (tránh log 2 lần)
    logger.propagate = False

    return logger


# ── Logger tiện dụng cho từng module ─────────────────────────────────────────
# Các module khác có thể import trực tiếp những logger này

ai_logger       = get_logger("finance_ai.ai")
db_logger       = get_logger("finance_ai.db")
ui_logger       = get_logger("finance_ai.ui")
auth_logger     = get_logger("finance_ai.auth")
sync_logger     = get_logger("finance_ai.sync")
