# main.py  (cập nhật: per-user database + session management + UTF-8 fix)
"""
Entry point của Finance AI.

Thay đổi so với phiên bản cũ:
  - init_auth_database() khởi tạo DB xác thực dùng chung (data/shared/auth.db)
  - init_database() per-user được gọi bên trong AuthManager.login()
  - user_session.session.set_user() được gọi sau đăng nhập thành công
  - DatabaseManager.reset() được gọi khi đăng xuất
  - Fix UnicodeEncodeError trên Windows: set stdout/stderr sang UTF-8
"""

import sys
import os
from pathlib import Path


# ── Fix UTF-8 encoding cho Windows console (trước mọi import khác) ───────────
# Ngăn UnicodeEncodeError khi traceback/log chứa emoji hoặc ký tự đặc biệt
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _use_project_venv():
    venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    running_this_script = Path(sys.argv[0]).resolve() == Path(__file__).resolve()
    if (running_this_script and venv_python.exists() and
            Path(sys.executable).resolve() != venv_python.resolve()):
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])


_use_project_venv()

from PyQt6.QtWidgets import QApplication
from app.core.theme_engine import theme_engine
from app.data.models import init_auth_database
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow
from app.core.error_handler import setup_global_handler
<<<<<<< HEAD
=======
from pyQt6.QtGui import QIcon

def _set_app_icon(app: QApplication):
    icon_path = Path(__file__).resolve().parent / "finance_ai_app" / "logo-AI.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
>>>>>>> 0f9883f6111b8d064c73b5d2f2039834c7327128

def main():
    app = QApplication(sys.argv)
    setup_global_handler(app)

    init_auth_database()

    theme_engine.apply(app)
    app.setStyle("Fusion")

    def on_login_success(user: dict):
        window = MainWindow(current_user=user)
        window.show()
        app._main_window = window

    login = LoginWindow()
    login.login_success.connect(on_login_success)
    login.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()