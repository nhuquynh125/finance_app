# app/ui/family_frame.py  (viết lại hoàn chỉnh — dùng FamilyManager thực sự)
"""
Thay đổi so với phiên bản cũ:
  - Tạo/tham gia nhóm lưu dữ liệu vào DB thực sự qua FamilyManager
  - Hiển thị danh sách thành viên sau khi tạo/tham gia
  - Nút "Rời nhóm" và "Giải tán nhóm" có chức năng thật
  - Tự động load trạng thái nhóm khi mở trang
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QInputDialog, QMessageBox, QDialog, QLineEdit,
    QFormLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from app.core.family_manager import FamilyManager


class FamilyFrame(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.fm = FamilyManager()
        self._build()
        QTimer.singleShot(100, self.refresh)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f5f5f5; }")

        self.content = QWidget()
        self.content.setStyleSheet("background:#f5f5f5;")
        self.cl = QVBoxLayout(self.content)
        self.cl.setContentsMargins(24, 20, 24, 20)
        self.cl.setSpacing(16)

        # Placeholder — sẽ được refresh() fill vào
        self.state_widget = QWidget()
        self.cl.addWidget(self.state_widget)
        self.cl.addStretch()

        scroll.setWidget(self.content)
        layout.addWidget(scroll)

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Quản lý quỹ")
        title.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()
        btn_refresh = QPushButton("Làm mới")
        btn_refresh.setStyleSheet(self._btn_normal())
        btn_refresh.clicked.connect(self.refresh)
        layout.addWidget(btn_refresh)
        return bar

    # ── Refresh — quyết định hiển thị gì ────────────────────────────────────

    def refresh(self):
        """Kiểm tra user có nhóm chưa → hiển thị UI tương ứng."""
        group = self.fm.get_my_group()
        self._replace_state_widget(
            self._build_group_view(group) if group
            else self._build_no_group_view()
        )

    def _replace_state_widget(self, new_widget: QWidget):
        """Thay thế widget trạng thái hiện tại."""
        self.cl.removeWidget(self.state_widget)
        self.state_widget.deleteLater()
        self.state_widget = new_widget
        # Chèn trước stretch (index cuối - 1)
        self.cl.insertWidget(0, self.state_widget)

    # ── View: chưa có nhóm ───────────────────────────────────────────────────

    def _build_no_group_view(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Intro card
        intro = QFrame()
        intro.setStyleSheet(
            "QFrame { background:#fff; border-radius:12px; border:1px solid #e8e8e8; }")
        il = QVBoxLayout(intro)
        il.setContentsMargins(20, 16, 20, 16)

        icon = QLabel("👨‍👩‍👧‍👦")
        icon.setFont(QFont("Segoe UI Emoji", 37))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("border:none;")
        il.addWidget(icon)

        title = QLabel("Quản lý tài chính gia đình")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#1A2B45; border:none;")
        il.addWidget(title)

        desc = QLabel(
            "Tạo nhóm quỹ để cùng nhau góp quỹ,chia sẻ và theo dõi tài chính chung.\n"
            "Mỗi thành viên giữ database riêng, nhóm chỉ chia sẻ thống kê tổng hợp."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color:#7a7872; border:none; font-size:17px;")
        il.addWidget(desc)
        layout.addWidget(intro)

        # Hai card hành động
        grid = QGridLayout()
        grid.setSpacing(12)

        card_create = self._action_card(
            icon="➕",
            title="Tạo nhóm mới",
            desc="Bắt đầu nhóm quỹ và nhận mã mời để chia sẻ.",
            btn_text="Tạo nhóm",
            btn_primary=True,
            callback=self._on_create_group
        )
        grid.addWidget(card_create, 0, 0)

        card_join = self._action_card(
            icon="🔑",
            title="Tham gia nhóm",
            desc="Nhập mã mời 6 ký tự từ thành viên cùng tham gia quỹ.",
            btn_text="Tham gia",
            btn_primary=False,
            callback=self._on_join_group
        )
        grid.addWidget(card_join, 0, 1)
        layout.addLayout(grid)

        return container

    # ── View: đã có nhóm ─────────────────────────────────────────────────────

    def _build_group_view(self, group: dict) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Header card — thông tin nhóm
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background:#fff; border-radius:12px; border:1px solid #e8e8e8; }")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(10)

        top_row = QHBoxLayout()
        name_lbl = QLabel(f"📋  {group['name']}")
        name_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color:#1A2B45; border:none;")
        top_row.addWidget(name_lbl)
        top_row.addStretch()

        role_text  = "Chủ nhóm" if group["my_role"] == "owner" else "Thành viên"
        role_color = "#0C447C" if group["my_role"] == "owner" else "#3B6D11"
        role_bg    = "#E6F1FB" if group["my_role"] == "owner" else "#EAF3DE"
        role_badge = QLabel(role_text)
        role_badge.setStyleSheet(
            f"QLabel {{ background:{role_bg}; color:{role_color}; "
            f"border:none; border-radius:10px; padding:3px 12px; font-size:16px; }}")
        top_row.addWidget(role_badge)
        hl.addLayout(top_row)

        info_row = QHBoxLayout()
        info_row.setSpacing(20)

        member_lbl = QLabel(f"👥  {group['member_count']} thành viên")
        member_lbl.setStyleSheet("color:#555; font-size:17px; border:none;")
        info_row.addWidget(member_lbl)

        # Hiển thị mã mời nếu là owner
        if group["my_role"] == "owner":
            from app.data.models import get_connection
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT invite_code FROM family_groups WHERE id=?",
                    (group["id"],)
                ).fetchone()
            if row:
                code_lbl = QLabel(f"🔑  Mã mời: {row['invite_code']}")
                code_lbl.setStyleSheet(
                    "color:#0C447C; font-size:17px; font-weight:bold; border:none;")
                info_row.addWidget(code_lbl)

        info_row.addStretch()
        hl.addLayout(info_row)
        layout.addWidget(header)

        # Danh sách thành viên
        members_card = QFrame()
        members_card.setStyleSheet(
            "QFrame { background:#fff; border-radius:12px; border:1px solid #e8e8e8; }")
        ml = QVBoxLayout(members_card)
        ml.setContentsMargins(20, 16, 20, 16)
        ml.setSpacing(8)

        members_title = QLabel("Thành viên")
        members_title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        members_title.setStyleSheet("border:none; color:#1A2B45;")
        ml.addWidget(members_title)

        members = self.fm.get_members(group["id"])
        if members:
            for m in members:
                row_w = self._member_row(m)
                ml.addWidget(row_w)
        else:
            ml.addWidget(QLabel("Chưa có thành viên."))

        layout.addWidget(members_card)

        # Nút hành động
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        if group["my_role"] == "owner":
            btn_disband = QPushButton("Giải tán nhóm")
            btn_disband.setStyleSheet(self._btn_danger())
            btn_disband.clicked.connect(self._on_disband_group)
            btn_row.addWidget(btn_disband)
        else:
            btn_leave = QPushButton("Rời nhóm")
            btn_leave.setStyleSheet(self._btn_danger())
            btn_leave.clicked.connect(self._on_leave_group)
            btn_row.addWidget(btn_leave)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        return container

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _action_card(self, icon: str, title: str, desc: str,
                     btn_text: str, btn_primary: bool,
                     callback) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background:#fff; border-radius:12px; border:1px solid #e8e8e8; }")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 27))
        icon_lbl.setStyleSheet("border:none;")
        cl.addWidget(icon_lbl)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t.setStyleSheet("color:#1A2B45; border:none;")
        cl.addWidget(t)

        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("color:#7a7872; font-size:17px; border:none;")
        cl.addWidget(d)

        cl.addSpacing(6)

        btn = QPushButton(btn_text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            self._btn_primary() if btn_primary else self._btn_normal())
        btn.clicked.connect(callback)
        cl.addWidget(btn)

        return card

    def _member_row(self, member: dict) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 4, 0, 4)
        rl.setSpacing(12)

        # Avatar chữ cái đầu
        initial = (member["username"][0] if member["username"] else "?").upper()
        avatar = QLabel(initial)
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        color = "#378ADD" if member["role"] == "owner" else "#888"
        avatar.setStyleSheet(
            f"background:{color}; color:white; border-radius:17px; border:none;")
        rl.addWidget(avatar)

        name_col = QWidget()
        name_col.setStyleSheet("background:transparent;")
        nc = QVBoxLayout(name_col)
        nc.setContentsMargins(0, 0, 0, 0)
        nc.setSpacing(1)

        name_lbl = QLabel(member["username"])
        name_lbl.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color:#1A2B45; border:none;")
        nc.addWidget(name_lbl)

        role_lbl = QLabel(member["role_display"])
        role_lbl.setFont(QFont("Segoe UI", 15))
        role_lbl.setStyleSheet("color:#8FA8C4; border:none;")
        nc.addWidget(role_lbl)

        rl.addWidget(name_col)
        rl.addStretch()

        joined = member.get("joined_at", "")
        if joined:
            try:
                from datetime import datetime
                dt = datetime.strptime(joined[:10], "%Y-%m-%d")
                joined_str = dt.strftime("Tham gia %d/%m/%Y")
            except Exception:
                joined_str = joined[:10]
            joined_lbl = QLabel(joined_str)
            joined_lbl.setStyleSheet("color:#aaa; font-size:15px; border:none;")
            rl.addWidget(joined_lbl)

        return row

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_create_group(self):
        name, ok = QInputDialog.getText(
            self, "Tạo nhóm quỹ", "Tên nhóm:")
        if not ok or not name.strip():
            return

        result = self.fm.create_group(name.strip())
        if result["success"]:
            QMessageBox.information(
                self, "Thành công",
                f"✅ {result['message']}\n\n"
                f"Mã mời của nhóm: {result['invite_code']}\n\n"
                "Hãy chia sẻ mã này để mời thành viên tham gia."
            )
            self.refresh()
        else:
            QMessageBox.warning(self, "Không thể tạo nhóm", result["message"])

    def _on_join_group(self):
        code, ok = QInputDialog.getText(
            self, "Tham gia nhóm", "Nhập mã mời (6 ký tự):")
        if not ok or not code.strip():
            return

        # Xem trước thông tin nhóm trước khi join
        preview = self.fm.get_group_by_invite(code.strip())
        if preview:
            reply = QMessageBox.question(
                self, "Xác nhận tham gia",
                f"Bạn muốn tham gia nhóm:\n\n"
                f"Tên nhóm : {preview['name']}\n"
                f"Chủ nhóm : {preview['owner_username']}\n"
                f"Thành viên: {preview['member_count']} người\n\n"
                "Tiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        result = self.fm.join_group(code.strip())
        if result["success"]:
            QMessageBox.information(self, "Thành công", f"✅ {result['message']}")
            self.refresh()
        else:
            QMessageBox.warning(self, "Không thể tham gia", result["message"])

    def _on_leave_group(self):
        reply = QMessageBox.question(
            self, "Rời nhóm",
            "Bạn có chắc muốn rời nhóm này không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self.fm.leave_group()
        if result["success"]:
            QMessageBox.information(self, "Đã rời nhóm", result["message"])
            self.refresh()
        else:
            QMessageBox.warning(self, "Lỗi", result["message"])

    def _on_disband_group(self):
        reply = QMessageBox.warning(
            self, "Giải tán nhóm",
            "Hành động này sẽ xóa nhóm và xóa tất cả thành viên.\n"
            "Dữ liệu tài chính cá nhân của từng người KHÔNG bị ảnh hưởng.\n\n"
            "Bạn có chắc chắn muốn giải tán nhóm?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self.fm.disband_group()
        if result["success"]:
            QMessageBox.information(self, "Đã giải tán", result["message"])
            self.refresh()
        else:
            QMessageBox.warning(self, "Lỗi", result["message"])

    # ── Style helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _btn_primary() -> str:
        return (
            "QPushButton { background:#185FA5; color:white; border:none; "
            "border-radius:8px; padding:8px 16px; font-weight:500; font-size:17px; } "
            "QPushButton:hover { background:#144f8a; }"
        )

    @staticmethod
    def _btn_normal() -> str:
        return (
            "QPushButton { background:#fff; color:#555; "
            "border:1px solid #ddd; border-radius:8px; "
            "padding:8px 16px; font-size:17px; } "
            "QPushButton:hover { background:#f5f5f5; }"
        )

    @staticmethod
    def _btn_danger() -> str:
        return (
            "QPushButton { background:#fff; color:#C0392B; "
            "border:1px solid #E24B4A; border-radius:8px; "
            "padding:8px 16px; font-size:17px; } "
            "QPushButton:hover { background:#FCEBEB; }"
        )
