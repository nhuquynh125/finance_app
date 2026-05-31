# app/ui/settings_frame.py  (cap nhat: them tab Thong tin nguoi dung)
"""
Thay doi:
  - Them QTabWidget de phan chia thanh 2 tab:
      Tab 1: "Ung dung"  -- toan bo cai dat cu
      Tab 2: "Tai khoan" -- them / sua / xoa thong tin ca nhan, doi mat khau
  - UserProfileTab: hien thi avatar, sua ho ten, vai tro (admin only: quan ly user list)
  - Doi mat khau khong can dang xuat
  - Admin: xem danh sach user, khoa / xoa tai khoan

FIX: Sua merge conflict trong import theme_engine (dung app.core.theme_engine)
"""

import os
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QComboBox, QCheckBox,
    QLineEdit, QMessageBox, QSizePolicy, QFileDialog,
    QTabWidget, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QSpacerItem
)

from app.core.settings_manager import (
    backup_database, export_database_to_excel, get_env_value, load_settings,
    package_status, restore_database, save_settings, update_env_value,
    get_exports_dir, _get_settings_path, _get_db_path
)
from app.core.sync_manager import SyncManager
# FIX: Su dung import chinh xac, loai bo merge conflict
from app.core.theme_engine import theme_engine

try:
    from config import APP_NAME, APP_VERSION, DATA_DIR, DB_PATH
except ImportError:
    APP_NAME    = "Finance AI"
    APP_VERSION = "1.0"
    DATA_DIR    = Path("data")
    DB_PATH     = Path("data") / "finance.db"


def _get_user_data_dir() -> Path:
    try:
        from user_session import session
        if session.is_logged_in:
            return session.data_dir
    except ImportError:
        pass
    return Path(DATA_DIR)


# ==============================================================================
# Tab 1 -- Thong tin tai khoan & quan ly nguoi dung
# ==============================================================================

class UserProfileTab(QWidget):
    """Tab quan ly thong tin ca nhan va (neu admin) danh sach user."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._build()
        QTimer.singleShot(100, self.refresh)

    # -- Build --

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f5f5f5; }")

        content = QWidget()
        content.setStyleSheet("background:#f5f5f5;")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(16, 16, 16, 16)
        self.body.setSpacing(14)

        self._build_profile_card()
        self._build_change_password_card()
        self._build_admin_card()
        self._build_danger_zone()
        self.body.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    # -- Profile card --

    def _build_profile_card(self):
        panel = self._panel_frame("Thong tin ca nhan")
        pl = panel.layout()

        top_row = QHBoxLayout()
        self.avatar_lbl = QLabel("?")
        self.avatar_lbl.setFixedSize(64, 64)
        self.avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_lbl.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.avatar_lbl.setStyleSheet(
            "background:#378ADD; color:white; border-radius:32px; border:none;")
        top_row.addWidget(self.avatar_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.username_badge = QLabel("@--")
        self.username_badge.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.username_badge.setStyleSheet("color:#1A2B45; border:none;")
        self.role_badge = QLabel("--")
        self.role_badge.setStyleSheet(
            "QLabel { background:#EAF3DE; color:#3B6D11; border:none; "
            "border-radius:10px; padding:2px 10px; font-size:11px; }")
        self.last_login_lbl = QLabel("")
        self.last_login_lbl.setStyleSheet("color:#aaa; font-size:11px; border:none;")
        info_col.addWidget(self.username_badge)
        info_col.addWidget(self.role_badge)
        info_col.addWidget(self.last_login_lbl)
        info_col.addStretch()
        top_row.addLayout(info_col)
        top_row.addStretch()
        pl.addLayout(top_row)

        pl.addWidget(self._divider())

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.le_fullname = QLineEdit()
        self.le_fullname.setPlaceholderText("Ho va ten day du...")
        self.le_fullname.setStyleSheet(self._input_style())
        form.addRow("Ho va ten:", self.le_fullname)

        self.le_phone = QLineEdit()
        self.le_phone.setPlaceholderText("0912 345 678 (dinh danh chinh cua tai khoan)")
        self.le_phone.setStyleSheet(self._input_style())
        form.addRow("So dien thoai *:", self.le_phone)

        self.le_username = QLineEdit()
        self.le_username.setReadOnly(True)
        self.le_username.setStyleSheet(
            self._input_style() + " background:#f7f7f7; color:#999;")
        form.addRow("Ten dang nhap:", self.le_username)

        pl.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("Luu thong tin")
        btn_save.setStyleSheet(self._btn_primary())
        btn_save.clicked.connect(self._save_profile)
        btn_row.addWidget(btn_save)
        pl.addLayout(btn_row)

        self.body.addWidget(panel)

    # -- Doi mat khau --

    def _build_change_password_card(self):
        panel = self._panel_frame("Doi mat khau")
        pl = panel.layout()

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.le_old_pw = QLineEdit()
        self.le_old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_old_pw.setPlaceholderText("Mat khau hien tai...")
        self.le_old_pw.setStyleSheet(self._input_style())
        form.addRow("Mat khau cu:", self.le_old_pw)

        self.le_new_pw = QLineEdit()
        self.le_new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_new_pw.setPlaceholderText("Toi thieu 6 ky tu...")
        self.le_new_pw.setStyleSheet(self._input_style())
        form.addRow("Mat khau moi:", self.le_new_pw)

        self.le_confirm_pw = QLineEdit()
        self.le_confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_confirm_pw.setPlaceholderText("Nhap lai mat khau moi...")
        self.le_confirm_pw.setStyleSheet(self._input_style())
        form.addRow("Xac nhan:", self.le_confirm_pw)

        pl.addLayout(form)

        self.pw_msg = QLabel("")
        self.pw_msg.setWordWrap(True)
        self.pw_msg.hide()
        pl.addWidget(self.pw_msg)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_pw = QPushButton("Doi mat khau")
        btn_pw.setStyleSheet(self._btn_normal())
        btn_pw.clicked.connect(self._change_password)
        btn_row.addWidget(btn_pw)
        pl.addLayout(btn_row)

        self.body.addWidget(panel)

    # -- Admin panel --

    def _build_admin_card(self):
        """Panel chi hien voi admin -- quan ly danh sach user."""
        self.admin_panel = self._panel_frame("Quan ly nguoi dung (Admin)")

        pl = self.admin_panel.layout()

        header_row = QHBoxLayout()
        desc = QLabel("Xem va quan ly toan bo tai khoan trong he thong.")
        desc.setStyleSheet("color:#888; font-size:12px; border:none;")
        header_row.addWidget(desc)
        header_row.addStretch()
        btn_add_user = QPushButton("Them user")
        btn_add_user.setStyleSheet(self._btn_primary())
        btn_add_user.clicked.connect(self._open_add_user_dialog)
        header_row.addWidget(btn_add_user)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(64)
        btn_refresh.setStyleSheet(self._btn_normal())
        btn_refresh.clicked.connect(self._load_user_table)
        header_row.addWidget(btn_refresh)
        pl.addLayout(header_row)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(7)
        self.user_table.setHorizontalHeaderLabels(
            ["Username", "Ho ten", "SDT", "Vai tro", "Trang thai", "Dang nhap cuoi", ""])
        self.user_table.setStyleSheet("""
            QTableWidget {
                background:#fff; border:1px solid #e8e8e8;
                border-radius:8px; gridline-color:#f0f0f0; font-size:12px;
            }
            QTableWidget::item { padding:6px 10px; color:#333; }
            QTableWidget::item:selected { background:#E6F1FB; color:#0C447C; }
            QHeaderView::section {
                background:#f7f7f7; color:#888;
                font-size:10px; font-weight:bold;
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

    # -- Danger zone --

    def _build_danger_zone(self):
        panel = self._panel_frame("Vung nguy hiem")
        panel.setStyleSheet(
            "QFrame { background:#fff8f8; border:1px solid #fcc; border-radius:10px; }")
        pl = panel.layout()

        row = QHBoxLayout()
        col = QVBoxLayout()
        title = QLabel("Xoa tai khoan")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color:#A32D2D; border:none;")
        desc = QLabel(
            "Xoa vinh vien tai khoan va toan bo du lieu tai chinh.\n"
            "Hanh dong nay KHONG THE hoan tac.")
        desc.setStyleSheet("color:#888; font-size:11px; border:none;")
        desc.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(desc)
        row.addLayout(col)
        row.addStretch()

        btn_delete = QPushButton("Xoa tai khoan")
        btn_delete.setStyleSheet(self._btn_danger())
        btn_delete.clicked.connect(self._delete_own_account)
        row.addWidget(btn_delete)
        pl.addLayout(row)

        self.body.addWidget(panel)

    # -- Refresh --

    def refresh(self):
        try:
            from user_session import session
            if not session.is_logged_in:
                return

            initial = (session.full_name or session.username)[0].upper()
            self.avatar_lbl.setText(initial)
            self.username_badge.setText(f"@{session.username}")
            self.le_username.setText(session.username)
            self.le_fullname.setText(session.full_name or "")

            try:
                conn_tmp = self._auth_conn()
                row_tmp = conn_tmp.execute(
                    "SELECT phone FROM users WHERE username=?",
                    (session.username,)
                ).fetchone()
                conn_tmp.close()
                self.le_phone.setText(
                    row_tmp["phone"] if row_tmp and row_tmp["phone"] else "")
            except Exception:
                self.le_phone.setText("")

            role_map = {"admin": "Quan tri vien", "user": "Nguoi dung"}
            role_text = role_map.get(session.role, session.role)
            self.role_badge.setText(role_text)

            conn = self._auth_conn()
            row = conn.execute(
                "SELECT last_login FROM users WHERE username=?",
                (session.username,)
            ).fetchone()
            conn.close()
            if row and row["last_login"]:
                self.last_login_lbl.setText(f"Dang nhap lan cuoi: {row['last_login'][:16]}")
            else:
                self.last_login_lbl.setText("")

            if session.role == "admin":
                self.admin_panel.show()
                self._load_user_table()
            else:
                self.admin_panel.hide()

        except Exception as e:
            print(f"[UserProfileTab] refresh error: {e}")

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
                self._tbl_item(r, 2, row["phone"] or "--", "#888")
                role_map = {"admin": "Quan tri vien", "user": "Nguoi dung"}
                self._tbl_item(r, 3, role_map.get(row["role"], row["role"]))

                status_item = QTableWidgetItem(
                    "Hoat dong" if row["is_active"] else "Khoa")
                status_item.setForeground(
                    QColor("#1D9E75") if row["is_active"] else QColor("#E24B4A"))
                self.user_table.setItem(r, 4, status_item)

                ll = (row["last_login"] or "Chua dang nhap")[:16]
                self._tbl_item(r, 5, ll, "#888")

                if row["username"] != current_username:
                    btn_w = QWidget()
                    btn_l = QHBoxLayout(btn_w)
                    btn_l.setContentsMargins(4, 2, 4, 2)
                    btn_l.setSpacing(4)

                    btn_edit = QPushButton("Sua")
                    btn_edit.setFixedSize(40, 22)
                    btn_edit.setStyleSheet(
                        "QPushButton { background:#E6F1FB; color:#0C447C; "
                        "border:none; border-radius:4px; font-size:10px; } "
                        "QPushButton:hover { background:#B5D4F4; }")
                    btn_edit.clicked.connect(
                        lambda _, u=dict(row): self._open_edit_user_dialog(u))

                    btn_toggle = QPushButton(
                        "Khoa" if row["is_active"] else "Mo")
                    btn_toggle.setFixedSize(40, 22)
                    btn_toggle.setStyleSheet(
                        "QPushButton { background:#FAEEDA; color:#633806; "
                        "border:none; border-radius:4px; font-size:10px; } "
                        "QPushButton:hover { background:#f5d5a0; }")
                    btn_toggle.clicked.connect(
                        lambda _, uid=row["id"], cur=bool(row["is_active"]):
                            self._toggle_user_active(uid, cur))

                    btn_del = QPushButton("Xoa")
                    btn_del.setFixedSize(40, 22)
                    btn_del.setStyleSheet(
                        "QPushButton { background:#FCEBEB; color:#A32D2D; "
                        "border:none; border-radius:4px; font-size:10px; } "
                        "QPushButton:hover { background:#f5c6cb; }")
                    btn_del.clicked.connect(
                        lambda _, uname=row["username"]:
                            self._delete_user(uname))

                    btn_l.addWidget(btn_edit)
                    btn_l.addWidget(btn_toggle)
                    btn_l.addWidget(btn_del)
                    self.user_table.setCellWidget(r, 6, btn_w)
                else:
                    me = QLabel("(ban)")
                    me.setStyleSheet("color:#aaa; font-size:11px; padding:0 6px;")
                    self.user_table.setCellWidget(r, 6, me)

            self.user_table.resizeRowsToContents()
        except Exception as e:
            print(f"[UserProfileTab] _load_user_table error: {e}")

    # -- Actions --

    def _save_profile(self):
        full_name = self.le_fullname.text().strip()
        phone_raw = self.le_phone.text().strip()

        if not full_name:
            self._msg_box("Loi", "Ho ten khong duoc de trong.", "warning")
            return

        if not phone_raw:
            self._msg_box("Loi", "So dien thoai la dinh danh chinh, khong duoc de trong.", "warning")
            return
        from app.data.auth_manager import _validate_phone
        ok, result = _validate_phone(phone_raw)
        if not ok:
            self._msg_box("Loi SDT", result, "warning")
            return
        phone_normalized = result

        try:
            from user_session import session

            if phone_normalized:
                _c = self._auth_conn()
                dup = _c.execute(
                    "SELECT username FROM users WHERE phone=? AND username!=?",
                    (phone_normalized, session.username)
                ).fetchone()
                _c.close()
                if dup:
                    self._msg_box(
                        "Loi SDT",
                        "So dien thoai nay da duoc dung boi tai khoan khac.",
                        "warning"
                    )
                    return

            conn = self._auth_conn()
            conn.execute(
                "UPDATE users SET full_name=?, phone=? WHERE username=?",
                (full_name, phone_normalized, session.username)
            )
            conn.commit()
            conn.close()

            session._user["full_name"] = full_name

            if self.main_window:
                self.main_window.setWindowTitle(f"Finance AI -- {full_name}")

            self._msg_box("Thanh cong", "Da cap nhat thong tin ca nhan!", "info")
            self.refresh()
        except Exception as e:
            self._msg_box("Loi", str(e), "critical")

    def _change_password(self):
        old_pw  = self.le_old_pw.text()
        new_pw  = self.le_new_pw.text()
        confirm = self.le_confirm_pw.text()

        if not old_pw or not new_pw:
            self._show_pw_msg("Vui long dien day du thong tin.", "error")
            return
        if len(new_pw) < 6:
            self._show_pw_msg("Mat khau moi phai co it nhat 6 ky tu.", "error")
            return
        if new_pw != confirm:
            self._show_pw_msg("Mat khau xac nhan khong khop.", "error")
            return

        try:
            import hashlib, secrets as _sec
            from user_session import session

            conn = self._auth_conn()
            row = conn.execute(
                "SELECT password_hash, salt FROM users WHERE username=?",
                (session.username,)
            ).fetchone()

            if not row:
                self._show_pw_msg("Khong tim thay tai khoan.", "error")
                conn.close()
                return

            expected = hashlib.sha256(
                (row["salt"] + old_pw).encode()).hexdigest()
            if expected != row["password_hash"]:
                self._show_pw_msg("Mat khau cu khong dung.", "error")
                conn.close()
                return

            new_salt    = _sec.token_hex(16)
            new_hash    = hashlib.sha256((new_salt + new_pw).encode()).hexdigest()
            conn.execute(
                "UPDATE users SET password_hash=?, salt=? WHERE username=?",
                (new_hash, new_salt, session.username)
            )
            conn.commit()
            conn.close()

            self.le_old_pw.clear()
            self.le_new_pw.clear()
            self.le_confirm_pw.clear()
            self._show_pw_msg("Doi mat khau thanh cong!", "success")
        except Exception as e:
            self._show_pw_msg(str(e), "error")

    def _delete_own_account(self):
        from user_session import session

        reply = QMessageBox.warning(
            self, "Xoa tai khoan",
            f"Ban sap xoa tai khoan '@{session.username}' va toan bo du lieu tai chinh.\n\n"
            "Hanh dong nay KHONG THE hoan tac!\n\nBan co chac chan?",
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

            QMessageBox.information(self, "Da xoa", "Tai khoan da duoc xoa. App se dong.")

            from app.data.auth_manager import AuthManager
            AuthManager().logout()

            from app.ui.login_window import LoginWindow
            self._login_window = LoginWindow()
            self._login_window.show()
            if self.main_window:
                self.main_window.close()

        except Exception as e:
            self._msg_box("Loi", str(e), "critical")

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
        action = "khoa" if current_active else "mo khoa"
        reply = QMessageBox.question(
            self, "Xac nhan",
            f"Ban muon {action} tai khoan nay?",
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
            self._msg_box("Loi", str(e), "critical")

    def _delete_user(self, username: str):
        reply = QMessageBox.warning(
            self, "Xoa tai khoan",
            f"Xoa tai khoan '@{username}'?\n\n"
            "Du lieu tai chinh trong thu muc cua user van con tren o dia.",
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
            self._msg_box("Loi", str(e), "critical")

    # -- Helpers --

    @staticmethod
    def _auth_conn():
        import sqlite3
        from user_session import session
        path = session.auth_db_path
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _show_pw_msg(self, msg: str, kind: str):
        colors = {
            "error":   ("background:#FEF0F0; color:#C0392B; border:1px solid #F5C6CB;"),
            "success": ("background:#EAF3DE; color:#2D7D1A; border:1px solid #B8DFAA;"),
        }
        self.pw_msg.setStyleSheet(
            f"QLabel {{ {colors.get(kind, colors['error'])} "
            f"border-radius:8px; padding:8px 12px; font-size:12px; }}")
        self.pw_msg.setText(msg)
        self.pw_msg.show()
        QTimer.singleShot(5000, self.pw_msg.hide)

    def _tbl_item(self, row, col, text, color="#333"):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        self.user_table.setItem(row, col, item)

    @staticmethod
    def _panel_frame(title: str) -> QFrame:
        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        panel.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#1A2B45; border:none;")
        layout.addWidget(lbl)
        return panel

    @staticmethod
    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background:#e8e8e8; border:none; max-height:1px;")
        return line

    @staticmethod
    def _input_style():
        return ("QLineEdit { border:1px solid #ddd; border-radius:6px; "
                "padding:7px 10px; font-size:12px; background:#fff; color:#222; }")

    @staticmethod
    def _btn_primary():
        return ("QPushButton { background:#E6F1FB; color:#0C447C; "
                "border:1px solid #B5D4F4; border-radius:6px; "
                "padding:7px 16px; font-size:12px; font-weight:500; } "
                "QPushButton:hover { background:#B5D4F4; }")

    @staticmethod
    def _btn_normal():
        return ("QPushButton { background:#fff; color:#555; "
                "border:1px solid #ddd; border-radius:6px; "
                "padding:7px 12px; font-size:12px; } "
                "QPushButton:hover { background:#f5f5f5; }")

    @staticmethod
    def _btn_danger():
        return ("QPushButton { background:#fff; color:#A32D2D; "
                "border:1px solid #E24B4A; border-radius:6px; "
                "padding:7px 14px; font-size:12px; } "
                "QPushButton:hover { background:#FCEBEB; }")

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


# ==============================================================================
# Dialogs phu
# ==============================================================================

class _ConfirmPasswordDialog(QDialog):
    """Yeu cau nhap mat khau xac nhan truoc khi xoa tai khoan."""

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.setWindowTitle("Xac nhan danh tinh")
        self.setFixedSize(360, 200)
        self.setStyleSheet("QDialog { background:#fff; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        lbl = QLabel(f"Nhap mat khau cua @{self.username} de xac nhan xoa:")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size:12px; color:#444; border:none;")
        layout.addWidget(lbl)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Mat khau...")
        self.pw_input.setStyleSheet(
            "QLineEdit { border:1px solid #ddd; border-radius:6px; "
            "padding:7px 10px; font-size:13px; }")
        self.pw_input.returnPressed.connect(self._verify)
        layout.addWidget(self.pw_input)

        self.err_lbl = QLabel("")
        self.err_lbl.setStyleSheet("color:#E24B4A; font-size:11px; border:none;")
        self.err_lbl.hide()
        layout.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Huy")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; border:1px solid #ddd; "
            "border-radius:6px; padding:6px 14px; }")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Xac nhan xoa")
        btn_ok.setStyleSheet(
            "QPushButton { background:#E24B4A; color:#fff; border:none; "
            "border-radius:6px; padding:6px 14px; font-weight:500; } "
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
                self.err_lbl.setText("Tai khoan khong ton tai.")
                self.err_lbl.show()
                return
            expected = hashlib.sha256(
                (row["salt"] + self.pw_input.text()).encode()).hexdigest()
            if expected != row["password_hash"]:
                self.err_lbl.setText("Mat khau khong dung.")
                self.err_lbl.show()
                return
            self.accept()
        except Exception as e:
            self.err_lbl.setText(str(e))
            self.err_lbl.show()


class _AddUserDialog(QDialog):
    """Dialog them user moi (admin only)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Them nguoi dung moi")
        self.setFixedSize(400, 300)
        self.setStyleSheet("QDialog { background:#fff; } "
                           "QLabel { font-size:12px; color:#444; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        _s = ("QLineEdit,QComboBox { border:1px solid #ddd; border-radius:6px; "
              "padding:7px 10px; font-size:12px; background:#fff; color:#222; }")

        self.le_fullname = QLineEdit()
        self.le_fullname.setPlaceholderText("Ho va ten")
        self.le_fullname.setStyleSheet(_s)
        form.addRow("Ho ten:", self.le_fullname)

        self.le_username = QLineEdit()
        self.le_username.setPlaceholderText("3-30 ky tu, khong dau cach")
        self.le_username.setStyleSheet(_s)
        form.addRow("Username:", self.le_username)

        self.le_pw = QLineEdit()
        self.le_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_pw.setPlaceholderText("Toi thieu 6 ky tu")
        self.le_pw.setStyleSheet(_s)
        form.addRow("Mat khau:", self.le_pw)

        self.cb_role = QComboBox()
        self.cb_role.addItem("Nguoi dung", "user")
        self.cb_role.addItem("Quan tri vien", "admin")
        self.cb_role.setStyleSheet(_s)
        form.addRow("Vai tro:", self.cb_role)

        layout.addLayout(form)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Huy")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; border:1px solid #ddd; "
            "border-radius:6px; padding:7px 14px; }")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Them user")
        btn_ok.setStyleSheet(
            "QPushButton { background:#E6F1FB; color:#0C447C; "
            "border:1px solid #B5D4F4; border-radius:6px; "
            "padding:7px 16px; font-weight:500; } "
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
            self._show_msg("Vui long dien day du thong tin.", "error")
            return
        if len(username) < 3:
            self._show_msg("Username phai co it nhat 3 ky tu.", "error")
            return
        if len(password) < 6:
            self._show_msg("Mat khau phai co it nhat 6 ky tu.", "error")
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
            f"QLabel {{ {c} border-radius:8px; padding:8px 12px; font-size:12px; }}")
        self.msg_lbl.setText(msg)
        self.msg_lbl.show()


class _EditUserDialog(QDialog):
    """Dialog sua thong tin user (admin only)."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"Sua thong tin @{user['username']}")
        self.setFixedSize(400, 260)
        self.setStyleSheet("QDialog { background:#fff; } "
                           "QLabel { font-size:12px; color:#444; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        _s = ("QLineEdit,QComboBox { border:1px solid #ddd; border-radius:6px; "
              "padding:7px 10px; font-size:12px; background:#fff; color:#222; }")

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.le_fullname = QLineEdit(self.user.get("full_name") or "")
        self.le_fullname.setStyleSheet(_s)
        form.addRow("Ho ten:", self.le_fullname)

        un = QLineEdit(self.user.get("username") or "")
        un.setReadOnly(True)
        un.setStyleSheet(_s + " background:#f7f7f7; color:#999;")
        form.addRow("Username:", un)

        self.cb_role = QComboBox()
        self.cb_role.addItem("Nguoi dung", "user")
        self.cb_role.addItem("Quan tri vien", "admin")
        self.cb_role.setStyleSheet(_s)
        idx = self.cb_role.findData(self.user.get("role", "user"))
        if idx >= 0:
            self.cb_role.setCurrentIndex(idx)
        form.addRow("Vai tro:", self.cb_role)

        self.le_reset_pw = QLineEdit()
        self.le_reset_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_reset_pw.setPlaceholderText("De trong = khong doi")
        self.le_reset_pw.setStyleSheet(_s)
        form.addRow("Dat lai mat khau:", self.le_reset_pw)

        layout.addLayout(form)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.hide()
        layout.addWidget(self.msg_lbl)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Huy")
        btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; border:1px solid #ddd; "
            "border-radius:6px; padding:7px 14px; }")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Luu")
        btn_ok.setStyleSheet(
            "QPushButton { background:#E6F1FB; color:#0C447C; "
            "border:1px solid #B5D4F4; border-radius:6px; "
            "padding:7px 16px; font-weight:500; } "
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
            self._show_msg("Ho ten khong duoc de trong.", "error")
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
                    self._show_msg("Mat khau moi phai co it nhat 6 ky tu.", "error")
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
            f"QLabel {{ {c} border-radius:8px; padding:8px 12px; font-size:12px; }}")
        self.msg_lbl.setText(msg)
        self.msg_lbl.show()


# ==============================================================================
# Main SettingsFrame -- dung QTabWidget
# ==============================================================================

class SettingsFrame(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.settings = load_settings()
        self._build()
        self._initial_refresh()

    def _initial_refresh(self):
        self.settings = load_settings()
        self.currency_combo.setCurrentText(self.settings["currency"])
        self.date_combo.setCurrentText(self.settings["date_format"])
        self._set_combo_data(self.month_combo, self.settings["default_month"])
        self.auto_refresh_check.setChecked(bool(self.settings["auto_refresh"]))
        self._set_combo_data(self.window_mode_combo, self.settings.get("window_mode", "default"))
        self._set_combo_data(self.theme_combo, theme_engine.mode)
        self.auto_classify_check.setChecked(bool(self.settings["auto_classification"]))
        self.anomaly_check.setChecked(bool(self.settings["anomaly_detection"]))
        self._set_combo_data(self.forecast_combo, self.settings["forecast_method"])
        self._set_combo_data(self.chat_engine_combo, self.settings["chat_engine"])
        self.gemini_key.setText(get_env_value("GEMINI_API_KEY"))
        self.supabase_url.setText(get_env_value("SUPABASE_URL"))
        self.supabase_key.setText(get_env_value("SUPABASE_KEY"))

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #f5f5f5;
            }
            QTabBar::tab {
                background: #fff;
                color: #888;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 10px 20px;
                font-size: 12px;
                font-family: 'Segoe UI';
                min-width: 120px;
            }
            QTabBar::tab:selected {
                color: #378ADD;
                border-bottom: 2px solid #378ADD;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #f5f5f5;
                color: #378ADD;
            }
            QTabWidget > QTabBar {
                background: #fff;
                border-bottom: 1px solid #e8e8e8;
            }
        """)

        self.app_tab = self._build_app_tab()
        self.tabs.addTab(self.app_tab, "Ung dung")

        self.profile_tab = UserProfileTab(main_window=self.main_window)
        self.tabs.addTab(self.profile_tab, "Tai khoan")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index: int):
        if index == 1:
            self.profile_tab.refresh()

    # -- Toolbar --

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        title = QLabel("Cai dat")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#1D9E75; font-size:12px; border:none;")
        layout.addWidget(self.status_label)

        btn_reload = QPushButton("Tai lai")
        btn_reload.setStyleSheet(self._btn_normal())
        btn_reload.clicked.connect(self.refresh)
        layout.addWidget(btn_reload)

        btn_save = QPushButton("Luu cai dat")
        btn_save.setStyleSheet(self._btn_primary())
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)
        return bar

    # -- Tab Ung dung --

    def _build_app_tab(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background:#f5f5f5;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f5f5f5; }")

        content = QWidget()
        content.setStyleSheet("background:#f5f5f5;")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(16, 14, 16, 16)
        self.body.setSpacing(12)

        self._build_app_info()
        self._build_general_settings()
        self._build_ai_settings()
        self._build_api_settings()
        self._build_data_tools()
        self._build_cloud_sync()
        self.body.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        return widget

    def _build_app_info(self):
        panel, grid = self._panel("Thong tin ung dung")

        try:
            from user_session import session
            if session.is_logged_in:
                self._add_readonly(grid, 0, "Nguoi dung",
                    f"{session.full_name} (@{session.username})")
                self._add_readonly(grid, 1, "Database",
                    str(session.db_path))
                self._add_readonly(grid, 2, "Thu muc du lieu",
                    str(session.data_dir))
                self._add_readonly(grid, 3, "Ten ung dung", APP_NAME)
                self._add_readonly(grid, 4, "Phien ban", APP_VERSION)
            else:
                self._add_readonly(grid, 0, "Ten ung dung", APP_NAME)
                self._add_readonly(grid, 1, "Phien ban", APP_VERSION)
                self._add_readonly(grid, 2, "Database", str(_get_db_path()))
        except ImportError:
            self._add_readonly(grid, 0, "Ten ung dung", APP_NAME)
            self._add_readonly(grid, 1, "Phien ban", APP_VERSION)
            self._add_readonly(grid, 2, "Database", str(_get_db_path()))

        self.body.addWidget(panel)

    def _build_general_settings(self):
        panel, grid = self._panel("Cai dat chung")

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["VND", "USD", "EUR"])
        self._add_control(grid, 0, "Tien te mac dinh", self.currency_combo)

        self.date_combo = QComboBox()
        self.date_combo.addItems(["dd/MM/yyyy", "yyyy-MM-dd", "MM/dd/yyyy"])
        self._add_control(grid, 1, "Dinh dang ngay", self.date_combo)

        self.month_combo = QComboBox()
        self.month_combo.addItem("Thang hien tai", "current")
        self.month_combo.addItem("Thang gan nhat co du lieu", "latest_data")
        self._add_control(grid, 2, "Thang mac dinh", self.month_combo)

        self.auto_refresh_check = QCheckBox("Tu dong lam moi du lieu")
        self.auto_refresh_check.setStyleSheet(self._check_style())
        self._add_control(grid, 3, "Lam moi", self.auto_refresh_check)

        self.window_mode_combo = QComboBox()
        self.window_mode_combo.addItem("Mac dinh (1150x700)", "default")
        self.window_mode_combo.addItem("Lon (1366x768)", "large")
        self.window_mode_combo.addItem("Toan man hinh", "fullscreen")
        self._add_control(grid, 4, "Che do cua so", self.window_mode_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Sang", "light")
        self.theme_combo.addItem("Toi", "dark")
        self.theme_combo.addItem("Theo he thong", "auto")
        self.theme_combo.currentIndexChanged.connect(
            lambda: theme_engine.set_mode(self.theme_combo.currentData())
        )
        self._add_control(grid, 5, "Chu de UI", self.theme_combo)

        accent_row = QWidget()
        accent_row.setStyleSheet("background:transparent;")
        accent_layout = QHBoxLayout(accent_row)
        accent_layout.setContentsMargins(0, 0, 0, 0)
        accent_layout.setSpacing(6)
        for name, hex_color in theme_engine.ACCENTS.items():
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(name)
            btn.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #ccc; border-radius: 12px;")
            btn.clicked.connect(lambda _, c=hex_color: theme_engine.set_accent(c))
            accent_layout.addWidget(btn)
        accent_layout.addStretch()
        self._add_control(grid, 6, "Mau nhan (Accent)", accent_row)

        self.body.addWidget(panel)

    def _build_ai_settings(self):
        panel, grid = self._panel("Cai dat AI")

        self.auto_classify_check = QCheckBox("Tu dong phan loai giao dich")
        self.auto_classify_check.setStyleSheet(self._check_style())
        self._add_control(grid, 0, "Phan loai", self.auto_classify_check)

        self.anomaly_check = QCheckBox("Bat phat hien bat thuong")
        self.anomaly_check.setStyleSheet(self._check_style())
        self._add_control(grid, 1, "Bat thuong", self.anomaly_check)

        self.forecast_combo = QComboBox()
        self.forecast_combo.addItem("Tu dong", "auto")
        self.forecast_combo.addItem("Trung binh dong", "moving_average")
        self.forecast_combo.addItem("Prophet neu co", "prophet")
        self._add_control(grid, 2, "Phuong phap du bao", self.forecast_combo)

        self.chat_engine_combo = QComboBox()
        self.chat_engine_combo.addItem("Gemini API", "gemini")
        self.chat_engine_combo.addItem("Ollama offline", "ollama")
        self.chat_engine_combo.addItem("Model nhung", "embedded")
        self._add_control(grid, 3, "Engine chatbot", self.chat_engine_combo)

        self.package_labels = {}
        status_row = QWidget()
        status_row.setStyleSheet("background:transparent;")
        row = QHBoxLayout(status_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for package in ["sklearn", "prophet", "torch"]:
            lbl = QLabel(package)
            lbl.setStyleSheet(self._badge_style(False))
            self.package_labels[package] = lbl
            row.addWidget(lbl)
        row.addStretch()
        self._add_control(grid, 4, "Trang thai package", status_row)
        self.body.addWidget(panel)

        QTimer.singleShot(200, self._refresh_package_status)

    def _build_api_settings(self):
        panel, grid = self._panel("Cau hinh API & Cloud")

        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText("GEMINI_API_KEY")
        self.gemini_key.setStyleSheet(self._input_style())
        self._add_control(grid, 0, "Gemini Key", self.gemini_key)

        self.supabase_url = QLineEdit()
        self.supabase_url.setPlaceholderText("https://xyz.supabase.co")
        self.supabase_url.setStyleSheet(self._input_style())
        self._add_control(grid, 1, "Supabase URL", self.supabase_url)

        self.supabase_key = QLineEdit()
        self.supabase_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.supabase_key.setPlaceholderText("Supabase Anon/Service Key")
        self.supabase_key.setStyleSheet(self._input_style())
        self._add_control(grid, 2, "Supabase Key", self.supabase_key)

        self.body.addWidget(panel)

    def _build_data_tools(self):
        panel, grid = self._panel("Quan ly du lieu")

        btn_backup = QPushButton("Sao luu database")
        btn_backup.setStyleSheet(self._btn_primary())
        btn_backup.clicked.connect(self._backup_db)
        self._add_control(grid, 0, "Backup", btn_backup)

        btn_export = QPushButton("Xuat Excel")
        btn_export.setStyleSheet(self._btn_normal())
        btn_export.clicked.connect(self._export_excel)
        self._add_control(grid, 1, "Xuat du lieu", btn_export)

        btn_restore = QPushButton("Phuc hoi database")
        btn_restore.setStyleSheet(self._btn_danger())
        btn_restore.clicked.connect(self._restore_db)
        self._add_control(grid, 2, "Phuc hoi", btn_restore)

        btn_folder = QPushButton("Mo thu muc du lieu")
        btn_folder.setStyleSheet(self._btn_normal())
        btn_folder.clicked.connect(self._open_data_folder)
        self._add_control(grid, 3, "Thu muc", btn_folder)

        self.backup_info = QLabel("")
        self.backup_info.setWordWrap(True)
        self.backup_info.setStyleSheet("color:#888; font-size:11px; border:none;")
        self._add_control(grid, 4, "Trang thai", self.backup_info)

        self.body.addWidget(panel)

    def _build_cloud_sync(self):
        panel, grid = self._panel("Dong bo dam may (Cloud Sync)")

        self.cloud_provider = QComboBox()
        self.cloud_provider.addItems(["Google Drive", "Dropbox", "OneDrive"])
        self.cloud_provider.setStyleSheet(self._input_style())
        self._add_control(grid, 0, "Dich vu", self.cloud_provider)

        btn_sync = QPushButton("Dong bo ngay")
        btn_sync.setStyleSheet(self._btn_primary())
        btn_sync.clicked.connect(self._sync_cloud)
        self._add_control(grid, 1, "Dong bo", btn_sync)

        self.cloud_info = QLabel("Chua cau hinh")
        self.cloud_info.setStyleSheet("color:#888; font-size:11px; border:none;")
        self._add_control(grid, 2, "Trang thai", self.cloud_info)

        self.body.addWidget(panel)

    # -- Refresh / Save --

    def refresh(self):
        self.settings = load_settings()
        self.currency_combo.setCurrentText(self.settings["currency"])
        self.date_combo.setCurrentText(self.settings["date_format"])
        self._set_combo_data(self.month_combo, self.settings["default_month"])
        self.auto_refresh_check.setChecked(bool(self.settings["auto_refresh"]))
        self._set_combo_data(self.window_mode_combo, self.settings.get("window_mode", "default"))
        self._set_combo_data(self.theme_combo, theme_engine.mode)
        self.auto_classify_check.setChecked(bool(self.settings["auto_classification"]))
        self.anomaly_check.setChecked(bool(self.settings["anomaly_detection"]))
        self._set_combo_data(self.forecast_combo, self.settings["forecast_method"])
        self._set_combo_data(self.chat_engine_combo, self.settings["chat_engine"])
        self.gemini_key.setText(get_env_value("GEMINI_API_KEY"))
        self.supabase_url.setText(get_env_value("SUPABASE_URL"))
        self.supabase_key.setText(get_env_value("SUPABASE_KEY"))
        self._refresh_package_status()

        if self.tabs.currentIndex() == 1:
            self.profile_tab.refresh()

    def _save(self):
        data = {
            "currency":            self.currency_combo.currentText(),
            "date_format":         self.date_combo.currentText(),
            "default_month":       self.month_combo.currentData(),
            "auto_refresh":        self.auto_refresh_check.isChecked(),
            "window_mode":         self.window_mode_combo.currentData(),
            "auto_classification": self.auto_classify_check.isChecked(),
            "anomaly_detection":   self.anomaly_check.isChecked(),
            "forecast_method":     self.forecast_combo.currentData(),
            "chat_engine":         self.chat_engine_combo.currentData(),
        }
        self.settings = save_settings(data)
        update_env_value("GEMINI_API_KEY", self.gemini_key.text().strip())
        update_env_value("SUPABASE_URL",   self.supabase_url.text().strip())
        update_env_value("SUPABASE_KEY",   self.supabase_key.text().strip())
        self.status_label.setText("Da luu")
        QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        QMessageBox.information(self, "Thong bao", "Cai dat da duoc luu thanh cong!")
        if self.main_window:
            self.main_window.refresh_all()

    # -- Data actions --

    def _backup_db(self):
        try:
            target = backup_database()
        except Exception as e:
            QMessageBox.critical(self, "Loi backup", str(e))
            return
        self.backup_info.setText(f"Da tao backup: {target.name}")
        QMessageBox.information(self, "Thanh cong",
                                f"Da sao luu database:\n{target}")

    def _export_excel(self):
        exports_dir = get_exports_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "Luu file Excel",
            str(exports_dir / "finance_export.xlsx"),
            "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            target = export_database_to_excel(path)
        except Exception as e:
            QMessageBox.critical(self, "Loi xuat Excel", str(e))
            return
        self.backup_info.setText(f"Da xuat Excel: {Path(target).name}")
        QMessageBox.information(self, "Thanh cong", f"Da xuat du lieu:\n{target}")

    def _restore_db(self):
        try:
            from user_session import session
            backup_dir = str(session.backups_dir) if session.is_logged_in else str(DATA_DIR)
        except ImportError:
            backup_dir = str(DATA_DIR)

        path, _ = QFileDialog.getOpenFileName(
            self, "Chon file database", backup_dir,
            "SQLite Database (*.db);;All Files (*)"
        )
        if not path:
            return
        reply = QMessageBox.warning(
            self, "Xac nhan phuc hoi",
            "Phuc hoi database se ghi de du lieu hien tai.\n"
            "App se tu dong sao luu truoc khi ghi de.\n\n"
            "Ban co muon tiep tuc?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            backup_path = restore_database(path)
        except Exception as e:
            QMessageBox.critical(self, "Loi phuc hoi", str(e))
            return
        self.backup_info.setText(
            f"Da phuc hoi. Backup cu: {Path(str(backup_path)).name if backup_path else 'N/A'}")
        if self.main_window:
            self.main_window.refresh_all()
        QMessageBox.information(
            self, "Thanh cong",
            f"Da phuc hoi database.\nBackup truoc khi phuc hoi:\n{backup_path}"
        )

    def _open_data_folder(self):
        user_data_dir = _get_user_data_dir()
        user_data_dir.mkdir(parents=True, exist_ok=True)
        import sys, subprocess
        folder = str(user_data_dir)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.call(["open", folder])
        else:
            subprocess.call(["xdg-open", folder])

    def _sync_cloud(self):
        provider = self.cloud_provider.currentText()
        self.cloud_info.setText(f"Dang dong bo voi {provider}...")
        self.cloud_info.setStyleSheet("color:#0C447C; font-size:11px; border:none;")
        success, msg = SyncManager.sync_to_cloud()
        if success:
            self.cloud_info.setText(
                f"Da dong bo luc: {datetime.now().strftime('%H:%M:%S')}")
            self.cloud_info.setStyleSheet("color:#3B6D11; font-size:11px; border:none;")
            QMessageBox.information(self, "Cloud Sync", msg)
        else:
            self.cloud_info.setText("Dong bo that bai")
            self.cloud_info.setStyleSheet("color:#A32D2D; font-size:11px; border:none;")
            QMessageBox.warning(self, "Cloud Sync", msg)

    def _refresh_package_status(self):
        statuses = package_status(list(self.package_labels.keys()))
        for name, ok in statuses.items():
            self.package_labels[name].setText(f"{name}: {'OK' if ok else 'thieu'}")
            self.package_labels[name].setStyleSheet(self._badge_style(ok))

    # -- Helpers --

    @staticmethod
    def _set_combo_data(combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _panel(self, title):
        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        panel.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        label.setStyleSheet("color:#222; border:none;")
        layout.addWidget(label)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return panel, grid

    def _add_readonly(self, grid, row, label, value):
        value_label = QLabel(str(value))
        value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        value_label.setWordWrap(True)
        value_label.setStyleSheet("color:#555; font-size:12px; border:none;")
        self._add_control(grid, row, label, value_label)

    def _add_control(self, grid, row, label, widget):
        label_widget = QLabel(label)
        label_widget.setFixedWidth(150)
        label_widget.setStyleSheet("color:#888; font-size:12px; border:none;")
        grid.addWidget(label_widget, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(widget, row, 1)

    @staticmethod
    def _input_style():
        return ("QLineEdit { border:1px solid #ddd; border-radius:6px; "
                "padding:6px 10px; font-size:12px; background:#fff; color:#222; }")

    @staticmethod
    def _check_style():
        return ("QCheckBox { color:#333; font-size:12px; border:none; } "
                "QCheckBox::indicator { width:16px; height:16px; }")

    @staticmethod
    def _badge_style(ok):
        if ok:
            return ("QLabel { background:#EAF3DE; color:#3B6D11; border:none; "
                    "border-radius:10px; padding:3px 10px; font-size:11px; }")
        return ("QLabel { background:#FCEBEB; color:#A32D2D; border:none; "
                "border-radius:10px; padding:3px 10px; font-size:11px; }")

    @staticmethod
    def _btn_primary():
        return ("QPushButton { background:#E6F1FB; color:#0C447C; "
                "border:1px solid #B5D4F4; border-radius:6px; "
                "padding:6px 14px; font-size:12px; font-weight:500; } "
                "QPushButton:hover { background:#B5D4F4; }")

    @staticmethod
    def _btn_normal():
        return ("QPushButton { background:#fff; color:#555; "
                "border:1px solid #ddd; border-radius:6px; "
                "padding:6px 12px; font-size:12px; } "
                "QPushButton:hover { background:#f5f5f5; }")

    @staticmethod
    def _btn_danger():
        return ("QPushButton { background:#fff; color:#A32D2D; "
                "border:1px solid #E24B4A; border-radius:6px; "
                "padding:6px 12px; font-size:12px; } "
                "QPushButton:hover { background:#FCEBEB; }")