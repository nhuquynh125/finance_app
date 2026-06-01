#app/ui/login_window.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QStackedWidget,
    QApplication, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QFont, QPixmap, QColor, QPainter, QLinearGradient,
    QBrush, QRadialGradient, QPainterPath,
)
from pathlib import Path

from app.data.auth_manager import AuthManager
from app.core.settings_manager import load_settings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_logo(size: int = 80) -> QPixmap | None:
    """Tìm và scale logo. Trả về None nếu không có file."""
    search_paths = [
        Path(__file__).resolve().parent.parent.parent / "logo.png",
        Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png",
        Path("logo.png"),
        Path("assets/logo.png"),
    ]
    for p in search_paths:
        if p.exists():
            px = QPixmap(str(p))
            if not px.isNull():
                return px.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
    return None

LOGIN_WINDOW_QSS = """
/* ── LoginWindow isolation ── */
QWidget#loginWindow {
    background: #F0F6FF;
    font-family: 'Segoe UI', sans-serif;
}

/* Right panel */
QWidget#loginRight {
    background: #F0F6FF;
}

/* Card */
QFrame#loginCard {
    background: #ffffff;
    border-radius: 20px;
    border: 1px solid #D0E4F7;
}

/* Input fields — specificity cao để override global QSS */
QWidget#loginWindow QLineEdit,
QFrame#loginCard QLineEdit {
    border: 1.5px solid #D0E4F7 !important;
    border-radius: 10px;
    padding: 0 16px;
    font-size:15px;
    background: #F5F9FF;
    color: #0B2A4A;
    font-family: 'Segoe UI', sans-serif;
    selection-background-color: #B5D4F4;
    selection-color: #0B2A4A;
}
QWidget#loginWindow QLineEdit:focus,
QFrame#loginCard QLineEdit:focus {
    border: 1.5px solid #1A6BAF !important;
    background: #ffffff;
}
QWidget#loginWindow QLineEdit:hover,
QFrame#loginCard QLineEdit:hover {
    border: 1.5px solid #8BAEC8 !important;
    background: #ffffff;
}

/* Labels */
QWidget#loginWindow QLabel,
QFrame#loginCard QLabel {
    color: #0B2A4A;
    background: transparent;
    border: none;
}

/* Buttons */
QWidget#loginWindow QPushButton,
QFrame#loginCard QPushButton {
    font-family: 'Segoe UI', sans-serif;
}

/* CheckBox */
QWidget#loginWindow QCheckBox,
QFrame#loginCard QCheckBox {
    color: #3A6B9A;
    font-size:14px;
    border: none;
    background: transparent;
}
QWidget#loginWindow QCheckBox::indicator,
QFrame#loginCard QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid #D0E4F7;
    background: #F5F9FF;
}
QWidget#loginWindow QCheckBox::indicator:checked,
QFrame#loginCard QCheckBox::indicator:checked {
    background: #1A6BAF;
    border-color: #1A6BAF;
}
"""


class StyledInput(QWidget):

    def __init__(self, placeholder: str, is_password: bool = False, parent=None):
        super().__init__(parent)
        self.is_password = is_password
        self._password_visible = False
        self.setFixedHeight(46)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(placeholder)
        self._edit.setFixedHeight(46)
        self._edit.setObjectName("loginInput")
        if is_password:
            self._edit.setEchoMode(QLineEdit.EchoMode.Password)

        # Style inline để đảm bảo luôn hiển thị đúng bất kể global QSS
        right_padding = "42px" if is_password else "16px"
        self._edit.setStyleSheet(f"""
            QLineEdit#loginInput {{
                border: 1.5px solid #D0E4F7;
                border-radius: 10px;
                padding: 0 {right_padding} 0 16px;
                font-size:15px;
                background-color: #F5F9FF;
                color: #0B2A4A;
                font-family: 'Segoe UI', sans-serif;
                selection-background-color: #B5D4F4;
                selection-color: #0B2A4A;
            }}
            QLineEdit#loginInput:focus {{
                border: 1.5px solid #1A6BAF;
                background-color: #ffffff;
            }}
            QLineEdit#loginInput:hover {{
                border: 1.5px solid #8BAEC8;
                background-color: #ffffff;
            }}
        """)
        layout.addWidget(self._edit)

        if is_password:
            self._eye_btn = QPushButton("👁", self)
            self._eye_btn.setFixedSize(32, 32)
            self._eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._eye_btn.setObjectName("eyeBtn")
            self._eye_btn.setStyleSheet("""
                QPushButton#eyeBtn {
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    font-size:18px;
                    color: #8BAEC8;
                    padding: 0;
                }
                QPushButton#eyeBtn:hover {
                    background: rgba(26,107,175,0.1);
                    color: #1A6BAF;
                }
            """)
            self._eye_btn.clicked.connect(self._toggle_visibility)
            self._position_eye_btn()

    def _position_eye_btn(self):
        if hasattr(self, "_eye_btn"):
            x = self.width() - self._eye_btn.width() - 7
            y = (self.height() - self._eye_btn.height()) // 2
            self._eye_btn.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_eye_btn()

    def _toggle_visibility(self):
        self._password_visible = not self._password_visible
        if self._password_visible:
            self._edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._eye_btn.setText("🙈")
        else:
            self._edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._eye_btn.setText("👁")

    # Proxy thường dùng
    def text(self) -> str:
        return self._edit.text()

    def setText(self, text: str):
        self._edit.setText(text)

    def setPlaceholderText(self, text: str):
        self._edit.setPlaceholderText(text)

    def clear(self):
        self._edit.clear()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._edit.setEnabled(enabled)

    @property
    def returnPressed(self):
        return self._edit.returnPressed

    @property
    def textChanged(self):
        return self._edit.textChanged


# ── Login Panel ───────────────────────────────────────────────────────────────

class LoginPanel(QWidget):
    login_success = pyqtSignal(dict)
    go_register = pyqtSignal()
    go_forgot = pyqtSignal()

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self.auth = auth
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        welcome = QLabel("💰Finance AI")
        welcome.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        welcome.setStyleSheet("color:#0B2A4A; border:none; background:transparent;")
        layout.addWidget(welcome)

        hint = QLabel("Quản lý tài chính thông minh")
        hint.setStyleSheet("color:#4A6785; font-size:14px; border:none; background:transparent;")
        layout.addWidget(hint)

        def _field_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "color:#3A6B9A; font-size:14px; font-weight:600; "
                "border:none; background:transparent;")
            return lbl

        layout.addWidget(_field_label("Tên đăng nhập"))
        self.username_input = StyledInput("Nhập tên đăng nhập...")
        layout.addWidget(self.username_input)

        pass_row_lbl = QHBoxLayout()
        pass_row_lbl.addWidget(_field_label("Mật khẩu"))
        pass_row_lbl.addStretch()
        forgot_btn = QPushButton("Quên mật khẩu?")
        forgot_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#1A6BAF; border:none; "
            "font-size:14px; padding:0; } "
            "QPushButton:hover { color:#0B2A4A; }"
        )
        forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot_btn.clicked.connect(self.go_forgot.emit)
        pass_row_lbl.addWidget(forgot_btn)
        layout.addLayout(pass_row_lbl)

        self.password_input = StyledInput("Nhập mật khẩu...", is_password=True)
        self.password_input.returnPressed.connect(self._do_login)
        layout.addWidget(self.password_input)

        self.remember_check = QCheckBox("Ghi nhớ đăng nhập")
        self.remember_check.setStyleSheet("""
            QCheckBox { color:#3A6B9A; font-size:14px; border:none; background:transparent; }
            QCheckBox::indicator {
                width:16px; height:16px; border-radius:4px;
                border:1.5px solid #D0E4F7; background:#F5F9FF;
            }
            QCheckBox::indicator:checked { background:#1A6BAF; border-color:#1A6BAF; }
        """)
        layout.addWidget(self.remember_check)

        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("errorLabel")
        self.error_lbl.setStyleSheet("""
            QLabel#errorLabel {
                background-color: #FEF0EB;
                color: #C0392B;
                border: 1px solid #F5C6CB;
                border-radius: 8px;
                padding: 8px 12px;
                font-size:14px;
            }
        """)
        self.error_lbl.setWordWrap(True)
        self.error_lbl.hide()
        layout.addWidget(self.error_lbl)

        self.login_btn = QPushButton("Đăng nhập")
        self.login_btn.setFixedHeight(48)
        self.login_btn.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setStyleSheet("""
            QPushButton#loginBtn {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1A6BAF, stop:1 #0B2A4A);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                letter-spacing: 0.5px;
            }
            QPushButton#loginBtn:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0B2A4A, stop:1 #0A4F6E);
            }
            QPushButton#loginBtn:pressed { background: #0A4F6E; }
            QPushButton#loginBtn:disabled { background: #8BAEC8; color: #fff; }
        """)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self._do_login)
        layout.addWidget(self.login_btn)

        reg_row = QHBoxLayout()
        reg_row.addStretch()
        no_acc = QLabel("Chưa có tài khoản?")
        no_acc.setStyleSheet("color:#4A6785; font-size:14px; border:none; background:transparent;")
        reg_row.addWidget(no_acc)
        reg_btn = QPushButton("Đăng ký ngay")
        reg_btn.setStyleSheet("""
            QPushButton { background:transparent; color:#1A6BAF;
                border:none; font-size:14px; font-weight:600; padding:0 4px; }
            QPushButton:hover { color:#0B2A4A; }
        """)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.clicked.connect(self.go_register.emit)
        reg_row.addWidget(reg_btn)
        reg_row.addStretch()
        layout.addLayout(reg_row)

    def _do_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self._show_error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
            return
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Đang đăng nhập...")
        result = self.auth.login(username, password, remember=self.remember_check.isChecked())
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Đăng nhập")
        if result["success"]:
            self.error_lbl.hide()
            self.login_success.emit(result["user"])
        else:
            self._show_error(result["message"])

    def _show_error(self, msg: str):
        self.error_lbl.setText(msg)
        self.error_lbl.show()
        QTimer.singleShot(4000, self.error_lbl.hide)

    def prefill_username(self, username: str):
        self.username_input.setText(username)
        self.remember_check.setChecked(True)


# ── Register Panel ────────────────────────────────────────────────────────────

class RegisterPanel(QWidget):
    register_success = pyqtSignal()
    go_login = pyqtSignal()

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self.auth = auth
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        back_btn = QPushButton("← Quay lại đăng nhập")
        back_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#1A6BAF; border:none; "
            "font-size:14px; padding:0; } "
            "QPushButton:hover { color:#0B2A4A; }"
        )
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_login.emit)
        layout.addWidget(back_btn)

        title = QLabel("Tạo tài khoản mới")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color:#0B2A4A; border:none; background:transparent;")
        layout.addWidget(title)

        sub = QLabel("Điền thông tin để bắt đầu quản lý tài chính")
        sub.setStyleSheet("color:#4A6785; font-size:14px; border:none; background:transparent;")
        layout.addWidget(sub)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(
                "color:#3A6B9A; font-size:14px; font-weight:600; "
                "border:none; background:transparent;")
            return l

        layout.addWidget(_lbl("Họ và tên"))
        self.fullname_input = StyledInput("Nguyễn Văn A...")
        layout.addWidget(self.fullname_input)

        layout.addWidget(_lbl("Số điện thoại (định danh chính)"))
        self.phone_input = StyledInput("0912 345 678...")
        layout.addWidget(self.phone_input)

        layout.addWidget(_lbl("Tên đăng nhập"))
        self.username_input = StyledInput("Nhập tên đăng nhập (3-30 ký tự)...")
        layout.addWidget(self.username_input)

        layout.addWidget(_lbl("Mật khẩu"))
        self.password_input = StyledInput("Tối thiểu 6 ký tự...", is_password=True)
        layout.addWidget(self.password_input)

        layout.addWidget(_lbl("Xác nhận mật khẩu"))
        self.confirm_input = StyledInput("Nhập lại mật khẩu...", is_password=True)
        self.confirm_input.returnPressed.connect(self._do_register)
        layout.addWidget(self.confirm_input)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        self.reg_btn = QPushButton("Tạo tài khoản")
        self.reg_btn.setFixedHeight(48)
        self.reg_btn.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.reg_btn.setObjectName("regBtn")
        self.reg_btn.setStyleSheet("""
            QPushButton#regBtn {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1D9E75, stop:1 #0A4F6E);
                color: #ffffff; border: none; border-radius: 12px;
            }
            QPushButton#regBtn:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #158060, stop:1 #0B2A4A);
            }
            QPushButton#regBtn:disabled { background:#8BAEC8; color:#fff; }
        """)
        self.reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reg_btn.clicked.connect(self._do_register)
        layout.addWidget(self.reg_btn)

    def _do_register(self):
        fullname = self.fullname_input.text().strip()
        phone = self.phone_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not fullname or not phone or not username or not password:
            self._show_msg("Vui lòng điền đầy đủ thông tin.", "error")
            return
        if len(username) < 3:
            self._show_msg("Tên đăng nhập phải có ít nhất 3 ký tự.", "error")
            return
        if len(password) < 6:
            self._show_msg("Mật khẩu phải có ít nhất 6 ký tự.", "error")
            return
        if password != confirm:
            self._show_msg("Mật khẩu xác nhận không khớp.", "error")
            return

        self.reg_btn.setEnabled(False)
        result = self.auth.register(username, password, fullname, phone)
        self.reg_btn.setEnabled(True)

        if result["success"]:
            self._show_msg("Tạo tài khoản thành công! Đang chuyển hướng...", "success")
            QTimer.singleShot(1200, self.register_success.emit)
        else:
            self._show_msg(result["message"], "error")

    def _show_msg(self, msg: str, kind: str):
        if kind == "error":
            self.msg_lbl.setStyleSheet("""
                QLabel { background-color:#FEF0EB; color:#C0392B;
                    border:1px solid #F5C6CB; border-radius:8px;
                    padding:8px 12px; font-size:14px; }
            """)
        else:
            self.msg_lbl.setStyleSheet("""
                QLabel { background-color:#EAF7F2; color:#0A4F3E;
                    border:1px solid #B8DFAA; border-radius:8px;
                    padding:8px 12px; font-size:14px; }
            """)
        self.msg_lbl.setText(msg)
        self.msg_lbl.show()


# ── Forgot Password Panel ─────────────────────────────────────────────────────

class ForgotPanel(QWidget):
    go_login = pyqtSignal()

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self.auth = auth
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        back_btn = QPushButton("← Quay lại đăng nhập")
        back_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#1A6BAF; border:none; "
            "font-size:14px; padding:0; }"
        )
        back_btn.clicked.connect(self.go_login.emit)
        layout.addWidget(back_btn)

        icon = QLabel("🔑")
        icon.setFont(QFont("Segoe UI Emoji", 34))
        icon.setStyleSheet("border:none; background:transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("Đặt lại mật khẩu")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color:#0B2A4A; border:none; background:transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(
                "color:#3A6B9A; font-size:14px; font-weight:600; "
                "border:none; background:transparent;")
            return l

        layout.addWidget(_lbl("Tên đăng nhập"))
        self.username_input = StyledInput("Nhập tên đăng nhập...")
        layout.addWidget(self.username_input)

        layout.addWidget(_lbl("Mật khẩu mới"))
        self.new_pass_input = StyledInput("Tối thiểu 6 ký tự...", is_password=True)
        layout.addWidget(self.new_pass_input)

        layout.addWidget(_lbl("Xác nhận mật khẩu mới"))
        self.confirm_input = StyledInput("Nhập lại mật khẩu...", is_password=True)
        self.confirm_input.returnPressed.connect(self._do_reset)
        layout.addWidget(self.confirm_input)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        reset_btn = QPushButton("Đặt lại mật khẩu")
        reset_btn.setFixedHeight(48)
        reset_btn.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        reset_btn.setObjectName("resetBtn")
        reset_btn.setStyleSheet("""
            QPushButton#resetBtn {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #E8921A, stop:1 #C47312);
                color:#ffffff; border:none; border-radius:12px;
            }
            QPushButton#resetBtn:hover { background: #C47312; }
        """)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._do_reset)
        layout.addWidget(reset_btn)

    def _do_reset(self):
        username = self.username_input.text().strip()
        new_pass = self.new_pass_input.text()
        confirm = self.confirm_input.text()

        if not username or not new_pass:
            self._show_msg("Vui lòng điền đầy đủ thông tin.", "error")
            return
        if len(new_pass) < 6:
            self._show_msg("Mật khẩu mới phải có ít nhất 6 ký tự.", "error")
            return
        if new_pass != confirm:
            self._show_msg("Mật khẩu xác nhận không khớp.", "error")
            return

        result = self.auth.reset_password(username, new_pass)
        if result["success"]:
            self._show_msg("Đặt lại thành công! Đang quay lại...", "success")
            QTimer.singleShot(1500, self.go_login.emit)
        else:
            self._show_msg(result["message"], "error")

    def _show_msg(self, msg: str, kind: str):
        c = (
            "background-color:#FEF0EB; color:#C0392B; border:1px solid #F5C6CB;"
            if kind == "error"
            else "background-color:#EAF7F2; color:#0A4F3E; border:1px solid #B8DFAA;"
        )
        self.msg_lbl.setStyleSheet(
            f"QLabel {{ {c} border-radius:8px; padding:8px 12px; font-size:14px; }}"
        )
        self.msg_lbl.setText(msg)
        self.msg_lbl.show()


# ── Branding Panel (left side — navy gradient + logo) ─────────────────────────

class BrandingPanel(QWidget):
    _T = "background: transparent; border: none;"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self._build()

    def _lbl(self, text, size=11, bold=False, color="white", center=False, wrap=False):
        l = QLabel(text)
        w = QFont.Weight.Bold if bold else QFont.Weight.Normal
        l.setFont(QFont("Segoe UI", size, w))
        l.setStyleSheet(f"{self._T} color: {color};")
        if center:
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if wrap:
            l.setWordWrap(True)
        return l

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)
        layout.addStretch()

        logo_px = _load_logo(100)
        if logo_px:
            logo_lbl = QLabel()
            logo_lbl.setPixmap(logo_px)
            logo_lbl.setFixedSize(100, 100)
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_lbl.setStyleSheet(self._T)
            layout.addWidget(logo_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addSpacing(16)
        else:
            icon_lbl = QLabel("🤖")
            icon_lbl.setFont(QFont("Segoe UI Emoji", 54))
            icon_lbl.setStyleSheet(self._T)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_lbl)
            layout.addSpacing(16)

        layout.addWidget(self._lbl("Finance AI", size=26, bold=True, center=True))
        layout.addSpacing(8)
        layout.addWidget(
            self._lbl(
                "Quản lý tài chính thông minh hơn",
                size=13, color="rgba(255,255,255,0.85)", center=True, wrap=True,
            )
        )
        layout.addSpacing(16)

        features = [
            ("🤖", "AI Chatbot tư vấn tài chính"),
            ("📈", "Dự báo chi tiêu theo tháng"),
            ("⚠️", "Phát hiện giao dịch bất thường"),
            ("📄", "Xuất báo cáo PDF tự động"),
        ]
        for icon_char, feat_text in features:
            pill = QWidget()
            pill.setStyleSheet("""
                QWidget {
                    background: rgba(255,255,255,0.1);
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.15);
                }
            """)
            pill_l = QHBoxLayout(pill)
            pill_l.setContentsMargins(14, 8, 14, 8)
            pill_l.setSpacing(10)
            ic = QLabel(icon_char)
            ic.setFont(QFont("Segoe UI Emoji", 15))
            ic.setStyleSheet(self._T)
            ic.setFixedWidth(26)
            pill_l.addWidget(ic)
            tx = QLabel(feat_text)
            tx.setFont(QFont("Segoe UI", 13))
            tx.setStyleSheet(f"{self._T} color: rgba(255,255,255,0.9);")
            pill_l.addWidget(tx)
            pill_l.addStretch()
            layout.addWidget(pill)
            layout.addSpacing(6)

        layout.addStretch()
        layout.addWidget(
            self._lbl(
                "Như Quỳnh (25AI043)  +  Hưng Phú (25AI034)",
                size=9, color="rgba(255,255,255,0.4)", center=True,
            )
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#061422"))
        gradient.setColorAt(0.4, QColor("#0B2A4A"))
        gradient.setColorAt(0.7, QColor("#0D4A6B"))
        gradient.setColorAt(1.0, QColor("#0A5C4A"))
        painter.fillRect(self.rect(), QBrush(gradient))
        radial = QRadialGradient(
            self.width() * 0.7, self.height() * 0.25, self.width() * 0.6
        )
        radial.setColorAt(0.0, QColor(26, 107, 175, 40))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), QBrush(radial))


# ── Main Login Window ─────────────────────────────────────────────────────────

class LoginWindow(QWidget):
    login_success = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth = AuthManager()
        self.setWindowTitle("Finance AI — Đăng nhập")
        self.setObjectName("loginWindow")

        # Đặt kích thước TRƯỚC khi build UI.
        self._configure_size()
        self._build()

        # Áp dụng QSS riêng cho login window SAU khi theme_engine đã set global QSS.
        # Dùng setStyleSheet trực tiếp trên widget này để override với specificity cao hơn.
        self.setStyleSheet(LOGIN_WINDOW_QSS)

        self._check_remembered()

        # fullscreen cần gọi sau khi window đã visible
        settings = load_settings()
        if settings.get("window_mode") == "fullscreen":
            QTimer.singleShot(0, self.showFullScreen)

    def _configure_size(self):
        """Chỉ đặt kích thước và vị trí, KHÔNG show window."""
        settings = load_settings()
        mode = settings.get("window_mode", "default")
        w, h = (1366, 768) if mode == "large" else (1000, 660)
        self.setMinimumSize(760, 520)
        self.resize(w, h)
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move((screen.width() - w) // 2, (screen.height() - h) // 2)
        except Exception:
            pass

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left: branding panel
        self.brand = BrandingPanel()
        self.brand.setFixedWidth(400)
        self.brand.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        root.addWidget(self.brand, stretch=0)

        # Right: form area
        right = QWidget()
        right.setObjectName("loginRight")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Top strip with logo
        top_strip = QWidget()
        top_strip.setObjectName("loginTopStrip")
        top_strip.setStyleSheet(
            "QWidget#loginTopStrip { background: #FFFFFF; "
            "border-bottom: 1px solid #D0E4F7; border-radius:0; }")
        top_strip.setFixedHeight(56)
        ts_l = QHBoxLayout(top_strip)
        ts_l.setContentsMargins(24, 0, 24, 0)
        logo_px2 = _load_logo(32)
        if logo_px2:
            lo = QLabel()
            lo.setPixmap(logo_px2)
            lo.setStyleSheet("border:none; background:transparent;")
            ts_l.addWidget(lo)
            ts_l.addSpacing(8)
        app_name = QLabel("Finance AI")
        app_name.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        app_name.setStyleSheet(
            "color:#0B2A4A; border:none; background:transparent;")
        ts_l.addWidget(app_name)
        ts_l.addStretch()

        right_outer = QVBoxLayout()
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)
        right_outer.addWidget(top_strip)
        right_outer.addStretch(1)

        # Login card
        card_wrap = QVBoxLayout()
        card_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(400)
        card.setStyleSheet("""
            QFrame#loginCard {
                background: #ffffff;
                border-radius: 20px;
                border: 1px solid #D0E4F7;
            }
        """)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(32, 32, 32, 32)
        card_l.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(
            "QStackedWidget { background:transparent; border:none; }")

        self.login_panel = LoginPanel(self.auth)
        self.register_panel = RegisterPanel(self.auth)
        self.forgot_panel = ForgotPanel(self.auth)

        self.stack.addWidget(self.login_panel)
        self.stack.addWidget(self.register_panel)
        self.stack.addWidget(self.forgot_panel)

        self.login_panel.login_success.connect(self._on_login_success)
        self.login_panel.go_register.connect(lambda: self.stack.setCurrentIndex(1))
        self.login_panel.go_forgot.connect(lambda: self.stack.setCurrentIndex(2))
        self.register_panel.go_login.connect(lambda: self.stack.setCurrentIndex(0))
        self.register_panel.register_success.connect(self._on_register_success)
        self.forgot_panel.go_login.connect(lambda: self.stack.setCurrentIndex(0))

        def _adjust_stack_height(idx):
            for i in range(self.stack.count()):
                w = self.stack.widget(i)
                if i == idx:
                    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                else:
                    w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.stack.adjustSize()
            card.adjustSize()

        self.stack.currentChanged.connect(_adjust_stack_height)
        _adjust_stack_height(0)

        card_l.addWidget(self.stack)
        card_wrap.addWidget(card)
        right_outer.addLayout(card_wrap)
        right_outer.addStretch(1)
        right_l.addLayout(right_outer)
        root.addWidget(right, stretch=1)

    def _check_remembered(self):
        remembered = self.auth.get_remembered_user()
        if remembered:
            self.login_panel.prefill_username(remembered)

    def _on_login_success(self, user: dict):
        self.login_success.emit(user)
        self.close()

    def _on_register_success(self):
        self.stack.setCurrentIndex(0)