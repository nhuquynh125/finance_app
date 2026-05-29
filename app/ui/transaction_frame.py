# app/ui/transaction_frame.py  (cập nhật: sửa bug alert + account dropdown + pagination)
"""
Thay đổi so với phiên bản cũ:
  - Sửa bug: add_transaction() trả về int (tx_id), không phải dict
    → Xóa đoạn check alert.get("type") gây lỗi
  - TransactionDialog: thêm dropdown chọn tài khoản thay vì hardcode account_id=1
  - Thêm phân trang (pagination) cho bảng giao dịch (100 dòng/trang)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox, QHeaderView,
    QAbstractItemView, QDialog, QFormLayout,
    QDateEdit, QDoubleSpinBox, QTextEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
from app.core.transaction_manager import TransactionManager
from app.data.models import get_connection
from app.core.event_bus import bus, BusConnectMixin
from app.data.repositories import BudgetRepo
from datetime import datetime
import pandas as pd


class ClassifyWorker(QThread):
    finished = pyqtSignal()

    def __init__(self, transactions):
        super().__init__()
        self.transactions = transactions

    def run(self):
        try:
            from app.ai.classifier import TransactionClassifier
            from app.ai.anomaly_detector import AnomalyDetector
            clf = TransactionClassifier()
            det = AnomalyDetector()
            with get_connection() as conn:
                for tx in self.transactions:
                    if not tx.get("category_id") and tx.get("description"):
                        cat_id = clf.predict_category_id(tx["description"])
                        if cat_id:
                            conn.execute(
                                "UPDATE transactions SET category_id=? WHERE id=?",
                                (cat_id, tx["id"])
                            )
                det.detect_and_mark()
        except Exception as e:
            from app.core.logger import get_logger
            get_logger(__name__).error(f"Lỗi phân loại AI: {e}", exc_info=True)
        finally:
            self.finished.emit()


class TransactionFrame(QWidget, BusConnectMixin):
    COLUMNS = ["Ngày", "Mô tả", "Danh mục", "Tài khoản", "Số tiền", "Ghi chú"]
    PAGE_SIZE = 100   # Số dòng mỗi trang

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self._all_transactions = []
        self._filtered_transactions = []
        self._page = 0
        self._build()
        self._connect_bus()

    def _connect_bus(self):
        bus.transaction_added.connect(self.refresh)
        bus.transaction_updated.connect(lambda _: self.refresh())
        bus.transaction_deleted.connect(lambda _: self.refresh())

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_filter_bar())
        layout.addWidget(self._build_table())
        layout.addWidget(self._build_statusbar())

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("QWidget { background:#fff; border-bottom:1px solid #e8e8e8; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Giao dịch")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()
        for text, slot in [("Nhập CSV", self._import_csv), ("Xuất Excel", self._export_excel)]:
            btn = QPushButton(text)
            btn.setStyleSheet(self._btn_style())
            btn.clicked.connect(slot)
            layout.addWidget(btn)
        btn_add = QPushButton("+ Thêm mới")
        btn_add.setStyleSheet(self._btn_style(primary=True))
        btn_add.clicked.connect(self._open_add_dialog)
        layout.addWidget(btn_add)
        return bar

    def _build_filter_bar(self):
        bar = QWidget()
        bar.setFixedHeight(42)
        bar.setStyleSheet(
            "QWidget { background:#f7f7f7; border-bottom:1px solid #e8e8e8; } "
            "QComboBox,QLineEdit { border:1px solid #ddd; border-radius:5px; "
            "padding:3px 8px; font-size:12px; background:#fff; color:#333; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self.cb_month = QComboBox()
        self.cb_month.setFixedWidth(130)
        self._populate_months()
        self.cb_month.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.cb_month)

        self.cb_type = QComboBox()
        self.cb_type.setFixedWidth(120)
        self.cb_type.addItems(["Tất cả loại", "Chi tiêu", "Thu nhập"])
        self.cb_type.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self.cb_type)

        self.cb_category = QComboBox()
        self.cb_category.setFixedWidth(140)
        self._populate_categories()
        self.cb_category.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self.cb_category)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Tìm kiếm mô tả...")
        self.search_box.setFixedWidth(180)
        self.search_box.textChanged.connect(self._apply_filters)
        layout.addWidget(self.search_box)
        layout.addStretch()

        btn_ai = QPushButton("Phân loại AI")
        btn_ai.setStyleSheet(self._btn_style())
        btn_ai.clicked.connect(self._run_ai_classify)
        layout.addWidget(btn_ai)
        return bar

    def _build_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setStyleSheet("""
            QTableWidget {
                background:#fff; border:none;
                gridline-color:#f0f0f0; font-size:12px;
            }
            QTableWidget::item { padding:6px 12px; color:#333; }
            QTableWidget::item:selected { background:#E6F1FB; color:#0C447C; }
            QHeaderView::section {
                background:#f7f7f7; color:#888;
                font-size:10px; font-weight:bold;
                border:none; border-bottom:1px solid #e8e8e8;
                padding:6px 12px;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_edit_dialog)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        return self.table

    def _build_statusbar(self):
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            "QWidget { background:#fff; border-top:1px solid #e8e8e8; } "
            "QLabel { font-size:11px; color:#999; } "
            "QPushButton { font-size:11px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        self.lbl_count   = QLabel("0 giao dịch")
        self.lbl_income  = QLabel("Thu: 0 đ")
        self.lbl_expense = QLabel("Chi: 0 đ")
        self.lbl_anomaly = QLabel("")
        for lbl in [self.lbl_count, self.lbl_income, self.lbl_expense, self.lbl_anomaly]:
            layout.addWidget(lbl)

        layout.addStretch()

        # ── Phân trang ────────────────────────────────────────────────────────
        self.btn_prev = QPushButton("◀ Trước")
        self.btn_prev.setFixedHeight(24)
        self.btn_prev.setStyleSheet(
            "QPushButton { background:#f7f7f7; color:#555; border:1px solid #ddd; "
            "border-radius:4px; padding:0 8px; } "
            "QPushButton:hover { background:#e8e8e8; } "
            "QPushButton:disabled { color:#ccc; border-color:#eee; }"
        )
        self.btn_prev.clicked.connect(lambda: self._change_page(-1))

        self.lbl_page = QLabel("Trang 1 / 1")
        self.lbl_page.setStyleSheet("color:#555; font-size:11px;")

        self.btn_next = QPushButton("Tiếp ▶")
        self.btn_next.setFixedHeight(24)
        self.btn_next.setStyleSheet(self.btn_prev.styleSheet())
        self.btn_next.clicked.connect(lambda: self._change_page(1))

        layout.addWidget(self.btn_prev)
        layout.addWidget(self.lbl_page)
        layout.addWidget(self.btn_next)
        return bar

    # ── Core refresh ──────────────────────────────────────────────────────────

    def refresh(self):
        month = self.cb_month.currentData()
        self._all_transactions = self.tm.get_transactions(month=month, limit=2000)
        self._populate_categories()
        self._page = 0
        self._apply_filters()

    def _apply_filters(self):
        type_filter = self.cb_type.currentText()
        cat_filter  = self.cb_category.currentText()
        search      = self.search_box.text().lower()

        filtered = []
        for tx in self._all_transactions:
            if type_filter == "Chi tiêu" and tx["type"] != "expense":
                continue
            if type_filter == "Thu nhập" and tx["type"] != "income":
                continue
            if cat_filter != "Tất cả danh mục" and tx.get("category_name") != cat_filter:
                continue
            if search and search not in (tx.get("description") or "").lower():
                continue
            filtered.append(tx)

        self._filtered_transactions = filtered

        # Reset về trang đầu khi filter thay đổi
        self._page = 0
        self._update_pagination()
        self._fill_table_paged()
        self._update_statusbar(filtered)

    def _update_pagination(self):
        total = len(self._filtered_transactions)
        total_pages = max(1, (total - 1) // self.PAGE_SIZE + 1)
        current_page = self._page + 1

        self.lbl_page.setText(f"Trang {current_page} / {total_pages}")
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._page < total_pages - 1)

    def _change_page(self, delta: int):
        total = len(self._filtered_transactions)
        total_pages = max(1, (total - 1) // self.PAGE_SIZE + 1)
        self._page = max(0, min(self._page + delta, total_pages - 1))
        self._update_pagination()
        self._fill_table_paged()

    def _fill_table_paged(self):
        start = self._page * self.PAGE_SIZE
        end   = start + self.PAGE_SIZE
        self._fill_table(self._filtered_transactions[start:end])

    # ── Render table ──────────────────────────────────────────────────────────

    def _fill_table(self, transactions: list):
        self.table.setRowCount(0)
        cat_colors = self._get_cat_colors()
        for row_idx, tx in enumerate(transactions):
            self.table.insertRow(row_idx)

            date_str = tx.get("date", "")
            try:
                date_str = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                pass
            self._set_cell(row_idx, 0, date_str, "#888")

            desc = tx.get("description") or ""
            if tx.get("is_anomaly"):
                desc += "  [!]"
            item_desc = QTableWidgetItem(desc)
            if "[!]" in desc:
                item_desc.setForeground(QBrush(QColor("#E24B4A")))
            item_desc.setData(Qt.ItemDataRole.UserRole, tx["id"])
            self.table.setItem(row_idx, 1, item_desc)

            cat_name = tx.get("category_name") or ""
            cat_item = QTableWidgetItem(cat_name)
            cat_item.setForeground(QBrush(QColor(cat_colors.get(cat_name, "#888"))))
            self.table.setItem(row_idx, 2, cat_item)

            self._set_cell(row_idx, 3, tx.get("account_name") or "", "#888")

            sign  = "+" if tx["type"] == "income" else "-"
            color = "#1D9E75" if tx["type"] == "income" else "#E24B4A"
            amt_item = QTableWidgetItem(f"{sign}{tx['amount']:,.0f} đ".replace(",", "."))
            amt_item.setForeground(QBrush(QColor(color)))
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 4, amt_item)

            self._set_cell(row_idx, 5, tx.get("note") or "—", "#aaa")

        self.table.resizeRowsToContents()

    def _update_statusbar(self, transactions: list):
        income  = sum(t["amount"] for t in transactions if t["type"] == "income")
        expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        anomaly = sum(1 for t in transactions if t.get("is_anomaly"))

        self.lbl_count.setText(f"{len(transactions)} giao dịch")
        self.lbl_income.setText(f"Thu: {income:,.0f} đ".replace(",", "."))
        self.lbl_income.setStyleSheet("font-size:11px; color:#1D9E75;")
        self.lbl_expense.setText(f"Chi: {expense:,.0f} đ".replace(",", "."))
        self.lbl_expense.setStyleSheet("font-size:11px; color:#E24B4A;")
        self.lbl_anomaly.setText(f"Bất thường: {anomaly}" if anomaly else "")
        if anomaly:
            self.lbl_anomaly.setStyleSheet("font-size:11px; color:#E24B4A;")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _run_ai_classify(self):
        month = self.cb_month.currentData()
        txs = self.tm.get_transactions(month=month, limit=500)
        self.ai_worker = ClassifyWorker(txs)
        self.ai_worker.finished.connect(self.refresh)
        self.ai_worker.start()

    def _open_add_dialog(self):
        dialog = TransactionDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            # Sửa: add_transaction() trả về int (tx_id), không phải dict
            # Budget alert đã tự phát qua bus.notify_warning trong TransactionManager
            self.tm.add_transaction(**data)

            if self.main_window:
                self.main_window.refresh_all()
            else:
                self.refresh()

    def _open_edit_dialog(self, index):
        row = index.row()
        item = self.table.item(row, 1)
        if not item:
            return
        tx_id = item.data(Qt.ItemDataRole.UserRole)
        tx = next((t for t in self._all_transactions if t["id"] == tx_id), None)
        if not tx:
            return
        dialog = TransactionDialog(parent=self, transaction=tx)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.tm.update_transaction(tx_id, **data)

            # Retrain AI nếu danh mục thay đổi
            if tx.get("category_id") != data.get("category_id"):
                try:
                    from app.ai.classifier import TransactionClassifier
                    TransactionClassifier().retrain()
                except Exception as e:
                    from app.core.logger import get_logger
                    get_logger(__name__).warning(f"Retrain thất bại: {e}")

            if self.main_window:
                self.main_window.refresh_all()
            else:
                self.refresh()

    def _context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        item = self.table.item(row, 1)
        if not item:
            return
        tx_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#fff; border:1px solid #ddd; border-radius:6px; } "
            "QMenu::item { padding:6px 16px; font-size:12px; } "
            "QMenu::item:selected { background:#E6F1FB; color:#0C447C; }"
        )
        menu.addAction("Sửa").triggered.connect(
            lambda: self._open_edit_dialog(self.table.indexFromItem(item)))

        tx = next((t for t in self._all_transactions if t["id"] == tx_id), None)
        if tx and tx.get("is_anomaly"):
            menu.addSeparator()
            menu.addAction("✓ Xác nhận Bất thường (Đúng)").triggered.connect(
                lambda: self._feedback_anomaly(tx_id, 1))
            menu.addAction("✗ Bỏ qua Bất thường (Sai)").triggered.connect(
                lambda: self._feedback_anomaly(tx_id, -1))

        menu.addSeparator()
        menu.addAction("Xóa").triggered.connect(
            lambda: self._delete_transaction(tx_id))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _delete_transaction(self, tx_id: int):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            "Bạn có chắc muốn xóa giao dịch này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.tm.delete_transaction(tx_id)
            if self.main_window:
                self.main_window.refresh_all()
            else:
                self.refresh()

    def _feedback_anomaly(self, tx_id: int, feedback_value: int):
        from app.data.models import DatabaseManager
        db = DatabaseManager()
        if feedback_value == -1:
            db.execute_write(
                "UPDATE transactions SET is_anomaly_feedback=?, is_anomaly=0 WHERE id=?",
                (feedback_value, tx_id)
            )
        else:
            db.execute_write(
                "UPDATE transactions SET is_anomaly_feedback=? WHERE id=?",
                (feedback_value, tx_id)
            )
        QMessageBox.information(
            self, "AI Feedback",
            "Cảm ơn bạn đã phản hồi! AI sẽ học từ dữ liệu này."
        )
        self.refresh()

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            from app.core.csv_importer import CsvImporter
            count, warnings = CsvImporter().import_file(path)
            msg = f"Đã nhập {count} giao dịch"
            if warnings:
                msg += "\n\nLog:\n" + "\n".join(warnings)
            QMessageBox.information(self, "Thành công", msg)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Excel", "bao_cao.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            month = self.cb_month.currentData()
            txs = self.tm.get_transactions(month=month, limit=10000)
            df = pd.DataFrame(txs)[
                ["date", "description", "category_name",
                 "account_name", "amount", "type", "note"]
            ]
            df.columns = ["Ngày", "Mô tả", "Danh mục",
                          "Tài khoản", "Số tiền", "Loại", "Ghi chú"]
            df.to_excel(path, index=False)
            QMessageBox.information(self, "Thành công", f"Đã xuất {len(df)} giao dịch")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_cell(self, row: int, col: int, text: str, color: str = "#333"):
        item = QTableWidgetItem(text)
        item.setForeground(QBrush(QColor(color)))
        self.table.setItem(row, col, item)

    def _populate_months(self):
        now = datetime.now()
        for i in range(11, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12; y -= 1
            self.cb_month.addItem(f"Tháng {m}/{y}", userData=f"{y}-{m:02d}")
        self.cb_month.setCurrentIndex(self.cb_month.count() - 1)

    def _populate_categories(self):
        current = self.cb_category.currentText()
        self.cb_category.clear()
        self.cb_category.addItem("Tất cả danh mục")
        with get_connection() as conn:
            for r in conn.execute(
                "SELECT name FROM categories ORDER BY name"
            ).fetchall():
                self.cb_category.addItem(r["name"])
        idx = self.cb_category.findText(current)
        if idx >= 0:
            self.cb_category.setCurrentIndex(idx)

    def _get_cat_colors(self) -> dict:
        with get_connection() as conn:
            rows = conn.execute("SELECT name, color FROM categories").fetchall()
        return {r["name"]: r["color"] for r in rows}

    @staticmethod
    def _btn_style(primary: bool = False) -> str:
        if primary:
            return (
                "QPushButton { background:#E6F1FB; color:#0C447C; "
                "border:1px solid #B5D4F4; border-radius:6px; "
                "padding:6px 14px; font-size:12px; font-weight:500; } "
                "QPushButton:hover { background:#B5D4F4; }"
            )
        return (
            "QPushButton { background:#fff; color:#555; "
            "border:1px solid #ddd; border-radius:6px; "
            "padding:6px 12px; font-size:12px; } "
            "QPushButton:hover { background:#f5f5f5; }"
        )


# ── TransactionDialog — thêm dropdown tài khoản ──────────────────────────────

class TransactionDialog(QDialog):
    def __init__(self, parent=None, transaction=None):
        super().__init__(parent)
        self.transaction = transaction
        is_edit = transaction is not None
        self.setWindowTitle("Sửa giao dịch" if is_edit else "Thêm giao dịch")
        self.setFixedSize(440, 480)
        self.setStyleSheet(
            "QDialog { background:#fff; } "
            "QLabel { font-size:12px; color:#444; } "
            "QLineEdit,QComboBox,QDoubleSpinBox,QDateEdit,QTextEdit { "
            "border:1px solid #ddd; border-radius:6px; "
            "padding:6px 10px; font-size:13px; background:#fff; color:#222; }"
        )
        self._build(is_edit)
        if is_edit:
            self._fill_data(transaction)

    def _build(self, is_edit: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(10)

        # Loại giao dịch
        self.cb_type = QComboBox()
        self.cb_type.addItems(["Chi tiêu", "Thu nhập"])
        form.addRow("Loại:", self.cb_type)

        # Mô tả
        self.le_desc = QLineEdit()
        self.le_desc.setPlaceholderText("Grab Food, Lương tháng 4...")
        form.addRow("Mô tả:", self.le_desc)

        # Số tiền
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0, 999_999_999)
        self.spin_amount.setSingleStep(10_000)
        self.spin_amount.setDecimals(0)
        self.spin_amount.setSuffix(" đ")
        form.addRow("Số tiền:", self.spin_amount)

        # Ngày
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setCalendarPopup(True)
        form.addRow("Ngày:", self.date_edit)

        # Danh mục
        self.cb_cat = QComboBox()
        self.cb_cat.addItem("-- Tự động (AI) --", userData=None)
        with get_connection() as conn:
            cats = conn.execute(
                "SELECT id, name FROM categories ORDER BY name"
            ).fetchall()
        for c in cats:
            self.cb_cat.addItem(c["name"], userData=c["id"])
        form.addRow("Danh mục:", self.cb_cat)

        # ── Tài khoản — dropdown thay vì hardcode ────────────────────────────
        self.cb_account = QComboBox()
        with get_connection() as conn:
            accounts = conn.execute(
                "SELECT id, name, balance FROM accounts ORDER BY name"
            ).fetchall()
        if accounts:
            for acc in accounts:
                bal = f"{acc['balance']:,.0f}đ".replace(",", ".")
                self.cb_account.addItem(f"{acc['name']} ({bal})", userData=acc["id"])
        else:
            # Fallback nếu chưa có tài khoản nào
            self.cb_account.addItem("Tiền mặt", userData=1)
        form.addRow("Tài khoản:", self.cb_account)

        # Ghi chú
        self.te_note = QTextEdit()
        self.te_note.setFixedHeight(70)
        self.te_note.setPlaceholderText("Ghi chú tùy chọn...")
        form.addRow("Ghi chú:", self.te_note)

        layout.addLayout(form)

        # Buttons
        btn_l = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(TransactionFrame._btn_style())
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Lưu" if is_edit else "Thêm giao dịch")
        btn_save.setStyleSheet(TransactionFrame._btn_style(primary=True))
        btn_save.clicked.connect(self.accept)
        btn_l.addWidget(btn_cancel)
        btn_l.addWidget(btn_save)
        layout.addLayout(btn_l)

    def _fill_data(self, tx: dict):
        self.cb_type.setCurrentText(
            "Thu nhập" if tx["type"] == "income" else "Chi tiêu")
        self.le_desc.setText(tx.get("description") or "")
        self.spin_amount.setValue(tx.get("amount") or 0)
        if tx.get("date"):
            d = datetime.strptime(tx["date"], "%Y-%m-%d")
            self.date_edit.setDate(QDate(d.year, d.month, d.day))
        if tx.get("category_id"):
            idx = self.cb_cat.findData(tx["category_id"])
            if idx >= 0:
                self.cb_cat.setCurrentIndex(idx)
        if tx.get("account_id"):
            idx = self.cb_account.findData(tx["account_id"])
            if idx >= 0:
                self.cb_account.setCurrentIndex(idx)
        self.te_note.setPlainText(tx.get("note") or "")

    def get_data(self) -> dict:
        return {
            "account_id":  self.cb_account.currentData() or 1,
            "amount":      self.spin_amount.value(),
            "type_":       "income" if self.cb_type.currentText() == "Thu nhập" else "expense",
            "description": self.le_desc.text().strip(),
            "date":        self.date_edit.date().toString("yyyy-MM-dd"),
            "category_id": self.cb_cat.currentData(),
            "note":        self.te_note.toPlainText().strip(),
        }
