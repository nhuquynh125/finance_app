# app/ui/budget_frame.py
# Refactored: improved typography contrast, larger fonts, fixed button overlap,
# tighter summary card margins, scaled-up AI tips text.

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QDialog, QFormLayout, QDoubleSpinBox,
    QComboBox, QProgressBar, QMessageBox, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from app.data.models import get_connection
from app.core.transaction_manager import TransactionManager
from app.data.repositories import BudgetRepo
from datetime import datetime


# ── Design tokens ─────────────────────────────────────────────────────────────
NAVY        = "#0B2A4A"
NAVY_MID    = "#1A6BAF"
NAVY_LIGHT  = "#378ADD"
MINT        = "#1D9E75"
ORANGE      = "#E8921A"
RED_SOFT    = "#E24B4A"
BG_PAGE     = "#F0F6FF"
BORDER_BLUE = "#D0E4F7"
CARD_WHITE  = "#FFFFFF"
TEXT_DARK   = "#0B2A4A"
TEXT_MID    = "#2C4A6A"
TEXT_MUTED  = "#4A6785"
ACCENT_BLUE = "#E6F1FB"


class BudgetFrame(QWidget):

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self._current_month = datetime.now().strftime("%Y-%m")
        self._build()
        QTimer.singleShot(100, self.refresh)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{BG_PAGE}; }}")
        content = QWidget()
        content.setStyleSheet(f"background:{BG_PAGE};")
        self.cl = QVBoxLayout(content)
        self.cl.setContentsMargins(16, 14, 16, 16)
        self.cl.setSpacing(14)

        # Summary KPI row
        self.summary_widget = QWidget()
        self.summary_widget.setStyleSheet("background:transparent;")
        self.summary_layout = QHBoxLayout(self.summary_widget)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(12)
        self.cl.addWidget(self.summary_widget)

        # Budget cards grid
        self.cards_widget = QWidget()
        self.cards_widget.setStyleSheet("background:transparent;")
        self.cards_layout = QGridLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cl.addWidget(self.cards_widget)

        # AI Tips section
        self.tips_panel = QFrame()
        self.tips_panel.setStyleSheet(
            f"QFrame {{ background:{CARD_WHITE}; border:1px solid {BORDER_BLUE}; border-radius:12px; }}")
        self.tips_layout = QVBoxLayout(self.tips_panel)
        self.tips_layout.setContentsMargins(20, 16, 20, 16)
        self.tips_layout.setSpacing(10)

        # Section heading — larger, high-contrast
        tips_title = QLabel("Gợi ý từ AI")
        tips_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        tips_title.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        self.tips_layout.addWidget(tips_title)
        self.cl.addWidget(self.tips_panel)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        # Page header — larger, darker
        title = QLabel("Ngân sách")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        layout.addWidget(title)
        layout.addStretch()

        # Month selector — larger font, high-contrast
        self.cb_month = QComboBox()
        self.cb_month.setFixedWidth(155)
        self.cb_month.setFixedHeight(36)
        self.cb_month.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 15px;
                font-weight: 600;
                color: {TEXT_DARK};
                background: {CARD_WHITE};
            }}
            QComboBox:hover {{ border-color: {NAVY_MID}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
        """)
        self._populate_months()
        self.cb_month.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.cb_month)

        btn_add = QPushButton("+ Đặt ngân sách")
        btn_add.setFixedHeight(36)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_BLUE};
                color: {NAVY_MID};
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                padding: 0 18px;
                font-size: 15px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {BORDER_BLUE}; color: {NAVY}; }}
        """)
        btn_add.clicked.connect(self._open_add_dialog)
        layout.addWidget(btn_add)

        return bar

    # ── Refresh ────────────────────────────────────────────────────────────────

    def refresh(self):
        month = self.cb_month.currentData()
        self._current_month = month
        self._sync_spent_amounts(month)
        budgets = self._load_budgets(month)
        summary = self._calc_summary(budgets)
        self._render_summary(summary)
        self._render_cards(budgets)
        self._render_tips(budgets, summary)

    def _sync_spent_amounts(self, month: str):
        BudgetRepo().sync_spent(month)

    def _load_budgets(self, month: str) -> list:
        conn = get_connection()
        rows = conn.execute("""
            SELECT b.*, c.name as cat_name, c.color
            FROM budgets b JOIN categories c ON b.category_id=c.id
            WHERE b.month=?
            ORDER BY b.limit_amount DESC
        """, (month,)).fetchall()
        conn.close()
        budgets = [dict(r) for r in rows]
        for b in budgets:
            limit = b["limit_amount"] or 1
            spent = b["spent_amount"] or 0
            b["pct"]       = min(100, int(spent / limit * 100))
            b["remaining"] = max(0, limit - spent)
            b["over"]      = max(0, spent - limit)
            if b["pct"] >= 100:
                b["status"] = "over"
            elif b["pct"] >= int((b.get("alert_threshold", 0.8)) * 100):
                b["status"] = "warning"
            else:
                b["status"] = "ok"
        return budgets

    def _calc_summary(self, budgets: list) -> dict:
        total_limit = sum(b["limit_amount"] for b in budgets)
        total_spent = sum(b["spent_amount"] or 0 for b in budgets)
        over_count  = sum(1 for b in budgets if b["status"] == "over")
        warn_count  = sum(1 for b in budgets if b["status"] == "warning")
        return {
            "total_limit": total_limit,
            "total_spent": total_spent,
            "remaining":   max(0, total_limit - total_spent),
            "over_count":  over_count,
            "warn_count":  warn_count,
        }

    # ── Summary KPI Cards ──────────────────────────────────────────────────────

    def _render_summary(self, summary: dict):
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        defs = [
            ("Tổng ngân sách",          summary["total_limit"],  TEXT_DARK,  "#E8F4FD"),
            ("Đã chi tiêu",              summary["total_spent"],  RED_SOFT,   "#FEF0F0"),
            ("Còn lại",                  summary["remaining"],    MINT,       "#EAF7F2"),
            ("Danh mục vượt ngân sách",  summary["over_count"],
             RED_SOFT if summary["over_count"] else MINT,
             "#FEF0F0" if summary["over_count"] else "#EAF7F2"),
        ]
        for label, value, val_color, bg in defs:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 1.5px solid {BORDER_BLUE};
                    border-radius: 12px;
                }}
            """)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cl = QVBoxLayout(card)
            # Tighter margins — remove dead space below title
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(4)

            # Sub-label — readable size and dark enough
            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
            lbl.setStyleSheet(f"color:{TEXT_MUTED}; border:none; background:transparent;")
            lbl.setWordWrap(True)
            cl.addWidget(lbl)

            # Value — scaled up, high-contrast
            if isinstance(value, int) and label.startswith("Danh mục"):
                val_text = str(value)
            else:
                val_text = f"{value:,.0f} đ".replace(",", ".")
            val = QLabel(val_text)
            val.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
            val.setStyleSheet(f"color:{val_color}; border:none; background:transparent;")
            cl.addWidget(val)

            self.summary_layout.addWidget(card)

    # ── Budget Category Cards ──────────────────────────────────────────────────

    def _render_cards(self, budgets: list):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not budgets:
            empty = QLabel("Chưa có ngân sách nào. Nhấn '+ Đặt ngân sách' để bắt đầu.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFont(QFont("Segoe UI", 16))
            empty.setStyleSheet(f"color:{TEXT_MUTED}; padding:40px; border:none;")
            self.cards_layout.addWidget(empty, 0, 0, 1, 2)
            return

        for idx, b in enumerate(budgets):
            card = self._make_budget_card(b)
            self.cards_layout.addWidget(card, idx // 2, idx % 2)

    def _make_budget_card(self, b: dict) -> QFrame:
        status = b["status"]
        if status == "over":
            border_color = RED_SOFT
            prog_color   = RED_SOFT
        elif status == "warning":
            border_color = ORANGE
            prog_color   = ORANGE
        else:
            border_color = BORDER_BLUE
            prog_color   = MINT

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {CARD_WHITE};
                border: 1.5px solid {border_color};
                border-radius: 12px;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # ── Row 1: Category name + badge ──────────────────────────────────────
        # Keep name and badge on one sub-row, action buttons on a separate row
        # to prevent any overlap with amount text below.
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        cat_color = b.get("color") or NAVY_MID
        name_label = QLabel(b["cat_name"])
        name_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color:{cat_color}; border:none; background:transparent;")
        name_row.addWidget(name_label)
        name_row.addStretch()

        if status == "over":
            badge_text  = "Vượt ngân sách"
            badge_style = f"background:#FCEBEB; color:#A32D2D;"
        elif status == "warning":
            badge_text  = "Sắp hết"
            badge_style = f"background:#FAEEDA; color:#633806;"
        else:
            badge_text  = "Bình thường"
            badge_style = f"background:#EAF3DE; color:#3B6D11;"

        badge = QLabel(badge_text)
        badge.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
        badge.setStyleSheet(
            f"QLabel {{ {badge_style} border:none; border-radius:10px; "
            f"padding:3px 10px; background:{badge_style.split(':')[1].split(';')[0]}; }}")
        name_row.addWidget(badge)
        layout.addLayout(name_row)

        # ── Row 2: Spending amounts (no buttons in this row) ──────────────────
        amounts = QHBoxLayout()
        amounts.setSpacing(0)

        spent_lbl = QLabel(f'Chi: <b>{self._fmt(b["spent_amount"] or 0)}</b>')
        spent_lbl.setFont(QFont("Segoe UI", 15))
        spent_lbl.setStyleSheet(f"color:{RED_SOFT}; border:none; background:transparent;")
        amounts.addWidget(spent_lbl)

        amounts.addStretch()

        limit_lbl = QLabel(f'Ngân sách: <b>{self._fmt(b["limit_amount"])}</b>')
        limit_lbl.setFont(QFont("Segoe UI", 15))
        limit_lbl.setStyleSheet(f"color:{TEXT_MID}; border:none; background:transparent;")
        amounts.addWidget(limit_lbl)

        layout.addLayout(amounts)

        # ── Row 3: Progress bar ────────────────────────────────────────────────
        prog = QProgressBar()
        prog.setRange(0, 100)
        prog.setValue(b["pct"])
        prog.setFixedHeight(8)
        prog.setTextVisible(False)
        prog.setStyleSheet(f"""
            QProgressBar {{
                background: #F0F4F8;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {prog_color};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(prog)

        # ── Row 4: Percent + remaining/over ───────────────────────────────────
        info_row = QHBoxLayout()
        info_row.setSpacing(0)

        pct_lbl = QLabel(f"{b['pct']}%")
        pct_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        pct_lbl.setStyleSheet(f"color:{prog_color}; border:none; background:transparent;")
        info_row.addWidget(pct_lbl)
        info_row.addStretch()

        if status == "over":
            rem_text  = f"Vượt: {self._fmt(b['over'])}"
            rem_color = RED_SOFT
        else:
            rem_text  = f"Còn lại: {self._fmt(b['remaining'])}"
            rem_color = MINT
        rem_lbl = QLabel(rem_text)
        rem_lbl.setFont(QFont("Segoe UI", 15))
        rem_lbl.setStyleSheet(f"color:{rem_color}; border:none; background:transparent;")
        info_row.addWidget(rem_lbl)
        layout.addLayout(info_row)

        # ── Row 5: Action buttons on their own dedicated row ──────────────────
        # Isolated from amount text — eliminates all overlap.
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch()

        btn_edit = QPushButton("✏ Sửa")
        btn_edit.setFixedHeight(28)
        btn_edit.setMinimumWidth(60)
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_BLUE};
                color: {NAVY_MID};
                border: 1px solid {BORDER_BLUE};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton:hover {{ background: {BORDER_BLUE}; color: {NAVY}; }}
        """)
        btn_edit.clicked.connect(lambda _, bid=b["id"]: self._open_edit_dialog(bid))
        action_row.addWidget(btn_edit)

        btn_del = QPushButton("🗑 Xóa")
        btn_del.setFixedHeight(28)
        btn_del.setMinimumWidth(60)
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background: #FEF0F0;
                color: {RED_SOFT};
                border: 1px solid #F5C6CB;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton:hover {{ background: #FCEBEB; color: #A32D2D; }}
        """)
        btn_del.clicked.connect(lambda _, bid=b["id"]: self._delete_budget(bid))
        action_row.addWidget(btn_del)

        layout.addLayout(action_row)

        return card

    # ── AI Tips ────────────────────────────────────────────────────────────────

    def _render_tips(self, budgets: list, summary: dict):
        # Keep title widget (index 0), remove rest
        while self.tips_layout.count() > 1:
            item = self.tips_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        tips = self._generate_tips(budgets, summary)
        if not tips:
            lbl = QLabel("Ngân sách đang được kiểm soát tốt! 🎉")
            lbl.setFont(QFont("Segoe UI", 16))
            lbl.setStyleSheet(f"color:{MINT}; border:none; background:transparent;")
            self.tips_layout.addWidget(lbl)
            return

        for icon, tip in tips:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(10)

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(22)
            icon_lbl.setFont(QFont("Segoe UI", 17))
            icon_lbl.setStyleSheet("border:none; background:transparent;")
            row.addWidget(icon_lbl)

            # AI tip text — scaled up for comfortable reading
            tip_lbl = QLabel(tip)
            tip_lbl.setFont(QFont("Segoe UI", 15))
            tip_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
            tip_lbl.setWordWrap(True)
            row.addWidget(tip_lbl)

            self.tips_layout.addWidget(row_w)

    def _generate_tips(self, budgets: list, summary: dict) -> list:
        tips = []
        over  = [b for b in budgets if b["status"] == "over"]
        warn  = [b for b in budgets if b["status"] == "warning"]
        ok    = [b for b in budgets if b["status"] == "ok"]

        for b in over:
            tips.append(("⚠", f"Danh mục '{b['cat_name']}' đã vượt ngân sách "
                               f"{self._fmt(b['over'])} — cần điều chỉnh chi tiêu."))
        for b in warn:
            pct = b["pct"]
            tips.append(("〜", f"Danh mục '{b['cat_name']}' đã dùng {pct}% ngân sách — "
                               f"còn {self._fmt(b['remaining'])} cho phần còn lại của tháng."))
        if not budgets:
            tips.append(("ℹ", "Hãy đặt ngân sách cho từng danh mục để theo dõi chi tiêu hiệu quả."))
        elif len(ok) == len(budgets) and budgets:
            tips.append(("✓", "Tuyệt vời! Tất cả danh mục đang trong ngưỡng ngân sách."))
        if summary["total_spent"] > 0 and summary["total_limit"] > 0:
            overall_pct = summary["total_spent"] / summary["total_limit"] * 100
            if overall_pct > 90:
                tips.append(("⚠", f"Đã chi {overall_pct:.0f}% tổng ngân sách — "
                                   f"còn {self._fmt(summary['remaining'])} cho tháng này."))
        return tips

    # ── Dialogs ────────────────────────────────────────────────────────────────

    def _open_add_dialog(self):
        dialog = BudgetDialog(parent=self, month=self._current_month)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self._save_budget(data)
            self.refresh()

    def _open_edit_dialog(self, budget_id: int):
        conn = get_connection()
        b = conn.execute(
            "SELECT * FROM budgets WHERE id=?", (budget_id,)
        ).fetchone()
        conn.close()
        if not b:
            return
        dialog = BudgetDialog(parent=self, month=self._current_month, budget=dict(b))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            conn = get_connection()
            conn.execute(
                "UPDATE budgets SET limit_amount=?, alert_threshold=? WHERE id=?",
                (data["limit_amount"], data["alert_threshold"], budget_id)
            )
            conn.commit()
            conn.close()
            self.refresh()

    def _delete_budget(self, budget_id: int):
        reply = QMessageBox.question(
            self, "Xác nhận xóa", "Xóa ngân sách này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM budgets WHERE id=?", (budget_id,))
            conn.commit()
            conn.close()
            self.refresh()

    def _save_budget(self, data: dict):
        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM budgets WHERE category_id=? AND month=?",
            (data["category_id"], data["month"])
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE budgets SET limit_amount=?, alert_threshold=? WHERE id=?",
                (data["limit_amount"], data["alert_threshold"], existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO budgets (category_id, limit_amount, spent_amount, month, alert_threshold) "
                "VALUES (?, ?, 0, ?, ?)",
                (data["category_id"], data["limit_amount"], data["month"], data["alert_threshold"])
            )
        conn.commit()
        conn.close()

    def _populate_months(self):
        now = datetime.now()
        for i in range(5, -3, -1):
            m = now.month + i
            y = now.year
            while m > 12:
                m -= 12; y += 1
            while m <= 0:
                m += 12; y -= 1
            self.cb_month.addItem(f"Tháng {m}/{y}", userData=f"{y}-{m:02d}")
        current = datetime.now().strftime("%Y-%m")
        for i in range(self.cb_month.count()):
            if self.cb_month.itemData(i) == current:
                self.cb_month.setCurrentIndex(i)
                break

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f} đ".replace(",", ".")


# ── BudgetDialog ───────────────────────────────────────────────────────────────

class BudgetDialog(QDialog):
    def __init__(self, parent=None, month: str = "", budget: dict = None):
        super().__init__(parent)
        self.month  = month
        self.budget = budget
        is_edit = budget is not None
        self.setWindowTitle("Sửa ngân sách" if is_edit else "Đặt ngân sách")
        self.setFixedSize(400, 310)
        self.setStyleSheet(f"""
            QDialog {{ background: {CARD_WHITE}; }}
            QLabel  {{ font-size: 15px; color: {TEXT_DARK}; }}
            QDoubleSpinBox, QComboBox {{
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 15px;
                background: {CARD_WHITE};
                color: {TEXT_DARK};
            }}
            QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {NAVY_MID}; }}
        """)
        self._build(is_edit)
        if is_edit:
            self._fill(budget)

    def _build(self, is_edit: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cb_cat = QComboBox()
        conn = get_connection()
        cats = conn.execute(
            "SELECT id, name FROM categories WHERE type='expense' ORDER BY name"
        ).fetchall()
        conn.close()
        for c in cats:
            self.cb_cat.addItem(c["name"], userData=c["id"])
        if is_edit:
            self.cb_cat.setEnabled(False)
        form.addRow("Danh mục:", self.cb_cat)

        self.spin_limit = QDoubleSpinBox()
        self.spin_limit.setRange(0, 999_999_999)
        self.spin_limit.setSingleStep(100_000)
        self.spin_limit.setDecimals(0)
        self.spin_limit.setSuffix(" đ")
        form.addRow("Ngân sách:", self.spin_limit)

        self.spin_alert = QDoubleSpinBox()
        self.spin_alert.setRange(10, 100)
        self.spin_alert.setSingleStep(5)
        self.spin_alert.setDecimals(0)
        self.spin_alert.setSuffix("%")
        self.spin_alert.setValue(80)
        form.addRow("Cảnh báo khi đạt:", self.spin_alert)

        layout.addLayout(form)

        note = QLabel("* Cảnh báo hiện khi chi tiêu vượt % ngân sách đặt ra")
        note.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
        layout.addWidget(note)

        layout.addStretch()

        btn_l = QHBoxLayout()
        btn_l.setSpacing(10)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {CARD_WHITE};
                color: {TEXT_MUTED};
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                font-size: 15px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {BG_PAGE}; }}
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Lưu" if is_edit else "Đặt ngân sách")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_BLUE};
                color: {NAVY_MID};
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: {BORDER_BLUE}; color: {NAVY}; }}
        """)
        btn_save.clicked.connect(self.accept)

        btn_l.addWidget(btn_cancel)
        btn_l.addWidget(btn_save)
        layout.addLayout(btn_l)

    def _fill(self, budget: dict):
        conn = get_connection()
        cat = conn.execute(
            "SELECT name FROM categories WHERE id=?", (budget["category_id"],)
        ).fetchone()
        conn.close()
        if cat:
            idx = self.cb_cat.findText(cat["name"])
            if idx >= 0:
                self.cb_cat.setCurrentIndex(idx)
        self.spin_limit.setValue(budget.get("limit_amount", 0))
        threshold = budget.get("alert_threshold", 0.8)
        self.spin_alert.setValue(int(threshold * 100))

    def get_data(self) -> dict:
        return {
            "category_id":     self.cb_cat.currentData(),
            "limit_amount":    self.spin_limit.value(),
            "alert_threshold": self.spin_alert.value() / 100,
            "month":           self.month,
        }