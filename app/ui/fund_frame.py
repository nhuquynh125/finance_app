# app/ui/fund_frame.py
"""
Quản lý Quỹ
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QInputDialog, QMessageBox, QDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from app.core.fund_manager import FundManager


class TransactionHistoryDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.fm = FundManager()
        self.setWindowTitle(f"Lịch sử góp quỹ - {username}")
        self.resize(600, 400)
        self.setStyleSheet("background:#fff;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel(f"Lịch sử góp quỹ của {self.username}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Ngày", "Số tiền", "Ghi chú"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self._load_data()
        
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet(
            "QPushButton { background:#f0f0f0; border:1px solid #ddd; border-radius:6px; padding:8px 16px; }"
            "QPushButton:hover { background:#e0e0e0; }"
        )
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _load_data(self):
        transactions = self.fm.get_member_transactions(self.username)
        self.table.setRowCount(len(transactions))
        for i, tx in enumerate(transactions):
            date_item = QTableWidgetItem(tx["date"])
            amount_item = QTableWidgetItem(f"{tx['amount']:,.0f} đ")
            note_item = QTableWidgetItem(tx["description"] or "")
            
            self.table.setItem(i, 0, date_item)
            self.table.setItem(i, 1, amount_item)
            self.table.setItem(i, 2, note_item)


class FundFrame(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.fm = FundManager()
        self.selected_group = None
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
        bar.setFixedHeight(60)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Quản lý Quỹ")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("color:#1A2B45; border:none;")
        layout.addWidget(title)
        layout.addStretch()
        btn_refresh = QPushButton("Làm mới")
        btn_refresh.setStyleSheet(self._btn_normal())
        btn_refresh.clicked.connect(self.refresh)
        layout.addWidget(btn_refresh)
        return bar

    # ── Refresh — quyết định hiển thị gì ────────────────────────────────────

    def refresh(self):
        """Hiển thị UI tùy thuộc vào việc có chọn nhóm cụ thể hay không."""
        if self.selected_group:
            self._replace_state_widget(self._build_group_view(self.selected_group))
        else:
            self._replace_state_widget(self._build_dashboard_view())

    def _replace_state_widget(self, new_widget: QWidget):
        """Thay thế widget trạng thái hiện tại."""
        self.cl.removeWidget(self.state_widget)
        self.state_widget.deleteLater()
        self.state_widget = new_widget
        # Chèn trước stretch (index cuối - 1)
        self.cl.insertWidget(0, self.state_widget)

    # ── View: Danh sách Quỹ (Dashboard) ──────────────────────────────────────

    def _build_dashboard_view(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Hai card hành động (Tạo quỹ & Tham gia)
        grid = QGridLayout()
        grid.setSpacing(16)

        card_create = self._action_card(
            icon="➕",
            title="Tạo nhóm quỹ mới",
            desc="Bắt đầu quỹ chung và nhận mã mời để chia sẻ với mọi người.",
            btn_text="Tạo quỹ",
            btn_primary=True,
            callback=self._on_create_group
        )
        grid.addWidget(card_create, 0, 0)

        card_join = self._action_card(
            icon="🔑",
            title="Tham gia nhóm quỹ",
            desc="Nhập mã mời 6 ký tự để tham gia vào quỹ đã có sẵn.",
            btn_text="Tham gia",
            btn_primary=False,
            callback=self._on_join_group
        )
        grid.addWidget(card_join, 0, 1)
        layout.addLayout(grid)

        # Danh sách các quỹ đang tham gia
        groups = self.fm.get_my_groups()
        
        list_card = QFrame()
        list_card.setStyleSheet(
            "QFrame { background:#fff; border-radius:12px; border:1px solid #e8e8e8; }")
        ll = QVBoxLayout(list_card)
        ll.setContentsMargins(20, 16, 20, 16)
        ll.setSpacing(12)
        
        list_title = QLabel(f"Các quỹ đang tham gia ({len(groups)})")
        list_title.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        list_title.setStyleSheet("color:#1A2B45; border:none;")
        ll.addWidget(list_title)
        
        if not groups:
            empty_lbl = QLabel("Bạn chưa tham gia quỹ nào. Hãy tạo hoặc tham gia quỹ mới ở trên.")
            empty_lbl.setStyleSheet("color:#7a7872; font-style:italic; border:none;")
            ll.addWidget(empty_lbl)
        else:
            for g in groups:
                btn_group = QPushButton()
                btn_group.setStyleSheet("""
                    QPushButton { 
                        background:#f9f9f9; border:1px solid #e8e8e8; 
                        border-radius:8px; padding:12px; text-align:left; 
                    }
                    QPushButton:hover { background:#f0f7ff; border:1px solid #bbd6f2; }
                """)
                # Layout nội bộ cho nút nhóm
                btn_layout = QHBoxLayout(btn_group)
                btn_layout.setContentsMargins(10, 5, 10, 5)
                
                name_lbl = QLabel(f"📋 {g['name']}")
                name_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
                name_lbl.setStyleSheet("color:#1A2B45; border:none; background:transparent;")
                
                info_lbl = QLabel(f"Thành viên: {g['member_count']} | Quyền: {'Chủ quỹ' if g['my_role']=='owner' else 'Thành viên'}")
                info_lbl.setStyleSheet("color:#666; border:none; background:transparent;")
                
                v_box = QVBoxLayout()
                v_box.addWidget(name_lbl)
                v_box.addWidget(info_lbl)
                btn_layout.addLayout(v_box)
                btn_layout.addStretch()
                
                arrow = QLabel("➔")
                arrow.setFont(QFont("Segoe UI", 16))
                arrow.setStyleSheet("color:#bbb; border:none; background:transparent;")
                btn_layout.addWidget(arrow)
                
                btn_group.clicked.connect(lambda checked, grp=g: self._on_select_group(grp))
                ll.addWidget(btn_group)
                
        layout.addWidget(list_card)
        return container

    # ── View: Chi tiết Quỹ ───────────────────────────────────────────────────

    def _build_group_view(self, group: dict) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Nút Quay lại
        btn_back = QPushButton("← Quay lại danh sách quỹ")
        btn_back.setStyleSheet(
            "QPushButton { background:transparent; color:#378ADD; font-size:15px; font-weight:bold; "
            "border:none; text-align:left; padding:0; } QPushButton:hover { color:#185FA5; text-decoration:underline; }")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self._on_back_to_dashboard)
        
        back_layout = QHBoxLayout()
        back_layout.addWidget(btn_back)
        back_layout.addStretch()
        layout.addLayout(back_layout)

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

        role_text  = "Chủ quỹ" if group["my_role"] == "owner" else "Thành viên"
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

        # Hiển thị mã mời
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

        members_title = QLabel("Thành viên & Đóng góp")
        members_title.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        members_title.setStyleSheet("border:none; color:#1A2B45;")
        ml.addWidget(members_title)
        
        desc_lbl = QLabel("Bấm vào tên thành viên để xem chi tiết lịch sử đóng góp.")
        desc_lbl.setStyleSheet("color:#666; font-size:16px;")
        ml.addWidget(desc_lbl)

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
            btn_disband = QPushButton("Giải tán quỹ")
            btn_disband.setStyleSheet(self._btn_danger())
            btn_disband.clicked.connect(lambda: self._on_disband_group(group["id"]))
            btn_row.addWidget(btn_disband)
        else:
            btn_leave = QPushButton("Rời quỹ")
            btn_leave.setStyleSheet(self._btn_danger())
            btn_leave.clicked.connect(lambda: self._on_leave_group(group["id"]))
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
        t.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
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
        # Sử dụng QPushButton giả lập thành card để click được
        row = QPushButton()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet("""
            QPushButton { 
                background:#fcfcfc; border:1px solid #f0f0f0; border-radius:8px; text-align:left;
            }
            QPushButton:hover { background:#f5f5f5; border:1px solid #e0e0e0; }
        """)
        
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 12, 14, 12)
        rl.setSpacing(16)

        # Avatar chữ cái đầu
        initial = (member["username"][0] if member["username"] else "?").upper()
        avatar = QLabel(initial)
        avatar.setFixedSize(44, 44)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        color = "#378ADD" if member["role"] == "owner" else "#888"
        avatar.setStyleSheet(
            f"background:{color}; color:white; border-radius:22px; border:none;")
        rl.addWidget(avatar)

        name_col = QWidget()
        name_col.setStyleSheet("background:transparent;")
        nc = QVBoxLayout(name_col)
        nc.setContentsMargins(0, 0, 0, 0)
        nc.setSpacing(2)

        name_lbl = QLabel(member["username"])
        name_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color:#1A2B45; border:none;")
        nc.addWidget(name_lbl)

        role_lbl = QLabel(member["role_display"])
        role_lbl.setFont(QFont("Segoe UI", 15))
        role_lbl.setStyleSheet("color:#8FA8C4; border:none;")
        nc.addWidget(role_lbl)

        rl.addWidget(name_col)
        rl.addStretch()

        # Hiển thị số tiền đóng góp
        contrib_val = member.get("total_contribution", 0)
        contrib_lbl = QLabel(f"Đã góp: <b style='color:#1D9E75;'>{contrib_val:,.0f} đ</b>")
        contrib_lbl.setFont(QFont("Segoe UI", 17))
        contrib_lbl.setStyleSheet("border:none;")
        rl.addWidget(contrib_lbl)
        
        arrow = QLabel(" › ")
        arrow.setStyleSheet("color:#999; font-size:24px; border:none;")
        rl.addWidget(arrow)
        
        # Bấm vào row -> Mở popup lịch sử giao dịch
        row.clicked.connect(lambda: self._on_view_member_history(member["username"]))

        return row

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_create_group(self):
        name, ok = QInputDialog.getText(
            self, "Tạo nhóm quỹ", "Tên quỹ:")
        if not ok or not name.strip():
            return

        result = self.fm.create_group(name.strip())
        if result["success"]:
            QMessageBox.information(
                self, "Thành công",
                f"✅ {result['message']}\n\n"
                f"Mã mời của quỹ: {result['invite_code']}\n\n"
                "Hãy chia sẻ mã này để mời thành viên tham gia."
            )
            self.refresh()
        else:
            QMessageBox.warning(self, "Không thể tạo quỹ", result["message"])

    def _on_join_group(self):
        code, ok = QInputDialog.getText(
            self, "Tham gia quỹ", "Nhập mã mời (6 ký tự):")
        if not ok or not code.strip():
            return

        # Xem trước thông tin nhóm trước khi join
        preview = self.fm.get_group_by_invite(code.strip())
        if preview:
            reply = QMessageBox.question(
                self, "Xác nhận tham gia",
                f"Bạn muốn tham gia quỹ:\n\n"
                f"Tên quỹ : {preview['name']}\n"
                f"Chủ quỹ : {preview['owner_username']}\n"
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
            
    def _on_select_group(self, group: dict):
        self.selected_group = group
        self.refresh()
        
    def _on_back_to_dashboard(self):
        self.selected_group = None
        self.refresh()
        
    def _on_view_member_history(self, username: str):
        dlg = TransactionHistoryDialog(username, self)
        dlg.exec()

    def _on_leave_group(self, group_id: int):
        reply = QMessageBox.question(
            self, "Rời quỹ",
            "Bạn có chắc muốn rời quỹ này không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self.fm.leave_group(group_id)
        if result["success"]:
            QMessageBox.information(self, "Đã rời quỹ", result["message"])
            self.selected_group = None
            self.refresh()
        else:
            QMessageBox.warning(self, "Lỗi", result["message"])

    def _on_disband_group(self, group_id: int):
        reply = QMessageBox.warning(
            self, "Giải tán quỹ",
            "Hành động này sẽ xóa quỹ và xóa tất cả thành viên.\n"
            "Bạn có chắc chắn muốn giải tán quỹ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self.fm.disband_group(group_id)
        if result["success"]:
            QMessageBox.information(self, "Đã giải tán", result["message"])
            self.selected_group = None
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

