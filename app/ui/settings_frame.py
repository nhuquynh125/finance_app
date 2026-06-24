# app/ui/settings_frame.py

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
    backup_database, export_database_to_excel, load_settings,
    package_status, restore_database, save_settings,
    get_exports_dir, _get_db_path
)
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
# Main SettingsFrame
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
        self.auto_classify_check.setChecked(bool(self.settings["auto_classification"]))
        self.anomaly_check.setChecked(bool(self.settings["anomaly_detection"]))
        self._update_badge(self._auto_refresh_badge, bool(self.settings["auto_refresh"]))
        self._update_badge(self._auto_classify_badge, bool(self.settings["auto_classification"]))
        self._update_badge(self._anomaly_badge, bool(self.settings["anomaly_detection"]))
        self._set_combo_data(self.forecast_combo, self.settings["forecast_method"])
        self._set_combo_data(self.chat_engine_combo, self.settings["chat_engine"])

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        self.app_tab = self._build_app_tab()
        layout.addWidget(self.app_tab)

    # -- Toolbar --

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(54)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Larger, darker page title
        title = QLabel("Cài đặt")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color:#0B2A4A; border:none;")
        layout.addWidget(title)
        layout.addStretch()

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 16))
        self.status_label.setStyleSheet("color:#1D9E75; border:none;")
        layout.addWidget(self.status_label)

        btn_reload = QPushButton("Tải lại")
        btn_reload.setStyleSheet(self._btn_normal())
        btn_reload.clicked.connect(self.refresh)
        layout.addWidget(btn_reload)

        btn_save = QPushButton("Lưu cài đặt")
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

        # NOTE: "Thông tin ứng dụng" block REMOVED entirely
        self._build_general_settings()
        self._build_ai_settings()
        self._build_data_tools()
        # NOTE: "Cấu hình API & Cloud" block REMOVED entirely
        self.body.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        return widget

    def _build_general_settings(self):
        panel, grid = self._panel("Cài đặt chung")

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["VND", "USD", "EUR"])
        self.currency_combo.setStyleSheet(self._combo_style())
        self._add_control(grid, 0, "Tiền tệ mặc định", self.currency_combo)

        self.date_combo = QComboBox()
        self.date_combo.addItems(["dd/MM/yyyy", "yyyy-MM-dd", "MM/dd/yyyy"])
        self.date_combo.setStyleSheet(self._combo_style())
        self._add_control(grid, 1, "Định dạng ngày", self.date_combo)

        self.month_combo = QComboBox()
        self.month_combo.addItem("Tháng hiện tại", "current")
        self.month_combo.addItem("Tháng gần nhất có dữ liệu", "latest_data")
        self.month_combo.setStyleSheet(self._combo_style())
        self._add_control(grid, 2, "Tháng mặc định", self.month_combo)

        self.auto_refresh_check = QCheckBox("Tự động làm mới dữ liệu")
        self.auto_refresh_check.setStyleSheet(self._check_style())
        self._auto_refresh_badge = self._make_status_badge()
        row_w = self._check_with_badge(self.auto_refresh_check, self._auto_refresh_badge)
        self.auto_refresh_check.stateChanged.connect(
            lambda s: self._update_badge(self._auto_refresh_badge, bool(s)))
        self._add_control(grid, 3, "Làm mới", row_w)

        self.body.addWidget(panel)

    def _build_ai_settings(self):
        panel, grid = self._panel("Cài đặt AI")

        self.auto_classify_check = QCheckBox("Tự động phân loại giao dịch")
        self.auto_classify_check.setStyleSheet(self._check_style())
        self._auto_classify_badge = self._make_status_badge()
        row_w2 = self._check_with_badge(self.auto_classify_check, self._auto_classify_badge)
        self.auto_classify_check.stateChanged.connect(
            lambda s: self._update_badge(self._auto_classify_badge, bool(s)))
        self._add_control(grid, 0, "Phân loại", row_w2)

        self.anomaly_check = QCheckBox("Bật phát hiện bất thường")
        self.anomaly_check.setStyleSheet(self._check_style())
        self._anomaly_badge = self._make_status_badge()
        row_w3 = self._check_with_badge(self.anomaly_check, self._anomaly_badge)
        self.anomaly_check.stateChanged.connect(
            lambda s: self._update_badge(self._anomaly_badge, bool(s)))
        self._add_control(grid, 1, "Bất thường", row_w3)

        self.forecast_combo = QComboBox()
        self.forecast_combo.addItem("Tự động", "auto")
        self.forecast_combo.addItem("Trung bình động", "moving_average")
        self.forecast_combo.addItem("Prophet nếu có", "prophet")
        self.forecast_combo.setStyleSheet(self._combo_style())
        self._add_control(grid, 2, "Phương pháp dự báo", self.forecast_combo)

        self.chat_engine_combo = QComboBox()
        self.chat_engine_combo.addItem("Finance-AI", "finance_ai")
        self.chat_engine_combo.setStyleSheet(self._combo_style())
        self._add_control(grid, 3, "Engine chatbot", self.chat_engine_combo)

        self.body.addWidget(panel)

    def _build_data_tools(self):
        panel, grid = self._panel("Quản lý dữ liệu")

        btn_backup = QPushButton("Sao lưu database")
        btn_backup.setStyleSheet(self._btn_primary())
        btn_backup.clicked.connect(self._backup_db)
        self._add_control(grid, 0, "Backup", btn_backup)

        btn_export = QPushButton("Xuất Excel")
        btn_export.setStyleSheet(self._btn_normal())
        btn_export.clicked.connect(self._export_excel)
        self._add_control(grid, 1, "Xuất dữ liệu", btn_export)

        btn_restore = QPushButton("Phục hồi database")
        btn_restore.setStyleSheet(self._btn_danger())
        btn_restore.clicked.connect(self._restore_db)
        self._add_control(grid, 2, "Phục hồi", btn_restore)

        btn_folder = QPushButton("Mở thư mục dữ liệu")
        btn_folder.setStyleSheet(self._btn_normal())
        btn_folder.clicked.connect(self._open_data_folder)
        self._add_control(grid, 3, "Thư mục", btn_folder)

        self.body.addWidget(panel)

    # -- Refresh / Save --

    def refresh(self):
        self.settings = load_settings()
        self.currency_combo.setCurrentText(self.settings["currency"])
        self.date_combo.setCurrentText(self.settings["date_format"])
        self._set_combo_data(self.month_combo, self.settings["default_month"])
        self.auto_refresh_check.setChecked(bool(self.settings["auto_refresh"]))
        self.auto_classify_check.setChecked(bool(self.settings["auto_classification"]))
        self.anomaly_check.setChecked(bool(self.settings["anomaly_detection"]))
        self._update_badge(self._auto_refresh_badge, bool(self.settings["auto_refresh"]))
        self._update_badge(self._auto_classify_badge, bool(self.settings["auto_classification"]))
        self._update_badge(self._anomaly_badge, bool(self.settings["anomaly_detection"]))
        self._set_combo_data(self.forecast_combo, self.settings["forecast_method"])
        self._set_combo_data(self.chat_engine_combo, self.settings["chat_engine"])


    def _save(self):
        data = {
            "currency":            self.currency_combo.currentText(),
            "date_format":         self.date_combo.currentText(),
            "default_month":       self.month_combo.currentData(),
            "auto_refresh":        self.auto_refresh_check.isChecked(),
            "auto_classification": self.auto_classify_check.isChecked(),
            "anomaly_detection":   self.anomaly_check.isChecked(),
            "forecast_method":     self.forecast_combo.currentData(),
            "chat_engine":         self.chat_engine_combo.currentData(),
        }
        self.settings = save_settings(data)
        self.status_label.setText("Đã lưu ✓")
        QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        self._show_message_box("Thông báo", "Cài đặt đã được lưu thành công!")
        if self.main_window:
            self.main_window.refresh_all()

    # -- Data actions --

    def _backup_db(self):
        try:
            target = backup_database()
        except Exception as e:
            self._show_message_box("Lỗi backup", str(e), QMessageBox.Icon.Critical)
            return
        self._show_message_box("Thành công", f"Đã sao lưu database:\n{target}")

    def _export_excel(self):
        exports_dir = get_exports_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu file Excel",
            str(exports_dir / "finance_export.xlsx"),
            "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            target = export_database_to_excel(path)
        except Exception as e:
            self._show_message_box("Lỗi xuất Excel", str(e), QMessageBox.Icon.Critical)
            return
        self._show_message_box("Thành công", f"Đã xuất dữ liệu:\n{target}")

    def _restore_db(self):
        try:
            from user_session import session
            backup_dir = str(session.backups_dir) if session.is_logged_in else str(DATA_DIR)
        except ImportError:
            backup_dir = str(DATA_DIR)

        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file database", backup_dir,
            "SQLite Database (*.db);;All Files (*)"
        )
        if not path:
            return
        reply = self._show_message_box(
            "Xác nhận phục hồi",
            "Phục hồi database sẽ ghi đè dữ liệu hiện tại.\n"
            "App sẽ tự động sao lưu trước khi ghi đè.\n\n"
            "Bạn có muốn tiếp tục?",
            QMessageBox.Icon.Warning,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            backup_path = restore_database(path)
        except Exception as e:
            self._show_message_box("Lỗi phục hồi", str(e), QMessageBox.Icon.Critical)
            return
        if self.main_window:
            self.main_window.refresh_all()
        self._show_message_box(
            "Thành công",
            f"Đã phục hồi database.\nBackup trước khi phục hồi:\n{backup_path}"
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

    def _show_message_box(self, title, text, icon=QMessageBox.Icon.Information, buttons=QMessageBox.StandardButton.Ok):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setStandardButtons(buttons)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QLabel {
                color: #0B2A4A;
                font-size: 16px;
                font-weight: 500;
                min-width: 300px;
                min-height: 50px;
            }
            QPushButton {
                background: #E6F1FB;
                color: #0B2A4A;
                border: 1px solid #B5D4F4;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 15px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #B5D4F4;
            }
        """)
        return msg.exec()

    @staticmethod
    def _make_status_badge() -> QLabel:
        badge = QLabel("")  
        badge.setFixedWidth(60)
        return badge

    @staticmethod
    def _update_badge(badge: QLabel, is_on: bool):
        if is_on:
            badge.setText("● BẬT")
            badge.setStyleSheet(
                "QLabel { background:#EAF3DE; color:#3B6D11; border:none; "
                "border-radius:10px; padding:2px 8px; font-size:14px; font-weight:bold; }")
        else:
            badge.setText("○ TẮT")
            badge.setStyleSheet(
                "QLabel { background:#F5F5F5; color:#999; border:none; "
                "border-radius:10px; padding:2px 8px; font-size:14px; font-weight:bold; }")

    @staticmethod
    def _check_with_badge(checkbox: QCheckBox, badge: QLabel) -> QWidget:
        """Gom checkbox + badge vào một widget hàng ngang."""
        from PyQt6.QtWidgets import QHBoxLayout
        w = QWidget()
        w.setStyleSheet("background:transparent; border:none;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        hl.addWidget(checkbox)
        hl.addWidget(badge)
        hl.addStretch()
        return w

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
        # Larger, darker section header
        label = QLabel(title)
        label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        label.setStyleSheet("color:#0B2A4A; border:none;")
        layout.addWidget(label)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        # Tighter ratio: label col ~40%, input col ~60%
        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 6)
        layout.addLayout(grid)
        return panel, grid

    def _add_control(self, grid, row, label_text, widget):
        """Add a label + widget pair with larger, darker label text."""
        label_widget = QLabel(label_text)
        label_widget.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))
        label_widget.setStyleSheet("color:#0B2A4A; border:none;")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(label_widget, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(widget, row, 1)

    @staticmethod
    def _combo_style():
        """QComboBox style with larger, darker text for better readability."""
        return (
            "QComboBox { border:1px solid #ddd; border-radius:6px; "
            "padding:6px 10px; font-size:16px; background:#fff; color:#0B2A4A; } "
            "QComboBox:hover { border-color:#378ADD; } "
            "QComboBox::drop-down { border:none; width:22px; } "
            "QComboBox QAbstractItemView { "
            "background:#fff; color:#0B2A4A; font-size:16px; "
            "border:1px solid #ddd; selection-background-color:#E6F1FB; }"
        )

    @staticmethod
    def _check_style():
        return ("QCheckBox { color:#0B2A4A; font-size:16px; border:none; } "
                "QCheckBox::indicator { width:17px; height:17px; }")

    @staticmethod
    def _badge_style(ok):
        if ok:
            return ("QLabel { background:#EAF3DE; color:#3B6D11; border:none; "
                    "border-radius:10px; padding:3px 10px; font-size:15px; }")
        return ("QLabel { background:#FCEBEB; color:#A32D2D; border:none; "
                "border-radius:10px; padding:3px 10px; font-size:15px; }")

    @staticmethod
    def _btn_primary():
        return ("QPushButton { background:#E6F1FB; color:#0B2A4A; "
                "border:1px solid #B5D4F4; border-radius:6px; "
                "padding:6px 14px; font-size:16px; font-weight:500; } "
                "QPushButton:hover { background:#B5D4F4; }")

    @staticmethod
    def _btn_normal():
        return ("QPushButton { background:#fff; color:#0B2A4A; "
                "border:1px solid #ddd; border-radius:6px; "
                "padding:6px 12px; font-size:16px; } "
                "QPushButton:hover { background:#f5f5f5; }")

    @staticmethod
    def _btn_danger():
        return ("QPushButton { background:#fff; color:#A32D2D; "
                "border:1px solid #E24B4A; border-radius:6px; "
                "padding:6px 12px; font-size:16px; } "
                "QPushButton:hover { background:#FCEBEB; }")