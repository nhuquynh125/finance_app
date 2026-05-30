# app/ui/main_window.py
"""
MainWindow — Finance AI.

Fix: blank-screen khi khởi động do _navigate("Dashboard") block main thread.

Thay đổi so với phiên bản cũ:
  - __init__ KHÔNG còn gọi _navigate("Dashboard") trực tiếp.
    Thay vào đó dùng QTimer.singleShot(0, ...) để trả quyền điều khiển
    về event-loop trước, cho phép cửa sổ paint lần đầu hoàn tất.
  - _navigate() KHÔNG còn gọi frame.refresh() ngay lập tức.
    Dùng QTimer.singleShot(50, ...) để refresh sau khi frame đã visible.
  - Thêm _LoadingPlaceholder làm placeholder trong khi frame nặng đang load.
<<<<<<< HEAD
  - Thêm trang "Chi tiêu" (SpendingFrame) vào sidebar và _create_page().
  - Không thay đổi bất kỳ logic nghiệp vụ nào khác.
=======
  - Không thay đổi bất kỳ logic nghiệp vụ nào.
>>>>>>> 0f9883f6111b8d064c73b5d2f2039834c7327128
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QFont, QPainter, QPainterPath, QBrush, QColor,
    QLinearGradient, QPixmap
)
from app.data.models import get_connection
from app.core.settings_manager import load_settings
from app.core.event_bus import bus
from app.ui.notification import notifier
from app.ui.command_palette import ShortcutManager
from datetime import datetime
from pathlib import Path
import os


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_logo_pixmap(size: int = 40) -> QPixmap | None:
    """Tìm logo trong thư mục project. Trả về None nếu không tìm thấy."""
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


# ── Sidebar components ────────────────────────────────────────────────────────

class SidebarButton(QPushButton):
    STYLE_ACTIVE = """
        QPushButton {
            background: rgba(255,255,255,0.18);
            color: #FFFFFF;
            border: none;
            border-left: 3px solid #E8921A;
            border-radius: 8px;
            text-align: left;
            padding: 9px 14px 9px 11px;
            font-size: 13px;
            font-weight: 600;
        }
    """
    STYLE_NORMAL = """
        QPushButton {
            background: transparent;
            color: rgba(255,255,255,0.75);
            border: none;
            border-radius: 8px;
            text-align: left;
            padding: 9px 14px;
            font-size: 13px;
        }
        QPushButton:hover {
            background: rgba(255,255,255,0.12);
            color: #FFFFFF;
        }
    """

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)

    def set_active(self, active: bool):
        self.setStyleSheet(self.STYLE_ACTIVE if active else self.STYLE_NORMAL)


class _SidebarAvatar(QPushButton):
    def __init__(self, initials: str, color: str, size: int = 34, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._size = size
        self._initials = initials.upper()[:2]
        self._color = color
        self._pixmap = None
        self._load_avatar()
        self.setStyleSheet("QPushButton { border:none; background:transparent; }")

    def _load_avatar(self):
        try:
            from user_session import session
            if not session.is_logged_in:
                return
            for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
                p = session.data_dir / f"avatar.{ext}"
                if p.exists():
                    raw = QPixmap(str(p))
                    if raw.isNull():
                        continue
                    s = self._size
                    raw = raw.scaled(
                        s, s,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    x = (raw.width() - s) // 2
                    y = (raw.height() - s) // 2
                    raw = raw.copy(x, y, s, s)
                    result = QPixmap(s, s)
                    result.fill(Qt.GlobalColor.transparent)
                    p2 = QPainter(result)
                    p2.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, s, s)
                    p2.setClipPath(path)
                    p2.drawPixmap(0, 0, raw)
                    p2.end()
                    self._pixmap = result
                    break
        except Exception:
            pass

    def refresh(self, initials: str, color: str):
        self._initials = initials.upper()[:2]
        self._color = color
        self._pixmap = None
        self._load_avatar()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self._size
        if self._pixmap and not self._pixmap.isNull():
            path = QPainterPath()
            path.addEllipse(0, 0, s, s)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#E8921A")))
            painter.drawEllipse(0, 0, s, s)
            painter.setPen(QColor("white"))
            font = QFont("Segoe UI", max(8, s // 3), QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(0, 0, s, s, Qt.AlignmentFlag.AlignCenter, self._initials)
        painter.end()


class Sidebar(QWidget):
    def __init__(self, current_user: dict = None, parent=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self.setFixedWidth(220)
        self.setStyleSheet("QWidget { background: transparent; }")
        self.setObjectName("sidebar")
        self._buttons: dict[str, SidebarButton] = {}
        self._on_navigate = None
        self._on_logout = None
        self._avatar_btn: _SidebarAvatar | None = None
        self._full_name_lbl: QLabel | None = None
        self._role_lbl: QLabel | None = None
        self._build()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#0B2A4A"))
        gradient.setColorAt(0.5, QColor("#0D3D5C"))
        gradient.setColorAt(1.0, QColor("#0A4F6E"))
        painter.fillRect(self.rect(), QBrush(gradient))

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo header
        logo_w = QWidget()
        logo_w.setStyleSheet("background: transparent;")
        logo_l = QHBoxLayout(logo_w)
        logo_l.setContentsMargins(16, 18, 16, 14)
        logo_l.setSpacing(10)
        logo_px = _get_logo_pixmap(36)
        if logo_px:
            logo_img = QLabel()
            logo_img.setPixmap(logo_px)
            logo_img.setFixedSize(36, 36)
            logo_img.setStyleSheet("border: none; background: transparent;")
            logo_l.addWidget(logo_img)
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("Finance AI")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        subtitle = QLabel(f"Tháng {datetime.now().strftime('%m/%Y')}")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet(
            "color: rgba(255,255,255,0.55); border: none; background: transparent;"
        )
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        logo_l.addLayout(title_col)
        logo_l.addStretch()
        layout.addWidget(logo_w)
        layout.addWidget(self._divider())

        # User info block
        if self.current_user:
            layout.addWidget(self._build_user_info_block(self.current_user))
        layout.addWidget(self._divider())

        # Navigation
        nav_area = QWidget()
        nav_area.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_area)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(2)

<<<<<<< HEAD
        # ── THÊM "Chi tiêu" vào section CHÍNH ────────────────────────────────
        sections = {
            "CHÍNH": ["Dashboard", "Chi tiêu", "Giao dịch", "Ngân sách"],
=======
        sections = {
            "CHÍNH": ["Dashboard", "Giao dịch", "Ngân sách"],
>>>>>>> 0f9883f6111b8d064c73b5d2f2039834c7327128
            "AI":    ["Dự báo", "Chatbot AI"],
            "NHÓM":  ["Gia đình"],
            "KHÁC":  ["Hồ sơ", "Báo cáo", "Cài đặt"],
        }
        icons = {
<<<<<<< HEAD
            "Dashboard":  "📊",
            "Chi tiêu":   "💸",   # ← icon mới cho trang Chi tiêu
            "Giao dịch":  "💳",
            "Ngân sách":  "💰",
            "Dự báo":     "📈",
            "Chatbot AI": "🤖",
            "Gia đình":   "👨\u200d👩\u200d👧",
            "Hồ sơ":      "👤",
            "Báo cáo":    "📄",
            "Cài đặt":    "⚙️",
=======
            "Dashboard":  "📊", "Giao dịch":  "💳", "Ngân sách": "💰",
            "Dự báo":     "📈", "Chatbot AI": "🤖", "Gia đình":  "👨‍👩‍👧",
            "Hồ sơ":      "👤", "Báo cáo":    "📄", "Cài đặt":   "⚙️",
>>>>>>> 0f9883f6111b8d064c73b5d2f2039834c7327128
        }
        for section_name, pages in sections.items():
            sec_lbl = QLabel(section_name)
            sec_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            sec_lbl.setStyleSheet(
                "color: rgba(255,255,255,0.4); padding: 10px 8px 4px; "
                "border: none; letter-spacing: 1.5px; background: transparent;"
            )
            nav_layout.addWidget(sec_lbl)
            for page in pages:
                icon = icons.get(page, "")
                btn = SidebarButton(f"  {icon}  {page}")
                btn.clicked.connect(lambda _, p=page: self._navigate(p))
                nav_layout.addWidget(btn)
                self._buttons[page] = btn
        nav_layout.addStretch()
        layout.addWidget(nav_area)

        # Footer
        layout.addWidget(self._divider())
        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(14, 10, 14, 16)
        fl.setSpacing(8)

        balance_card = QWidget()
        balance_card.setStyleSheet("""
            QWidget {
                background: rgba(255,255,255,0.08);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.12);
            }
        """)
        bcl = QVBoxLayout(balance_card)
        bcl.setContentsMargins(12, 8, 12, 8)
        bcl.setSpacing(3)
        fl_label = QLabel("Tổng số dư")
        fl_label.setFont(QFont("Segoe UI", 9))
        fl_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); border: none; background: transparent;"
        )
        self.balance_label = QLabel("...")
        self.balance_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.balance_label.setStyleSheet(
            "color: #7CE8C3; border: none; background: transparent;"
        )
        bcl.addWidget(fl_label)
        bcl.addWidget(self.balance_label)
        fl.addWidget(balance_card)

        btn_bell = QPushButton("🔔  Thông báo")
        btn_bell.setFixedHeight(32)
        btn_bell.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.75);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px; font-size: 12px; padding: 0 10px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); color: white; }
        """)
        btn_bell.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bell.clicked.connect(lambda: notifier.show_center(self.window()))
        fl.addWidget(btn_bell)

        btn_logout = QPushButton("⏻  Đăng xuất")
        btn_logout.setFixedHeight(32)
        btn_logout.setStyleSheet("""
            QPushButton {
                background: rgba(232, 80, 32, 0.15);
                color: #FF8B6A;
                border: 1px solid rgba(232, 80, 32, 0.3);
                border-radius: 8px; font-size: 12px; padding: 0 10px;
            }
            QPushButton:hover { background: rgba(232, 80, 32, 0.25); color: #FFAA8A; }
        """)
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._do_logout)
        fl.addWidget(btn_logout)
        layout.addWidget(footer)

    def _build_user_info_block(self, user: dict) -> QWidget:
        username  = user.get("username", "?")
        full_name = user.get("full_name", username)
        role      = user.get("role", "user")
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT color FROM user_profiles WHERE username=?", (username,)
            ).fetchone()
            conn.close()
            color = row["color"] if row and row["color"] else "#E8921A"
        except Exception:
            color = "#E8921A"

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        hl = QHBoxLayout(w)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(10)

        initials = (full_name[:2] if full_name else "?").upper()
        self._avatar_btn = _SidebarAvatar(initials, color, size=36)
        self._avatar_btn.clicked.connect(lambda: self._navigate("Hồ sơ"))
        hl.addWidget(self._avatar_btn)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(2)
        display = full_name[:16] if len(full_name) > 16 else full_name
        self._full_name_lbl = QLabel(display)
        self._full_name_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._full_name_lbl.setStyleSheet(
            "color: #FFFFFF; border: none; background: transparent;"
        )
        role_map = {"admin": "Quản trị viên", "user": "Người dùng"}
        self._role_lbl = QLabel(role_map.get(role, "Người dùng"))
        self._role_lbl.setFont(QFont("Segoe UI", 9))
        self._role_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.55); border: none; background: transparent;"
        )
        name_col.addWidget(self._full_name_lbl)
        name_col.addWidget(self._role_lbl)
        hl.addLayout(name_col)
        hl.addStretch()

        arrow = QLabel("›")
        arrow.setStyleSheet(
            "color: rgba(255,255,255,0.3); font-size:18px; border:none; background:transparent;"
        )
        hl.addWidget(arrow)
        w.mousePressEvent = lambda e: self._navigate("Hồ sơ")
        return w

    def _refresh_user_info(self, full_name: str, username: str, role: str):
        if self._full_name_lbl:
            display = full_name[:16] if len(full_name) > 16 else full_name
            self._full_name_lbl.setText(display)
        if self._role_lbl:
            role_map = {"admin": "Quản trị viên", "user": "Người dùng"}
            self._role_lbl.setText(role_map.get(role, "Người dùng"))
        if self._avatar_btn:
            initials = (full_name[:2] if full_name else "?").upper()
            self._avatar_btn.refresh(initials, "#E8921A")

    def set_navigate_callback(self, cb):
        self._on_navigate = cb

    def set_logout_callback(self, cb):
        self._on_logout = cb

    def _navigate(self, page: str):
        for name, btn in self._buttons.items():
            btn.set_active(name == page)
        if self._on_navigate:
            self._on_navigate(page)

    def _do_logout(self):
        if self._on_logout:
            self._on_logout()

    def set_active_page(self, page: str):
        for name, btn in self._buttons.items():
            btn.set_active(name == page)

    def refresh_balance(self):
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT COALESCE(SUM(balance),0) as total FROM accounts"
            ).fetchone()
            conn.close()
            self.balance_label.setText(f"{row['total']:,.0f} đ".replace(",", "."))
        except Exception:
            self.balance_label.setText("—")

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(
            "background: rgba(255,255,255,0.1); border: none; max-height: 1px;"
        )
        return line


# ── Loading placeholder ───────────────────────────────────────────────────────

class _LoadingPlaceholder(QWidget):
    """Widget hiển thị trong khi frame nặng đang được khởi tạo."""

    def __init__(self, page_name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #F0F6FF;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner = QLabel("⏳")
        spinner.setFont(QFont("Segoe UI Emoji", 32))
        spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner.setStyleSheet("border:none; background:transparent;")

        msg = QLabel(f"Đang tải {page_name}...")
        msg.setFont(QFont("Segoe UI", 13))
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("color: #8BAEC8; border:none; background:transparent;")

        layout.addWidget(spinner)
        layout.addSpacing(10)
        layout.addWidget(msg)


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, current_user: dict = None):
        super().__init__()
        self.current_user = current_user or {}
        self._pages: dict[str, QWidget] = {}
        self._current_page: str = ""

        self.setWindowTitle(
            f"Finance AI — "
            f"{self.current_user.get('full_name', self.current_user.get('username', ''))}"
        )
        self._apply_window_settings()
        self.setStyleSheet("QMainWindow { background: #F0F6FF; }")

        # Build skeleton layout (sidebar + stack) — không import frame nặng ở đây
        self._build()

        # Dùng singleShot(0) để nhường event-loop paint cửa sổ lần đầu,
        # sau đó mới bắt đầu load Dashboard.
<<<<<<< HEAD
=======
        # delay=0 ms đủ để Qt flush paint queue trước khi import matplotlib.
>>>>>>> 0f9883f6111b8d064c73b5d2f2039834c7327128
        QTimer.singleShot(0, lambda: self._navigate("Dashboard"))

    # ── Build skeleton ────────────────────────────────────────────────────────

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(current_user=self.current_user)
        self.sidebar.set_navigate_callback(self._navigate)
        self.sidebar.set_logout_callback(self._logout)
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: #F0F6FF;")
        root.addWidget(self.stack)

        # Bus signals
        bus.navigate_to.connect(self._navigate)
        bus.balance_changed.connect(self.sidebar.refresh_balance)
        bus.profile_updated.connect(self._on_profile_updated)

        # Shortcuts và notifications
        self.shortcut_mgr = ShortcutManager(self)
        self.shortcut_mgr.setup()
        notifier.set_parent(self)
        bus.notify_success.connect(notifier.success)
        bus.notify_warning.connect(notifier.warning)
        bus.notify_error.connect(notifier.error)
        bus.notify_info.connect(notifier.info)

        # Load balance sau khi layout ổn định
        QTimer.singleShot(100, self.sidebar.refresh_balance)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, page: str):
        """
        Điều hướng đến trang cho trước.

        Nếu frame đã tồn tại → chuyển thẳng, refresh sau 50ms.
        Nếu frame chưa có:
          1. Hiện loading placeholder ngay lập tức (tránh blank screen).
          2. Tạo frame thực sự sau 10ms (sau khi placeholder đã paint).
          3. Thay placeholder bằng frame thực.
          4. Gọi frame.refresh() sau thêm 50ms (frame đã visible).
        """
        if page in self._pages:
            self.stack.setCurrentWidget(self._pages[page])
            self.sidebar.set_active_page(page)
            self._current_page = page
            frame = self._pages[page]
            if hasattr(frame, "refresh"):
                QTimer.singleShot(50, frame.refresh)
            return

        # Hiện placeholder ngay để tránh blank screen
        placeholder = _LoadingPlaceholder(page)
        self.stack.addWidget(placeholder)
        self.stack.setCurrentWidget(placeholder)
        self.sidebar.set_active_page(page)
        self._current_page = page

        # Tạo frame thực sự sau 10ms (sau khi placeholder đã paint)
        def _do_create():
            widget = self._create_page(page)
            if widget is None:
                self.stack.removeWidget(placeholder)
                placeholder.deleteLater()
                return
            self._pages[page] = widget
            self.stack.addWidget(widget)
            self.stack.setCurrentWidget(widget)
            self.stack.removeWidget(placeholder)
            placeholder.deleteLater()
            # Refresh sau khi widget đã visible
            if hasattr(widget, "refresh"):
                QTimer.singleShot(50, widget.refresh)

        QTimer.singleShot(10, _do_create)

    def _create_page(self, page: str) -> QWidget | None:
        """Factory tạo frame theo tên trang. Import lazy để tránh block startup."""
        if page == "Dashboard":
            from app.ui.dashboard_frame import DashboardFrame
            return DashboardFrame(main_window=self)
<<<<<<< HEAD
        # ── TRANG MỚI: Chi tiêu ───────────────────────────────────────────────
        if page == "Chi tiêu":
            from app.ui.spending_frame import SpendingFrame
            return SpendingFrame(main_window=self)
        # ─────────────────────────────────────────────────────────────────────
=======
>>>>>>> 0f9883f6111b8d064c73b5d2f2039834c7327128
        if page == "Giao dịch":
            from app.ui.transaction_frame import TransactionFrame
            return TransactionFrame(main_window=self)
        if page == "Ngân sách":
            from app.ui.budget_frame import BudgetFrame
            return BudgetFrame(main_window=self)
        if page == "Dự báo":
            from app.ui.forecast_frame import ForecastFrame
            return ForecastFrame(main_window=self)
        if page == "Chatbot AI":
            from app.ui.chatbot_frame import ChatbotFrame
            return ChatbotFrame(main_window=self)
        if page == "Gia đình":
            from app.ui.family_frame import FamilyFrame
            return FamilyFrame(main_window=self)
        if page == "Hồ sơ":
            from app.ui.profile_frame import ProfileFrame
            return ProfileFrame(main_window=self)
        if page == "Báo cáo":
            from app.ui.report_frame import ReportFrame
            return ReportFrame(main_window=self)
        if page == "Cài đặt":
            from app.ui.settings_frame import SettingsFrame
            return SettingsFrame(main_window=self)
        # Trang chưa implement
        placeholder = QWidget()
        lbl = QLabel(f"Trang '{page}' — đang phát triển")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#999; font-size:14px;")
        from PyQt6.QtWidgets import QVBoxLayout as VBL
        VBL(placeholder).addWidget(lbl)
        return placeholder

    # ── Logout ────────────────────────────────────────────────────────────────

    def _logout(self):
        reply = QMessageBox.question(
            self, "Xác nhận đăng xuất",
            "Bạn có chắc muốn đăng xuất không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        username = self.current_user.get("username")
        try:
            from app.ai.classifier import TransactionClassifier
            TransactionClassifier.reset_for_user(username)
        except Exception:
            pass

        from app.data.auth_manager import AuthManager
        AuthManager().logout()

        from app.ui.login_window import LoginWindow
        self._login_window = LoginWindow()
        self._login_window.login_success.connect(self._reopen_main)
        self._login_window.show()
        self.close()

    def _reopen_main(self, user: dict):
        new_window = MainWindow(current_user=user)
        new_window.show()
        self._new_window = new_window  # giữ reference

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_profile_updated(self, username: str):
        try:
            from user_session import session
            if session.is_logged_in:
                self.setWindowTitle(f"Finance AI — {session.full_name}")
                self.sidebar._refresh_user_info(
                    session.full_name, session.username, session.role)
        except Exception:
            pass

    def refresh_all(self):
        """Refresh toàn bộ: settings, balance, và frame đang hiển thị."""
        self._apply_window_settings()
        self.sidebar.refresh_balance()
        frame = self._pages.get(self._current_page)
        if frame and hasattr(frame, "refresh"):
            frame.refresh()

    # ── Window settings ───────────────────────────────────────────────────────

    def _apply_window_settings(self):
        settings = load_settings()
        mode = settings.get("window_mode", "default")
        self.showNormal()
        if mode == "fullscreen":
            self.showFullScreen()
        elif mode == "large":
            self.resize(1366, 768)
            screen = self.screen().availableGeometry()
            self.move(
                (screen.width() - 1366) // 2,
                (screen.height() - 768) // 2,
            )
        else:
            self.resize(1150, 700)
            screen = self.screen().availableGeometry()
            self.move(
                (screen.width() - 1150) // 2,
                (screen.height() - 700) // 2,
            )
        self.setMinimumSize(900, 580)
