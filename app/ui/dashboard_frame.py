# app/ui/dashboard_frame.py
"""
Dashboard — tổng quan tài chính tháng.

Fix blank-screen:
  - __init__ KHÔNG còn gọi QTimer.singleShot(100, self.refresh) trực tiếp.
    Việc refresh() được gọi bởi MainWindow._navigate() sau khi frame visible.
  - Debounce timer giữ nguyên (150ms) — chống flood event-bus.
  - Matplotlib backend được set một lần ở module level (đã đúng).
  - Không thay đổi bất kỳ logic nghiệp vụ nào.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout,
    QDialog, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app.core.transaction_manager import TransactionManager
from app.data.models import get_connection
from app.core.event_bus import bus, BusConnectMixin
from datetime import datetime


# ── Color palette (từ logo) ───────────────────────────────────────────────────
NAVY        = "#0B2A4A"
NAVY_MID    = "#1A6BAF"
MINT        = "#1D9E75"
ORANGE      = "#E8921A"
RED_SOFT    = "#E85020"
BG_BLUE     = "#F0F6FF"
BORDER_BLUE = "#D0E4F7"
CARD_WHITE  = "#FFFFFF"


# ── MetricCard ────────────────────────────────────────────────────────────────

class MetricCard(QFrame):
    """Card KPI với accent bar mỏng ở trên cùng."""

    def __init__(self, label: str, value: str = "--",
                 color: str = NAVY_MID, icon: str = "", parent=None):
        super().__init__(parent)
        self._accent_color = color
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD_WHITE};
                border: 1px solid {BORDER_BLUE};
                border-radius: 14px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        if icon:
            ic = QLabel(icon)
            ic.setFont(QFont("Segoe UI Emoji", 16))
            ic.setStyleSheet("border:none; background:transparent;")
            ic.setFixedWidth(28)
            top.addWidget(ic)
        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet("color:#8BAEC8; border:none; background:transparent;")
        top.addWidget(lbl)
        top.addStretch()
        layout.addLayout(top)

        self.val_lbl = QLabel(value)
        self.val_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.val_lbl.setStyleSheet(f"color:{color}; border:none; background:transparent;")
        layout.addWidget(self.val_lbl)

        self.trend_lbl = QLabel("")
        self.trend_lbl.setFont(QFont("Segoe UI", 9))
        self.trend_lbl.setStyleSheet("color:#8BAEC8; border:none; background:transparent;")
        layout.addWidget(self.trend_lbl)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self._accent_color)))
        painter.drawRoundedRect(0, 0, self.width(), 4, 2, 2)
        painter.end()

    def set_value(self, text: str):
        self.val_lbl.setText(text)

    def set_trend(self, text: str, color: str):
        self.trend_lbl.setText(text)
        self.trend_lbl.setStyleSheet(f"color:{color}; border:none; background:transparent;")


# ── DashboardFrame ────────────────────────────────────────────────────────────

class DashboardFrame(QWidget, BusConnectMixin):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self.current_month = datetime.now().strftime("%Y-%m")

        # Debounce timer — chống refresh flood khi nhiều signal đến cùng lúc
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(150)
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._pie_legend_widgets: list = []
        self._metric_cards: dict[str, MetricCard] = {}

        self._build()
        self._connect_bus()

        # Không gọi refresh() ở đây.
        # MainWindow._navigate() sẽ gọi refresh() sau khi frame visible.

    def _connect_bus(self):
        bus.transaction_added.connect(self.refresh)
        bus.balance_changed.connect(self.refresh)
        bus.budget_updated.connect(
            lambda m: self.refresh() if m == self.current_month else None
        )

    def refresh(self):
        """Public entry — debounced để tránh nhiều lần refresh liên tiếp."""
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    # ── Build layout ──────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_BLUE}; }}")

        content = QWidget()
        content.setStyleSheet(f"background: {BG_BLUE};")
        self.cl = QVBoxLayout(content)
        self.cl.setContentsMargins(20, 18, 20, 20)
        self.cl.setSpacing(14)

        self._build_cards()
        self._build_charts()
        self._build_recent()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(54)
        bar.setStyleSheet(
            f"background: {CARD_WHITE}; border-bottom: 1px solid {BORDER_BLUE};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        title = QLabel("Dashboard")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{NAVY}; border:none;")
        layout.addWidget(title)

        today_lbl = QLabel("\U0001f4c5  " + datetime.now().strftime("%d/%m/%Y"))
        today_lbl.setStyleSheet("color:#8BAEC8; font-size:12px; border:none;")
        layout.addWidget(today_lbl)

        layout.addStretch()

        self.cb_month = QComboBox()
        self.cb_month.setFixedWidth(148)
        self.cb_month.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 12px;
                background: {CARD_WHITE};
                color: {NAVY};
            }}
            QComboBox:hover {{ border-color: {NAVY_MID}; }}
        """)
        self._populate_months()
        self.cb_month.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.cb_month)

        btn_add = QPushButton("＋  Thêm giao dịch")
        btn_add.setFixedHeight(36)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {NAVY_MID}, stop:1 {NAVY});
                color: #FFFFFF; border: none; border-radius: 9px;
                padding: 0 18px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {NAVY}, stop:1 #061422);
            }}
        """)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._open_add_dialog)
        layout.addWidget(btn_add)
        return bar

    def _build_cards(self):
        self.cards_w = QWidget()
        self.cards_w.setStyleSheet("background: transparent;")
        g = QGridLayout(self.cards_w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(12)

        defs = [
            ("Thu nhập",        MINT,     "💰"),
            ("Chi tiêu",        RED_SOFT, "💳"),
            ("Tiết kiệm",       NAVY_MID, "🏦"),
            ("AI dự báo T.sau", ORANGE,   "📈"),
        ]
        for i, (label, color, icon) in enumerate(defs):
            card = MetricCard(label, "--", color, icon)
            g.addWidget(card, 0, i)
            self._metric_cards[label] = card

        self.cl.addWidget(self.cards_w)

    def _build_charts(self):
        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(14)

        # Bar chart panel
        self.bar_panel = QFrame()
        self.bar_panel.setStyleSheet(f"""
            QFrame {{
                background: {CARD_WHITE};
                border: 1px solid {BORDER_BLUE};
                border-radius: 14px;
            }}
        """)
        bar_l = QVBoxLayout(self.bar_panel)
        bar_l.setContentsMargins(18, 14, 18, 14)
        bar_l.setSpacing(8)

        bar_header = QHBoxLayout()
        t1 = QLabel("Thu chi 6 tháng gần đây")
        t1.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t1.setStyleSheet(f"color:{NAVY}; border:none;")
        bar_header.addWidget(t1)
        bar_header.addStretch()
        for color, text in [(MINT, "Thu nhập"), (ORANGE, "Chi tiêu")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:14px; border:none;")
            lbl = QLabel(text)
            lbl.setStyleSheet("color:#8BAEC8; font-size:11px; border:none;")
            bar_header.addWidget(dot)
            bar_header.addWidget(lbl)
            bar_header.addSpacing(8)
        bar_l.addLayout(bar_header)

        self.bar_fig = Figure(figsize=(5, 2.4), facecolor="none")
        self.bar_canvas = FigureCanvasQTAgg(self.bar_fig)
        self.bar_canvas.setFixedHeight(200)
        bar_l.addWidget(self.bar_canvas)
        row_l.addWidget(self.bar_panel, stretch=2)

        # Pie chart panel
        self.pie_panel = QFrame()
        self.pie_panel.setStyleSheet(f"""
            QFrame {{
                background: {CARD_WHITE};
                border: 1px solid {BORDER_BLUE};
                border-radius: 14px;
            }}
        """)
        self.pie_layout = QVBoxLayout(self.pie_panel)
        self.pie_layout.setContentsMargins(18, 14, 18, 14)
        self.pie_layout.setSpacing(6)

        t2 = QLabel("Danh mục chi tiêu")
        t2.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t2.setStyleSheet(f"color:{NAVY}; border:none;")
        self.pie_layout.addWidget(t2)

        self.pie_fig = Figure(figsize=(2.4, 2.4), facecolor="none")
        self.pie_canvas = FigureCanvasQTAgg(self.pie_fig)
        self.pie_canvas.setFixedHeight(150)
        self.pie_layout.addWidget(self.pie_canvas)
        row_l.addWidget(self.pie_panel, stretch=1)

        self.cl.addWidget(row_w)

    def _build_recent(self):
        self.tx_panel = QFrame()
        self.tx_panel.setStyleSheet(f"""
            QFrame {{
                background: {CARD_WHITE};
                border: 1px solid {BORDER_BLUE};
                border-radius: 14px;
            }}
        """)
        self.tx_layout = QVBoxLayout(self.tx_panel)
        self.tx_layout.setContentsMargins(18, 14, 18, 14)
        self.tx_layout.setSpacing(8)

        header = QHBoxLayout()
        t = QLabel("Giao dịch gần đây")
        t.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{NAVY}; border:none;")
        header.addWidget(t)
        header.addStretch()
        if self.main_window:
            btn = QPushButton("Xem tất cả →")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{NAVY_MID};
                    border:none; font-size:12px; font-weight:500;
                }}
                QPushButton:hover {{ color:{NAVY}; }}
            """)
            btn.clicked.connect(lambda: self.main_window._navigate("Giao dịch"))
            header.addWidget(btn)
        self.tx_layout.addLayout(header)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background:{BORDER_BLUE}; border:none; max-height:1px;")
        self.tx_layout.addWidget(div)

        self.cl.addWidget(self.tx_panel)

    # ── Refresh logic ─────────────────────────────────────────────────────────

    def _do_refresh(self):
        month = self.cb_month.currentData()
        if not month:
            return
        self.current_month = month

        now = datetime.now()
        bar_months = []
        for i in range(5, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            bar_months.append(f"{y}-{m:02d}")

        # Tính prev_month để hiện trend
        all_months = list(dict.fromkeys(bar_months + [month]))
        try:
            prev_dt = datetime.strptime(month, "%Y-%m")
            prev_month = (
                prev_dt.replace(year=prev_dt.year - 1, month=12).strftime("%Y-%m")
                if prev_dt.month == 1
                else prev_dt.replace(month=prev_dt.month - 1).strftime("%Y-%m")
            )
            if prev_month not in all_months:
                all_months.append(prev_month)
        except Exception:
            prev_month = None

        summaries = self.tm.get_multi_month_summary(all_months)
        cur     = summaries.get(month, {"total_income": 0, "total_expense": 0})
        income  = cur["total_income"]
        expense = cur["total_expense"]
        saving  = income - expense

        prev_income = prev_expense = prev_saving = None
        if prev_month and prev_month in summaries:
            p = summaries[prev_month]
            prev_income  = p["total_income"]
            prev_expense = p["total_expense"]
            prev_saving  = prev_income - prev_expense

        fc = self._get_forecast(month)

        # Cập nhật metric cards
        self._metric_cards["Thu nhập"].set_value(self._fmt(income))
        self._metric_cards["Chi tiêu"].set_value(self._fmt(expense))
        self._metric_cards["Tiết kiệm"].set_value(self._fmt(saving))
        self._metric_cards["AI dự báo T.sau"].set_value(self._fmt(fc))

        self._update_trend("Thu nhập",  income,  prev_income)
        self._update_trend("Chi tiêu",  expense, prev_expense)
        self._update_trend("Tiết kiệm", saving,  prev_saving)

        self._draw_bar(bar_months, summaries)
        self._draw_pie(month)
        self._draw_recent(month)

    def _update_trend(self, label: str, current: float, previous):
        card = self._metric_cards.get(label)
        if not card:
            return
        if previous is None or previous == 0:
            card.set_trend("", "#8BAEC8")
            return
        delta = current - previous
        pct   = (delta / previous) * 100
        arrow = "↑" if delta > 0 else "↓"
        is_good = (delta > 0) if label != "Chi tiêu" else (delta < 0)
        color = MINT if is_good else RED_SOFT
        card.set_trend(f"{arrow} {abs(pct):.1f}% so với tháng trước", color)

    def _draw_bar(self, bar_months: list, summaries: dict):
        months_data = []
        for ms in bar_months:
            s = summaries.get(ms, {"total_income": 0, "total_expense": 0})
            try:
                m_num = int(ms.split("-")[1])
            except Exception:
                m_num = 0
            months_data.append({
                "label":   f"T{m_num}",
                "income":  (s["total_income"]  or 0) / 1e6,
                "expense": (s["total_expense"] or 0) / 1e6,
            })

        self.bar_fig.clear()
        ax = self.bar_fig.add_subplot(111)
        self.bar_fig.subplots_adjust(left=0.10, right=0.97, top=0.92, bottom=0.15)
        ax.set_facecolor("#FFFFFF")

        labels  = [d["label"]   for d in months_data]
        incomes = [d["income"]  for d in months_data]
        expens  = [d["expense"] for d in months_data]
        x = range(len(labels))
        w = 0.35

        ax.bar([i - w / 2 for i in x], incomes, w,
               color=MINT,   alpha=0.90, zorder=3, linewidth=0)
        ax.bar([i + w / 2 for i in x], expens,  w,
               color=ORANGE, alpha=0.90, zorder=3, linewidth=0)

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=9, color="#8BAEC8")
        ax.tick_params(labelsize=9, colors="#8BAEC8", length=0)
        ax.set_ylabel("Triệu đ", fontsize=9, color="#8BAEC8")
        ax.yaxis.grid(True, color=BORDER_BLUE, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(axis="x", bottom=False)
        self.bar_canvas.draw()

    def _draw_pie(self, month: str):
        conn = get_connection()
        rows = conn.execute("""
            SELECT c.name, c.color, SUM(t.amount) as total
            FROM transactions t JOIN categories c ON t.category_id=c.id
            WHERE t.type='expense' AND strftime('%Y-%m',t.date)=?
            GROUP BY c.id ORDER BY total DESC LIMIT 6
        """, (month,)).fetchall()

        for w in self._pie_legend_widgets:
            self.pie_layout.removeWidget(w)
            w.deleteLater()
        self._pie_legend_widgets.clear()

        self.pie_fig.clear()
        if not rows:
            self.pie_canvas.draw()
            return

        sizes  = [r["total"] for r in rows]
        colors = [r["color"] for r in rows]
        names  = [r["name"]  for r in rows]

        ax = self.pie_fig.add_subplot(111)
        ax.set_facecolor("#FFFFFF")
        self.pie_fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        wedges, _ = ax.pie(sizes, colors=colors, startangle=90,
                           wedgeprops={"linewidth": 2, "edgecolor": "#F0F6FF"})
        import matplotlib.pyplot as plt
        ax.add_artist(plt.Circle((0, 0), 0.58, color="#FFFFFF"))
        self.pie_canvas.draw()

        total = sum(sizes)
        for name, color, size in zip(names, colors, sizes):
            pct = size / total * 100 if total else 0
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(7)
            dot = QFrame()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(f"background:{color}; border-radius:4px; border:none;")
            rl.addWidget(dot)
            lbl = QLabel(name)
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color:{NAVY}; border:none;")
            rl.addWidget(lbl)
            rl.addStretch()
            pct_lbl = QLabel(f"{pct:.0f}%")
            pct_lbl.setStyleSheet("color:#8BAEC8; font-size:10px; border:none;")
            rl.addWidget(pct_lbl)
            self.pie_layout.addWidget(row_w)
            self._pie_legend_widgets.append(row_w)

    def _draw_recent(self, month: str):
        # Xóa row cũ (giữ header=index-0 và divider=index-1)
        while self.tx_layout.count() > 2:
            item = self.tx_layout.takeAt(2)
            if item.widget():
                item.widget().deleteLater()

        txs = self.tm.get_transactions(month=month, limit=7)
        if not txs:
            lbl = QLabel("Chưa có giao dịch trong tháng này")
            lbl.setStyleSheet(
                "color:#8BAEC8; font-size:12px; padding:16px; border:none;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tx_layout.addWidget(lbl)
            return

        for tx in txs:
            row = QWidget()
            row.setStyleSheet(f"""
                QWidget {{
                    background: {BG_BLUE};
                    border-radius: 10px;
                    border: 1px solid {BORDER_BLUE};
                }}
                QWidget:hover {{ background: #E0EEFF; }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 9, 14, 9)
            rl.setSpacing(12)

            is_income = tx["type"] == "income"
            dot_bg    = "#EAF7F2" if is_income else "#FEF5EC"
            dot_color = MINT      if is_income else ORANGE
            dot_text  = "+"       if is_income else "-"

            dot = QLabel(dot_text)
            dot.setFixedSize(32, 32)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            dot.setStyleSheet(
                f"background:{dot_bg}; color:{dot_color}; "
                f"border-radius:8px; border:none;"
            )
            rl.addWidget(dot)

            desc_w = QWidget()
            desc_w.setStyleSheet("background:transparent; border:none;")
            dl = QVBoxLayout(desc_w)
            dl.setContentsMargins(0, 0, 0, 0)
            dl.setSpacing(2)

            desc_str  = tx.get("description") or "Không có mô tả"
            cat_label = f"  [{tx['category_name']}]" if tx.get("category_name") else ""
            if tx.get("is_anomaly"):
                desc_str += "  ⚠"

            name_lbl = QLabel(desc_str)
            name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color:{NAVY}; border:none; background:transparent;")
            dl.addWidget(name_lbl)

            meta = QLabel(f"{tx['date']}{cat_label} · {tx.get('account_name', '')}")
            meta.setFont(QFont("Segoe UI", 10))
            meta.setStyleSheet("color:#8BAEC8; border:none; background:transparent;")
            dl.addWidget(meta)
            rl.addWidget(desc_w)
            rl.addStretch()

            amt = QLabel(f"{dot_text}{tx['amount']:,.0f} đ".replace(",", "."))
            amt.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            amt.setStyleSheet(
                f"color:{dot_color}; border:none; background:transparent;"
            )
            rl.addWidget(amt)
            self.tx_layout.addWidget(row)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_forecast(self, month: str) -> float:
        conn = get_connection()
        row = conn.execute(
            "SELECT COALESCE(SUM(predicted_amount),0) as t "
            "FROM ai_predictions WHERE month=?",
            (month,),
        ).fetchone()
        return row["t"] if row else 0

    def _populate_months(self):
        now = datetime.now()
        for i in range(11, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            self.cb_month.addItem(f"Tháng {m}/{y}", userData=f"{y}-{m:02d}")
        self.cb_month.setCurrentIndex(self.cb_month.count() - 1)

    def _open_add_dialog(self):
        from app.ui.transaction_frame import TransactionDialog
        dialog = TransactionDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.tm.add_transaction(**data)
            if self.main_window:
                self.main_window.refresh_all()
            else:
                self.refresh()

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f} đ".replace(",", ".")
