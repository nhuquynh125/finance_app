# app/ui/profile_frame.py
"""
Trang Hồ sơ cá nhân (Profile) — trang riêng, không nằm trong Settings.

Tính năng:
  - Xem / sửa thông tin cá nhân (họ tên, bio, màu avatar)
  - Upload ảnh đại diện (PNG/JPG/GIF → lưu vào data/users/{username}/avatar.*)
  - Thống kê nhanh: tổng giao dịch, số dư, danh mục, mục tiêu
  - Đổi mật khẩu inline
  - Bus signal: cập nhật Sidebar ngay khi lưu tên/avatar

Changes vs previous version:
  - Typography: increased font sizes and darkened label colours throughout
    "Thông tin cá nhân" and "Bảo mật" form sections for legibility.
  - User identity block (name / handle / role badge): scaled up.
  - Avatar action buttons and hint text: scaled up.
  - Section group titles "Thông tin cá nhân" and "Bảo mật": scaled up.
  - StatCard label + value fonts: scaled up.
  - "Thông tin phiên" (Session Info) section: COMPLETELY REMOVED — no widget,
    no layout method, no backend path-resolution logic remains.
"""

from __future__ import annotations

import hashlib
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter, QPainterPath, QBrush
from PyQt6.QtWidgets import ( QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, 
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QGridLayout, QDialog,
    QFormLayout, QFileDialog, QMessageBox, QTextEdit,
    QSizePolicy, QSpacerItem, QProgressBar, QStackedWidget
)

from app.data.models import get_connection
from app.core.event_bus import bus


# ── Avatar sizes ──────────────────────────────────────────────────────────────
AVATAR_SIZE  = 96   # px — displayed size on profile page
SIDEBAR_SIZE = 32   # px — in sidebar
AVATAR_FNAME = "avatar"   # will be avatar.png / avatar.jpg etc.

ACCENT_COLORS = [
    ("#378ADD", "Xanh dương"),
    ("#1D9E75", "Xanh lá"),
    ("#E24B4A", "Đỏ"),
    ("#BA7517", "Cam"),
    ("#7F77DD", "Tím"),
    ("#D4537E", "Hồng"),
    ("#639922", "Xanh olive"),
    ("#0C447C", "Xanh navy"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_avatar_path() -> Optional[Path]:
    """Tìm file avatar hiện tại của user (bất kỳ đuôi ảnh nào)."""
    try:
        from user_session import session
        if not session.is_logged_in:
            return None
        base = session.data_dir
        for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
            p = base / f"{AVATAR_FNAME}.{ext}"
            if p.exists():
                return p
    except Exception:
        pass
    return None


def _save_avatar(src_path: str) -> Optional[Path]:
    """Copy ảnh đã chọn vào thư mục user, trả về path mới."""
    try:
        from user_session import session
        if not session.is_logged_in:
            return None
        ext = Path(src_path).suffix.lower().lstrip(".")
        if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
            return None
        dst = session.data_dir / f"{AVATAR_FNAME}.{ext}"
        for old in session.data_dir.glob(f"{AVATAR_FNAME}.*"):
            try:
                old.unlink()
            except Exception:
                pass
        shutil.copy2(src_path, dst)
        return dst
    except Exception:
        return None


def _make_round_pixmap(path: str, size: int) -> QPixmap:
    """Tạo pixmap tròn từ file ảnh."""
    raw = QPixmap(path)
    if raw.isNull():
        return QPixmap()
    raw = raw.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    x = (raw.width()  - size) // 2
    y = (raw.height() - size) // 2
    raw = raw.copy(x, y, size, size)

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path_obj = QPainterPath()
    path_obj.addEllipse(0, 0, size, size)
    painter.setClipPath(path_obj)
    painter.drawPixmap(0, 0, raw)
    painter.end()
    return result


def _get_user_color() -> str:
    try:
        conn = get_connection()
        from user_session import session
        row = conn.execute(
            "SELECT color FROM user_profiles WHERE username=?",
            (session.username,)
        ).fetchone()
        conn.close()
        if row and row["color"]:
            return row["color"]
    except Exception:
        pass
    return "#378ADD"


def _save_user_color(color: str):
    try:
        conn = get_connection()
        from user_session import session
        conn.execute("""
            INSERT INTO user_profiles (username, color, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET color=excluded.color
        """, (session.username, color, session.full_name))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _get_user_bio() -> str:
    try:
        conn = get_connection()
        from user_session import session
        row = conn.execute(
            "SELECT bio FROM user_profiles WHERE username=?",
            (session.username,)
        ).fetchone()
        conn.close()
        return row["bio"] if row and "bio" in row.keys() else ""
    except Exception:
        return ""


def _save_user_bio(bio: str):
    try:
        conn = get_connection()
        from user_session import session
        try:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN bio TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass
        conn.execute("""
            INSERT INTO user_profiles (username, bio, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET bio=excluded.bio
        """, (session.username, bio, session.full_name))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Avatar Widget ─────────────────────────────────────────────────────────────

class AvatarWidget(QWidget):
    """
    Widget avatar tròn.
    - Hiển thị ảnh từ file nếu có, không thì chữ cái đầu với màu accent.
    - Click → mở dialog chọn ảnh.
    - Emit avatar_changed khi ảnh mới được lưu.
    """
    avatar_changed = pyqtSignal(str)  # emits new avatar path

    def __init__(self, size: int = AVATAR_SIZE, clickable: bool = True, parent=None):
        super().__init__(parent)
        self._size       = size
        self._clickable  = clickable
        self._color      = "#378ADD"
        self._initials   = "?"
        self._pixmap: Optional[QPixmap] = None

        self.setFixedSize(size + 8, size + 8)
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Nhấp để thay đổi ảnh đại diện")

    def set_user(self, initials: str, color: str):
        self._initials = initials.upper()[:2]
        self._color    = color
        self._pixmap   = None
        path = _get_avatar_path()
        if path:
            px = _make_round_pixmap(str(path), self._size)
            if not px.isNull():
                self._pixmap = px
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width()  // 2
        cy = self.height() // 2
        r  = self._size    // 2

        ring_color = QColor(self._color)
        ring_color.setAlpha(80)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(ring_color))
        painter.drawEllipse(cx - r - 3, cy - r - 3, (r + 3) * 2, (r + 3) * 2)

        if self._pixmap and not self._pixmap.isNull():
            path_obj = QPainterPath()
            path_obj.addEllipse(cx - r, cy - r, r * 2, r * 2)
            painter.setClipPath(path_obj)
            painter.drawPixmap(cx - r, cy - r, self._pixmap)
            painter.setClipping(False)
        else:
            painter.setBrush(QBrush(QColor(self._color)))
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            painter.setPen(QColor("white"))
            font = QFont("Segoe UI", max(10, r // 2), QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(cx - r, cy - r, r * 2, r * 2,
                             Qt.AlignmentFlag.AlignCenter, self._initials)

        if self._clickable:
            icon_r = max(12, r // 3)
            ix = cx + r - icon_r
            iy = cy + r - icon_r
            painter.setClipping(False)
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QColor(self._color))
            painter.drawEllipse(ix - icon_r // 2, iy - icon_r // 2,
                                icon_r, icon_r)
            painter.setPen(QColor(self._color))
            font2 = QFont("Segoe UI Emoji", max(6, icon_r // 2 - 1))
            painter.setFont(font2)
            painter.drawText(ix - icon_r // 2, iy - icon_r // 2,
                             icon_r, icon_r,
                             Qt.AlignmentFlag.AlignCenter, "📷")

        painter.end()

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self._pick_image()

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh đại diện", "",
            "Ảnh (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if not path:
            return
        saved = _save_avatar(path)
        if saved:
            px = _make_round_pixmap(str(saved), self._size)
            if not px.isNull():
                self._pixmap = px
                self.update()
                self.avatar_changed.emit(str(saved))
                bus.notify_success.emit("Ảnh đại diện", "Đã cập nhật ảnh đại diện!")
        else:
            bus.notify_error.emit("Lỗi", "Không thể lưu ảnh. Kiểm tra định dạng file.")

    def remove_avatar(self):
        """Xóa ảnh, trở về chữ cái đầu."""
        try:
            from user_session import session
            for f in session.data_dir.glob(f"{AVATAR_FNAME}.*"):
                f.unlink()
        except Exception:
            pass
        self._pixmap = None
        self.update()
        bus.notify_info.emit("Ảnh đại diện", "Đã xóa ảnh đại diện")


# ── Stat card ─────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    """
    KPI card used in the summary stats bar.
    Font sizes scaled up for better readability.
    """
    def __init__(self, icon: str, label: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 22))   # was 21
        icon_lbl.setStyleSheet("border:none; background:transparent;")
        top.addWidget(icon_lbl)
        top.addStretch()
        # Label text: darkened colour + larger font
        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 15))               # was 14
        lbl.setStyleSheet("color:#0B2A4A; border:none;") # was #aaa
        top.addWidget(lbl)
        layout.addLayout(top)

        # Value text: larger font
        self.val_lbl = QLabel(value)
        self.val_lbl.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))  # was 23
        self.val_lbl.setStyleSheet(f"color:{color}; border:none;")
        layout.addWidget(self.val_lbl)

    def set_value(self, value: str):
        self.val_lbl.setText(value)


# ══════════════════════════════════════════════════════════════════════════════
# ── Main ProfileFrame ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class ProfileFrame(QWidget):
    """
    Trang Hồ sơ cá nhân độc lập.
    Thêm vào MainWindow như một page bình thường.
    """

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._color      = "#378ADD"
        self._build()
        QTimer.singleShot(150, self.refresh)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f5f5f5; }")

        content = QWidget()
        content.setStyleSheet("background:#f5f5f5;")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(24, 20, 24, 24)
        self.body.setSpacing(16)

        self._build_hero()
        self._build_stats_row()
        self._build_info_card()
        self._build_security_card()
        self._build_admin_card()
        self._build_danger_zone()
        # NOTE: "Thông tin phiên" section intentionally not built — removed.
        self.body.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Page title: darkened colour + larger font
        title = QLabel("Hồ sơ cá nhân")
        title.setFont(QFont("Segoe UI", 21, QFont.Weight.Bold))  # was 19
        title.setStyleSheet("color:#0B2A4A;")                    # was default (faint)
        layout.addWidget(title)
        layout.addStretch()

        self.btn_save_all = QPushButton("💾  Lưu thay đổi")
        self.btn_save_all.setStyleSheet(self._btn_primary())
        self.btn_save_all.clicked.connect(self._save_all)
        layout.addWidget(self.btn_save_all)
        return bar

    # ── Hero (avatar + tên + màu) ─────────────────────────────────────────────

    def _build_hero(self):
        hero = QFrame()
        hero.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:14px; }")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(24, 20, 24, 20)
        hl.setSpacing(14)

        row = QHBoxLayout()
        row.setSpacing(20)

        # Avatar
        self.avatar_w = AvatarWidget(size=AVATAR_SIZE, clickable=True)
        self.avatar_w.avatar_changed.connect(self._on_avatar_changed)
        row.addWidget(self.avatar_w)

        # Info column — all fonts scaled up
        info = QVBoxLayout()
        info.setSpacing(6)

        self.lbl_display_name = QLabel("—")
        self.lbl_display_name.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))  # was 25
        self.lbl_display_name.setStyleSheet("color:#1A2B45; border:none;")
        info.addWidget(self.lbl_display_name)

        self.lbl_username_at = QLabel("@—")
        self.lbl_username_at.setStyleSheet(
            "color:#0B2A4A; font-size:20px; border:none;")  # was #8FA8C4 / 18px
        info.addWidget(self.lbl_username_at)

        self.lbl_role_badge = QLabel("—")
        self.lbl_role_badge.setStyleSheet(
            "QLabel { background:#EAF3DE; color:#3B6D11; border:none; "
            "border-radius:10px; padding:3px 12px; font-size:18px; max-width:140px; }"
        )  # font-size was 16px
        info.addWidget(self.lbl_role_badge)
        info.addStretch()
        row.addLayout(info, stretch=1)

        # Right: avatar actions — fonts scaled up
        avatar_actions = QVBoxLayout()
        avatar_actions.setSpacing(6)
        avatar_actions.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn_upload = QPushButton("📷  Tải ảnh lên")
        btn_upload.setFixedWidth(150)
        btn_upload.setStyleSheet(self._btn_normal_large())  # larger style
        btn_upload.clicked.connect(self.avatar_w._pick_image)
        avatar_actions.addWidget(btn_upload)

        self.btn_remove_avatar = QPushButton("🗑  Xóa ảnh")
        self.btn_remove_avatar.setFixedWidth(150)
        self.btn_remove_avatar.setStyleSheet(self._btn_danger_large())  # larger style
        self.btn_remove_avatar.clicked.connect(self._remove_avatar)
        avatar_actions.addWidget(self.btn_remove_avatar)

        # Format hint text: larger + darker
        hint = QLabel("PNG, JPG, GIF · tối đa 5MB")
        hint.setStyleSheet(
            "color:#4A6785; font-size:15px; border:none;")  # was #bbb / 15px
        avatar_actions.addWidget(hint)
        row.addLayout(avatar_actions)

        hl.addLayout(row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#f0f0f0; border:none; max-height:1px;")
        hl.addWidget(div)

        self.body.addWidget(hero)

    # ── Stats row ─────────────────────────────────────────────────────────────

    def _build_stats_row(self):
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        rl = QGridLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        self.stat_balance   = StatCard("💰", "Số dư tổng",  "—",  "#1D9E75")
        self.stat_tx        = StatCard("📋", "Giao dịch",   "—",  "#378ADD")
        self.stat_cats      = StatCard("🏷", "Danh mục",    "—",  "#BA7517")
        self.stat_goals     = StatCard("🎯", "Mục tiêu",    "—",  "#7F77DD")

        for i, card in enumerate([
            self.stat_balance, self.stat_tx,
            self.stat_cats,    self.stat_goals
        ]):
            rl.addWidget(card, 0, i)

        self.body.addWidget(row)

    # ── Info card ─────────────────────────────────────────────────────────────

    def _build_info_card(self):
        panel = self._panel("✏️  Thông tin cá nhân")
        pl = panel.layout()

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.le_fullname = QLineEdit()
        self.le_fullname.setPlaceholderText("Họ và tên đầy đủ...")
        self.le_fullname.setStyleSheet(self._input_style())
        form.addRow(self._form_label("Họ và tên:"), self.le_fullname)

        self.le_phone = QLineEdit()
        self.le_phone.setPlaceholderText("0912 345 678 (bắt buộc, dùng làm mã định danh)")
        self.le_phone.setStyleSheet(self._input_style())
        form.addRow(self._form_label("Số điện thoại:"), self.le_phone)

        self.le_username_ro = QLineEdit()
        self.le_username_ro.setReadOnly(True)
        self.le_username_ro.setStyleSheet(
            self._input_style() + " background:#f7f7f7; color:#888;")
        form.addRow(self._form_label("Tên đăng nhập:"), self.le_username_ro)

        self.te_bio = QTextEdit()
        self.te_bio.setFixedHeight(72)
        self.te_bio.setPlaceholderText(
            "Giới thiệu ngắn về bản thân... VD: Kỹ sư phần mềm tại Hà Nội 🏙")
        self.te_bio.setStyleSheet(
            "QTextEdit { border:1px solid #ddd; border-radius:6px; "
            "padding:8px; font-size:17px; background:#fff; color:#222; }")
        form.addRow(self._form_label("Giới thiệu:"), self.te_bio)

        pl.addLayout(form)
        self.body.addWidget(panel)

    # ── Security card ─────────────────────────────────────────────────────────

    def _build_security_card(self):
        panel = self._panel("🔒  Bảo mật")
        pl = panel.layout()

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.le_old_pw = QLineEdit()
        self.le_old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_old_pw.setPlaceholderText("Mật khẩu hiện tại...")
        self.le_old_pw.setStyleSheet(self._input_style())
        form.addRow(self._form_label("Mật khẩu cũ:"), self.le_old_pw)

        self.le_new_pw = QLineEdit()
        self.le_new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_new_pw.setPlaceholderText("Tối thiểu 6 ký tự...")
        self.le_new_pw.setStyleSheet(self._input_style())
        self.le_new_pw.textChanged.connect(self._update_pw_strength)
        form.addRow(self._form_label("Mật khẩu mới:"), self.le_new_pw)

        self.le_confirm_pw = QLineEdit()
        self.le_confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_confirm_pw.setPlaceholderText("Nhập lại mật khẩu mới...")
        self.le_confirm_pw.setStyleSheet(self._input_style())
        form.addRow(self._form_label("Xác nhận:"), self.le_confirm_pw)

        # Password strength bar
        self.pw_strength_bar = QProgressBar()
        self.pw_strength_bar.setRange(0, 4)
        self.pw_strength_bar.setValue(0)
        self.pw_strength_bar.setFixedHeight(5)
        self.pw_strength_bar.setTextVisible(False)
        self.pw_strength_bar.setStyleSheet(
            "QProgressBar { background:#f0f0f0; border:none; border-radius:3px; } "
            "QProgressBar::chunk { background:#E24B4A; border-radius:3px; }")
        self.pw_strength_lbl = QLabel("")
        self.pw_strength_lbl.setStyleSheet(
            "color:#0B2A4A; font-size:16px; border:none;")  # was #aaa

        strength_w = QWidget()
        strength_w.setStyleSheet("background:transparent;")
        sw = QVBoxLayout(strength_w)
        sw.setContentsMargins(0, 0, 0, 0)
        sw.setSpacing(2)
        sw.addWidget(self.pw_strength_bar)
        sw.addWidget(self.pw_strength_lbl)
        form.addRow(self._form_label("Độ mạnh:"), strength_w)

        pl.addLayout(form)

        self.pw_msg = QLabel("")
        self.pw_msg.setWordWrap(True)
        self.pw_msg.hide()
        pl.addWidget(self.pw_msg)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_change_pw = QPushButton("🔑  Đổi mật khẩu")
        btn_change_pw.setStyleSheet(self._btn_normal())
        btn_change_pw.clicked.connect(self._change_password)
        btn_row.addWidget(btn_change_pw)
        pl.addLayout(btn_row)
        self.body.addWidget(panel)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        try:
            from user_session import session
            if not session.is_logged_in:
                return

            self._color = _get_user_color()
            initials    = (session.full_name or session.username)[:2].upper()
            self.avatar_w.set_user(initials, self._color)

            self.lbl_display_name.setText(session.full_name or session.username)
            self.lbl_username_at.setText(f"@{session.username}")
            role_map = {"admin": "Quản trị viên", "user": "Người dùng"}
            self.lbl_role_badge.setText(role_map.get(session.role, session.role))

            self.le_fullname.setText(session.full_name or "")
            self.le_username_ro.setText(session.username)

            try:
                import sqlite3 as _sq
                _c = _sq.connect(str(session.auth_db_path))
                _c.row_factory = _sq.Row
                _row = _c.execute(
                    "SELECT phone FROM users WHERE username=?",
                    (session.username,)
                ).fetchone()
                _c.close()
                self.le_phone.setText(_row["phone"] if _row and _row["phone"] else "")
            except Exception:
                self.le_phone.setText("")

            self.te_bio.setPlainText(_get_user_bio())

            self._load_stats()

            has_avatar = _get_avatar_path() is not None
            self.btn_remove_avatar.setVisible(has_avatar)
            if session.role == "admin":
                self.admin_panel.show()
                self._load_user_table()
            else:
                self.admin_panel.hide()


        except Exception as e:
            print(f"[ProfileFrame] refresh error: {e}")

    def _load_stats(self):
        try:
            conn = get_connection()
            balance = conn.execute(
                "SELECT COALESCE(SUM(balance),0) as t FROM accounts"
            ).fetchone()["t"]
            tx_count = conn.execute(
                "SELECT COUNT(*) as n FROM transactions"
            ).fetchone()["n"]
            cat_count = conn.execute(
                "SELECT COUNT(*) as n FROM categories"
            ).fetchone()["n"]
            goal_count = conn.execute(
                "SELECT COUNT(*) as n FROM savings_goals"
            ).fetchone()["n"]
            conn.close()

            self.stat_balance.set_value(f"{balance:,.0f} đ".replace(",", "."))
            self.stat_tx.set_value(str(tx_count))
            self.stat_cats.set_value(str(cat_count))
            self.stat_goals.set_value(str(goal_count))
        except Exception:
            pass


    @staticmethod
    def _msg_box(title: str, msg: str, kind: str):
        box = QMessageBox()
        box.setWindowTitle(title)
        box.setText(msg)
        if kind == "critical":
            box.setIcon(QMessageBox.Icon.Critical)
        elif kind == "warning":
            box.setIcon(QMessageBox.Icon.Warning)
        else:
            box.setIcon(QMessageBox.Icon.Information)
        box.exec()

    def _build_admin_card(self):
        """Panel chi hien voi admin -- quan ly danh sach user."""
        self.admin_panel = self._panel("Quản lý người dùng (Admin)")

        pl = self.admin_panel.layout()

        header_row = QHBoxLayout()
        desc = QLabel("Xem và quản lý toàn bộ tài khoản trong hệ thống.")
        desc.setFont(QFont("Segoe UI", 16))
        desc.setStyleSheet("color:#4A6785; border:none;")
        header_row.addWidget(desc)
        header_row.addStretch()
        btn_add_user = QPushButton("Thêm user")
        btn_add_user.setStyleSheet(self._btn_primary())
        btn_add_user.clicked.connect(self._open_add_user_dialog)
        header_row.addWidget(btn_add_user)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(72)
        btn_refresh.setStyleSheet(self._btn_normal())
        btn_refresh.clicked.connect(self._load_user_table)
        header_row.addWidget(btn_refresh)
        pl.addLayout(header_row)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(7)
        self.user_table.setHorizontalHeaderLabels(
            ["Username", "Họ tên", "SĐT", "Vai trò", "Trạng thái", "Đăng nhập cuối", ""])
        self.user_table.setStyleSheet("""
            QTableWidget {
                background:#fff; border:1px solid #e8e8e8;
                border-radius:8px; gridline-color:#f0f0f0; font-size:16px;
            }
            QTableWidget::item { padding:6px 10px; color:#0B2A4A; }
            QTableWidget::item:selected { background:#E6F1FB; color:#0B2A4A; }
            QHeaderView::section {
                background:#f7f7f7; color:#4A6785;
                font-size:14px; font-weight:bold;
                border:none; border-bottom:1px solid #e8e8e8;
                padding:5px 10px;
            }
        """)
        self.user_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.user_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.user_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.setFixedHeight(220)
        pl.addWidget(self.user_table)

        self.body.addWidget(self.admin_panel)
        self.admin_panel.hide()

    def _build_danger_zone(self):
        panel = self._panel("Vùng nguy hiểm")
        panel.setStyleSheet(
            "QFrame { background:#fff8f8; border:1px solid #fcc; border-radius:10px; }")
        pl = panel.layout()

        row = QHBoxLayout()
        col = QVBoxLayout()

        # Larger, bolder "Xóa tài khoản" title
        title = QLabel("Xóa tài khoản")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color:#A32D2D; border:none;")

        desc = QLabel(
            "Xóa vĩnh viễn tài khoản và toàn bộ dữ liệu tài chính.\n"
            "Hành động này KHÔNG THỂ hoàn tác.")
        desc.setFont(QFont("Segoe UI", 15))
        desc.setStyleSheet("color:#666; border:none;")
        desc.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(desc)
        row.addLayout(col)
        row.addStretch()

        btn_delete = QPushButton("Xóa tài khoản")
        btn_delete.setStyleSheet(self._btn_danger())
        btn_delete.clicked.connect(self._delete_own_account)
        row.addWidget(btn_delete)
        pl.addLayout(row)

        self.body.addWidget(panel)

    def _load_user_table(self):
        try:
            conn = self._auth_conn()
            rows = conn.execute(
                "SELECT id, username, full_name, phone, role, is_active, last_login "
                "FROM users ORDER BY id"
            ).fetchall()
            conn.close()

            self.user_table.setRowCount(0)
            from user_session import session as _sess
            current_username = _sess.username if _sess.is_logged_in else ""

            for row in rows:
                r = self.user_table.rowCount()
                self.user_table.insertRow(r)

                self._tbl_item(r, 0, row["username"])
                self._tbl_item(r, 1, row["full_name"] or "")
                self._tbl_item(r, 2, row["phone"] or "--", "#4A6785")
                role_map = {"admin": "Quản trị viên", "user": "Người dùng"}
                self._tbl_item(r, 3, role_map.get(row["role"], row["role"]))

                status_item = QTableWidgetItem(
                    "Hoạt động" if row["is_active"] else "Khóa")
                status_item.setForeground(
                    QColor("#1D9E75") if row["is_active"] else QColor("#E24B4A"))
                self.user_table.setItem(r, 4, status_item)

                ll = (row["last_login"] or "Chưa đăng nhập")[:16]
                self._tbl_item(r, 5, ll, "#4A6785")

                if row["username"] != current_username:
                    btn_w = QWidget()
                    btn_l = QHBoxLayout(btn_w)
                    btn_l.setContentsMargins(4, 2, 4, 2)
                    btn_l.setSpacing(4)

                    btn_edit = QPushButton("Sửa")
                    btn_edit.setFixedSize(44, 24)
                    btn_edit.setStyleSheet(
                        "QPushButton { background:#E6F1FB; color:#0B2A4A; "
                        "border:none; border-radius:4px; font-size:14px; } "
                        "QPushButton:hover { background:#B5D4F4; }")
                    btn_edit.clicked.connect(
                        lambda _, u=dict(row): self._open_edit_user_dialog(u))

                    btn_toggle = QPushButton(
                        "Khóa" if row["is_active"] else "Mở")
                    btn_toggle.setFixedSize(44, 24)
                    btn_toggle.setStyleSheet(
                        "QPushButton { background:#FAEEDA; color:#633806; "
                        "border:none; border-radius:4px; font-size:14px; } "
                        "QPushButton:hover { background:#f5d5a0; }")
                    btn_toggle.clicked.connect(
                        lambda _, uid=row["id"], cur=bool(row["is_active"]):
                            self._toggle_user_active(uid, cur))

                    btn_del = QPushButton("Xóa")
                    btn_del.setFixedSize(44, 24)
                    btn_del.setStyleSheet(
                        "QPushButton { background:#FCEBEB; color:#A32D2D; "
                        "border:none; border-radius:4px; font-size:14px; } "
                        "QPushButton:hover { background:#f5c6cb; }")
                    btn_del.clicked.connect(
                        lambda _, uname=row["username"]:
                            self._delete_user(uname))

                    btn_l.addWidget(btn_edit)
                    btn_l.addWidget(btn_toggle)
                    btn_l.addWidget(btn_del)
                    self.user_table.setCellWidget(r, 6, btn_w)
                else:
                    me = QLabel("(bạn)")
                    me.setStyleSheet("color:#aaa; font-size:15px; padding:0 6px;")
                    self.user_table.setCellWidget(r, 6, me)

            self.user_table.resizeRowsToContents()
        except Exception as e:
            print(f"[UserProfileTab] _load_user_table error: {e}")

    # -- Admin actions --

    def _open_add_user_dialog(self):
        dialog = _AddUserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_user_table()

    def _open_edit_user_dialog(self, user: dict):
        dialog = _EditUserDialog(user, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_user_table()

    def _toggle_user_active(self, user_id: int, current_active: bool):
        action = "khóa" if current_active else "mở khóa"
        reply = QMessageBox.question(
            self, "Xác nhận",
            f"Bạn muốn {action} tài khoản này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            conn = self._auth_conn()
            conn.execute(
                "UPDATE users SET is_active=? WHERE id=?",
                (0 if current_active else 1, user_id)
            )
            conn.commit()
            conn.close()
            self._load_user_table()
        except Exception as e:
            self._msg_box("Lỗi", str(e), "critical")

    def _delete_user(self, username: str):
        reply = QMessageBox.warning(
            self, "Xóa tài khoản",
            f"Xóa tài khoản '@{username}'?\n\n"
            "Dữ liệu tài chính trong thư mục của user vẫn còn trên ổ đĩa.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            conn = self._auth_conn()
            conn.execute("DELETE FROM users WHERE username=?", (username,))
            conn.commit()
            conn.close()
            self._load_user_table()
        except Exception as e:
            self._msg_box("Lỗi", str(e), "critical")

    def _delete_own_account(self):
        from user_session import session

        reply = QMessageBox.warning(
            self, "Xóa tài khoản",
            f"Bạn sắp xóa tài khoản '@{session.username}' và toàn bộ dữ liệu tài chính.\n\n"
            "Hành động này KHÔNG THỂ hoàn tác!\n\nBạn có chắc chắn?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pw_dialog = _ConfirmPasswordDialog(session.username, self)
        if pw_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            import shutil
            conn = self._auth_conn()
            conn.execute("DELETE FROM users WHERE username=?", (session.username,))
            conn.commit()
            conn.close()

            user_dir = session.data_dir
            if user_dir.exists():
                shutil.rmtree(str(user_dir), ignore_errors=True)

            QMessageBox.information(self, "Đã xóa", "Tài khoản đã được xóa. App sẽ đóng.")

            from app.data.auth_manager import AuthManager
            AuthManager().logout()

            from app.ui.login_window import LoginWindow
            self._login_window = LoginWindow()
            self._login_window.show()
            if self.main_window:
                self.main_window.close()

        except Exception as e:
            self._msg_box("Lỗi", str(e), "critical")

    @staticmethod
    def _auth_conn():
        import sqlite3
        from user_session import session
        path = session.auth_db_path
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    def _tbl_item(self, row, col, text, color="#0B2A4A"):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        self.user_table.setItem(row, col, item)


    # ── Actions ───────────────────────────────────────────────────────────────

    def _save_all(self):
        """Lưu họ tên + SĐT + bio + màu cùng lúc."""
        full_name = self.le_fullname.text().strip()
        phone_raw = self.le_phone.text().strip()

        if not full_name:
            bus.notify_error.emit("Lỗi", "Họ và tên không được để trống.")
            return

        if not phone_raw:
            bus.notify_error.emit("Lỗi", "Số điện thoại là định danh chính, không được để trống.")
            return
        from app.data.auth_manager import _validate_phone
        ok, result = _validate_phone(phone_raw)
        if not ok:
            bus.notify_error.emit("Lỗi SĐT", result)
            return
        phone_normalized = result

        try:
            from user_session import session
            import sqlite3

            if phone_normalized:
                _c = sqlite3.connect(str(session.auth_db_path))
                _c.row_factory = sqlite3.Row
                dup = _c.execute(
                    "SELECT username FROM users WHERE phone=? AND username!=?",
                    (phone_normalized, session.username)
                ).fetchone()
                _c.close()
                if dup:
                    bus.notify_error.emit(
                        "Lỗi SĐT",
                        "Số điện thoại này đã được dùng bởi tài khoản khác."
                    )
                    return

            conn = sqlite3.connect(str(session.auth_db_path))
            conn.execute(
                "UPDATE users SET full_name=?, phone=? WHERE username=?",
                (full_name, phone_normalized, session.username)
            )
            conn.commit()
            conn.close()

            bio = self.te_bio.toPlainText().strip()
            _save_user_bio(bio)
            _save_user_color(self._color)

            session._user["full_name"] = full_name

            self.lbl_display_name.setText(full_name)
            initials = full_name[:2].upper()
            self.avatar_w.set_user(initials, self._color)

            if self.main_window and hasattr(self.main_window, "sidebar"):
                self.main_window.setWindowTitle(f"Finance AI — {full_name}")
                self.main_window.sidebar._refresh_user_info(
                    full_name, session.username, session.role)

            bus.profile_updated.emit(session.username)
            bus.notify_success.emit("Đã lưu", "Thông tin hồ sơ đã được cập nhật!")

        except Exception as e:
            bus.notify_error.emit("Lỗi", str(e))

    def _on_avatar_changed(self, path: str):
        try:
            from user_session import session
            if self.main_window and hasattr(self.main_window, "sidebar"):
                self.main_window.sidebar._refresh_user_info(
                    session.full_name, session.username, session.role)
        except Exception:
            pass
        self.btn_remove_avatar.setVisible(True)

    def _remove_avatar(self):
        reply = QMessageBox.question(
            self, "Xóa ảnh", "Xóa ảnh đại diện và trở về chữ cái đầu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.avatar_w.remove_avatar()
            try:
                from user_session import session
                if self.main_window and hasattr(self.main_window, "sidebar"):
                    self.main_window.sidebar._refresh_user_info(
                        session.full_name, session.username, session.role)
            except Exception:
                pass
            self.btn_remove_avatar.setVisible(False)

    def _set_color(self, hex_color: str):
        self._color = hex_color
        try:
            from user_session import session
            initials = (session.full_name or session.username)[:2].upper()
            self.avatar_w.set_user(initials, hex_color)
        except Exception:
            pass

    def _update_pw_strength(self, pw: str):
        score = 0
        if len(pw) >= 6:   score += 1
        if len(pw) >= 10:  score += 1
        if any(c.isdigit() for c in pw):    score += 1
        if any(c in "!@#$%^&*()_+-=[]{}|" for c in pw): score += 1

        colors  = ["#E24B4A", "#E24B4A", "#BA7517", "#1D9E75", "#1D9E75"]
        labels  = ["", "Yếu", "Trung bình", "Mạnh", "Rất mạnh"]
        self.pw_strength_bar.setValue(score)
        self.pw_strength_bar.setStyleSheet(
            f"QProgressBar {{ background:#f0f0f0; border:none; border-radius:3px; }} "
            f"QProgressBar::chunk {{ background:{colors[score]}; border-radius:3px; }}")
        self.pw_strength_lbl.setText(labels[score] if pw else "")
        self.pw_strength_lbl.setStyleSheet(
            f"color:{colors[score]}; font-size:16px; border:none;")

    def _change_password(self):
        old_pw  = self.le_old_pw.text()
        new_pw  = self.le_new_pw.text()
        confirm = self.le_confirm_pw.text()

        if not old_pw or not new_pw:
            self._show_pw_msg("Vui lòng điền đầy đủ.", "error")
            return
        if len(new_pw) < 6:
            self._show_pw_msg("Mật khẩu mới phải có ít nhất 6 ký tự.", "error")
            return
        if new_pw != confirm:
            self._show_pw_msg("Mật khẩu xác nhận không khớp.", "error")
            return

        try:
            from user_session import session
            import sqlite3
            conn = sqlite3.connect(str(session.auth_db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT password_hash, salt FROM users WHERE username=?",
                (session.username,)
            ).fetchone()
            expected = hashlib.sha256(
                (row["salt"] + old_pw).encode()).hexdigest()
            if expected != row["password_hash"]:
                self._show_pw_msg("Mật khẩu cũ không đúng.", "error")
                conn.close()
                return

            new_salt = secrets.token_hex(16)
            new_hash = hashlib.sha256((new_salt + new_pw).encode()).hexdigest()
            conn.execute(
                "UPDATE users SET password_hash=?, salt=? WHERE username=?",
                (new_hash, new_salt, session.username)
            )
            conn.commit()
            conn.close()

            self.le_old_pw.clear()
            self.le_new_pw.clear()
            self.le_confirm_pw.clear()
            self.pw_strength_bar.setValue(0)
            self.pw_strength_lbl.setText("")
            self._show_pw_msg("Đổi mật khẩu thành công! ✅", "success")
        except Exception as e:
            self._show_pw_msg(str(e), "error")

    def _show_pw_msg(self, msg: str, kind: str):
        colors = {
            "error":   "background:#FEF0F0; color:#C0392B; border:1px solid #F5C6CB;",
            "success": "background:#EAF3DE; color:#2D7D1A; border:1px solid #B8DFAA;",
        }
        self.pw_msg.setStyleSheet(
            f"QLabel {{ {colors.get(kind, colors['error'])} "
            f"border-radius:8px; padding:8px 12px; font-size:17px; }}")
        self.pw_msg.setText(msg)
        self.pw_msg.show()
        QTimer.singleShot(5000, self.pw_msg.hide)

    # ── Style helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _panel(title: str) -> QFrame:
        """
        Card panel with scaled-up, high-contrast section title.
        """
        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        panel.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:12px; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        # Section title: larger font + dark colour
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))   # was 17
        lbl.setStyleSheet("color:#0B2A4A; border:none;")        # was default (faint)
        layout.addWidget(lbl)
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#f0f0f0; border:none; max-height:1px;")
        layout.addWidget(div)
        return panel

    @staticmethod
    def _form_label(text: str) -> QLabel:
        """
        Reusable form row label with high-contrast dark colour and readable font size.
        Replaces the previous inline QFormLayout.addRow(str, ...) calls.
        """
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))  # was implicit ~13-14
        lbl.setStyleSheet("color:#0B2A4A; border:none;")          # was very faint grey
        return lbl

    @staticmethod
    def _input_style() -> str:
        return ("QLineEdit { border:1px solid #ddd; border-radius:6px; "
                "padding:7px 10px; font-size:17px; background:#fff; color:#222; }")

    @staticmethod
    def _btn_primary() -> str:
        return ("QPushButton { background:#378ADD; color:#fff; border:none; "
                "border-radius:8px; padding:7px 18px; font-size:17px; font-weight:500; } "
                "QPushButton:hover { background:#185FA5; }")

    @staticmethod
    def _btn_normal() -> str:
        return ("QPushButton { background:#fff; color:#555; "
                "border:1px solid #ddd; border-radius:6px; "
                "padding:7px 12px; font-size:17px; } "
                "QPushButton:hover { background:#f5f5f5; }")

    @staticmethod
    def _btn_normal_large() -> str:
        """Avatar action button — scaled up font."""
        return ("QPushButton { background:#fff; color:#333; "
                "border:1px solid #ddd; border-radius:6px; "
                "padding:7px 12px; font-size:16px; font-weight:500; } "
                "QPushButton:hover { background:#f5f5f5; }")

    @staticmethod
    def _btn_danger() -> str:
        return ("QPushButton { background:#fff; color:#A32D2D; "
                "border:1px solid #E24B4A; border-radius:6px; "
                "padding:7px 12px; font-size:17px; } "
                "QPushButton:hover { background:#FCEBEB; }")

    @staticmethod
    def _btn_danger_large() -> str:
        """Avatar delete button — scaled up font."""
        return ("QPushButton { background:#fff; color:#A32D2D; "
                "border:1px solid #E24B4A; border-radius:6px; "
                "padding:7px 12px; font-size:16px; font-weight:500; } "
                "QPushButton:hover { background:#FCEBEB; }")
class _ConfirmPasswordDialog(QDialog):
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.setWindowTitle("Xác nhận danh tính")
        self.setFixedSize(380, 210)
        self.setStyleSheet("QDialog { background:#fff; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        lbl = QLabel(f"Nhập mật khẩu của @{self.username} để xác nhận xóa:")
        lbl.setWordWrap(True)
        lbl.setFont(QFont("Segoe UI", 16))
        lbl.setStyleSheet("color:#0B2A4A; border:none;")
        layout.addWidget(lbl)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Mật khẩu...")
        self.pw_input.setStyleSheet(
            "QLineEdit { border:1px solid #ddd; border-radius:6px; "
            "padding:7px 10px; font-size:16px; color:#0B2A4A; }")
        self.pw_input.returnPressed.connect(self._verify)
        layout.addWidget(self.pw_input)

        self.err_lbl = QLabel("")
        self.err_lbl.setFont(QFont("Segoe UI", 15))
        self.err_lbl.setStyleSheet("color:#E24B4A; border:none;")
        self.err_lbl.hide()
        layout.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; border:1px solid #ddd; "
            "border-radius:6px; padding:6px 14px; font-size:15px; }")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Xác nhận xóa")
        btn_ok.setStyleSheet(
            "QPushButton { background:#E24B4A; color:#fff; border:none; "
            "border-radius:6px; padding:6px 14px; font-weight:500; font-size:15px; } "
            "QPushButton:hover { background:#C0392B; }")
        btn_ok.clicked.connect(self._verify)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _verify(self):
        import hashlib
        import sqlite3
        from user_session import session
        try:
            path = session.auth_db_path
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT password_hash, salt FROM users WHERE username=?",
                (self.username,)
            ).fetchone()
            conn.close()
            if not row:
                self.err_lbl.setText("Tài khoản không tồn tại.")
                self.err_lbl.show()
                return
            expected = hashlib.sha256(
                (row["salt"] + self.pw_input.text()).encode()).hexdigest()
            if expected != row["password_hash"]:
                self.err_lbl.setText("Mật khẩu không đúng.")
                self.err_lbl.show()
                return
            self.accept()
        except Exception as e:
            self.err_lbl.setText(str(e))
            self.err_lbl.show()


class _AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thêm người dùng mới")
        self.setFixedSize(420, 320)
        self.setStyleSheet("QDialog { background:#fff; } "
                           "QLabel { font-size:16px; color:#0B2A4A; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        _s = ("QLineEdit,QComboBox { border:1px solid #ddd; border-radius:6px; "
              "padding:7px 10px; font-size:16px; background:#fff; color:#0B2A4A; }")

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.le_fullname = QLineEdit()
        self.le_fullname.setPlaceholderText("Họ và tên")
        self.le_fullname.setStyleSheet(_s)
        form.addRow("Họ tên:", self.le_fullname)

        self.le_username = QLineEdit()
        self.le_username.setPlaceholderText("3-30 ký tự, không dấu cách")
        self.le_username.setStyleSheet(_s)
        form.addRow("Username:", self.le_username)

        self.le_pw = QLineEdit()
        self.le_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_pw.setPlaceholderText("Tối thiểu 6 ký tự")
        self.le_pw.setStyleSheet(_s)
        form.addRow("Mật khẩu:", self.le_pw)

        self.cb_role = QComboBox()
        self.cb_role.addItem("Người dùng", "user")
        self.cb_role.addItem("Quản trị viên", "admin")
        self.cb_role.setStyleSheet(_s)
        form.addRow("Vai trò:", self.cb_role)

        layout.addLayout(form)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; border:1px solid #ddd; "
            "border-radius:6px; padding:7px 14px; font-size:15px; }")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Thêm user")
        btn_ok.setStyleSheet(
            "QPushButton { background:#E6F1FB; color:#0B2A4A; "
            "border:1px solid #B5D4F4; border-radius:6px; "
            "padding:7px 16px; font-weight:500; font-size:15px; } "
            "QPushButton:hover { background:#B5D4F4; }")
        btn_ok.clicked.connect(self._do_add)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _do_add(self):
        fullname = self.le_fullname.text().strip()
        username = self.le_username.text().strip()
        password = self.le_pw.text()
        role     = self.cb_role.currentData()

        if not fullname or not username or not password:
            self._show_msg("Vui lòng điền đầy đủ thông tin.", "error")
            return
        if len(username) < 3:
            self._show_msg("Username phải có ít nhất 3 ký tự.", "error")
            return
        if len(password) < 6:
            self._show_msg("Mật khẩu phải có ít nhất 6 ký tự.", "error")
            return

        from app.data.auth_manager import AuthManager
        result = AuthManager().register(username, password, fullname)
        if not result["success"]:
            self._show_msg(result["message"], "error")
            return

        if role == "admin":
            from user_session import session
            import sqlite3
            conn = sqlite3.connect(str(session.auth_db_path))
            conn.execute("UPDATE users SET role='admin' WHERE username=?", (username,))
            conn.commit()
            conn.close()

        self.accept()

    def _show_msg(self, msg: str, kind: str):
        c = ("background:#FEF0F0; color:#C0392B; border:1px solid #F5C6CB;"
             if kind == "error"
             else "background:#EAF3DE; color:#2D7D1A; border:1px solid #B8DFAA;")
        self.msg_lbl.setStyleSheet(
            f"QLabel {{ {c} border-radius:8px; padding:8px 12px; font-size:15px; }}")
        self.msg_lbl.setText(msg)
        self.msg_lbl.show()


class _EditUserDialog(QDialog):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"Sửa thông tin @{user['username']}")
        self.setFixedSize(420, 280)
        self.setStyleSheet("QDialog { background:#fff; } "
                           "QLabel { font-size:16px; color:#0B2A4A; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        _s = ("QLineEdit,QComboBox { border:1px solid #ddd; border-radius:6px; "
              "padding:7px 10px; font-size:16px; background:#fff; color:#0B2A4A; }")

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.le_fullname = QLineEdit(self.user.get("full_name") or "")
        self.le_fullname.setStyleSheet(_s)
        form.addRow("Họ tên:", self.le_fullname)

        un = QLineEdit(self.user.get("username") or "")
        un.setReadOnly(True)
        un.setStyleSheet(_s + " background:#f7f7f7; color:#999;")
        form.addRow("Username:", un)

        self.cb_role = QComboBox()
        self.cb_role.addItem("Người dùng", "user")
        self.cb_role.addItem("Quản trị viên", "admin")
        self.cb_role.setStyleSheet(_s)
        idx = self.cb_role.findData(self.user.get("role", "user"))
        if idx >= 0:
            self.cb_role.setCurrentIndex(idx)
        form.addRow("Vai trò:", self.cb_role)

        self.le_reset_pw = QLineEdit()
        self.le_reset_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_reset_pw.setPlaceholderText("Để trống = không đổi")
        self.le_reset_pw.setStyleSheet(_s)
        form.addRow("Đặt lại mật khẩu:", self.le_reset_pw)

        layout.addLayout(form)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; border:1px solid #ddd; "
            "border-radius:6px; padding:7px 14px; font-size:15px; }")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Lưu")
        btn_ok.setStyleSheet(
            "QPushButton { background:#E6F1FB; color:#0B2A4A; "
            "border:1px solid #B5D4F4; border-radius:6px; "
            "padding:7px 16px; font-weight:500; font-size:15px; } "
            "QPushButton:hover { background:#B5D4F4; }")
        btn_ok.clicked.connect(self._do_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _do_save(self):
        fullname = self.le_fullname.text().strip()
        role     = self.cb_role.currentData()
        new_pw   = self.le_reset_pw.text()

        if not fullname:
            self._show_msg("Họ tên không được để trống.", "error")
            return

        try:
            import sqlite3, hashlib, secrets as _sec
            from user_session import session
            conn = sqlite3.connect(str(session.auth_db_path))
            conn.execute(
                "UPDATE users SET full_name=?, role=? WHERE username=?",
                (fullname, role, self.user["username"])
            )
            if new_pw:
                if len(new_pw) < 6:
                    self._show_msg("Mật khẩu mới phải có ít nhất 6 ký tự.", "error")
                    conn.close()
                    return
                salt    = _sec.token_hex(16)
                pw_hash = hashlib.sha256((salt + new_pw).encode()).hexdigest()
                conn.execute(
                    "UPDATE users SET password_hash=?, salt=? WHERE username=?",
                    (pw_hash, salt, self.user["username"])
                )
            conn.commit()
            conn.close()
            self.accept()
        except Exception as e:
            self._show_msg(str(e), "error")

    def _show_msg(self, msg: str, kind: str):
        c = ("background:#FEF0F0; color:#C0392B; border:1px solid #F5C6CB;"
             if kind == "error"
             else "background:#EAF3DE; color:#2D7D1A; border:1px solid #B8DFAA;")
        self.msg_lbl.setStyleSheet(
            f"QLabel {{ {c} border-radius:8px; padding:8px 12px; font-size:15px; }}")
        self.msg_lbl.setText(msg)
        self.msg_lbl.show()


