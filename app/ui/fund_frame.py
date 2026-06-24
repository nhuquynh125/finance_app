# app/ui/fund_frame.py
"""
Quản lý Quỹ
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QInputDialog, QMessageBox, QDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from app.core.fund_manager import FundManager


class FundContributionDialog(QDialog):
    def __init__(self, tx=None, parent=None):
        super().__init__(parent)
        self.tx = tx
        self.setWindowTitle("Sửa đóng góp" if tx else "Thêm đóng góp")
        self.resize(400, 300)
        self.setStyleSheet("""
            QDialog { background: #ffffff; }
            QLabel { color: #1A2B45; font-size: 15px; font-weight: bold; }
            QLineEdit { border: 1px solid #dcdcdc; border-radius: 4px; padding: 8px; font-size: 15px; }
            QPushButton { background: #185FA5; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-size: 15px; font-weight: bold; }
            QPushButton:hover { background: #144f8a; }
            QPushButton#cancel { background: #f0f0f0; color: #555; }
            QPushButton#cancel:hover { background: #e0e0e0; }
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Ngày (YYYY-MM-DD):"))
        self.date_input = QLineEdit()
        from datetime import datetime
        self.date_input.setText(self.tx["date"] if self.tx else datetime.now().strftime("%Y-%m-%d"))
        layout.addWidget(self.date_input)
        
        layout.addWidget(QLabel("Số tiền:"))
        self.amount_input = QLineEdit()
        self.amount_input.setText(str(int(self.tx["amount"])) if self.tx else "")
        layout.addWidget(self.amount_input)
        
        layout.addWidget(QLabel("Ghi chú:"))
        self.note_input = QLineEdit()
        self.note_input.setText(self.tx["description"] if self.tx else "")
        layout.addWidget(self.note_input)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = QPushButton("Lưu")
        btn_ok.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            "date": self.date_input.text().strip(),
            "amount": float(self.amount_input.text().strip() or 0),
            "description": self.note_input.text().strip()
        }


class TransactionHistoryDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.fm = FundManager()
        self.transactions = []
        self.setWindowTitle(f"Lịch sử góp quỹ - {username}")
        self.resize(650, 450)
        self.setStyleSheet("QDialog { background:#fff; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel(f"Lịch sử góp quỹ của {self.username}")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #1A2B45; border: none;")
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Ngày", "Số tiền", "Ghi chú"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.table.setStyleSheet("""
            QTableWidget {
                font-size: 15px;
                color: #1A2B45;
                background-color: #ffffff;
                alternate-background-color: #f4f8fc;
                gridline-color: #dcdcdc;
                border: 1px solid #dcdcdc;
                border-radius: 8px;
            }
            QTableWidget::item {
                color: #1A2B45;
                padding: 8px;
            }
            QHeaderView::section {
                font-size: 15px;
                font-weight: bold;
                background-color: #0B2A4A;
                color: #ffffff;
                padding: 10px;
                border: none;
                border-right: 1px solid #163e68;
            }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)
        
        self._load_data()
        
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("Thêm")
        btn_edit = QPushButton("Sửa")
        btn_delete = QPushButton("Xóa")
        btn_close = QPushButton("Đóng")
        
        for btn in (btn_add, btn_edit, btn_delete, btn_close):
            btn.setStyleSheet(
                "QPushButton { background:#f0f0f0; color: #333; border:1px solid #ddd; border-radius:6px; padding:8px 16px; font-weight: bold; }"
                "QPushButton:hover { background:#e0e0e0; }"
            )
            
        btn_add.clicked.connect(self._on_add)
        btn_edit.clicked.connect(self._on_edit)
        btn_delete.clicked.connect(self._on_delete)
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def _load_data(self):
        self.transactions = self.fm.get_member_transactions(self.username)
        self.table.setRowCount(len(self.transactions))
        for i, tx in enumerate(self.transactions):
            date_item = QTableWidgetItem(tx["date"])
            date_item.setData(Qt.ItemDataRole.UserRole, tx["id"])
            amount_item = QTableWidgetItem(f"{tx['amount']:,.0f} đ")
            note_item = QTableWidgetItem(tx["description"] or "")
            
            self.table.setItem(i, 0, date_item)
            self.table.setItem(i, 1, amount_item)
            self.table.setItem(i, 2, note_item)

    def _on_add(self):
        dlg = FundContributionDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data["amount"] <= 0:
                QMessageBox.warning(self, "Lỗi", "Số tiền phải lớn hơn 0")
                return
            
            from app.core.transaction_manager import TransactionManager
            from app.data.models import get_connection
            tm = TransactionManager()
            
            with get_connection() as conn:
                acc = conn.execute("SELECT id FROM accounts LIMIT 1").fetchone()
                cat = conn.execute("SELECT id FROM categories WHERE type='income' LIMIT 1").fetchone()
            
            if not acc or not cat:
                QMessageBox.warning(self, "Lỗi", "Chưa có tài khoản hoặc danh mục thu nhập để thêm.")
                return
                
            tm.add_transaction(
                account_id=acc["id"],
                amount=data["amount"],
                type_="income",
                description=data["description"],
                date=data["date"],
                category_id=cat["id"]
            )
            
            # Cập nhật lại owner_username cho giao dịch vừa thêm (vì add_transaction lấy username của session, nhưng ở đây có thể thêm cho member khác)
            with get_connection() as conn:
                conn.execute("UPDATE transactions SET owner_username = ? WHERE id = (SELECT MAX(id) FROM transactions)", (self.username,))
            
            self._load_data()

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một dòng để sửa.")
            return
            
        tx = self.transactions[row]
        dlg = FundContributionDialog(tx=tx, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data["amount"] <= 0:
                QMessageBox.warning(self, "Lỗi", "Số tiền phải lớn hơn 0")
                return
                
            from app.core.transaction_manager import TransactionManager
            tm = TransactionManager()
            tm.update_transaction(
                transaction_id=tx["id"],
                account_id=tx["account_id"],
                amount=data["amount"],
                type_="income",
                description=data["description"],
                date=data["date"],
                category_id=tx["category_id"],
                note=tx["note"]
            )
            self._load_data()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một dòng để xóa.")
            return
            
        tx = self.transactions[row]
        reply = QMessageBox.question(self, "Xác nhận", "Bạn có chắc chắn muốn xóa đóng góp này?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from app.core.transaction_manager import TransactionManager
            tm = TransactionManager()
            tm.delete_transaction(tx["id"])
            self._load_data()


class CustomInputDialog(QDialog):
    def __init__(self, title, label_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 250)
        self.setStyleSheet("""
            QDialog { background: #ffffff; }
            QLabel { color: #1A2B45; font-size: 18px; font-weight: bold; border: none; }
            QLineEdit { 
                border: 2px solid #e8e8e8; border-radius: 8px; padding: 12px; 
                font-size: 18px; color: #1A2B45; background: #f9f9f9;
            }
            QLineEdit:focus { border: 2px solid #185FA5; background: #ffffff; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        lbl = QLabel(label_text)
        layout.addWidget(lbl)
        
        self.input_field = QLineEdit()
        layout.addWidget(self.input_field)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton { 
                background: #f0f0f0; color: #555; border: 1px solid #ddd; 
                border-radius: 8px; padding: 10px 24px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background: #e4e4e4; }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ok.setStyleSheet("""
            QPushButton { 
                background: #185FA5; color: white; border: none; 
                border-radius: 8px; padding: 10px 24px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background: #144f8a; }
        """)
        self.btn_ok.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        
        layout.addLayout(btn_layout)

    def get_text(self):
        return self.input_field.text()


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
        """Xóa toàn bộ nội dung layout và xây dựng lại từ đầu."""
        # Xóa tất cả widget hiện có trong layout
        while self.cl.count():
            item = self.cl.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Xây lại nội dung phù hợp
        if self.selected_group:
            new_widget = self._build_group_view(self.selected_group)
        else:
            new_widget = self._build_dashboard_view()

        self.cl.addWidget(new_widget)
        self.cl.addStretch()

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
            btn_manage_members = QPushButton("Quản lý thành viên")
            btn_manage_members.setStyleSheet(self._btn_primary())
            btn_manage_members.clicked.connect(lambda: self._on_manage_members(group["id"]))
            btn_row.addWidget(btn_manage_members)
            
            btn_add_member = QPushButton("Thêm thành viên")
            btn_add_member.setStyleSheet(self._btn_normal())
            btn_add_member.clicked.connect(lambda: self._on_add_member(group["id"]))
            btn_row.addWidget(btn_add_member)

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
        # Sử dụng QFrame giả lập thành card để click được
        row = QFrame()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        row.setStyleSheet("""
            QFrame { 
                background:#fcfcfc; border:1px solid #f0f0f0; border-radius:8px;
            }
            QFrame:hover { background:#f5f5f5; border:1px solid #e0e0e0; }
        """)
        
        # Để click được
        def on_click(event, u=member["username"]):
            self._on_view_member_history(u)
        row.mousePressEvent = on_click

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
        contrib_lbl.setStyleSheet("border:none; background:transparent; color:#1A2B45;")
        rl.addWidget(contrib_lbl)
        
        arrow = QLabel(" › ")
        arrow.setStyleSheet("color:#999; font-size:24px; border:none; background:transparent;")
        rl.addWidget(arrow)

        return row

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_create_group(self):
        dlg = CustomInputDialog("Tạo nhóm quỹ", "Tên quỹ:", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = dlg.get_text()
        if not name.strip():
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
        dlg = CustomInputDialog("Tham gia quỹ", "Nhập mã mời (6 ký tự):", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        code = dlg.get_text()
        if not code.strip():
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
        self.refresh()

    def _on_manage_members(self, group_id: int):
        members = self.fm.get_members(group_id)
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Quản lý thành viên")
        dlg.resize(480, 360)
        dlg.setStyleSheet("""
            QDialog { background: #ffffff; }
            QTableWidget { font-size: 14px; background: #ffffff; color: #1A2B45; border: 1px solid #dde6ef; border-radius: 8px; }
            QTableWidget::item { padding: 10px 14px; color: #1A2B45; }
            QHeaderView::section {
                font-size: 13px;
                font-weight: bold;
                background-color: #1A6BAF;
                color: #ffffff;
                padding: 10px 14px;
                border: none;
                border-right: 1px solid #155c96;
            }
            QPushButton { font-size: 13px; padding: 7px 16px; border-radius: 6px; font-weight: bold; }
        """)
        
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Thành viên", "Hành động"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        # Lọc ra các thành viên không phải owner
        members_to_manage = [m for m in members if m["role"] != "owner"]
        table.setRowCount(len(members_to_manage))
        
        for i, m in enumerate(members_to_manage):
            table.setItem(i, 0, QTableWidgetItem(m["username"]))
            
            btn_remove = QPushButton("Xóa")
            btn_remove.setStyleSheet("QPushButton { background: #C0392B; color: white; border: none; border-radius: 5px; padding: 6px 14px; font-size: 13px; font-weight: bold; } QPushButton:hover { background: #a93226; }")
            
            def make_remove_callback(username):
                def remove():
                    reply = QMessageBox.question(dlg, "Xác nhận", f"Bạn có chắc muốn xóa {username} khỏi quỹ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        res = self.fm.remove_member(group_id, username)
                        if res["success"]:
                            QMessageBox.information(dlg, "Thành công", res["message"])
                            dlg.accept()
                            self.refresh()
                        else:
                            QMessageBox.warning(dlg, "Lỗi", res["message"])
                return remove
                
            btn_remove.clicked.connect(make_remove_callback(m["username"]))
            table.setCellWidget(i, 1, btn_remove)
            
        layout.addWidget(table)
        
        btn_close = QPushButton("Đóng")
        btn_close.setStyleSheet("QPushButton { background: #f0f0f0; color: #333; border: 1px solid #ccc; border-radius: 7px; padding: 9px 24px; font-size: 14px; font-weight: bold; } QPushButton:hover { background: #e0e0e0; }")
        btn_close.clicked.connect(dlg.reject)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        
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

    def _on_add_member(self, group_id: int):
        dlg = CustomInputDialog("Thêm thành viên", "Nhập số điện thoại:", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        phone = dlg.get_text().strip()
        if not phone:
            return

        from app.data.auth_manager import AuthManager
        auth_mgr = AuthManager()
        user_info = auth_mgr.find_user_by_phone(phone)
        
        if not user_info:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy thành viên với số điện thoại này.")
            return
            
        reply = QMessageBox.question(
            self, "Xác nhận thêm thành viên",
            f"Đã tìm thấy thành viên:\n\n"
            f"Tên: {user_info['full_name']}\n"
            f"Username: {user_info['username']}\n\n"
            "Bạn có muốn thêm thành viên này vào quỹ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        result = self.fm.add_member_by_username(group_id, user_info['username'])
        if result["success"]:
            QMessageBox.information(self, "Thành công", result["message"])
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

