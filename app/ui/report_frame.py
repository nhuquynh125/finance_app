# app/ui/report_frame.py  (cập nhật: sửa dialog "Thiếu thư viện" bị trắng/mờ)
"""
Thay đổi:
  - FIX: Dialog cảnh báo thiếu thư viện (reportlab) hiển thị text/button rõ ràng.
    Trước đây QMessageBox.warning() bị theme_engine global QSS override làm chữ
    trắng trên nền trắng. Thay bằng custom QDialog có stylesheet riêng, đảm bảo
    màu chữ đậm tương phản cao.
  - EXPORTS_DIR lấy động từ settings_manager.get_exports_dir() (per-user).
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QScrollArea, QFileDialog, QMessageBox,
    QProgressBar, QGridLayout, QDialog, QDialogButtonBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from app.data.models import get_connection
from app.core.transaction_manager import TransactionManager
from app.core.settings_manager import get_exports_dir
from datetime import datetime


# ── Missing-library warning dialog — crisp, high-contrast ────────────────────

class MissingLibraryDialog(QDialog):
    """
    Replaces QMessageBox.warning() for the "reportlab not installed" case.

    FIX: The global theme_engine QSS was making QMessageBox text white-on-white.
    This custom dialog hard-codes a dark-text, white-background style that cannot
    be overridden by the application-level stylesheet.
    """

    # Inline QSS applied directly to this dialog — overrides any global theme.
    _DIALOG_QSS = """
        QDialog {
            background-color: #FFFFFF;
        }
        QLabel#titleLabel {
            color: #0B2A4A;
            font-size: 15px;
            font-weight: 700;
            border: none;
            background: transparent;
        }
        QLabel#bodyLabel {
            color: #333333;
            font-size: 13px;
            border: none;
            background: transparent;
        }
        QLabel#codeLabel {
            color: #1A6BAF;
            font-size: 13px;
            font-weight: 600;
            background: #EFF6FF;
            border: 1px solid #B5D4F4;
            border-radius: 6px;
            padding: 8px 14px;
        }
        QPushButton#okBtn {
            background-color: #378ADD;
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 8px 26px;
            font-size: 13px;
            font-weight: 600;
        }
        QPushButton#okBtn:hover {
            background-color: #1A6BAF;
        }
        QPushButton#okBtn:pressed {
            background-color: #0B2A4A;
        }
        QFrame#divider {
            background: #E8E8E8;
            border: none;
            max-height: 1px;
        }
    """

    def __init__(self, parent=None, missing_package: str = "reportlab"):
        super().__init__(parent)
        self.setWindowTitle("Thiếu thư viện")
        self.setFixedSize(440, 270)
        # Apply our own stylesheet AFTER the dialog is created so it takes
        # precedence over any inherited application-level QSS.
        self.setStyleSheet(self._DIALOG_QSS)
        self._build(missing_package)

    def _build(self, pkg: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Icon + title row
        title_row = QHBoxLayout()
        icon_lbl = QLabel("📦")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 22))
        icon_lbl.setStyleSheet("border:none; background:transparent;")
        title_row.addWidget(icon_lbl)
        title_lbl = QLabel("Thiếu thư viện bắt buộc")
        title_lbl.setObjectName("titleLabel")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Description
        body = QLabel(
            f"Thư viện <b>{pkg}</b> chưa được cài đặt.\n"
            "Vui lòng chạy lệnh sau trong terminal để cài đặt:"
        )
        body.setObjectName("bodyLabel")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        # Install command — styled as code block
        install_cmd = QLabel(f"pip install {pkg}")
        install_cmd.setObjectName("codeLabel")
        install_cmd.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(install_cmd)

        # Divider
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        # OK button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("Đã hiểu")
        ok_btn.setObjectName("okBtn")
        ok_btn.setFixedHeight(38)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)


# ── Worker thread ─────────────────────────────────────────────────────────────

class ReportWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, month: str, output_path: str):
        super().__init__()
        self.month       = month
        self.output_path = output_path

    def run(self):
        try:
            from app.core.report_generator import ReportGenerator
            gen  = ReportGenerator()
            path = gen.generate_monthly_report(self.month, self.output_path)
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


# ── ReportFrame ───────────────────────────────────────────────────────────────

class ReportFrame(QWidget):

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f5f5f5; }")
        content = QWidget()
        content.setStyleSheet("background:#f5f5f5;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(16)

        # ── Generate panel ────────────────────────────────────────────────────
        gen_panel = QFrame()
        gen_panel.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        gpl = QVBoxLayout(gen_panel)
        gpl.setContentsMargins(24, 20, 24, 20)
        gpl.setSpacing(12)

        t = QLabel("Tạo báo cáo PDF tháng")
        t.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        t.setStyleSheet("color:#0B2A4A; border:none;")
        gpl.addWidget(t)

        desc = QLabel(
            "Xuất báo cáo tổng kết tài chính tháng bao gồm: tổng kết thu chi, "
            "phân tích theo danh mục, danh sách giao dịch và dự báo AI tháng tới.")
        desc.setWordWrap(True)
        desc.setFont(QFont("Segoe UI", 12))
        desc.setStyleSheet("color:#555; border:none;")
        gpl.addWidget(desc)

        row = QHBoxLayout()
        lbl = QLabel("Chọn tháng:")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#222; border:none;")
        row.addWidget(lbl)

        self.cb_month = QComboBox()
        self.cb_month.setFixedWidth(160)
        self.cb_month.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:6px; "
            "padding:6px 10px; font-size:12px; background:#fff; }")
        self._populate_months()
        row.addWidget(self.cb_month)
        row.addStretch()

        self.btn_gen = QPushButton("Tạo & Tải PDF")
        self.btn_gen.setFixedHeight(38)
        self.btn_gen.setStyleSheet(
            "QPushButton { background:#378ADD; color:#fff; border:none; border-radius:8px; "
            "padding:8px 24px; font-size:13px; font-weight:500; } "
            "QPushButton:hover { background:#185FA5; } "
            "QPushButton:disabled { background:#ccc; }")
        self.btn_gen.clicked.connect(self._generate_report)
        row.addWidget(self.btn_gen)
        gpl.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        self.progress.setStyleSheet(
            "QProgressBar { border:none; border-radius:2px; background:#e8e8e8; } "
            "QProgressBar::chunk { background:#378ADD; border-radius:2px; }")
        gpl.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Segoe UI", 11))
        self.status_lbl.setStyleSheet("color:#1D9E75; border:none;")
        gpl.addWidget(self.status_lbl)

        cl.addWidget(gen_panel)

        # ── Preview panel ─────────────────────────────────────────────────────
        self.preview_panel = QFrame()
        self.preview_panel.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        self.preview_layout = QVBoxLayout(self.preview_panel)
        self.preview_layout.setContentsMargins(24, 20, 24, 20)
        self.preview_layout.setSpacing(10)
        preview_title = QLabel("Xem trước nội dung báo cáo")
        preview_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        preview_title.setStyleSheet("color:#0B2A4A; border:none;")
        self.preview_layout.addWidget(preview_title)
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(10)
        self.preview_layout.addLayout(self.stats_grid)
        cl.addWidget(self.preview_panel)

        # ── History panel ─────────────────────────────────────────────────────
        hist_panel = QFrame()
        hist_panel.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        hist_l = QVBoxLayout(hist_panel)
        hist_l.setContentsMargins(24, 20, 24, 20)
        hist_l.setSpacing(8)
        hist_title = QLabel("File báo cáo đã tạo")
        hist_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        hist_title.setStyleSheet("color:#0B2A4A; border:none;")
        hist_l.addWidget(hist_title)
        self.hist_layout = QVBoxLayout()
        hist_l.addLayout(self.hist_layout)
        cl.addWidget(hist_panel)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.cb_month.currentIndexChanged.connect(
            lambda: QTimer.singleShot(100, self._update_preview))
        QTimer.singleShot(200, self._update_preview)
        QTimer.singleShot(200, self._load_history)

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Báo cáo")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#0B2A4A; border:none;")
        layout.addWidget(title)
        layout.addStretch()
        return bar

    def refresh(self):
        self._update_preview()
        self._load_history()

    def _update_preview(self):
        month = self.cb_month.currentData()
        if not month:
            return

        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        conn = get_connection()
        summary = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as expense,
                COUNT(*) as count
            FROM transactions WHERE strftime('%Y-%m', date)=?
        """, (month,)).fetchone()
        top_cat = conn.execute("""
            SELECT c.name, SUM(t.amount) as total
            FROM transactions t JOIN categories c ON t.category_id=c.id
            WHERE t.type='expense' AND strftime('%Y-%m',t.date)=?
            GROUP BY c.id ORDER BY total DESC LIMIT 1
        """, (month,)).fetchone()
        anomaly_count = conn.execute("""
            SELECT COUNT(*) as n FROM transactions
            WHERE is_anomaly=1 AND strftime('%Y-%m',date)=?
        """, (month,)).fetchone()
        forecast_count = conn.execute(
            "SELECT COUNT(*) as n FROM ai_predictions WHERE month=?",
            (month,)
        ).fetchone()
        conn.close()

        income  = summary["income"]
        expense = summary["expense"]
        saving  = income - expense

        stats = [
            ("Thu nhập",           self._fmt(income),       "#1D9E75"),
            ("Chi tiêu",           self._fmt(expense),      "#E24B4A"),
            ("Tiết kiệm",          self._fmt(saving),       "#378ADD" if saving >= 0 else "#E24B4A"),
            ("Số giao dịch",       str(summary["count"]),   "#333"),
            ("Danh mục chi nhiều", top_cat["name"] if top_cat else "—", "#BA7517"),
            ("Bất thường phát hiện", str(anomaly_count["n"]),
             "#E24B4A" if anomaly_count["n"] else "#1D9E75"),
            ("Danh mục dự báo AI", str(forecast_count["n"]), "#7F77DD"),
        ]
        for i, (label, value, color) in enumerate(stats):
            row, col = divmod(i, 2)
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background:#f7f7f7; border-radius:8px; border:none; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
            lbl.setStyleSheet("color:#555; border:none;")
            cl.addWidget(lbl)
            val = QLabel(value)
            val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            val.setStyleSheet(f"color:{color}; border:none;")
            cl.addWidget(val)
            self.stats_grid.addWidget(card, row, col)

    def _generate_report(self):
        month = self.cb_month.currentData()
        if not month:
            return

        exports_dir = get_exports_dir()
        exports_dir.mkdir(parents=True, exist_ok=True)
        default_name = f"bao_cao_{month}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu báo cáo PDF",
            str(exports_dir / default_name),
            "PDF Files (*.pdf)"
        )
        if not path:
            return

        self.btn_gen.setEnabled(False)
        self.progress.show()
        self.status_lbl.setText("Đang tạo báo cáo...")
        self.status_lbl.setStyleSheet("color:#378ADD; border:none;")

        self.worker = ReportWorker(month, path)
        self.worker.finished.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_done(self, path: str):
        self.progress.hide()
        self.btn_gen.setEnabled(True)
        self.status_lbl.setText(f"Đã tạo: {os.path.basename(path)}")
        self.status_lbl.setStyleSheet("color:#1D9E75; border:none;")
        self._load_history()

        reply = QMessageBox.question(
            self, "Thành công",
            f"Báo cáo đã được tạo!\n{path}\n\nMở file ngay?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._open_file(path)

    def _on_error(self, msg: str):
        self.progress.hide()
        self.btn_gen.setEnabled(True)
        self.status_lbl.setText(f"Lỗi: {msg}")
        self.status_lbl.setStyleSheet("color:#E24B4A; border:none;")

        # ── FIX: Use custom dialog instead of QMessageBox.warning() ──────────
        # QMessageBox.warning() inherits the app-level QSS which sets all
        # QLabel/QPushButton text to near-white, making the dialog unreadable.
        # MissingLibraryDialog has its own hard-coded dark-text stylesheet.
        if "reportlab" in msg.lower() or "no module" in msg.lower():
            pkg = "reportlab"
            if "no module named" in msg.lower():
                # Try to extract the actual package name from the error
                try:
                    pkg = msg.lower().split("no module named")[1].strip().strip("'\"")
                except Exception:
                    pkg = "reportlab"
            dlg = MissingLibraryDialog(self, missing_package=pkg)
            dlg.exec()
        else:
            # Generic error — use a styled QMessageBox with explicit palette
            mb = QMessageBox(self)
            mb.setWindowTitle("Lỗi tạo báo cáo")
            mb.setText(msg)
            mb.setIcon(QMessageBox.Icon.Critical)
            # Force dark text so it stays legible regardless of global QSS
            mb.setStyleSheet("""
                QMessageBox {
                    background-color: #FFFFFF;
                }
                QMessageBox QLabel {
                    color: #222222;
                    font-size: 13px;
                    background: transparent;
                    border: none;
                }
                QMessageBox QPushButton {
                    color: #0B2A4A;
                    background: #E6F1FB;
                    border: 1px solid #B5D4F4;
                    border-radius: 6px;
                    padding: 5px 18px;
                    font-size: 12px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background: #B5D4F4;
                }
            """)
            mb.exec()

    def _load_history(self):
        while self.hist_layout.count():
            item = self.hist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            exports_dir = get_exports_dir()
            files = sorted(exports_dir.glob("bao_cao_*.pdf"), reverse=True)
        except Exception:
            files = []

        if not files:
            lbl = QLabel("Chưa có báo cáo nào được tạo.")
            lbl.setStyleSheet("color:#bbb; font-size:12px; border:none;")
            self.hist_layout.addWidget(lbl)
            return

        for f in files[:10]:
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 4, 0, 4)
            rl.setSpacing(12)

            name_lbl = QLabel(f.name)
            name_lbl.setFont(QFont("Segoe UI", 12))
            name_lbl.setStyleSheet("color:#333; border:none;")
            rl.addWidget(name_lbl)

            size_kb = f.stat().st_size // 1024
            size_lbl = QLabel(f"{size_kb} KB")
            size_lbl.setFont(QFont("Segoe UI", 10))
            size_lbl.setStyleSheet("color:#aaa; border:none;")
            rl.addWidget(size_lbl)
            rl.addStretch()

            btn_open = QPushButton("Mở")
            btn_open.setFixedSize(50, 26)
            btn_open.setStyleSheet(
                "QPushButton { background:#E6F1FB; color:#0C447C; border:none; "
                "border-radius:5px; font-size:11px; font-weight:500; } "
                "QPushButton:hover { background:#B5D4F4; }")
            btn_open.clicked.connect(lambda _, p=str(f): self._open_file(p))
            rl.addWidget(btn_open)

            self.hist_layout.addWidget(row)

            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet("background:#f0f0f0; border:none; max-height:1px;")
            self.hist_layout.addWidget(div)

    def _open_file(self, path: str):
        import subprocess, sys
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            # Show a legible error dialog
            mb = QMessageBox(self)
            mb.setWindowTitle("Lỗi")
            mb.setText(f"Không mở được file:\n{e}")
            mb.setIcon(QMessageBox.Icon.Warning)
            mb.setStyleSheet("""
                QMessageBox { background-color: #FFFFFF; }
                QMessageBox QLabel {
                    color: #222222; font-size: 13px;
                    background: transparent; border: none;
                }
                QMessageBox QPushButton {
                    color: #0B2A4A; background: #E6F1FB;
                    border: 1px solid #B5D4F4; border-radius: 6px;
                    padding: 5px 18px; font-size: 12px; min-width: 60px;
                }
                QMessageBox QPushButton:hover { background: #B5D4F4; }
            """)
            mb.exec()

    def _populate_months(self):
        now = datetime.now()
        for i in range(11, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12; y -= 1
            self.cb_month.addItem(f"Tháng {m}/{y}", userData=f"{y}-{m:02d}")
        self.cb_month.setCurrentIndex(self.cb_month.count() - 1)

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f} d".replace(",", ".")
