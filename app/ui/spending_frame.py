# app/ui/spending_frame.py
"""
Trang Quản lý Chi tiêu — Finance AI
Tính năng:
  - Biểu đồ donut phân loại chi tiêu theo danh mục
  - Danh mục con / danh mục cha (tab)
  - Xu hướng chi tiêu 3 tháng (bar chart)
  - Ngân sách chi tiêu inline
  - Cảnh báo tăng bất thường so với tháng trước
  - Điều hướng tháng (< >)
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy, QStackedWidget,
    QButtonGroup,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient, QRadialGradient, QConicalGradient,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

from app.data.models import get_connection
from app.core.transaction_manager import TransactionManager


# ── Bảng màu danh mục ────────────────────────────────────────────────────────

CATEGORY_PALETTE = [
    "#FF7043",  # Ăn uống — Cam đỏ
    "#FFA726",  # Mua sắm — Cam vàng
    "#AB47BC",  # Giải trí — Tím
    "#26C6DA",  # Hóa đơn — Xanh ngọc
    "#66BB6A",  # Di chuyển — Xanh lá
    "#EC407A",  # Y tế — Hồng
    "#42A5F5",  # Giáo dục — Xanh dương
    "#8D6E63",  # Khác — Nâu
    "#BDBDBD",  # Chưa phân loại — Xám
]

BG_COLOR    = "#FFF8F8"
CARD_WHITE  = "#FFFFFF"
PINK_ACCENT = "#F06292"
PINK_LIGHT  = "#FCE4EC"
PINK_BORDER = "#F8BBD9"
TEXT_DARK   = "#2D2D2D"
TEXT_MUTED  = "#9E9E9E"
ORANGE_WARN = "#FF6D00"
GREEN_OK    = "#2E7D32"


# ══════════════════════════════════════════════════════════════════════════════
# ── Donut Chart Widget (thuần PyQt, không matplotlib) ────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class DonutChartWidget(QWidget):
    """
    Biểu đồ donut thuần PyQt — không cần matplotlib.
    Vẽ trực tiếp bằng QPainter → mượt, nhanh, đẹp.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._data: list[dict] = []          # [{name, value, color, pct}]
        self._hovered: int = -1
        self._total: float = 0
        self.setMouseTracking(True)

    def set_data(self, data: list[dict]):
        """data = list of {name, value, color}"""
        total = sum(d["value"] for d in data) or 1
        self._total = total
        self._data = []
        for d in data:
            pct = d["value"] / total * 100
            self._data.append({**d, "pct": pct})
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h) - 20
        cx = w / 2
        cy = h / 2

        outer_r = size / 2
        inner_r = outer_r * 0.58    # donut hole ratio

        rect_outer = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
        rect_inner = QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        start_angle = 90 * 16   # Qt angles: 1/16th degree, start at top

        gap = 1.5 * 16          # gap between segments (in Qt units)

        for i, seg in enumerate(self._data):
            span = -int(seg["pct"] / 100 * 360 * 16)

            color = QColor(seg["color"])
            if i == self._hovered:
                color = color.lighter(120)

            path = QPainterPath()
            path.moveTo(cx, cy)
            path.arcTo(rect_outer, start_angle / 16, span / 16)
            path.arcTo(rect_inner, (start_angle + span) / 16, -span / 16)
            path.closeSubpath()

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

            # Gap (white separator)
            pen = QPen(QColor("#FFF8F8"), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            start_angle += span

        # Center hole — white fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(CARD_WHITE)))
        painter.drawEllipse(rect_inner)

        # Center text
        painter.setPen(QColor(TEXT_DARK))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(cx - inner_r, cy - 20, inner_r * 2, 18),
                         Qt.AlignmentFlag.AlignCenter, "Chi tiêu")
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.setPen(QColor(PINK_ACCENT))
        total_str = self._fmt(self._total)
        painter.drawText(QRectF(cx - inner_r, cy - 2, inner_r * 2, 22),
                         Qt.AlignmentFlag.AlignCenter, total_str)

        painter.end()

    def mouseMoveEvent(self, event):
        # Detect hover over segment
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        dx = event.position().x() - cx
        dy = event.position().y() - cy
        dist = math.sqrt(dx * dx + dy * dy)
        size = min(w, h) - 20
        outer_r = size / 2
        inner_r = outer_r * 0.58

        if inner_r < dist < outer_r:
            angle = math.degrees(math.atan2(-dy, dx))
            if angle < 0:
                angle += 360
            # convert: our 0° is at top (90°)
            angle = (90 - angle) % 360

            cumulative = 0
            hovered = -1
            for i, seg in enumerate(self._data):
                end = cumulative + seg["pct"] / 100 * 360
                if cumulative <= angle < end:
                    hovered = i
                    break
                cumulative = end
            if hovered != self._hovered:
                self._hovered = hovered
                self.update()
        else:
            if self._hovered != -1:
                self._hovered = -1
                self.update()

    def leaveEvent(self, event):
        self._hovered = -1
        self.update()

    @staticmethod
    def _fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}K"
        return f"{v:.0f}"


# ══════════════════════════════════════════════════════════════════════════════
# ── Trend Bar Canvas ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TrendBarCanvas(FigureCanvasQTAgg):
    """Bar chart xu hướng chi tiêu 3 tháng."""

    def __init__(self):
        self.fig = Figure(figsize=(4, 2.2), facecolor="none")
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(160)

    def plot(self, months: list[str], values: list[float], current_idx: int = -1):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.18)
        ax.set_facecolor("#FFFFFF")

        max_v = max(values) if values else 1
        colors = []
        for i, _ in enumerate(values):
            if i == current_idx or (current_idx == -1 and i == len(values) - 1):
                colors.append(PINK_ACCENT)
            else:
                colors.append("#F8BBD9")

        x = list(range(len(months)))
        bars = ax.bar(x, [v / 1e6 for v in values], color=colors,
                      width=0.55, zorder=3, linewidth=0, edgecolor="none")

        # Round top corners effect via overlay
        for bar, color in zip(bars, colors):
            bar.set_linewidth(0)

        labels = []
        for m in months:
            try:
                dt = datetime.strptime(m, "%Y-%m")
                lbl = f"T{dt.month}"
            except Exception:
                lbl = m
            labels.append(lbl)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10, color=TEXT_DARK)
        # highlight current month label
        for i, tick in enumerate(ax.get_xticklabels()):
            if i == len(months) - 1 or i == current_idx:
                tick.set_color(PINK_ACCENT)
                tick.set_fontweight("bold")

        ax.set_yticks([])
        ax.set_ylim(0, max_v / 1e6 * 1.3)
        ax.yaxis.grid(False)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="x", bottom=False, length=0)

        # Value labels on bars
        for bar, val in zip(bars, values):
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + max_v / 1e6 * 0.03,
                    f"{val/1e6:.1f}M" if val >= 1e6 else f"{val/1e3:.0f}K",
                    ha="center", va="bottom", fontsize=8, color=TEXT_MUTED)

        self.draw()


# ══════════════════════════════════════════════════════════════════════════════
# ── Category Row ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class CategoryRow(QWidget):
    """Một hàng danh mục với icon màu, tên, số tiền, và mũi tên."""

    clicked = pyqtSignal(dict)

    def __init__(self, cat_data: dict, parent=None):
        super().__init__(parent)
        self._data = cat_data
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(52)
        self.setStyleSheet("""
            QWidget {
                background: white;
                border-bottom: 1px solid #FCE4EC;
            }
            QWidget:hover {
                background: #FFF8F8;
            }
        """)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 12, 8)
        layout.setSpacing(12)

        # Color dot
        dot = QFrame()
        dot.setFixedSize(38, 38)
        dot.setStyleSheet(f"""
            QFrame {{
                background: {self._data.get('color', '#BDBDBD')};
                border-radius: 12px;
                border: none;
            }}
        """)
        layout.addWidget(dot)

        # Name
        name_lbl = QLabel(self._data.get("name", ""))
        name_lbl.setFont(QFont("Segoe UI", 12))
        name_lbl.setStyleSheet("color:#2D2D2D; border:none; background:transparent;")
        layout.addWidget(name_lbl, stretch=1)

        # Tag nếu chưa phân loại
        if self._data.get("unclassified_count", 0):
            tag = QLabel(f"  {self._data['unclassified_count']}  ")
            tag.setStyleSheet("""
                QLabel {
                    background: #F06292;
                    color: white;
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: bold;
                    border: none;
                    padding: 2px 6px;
                }
            """)
            layout.addWidget(tag)

        # Amount
        amt_lbl = QLabel(self._fmt(self._data.get("total", 0)))
        amt_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        amt_lbl.setStyleSheet("color:#2D2D2D; border:none; background:transparent;")
        layout.addWidget(amt_lbl)

        # Arrow
        arrow = QLabel("›")
        arrow.setFont(QFont("Segoe UI", 16))
        arrow.setStyleSheet("color:#E0E0E0; border:none; background:transparent;")
        layout.addWidget(arrow)

    def mousePressEvent(self, event):
        self.clicked.emit(self._data)

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f}đ".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
# ── Budget Mini Card ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class BudgetMiniCard(QWidget):
    """Card ngân sách nhỏ hiển thị inline."""

    def __init__(self, budget_data: dict, parent=None):
        super().__init__(parent)
        self.setFixedSize(170, 140)
        self._data = budget_data
        self.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 16px;
                border: 1px solid #F8BBD9;
            }
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Icon + name
        name = self._data.get("name", "Ngân sách")
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        name_lbl.setStyleSheet("border:none; color:#2D2D2D;")
        layout.addWidget(name_lbl)

        # Circular progress (simple via QLabel + stylesheet)
        pct = self._data.get("pct", 0)
        over = pct >= 100

        if over:
            status_color = "#FF6D00"
            status_text  = "🔥 Đã vượt"
            status_style = "color:#FF6D00; font-weight:bold;"
        else:
            status_color = PINK_ACCENT
            status_text  = "Gợi ý"
            status_style = "color:#9E9E9E;"

        # Progress ring (drawn via paintEvent override — simplified as bar here)
        prog_track = QFrame()
        prog_track.setFixedHeight(6)
        prog_track.setStyleSheet(f"background:#FCE4EC; border-radius:3px; border:none;")
        prog_inner = QFrame(prog_track)
        prog_inner.setFixedHeight(6)
        prog_width = max(4, min(150, int(min(pct, 100) / 100 * 142)))
        prog_inner.setFixedWidth(prog_width)
        prog_inner.setStyleSheet(
            f"background:{status_color}; border-radius:3px; border:none;")
        layout.addWidget(prog_track)

        # Amount
        limit   = self._data.get("limit_amount", 0)
        suggest = self._data.get("suggest", 0)
        show_amount = limit if limit > 0 else suggest

        status_lbl = QLabel(status_text)
        status_lbl.setFont(QFont("Segoe UI", 9))
        status_lbl.setStyleSheet(f"border:none; {status_style}")
        layout.addWidget(status_lbl)

        amount_lbl = QLabel(self._fmt(show_amount))
        amount_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        amount_lbl.setStyleSheet(f"color:{status_color}; border:none;")
        layout.addWidget(amount_lbl)

        if not limit:
            btn = QPushButton("Đặt ngay →")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {PINK_ACCENT};
                    border: none;
                    font-size: 11px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{ color: #C2185B; }}
            """)
            layout.addWidget(btn)

    @staticmethod
    def _fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M đ"
        return f"{v:,.0f}đ".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
# ── Spending Frame (Main) ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class SpendingFrame(QWidget):
    """
    Trang Quản lý Chi tiêu.
    Thêm vào MainWindow như một page: "Quản lý Chi tiêu".
    """

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self._current_month = datetime.now().strftime("%Y-%m")
        self._view_mode = "sub"   # "sub" | "parent"
        self._show_trend = False
        self._build()
        QTimer.singleShot(100, self.refresh)

    # ── Build skeleton ────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(f"QWidget {{ background: {BG_COLOR}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        self._content = QWidget()
        self._content.setStyleSheet(f"background:{BG_COLOR};")
        self._body = QVBoxLayout(self._content)
        self._body.setContentsMargins(0, 0, 0, 20)
        self._body.setSpacing(0)

        # Sections
        self._build_summary_section()
        self._build_chart_section()
        self._build_category_section()
        self._build_budget_section()

        scroll.setWidget(self._content)
        root.addWidget(scroll)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"background:{CARD_WHITE}; border-bottom:1px solid {PINK_BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        title = QLabel("Quản lý chi tiêu")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        layout.addWidget(title)
        layout.addStretch()

        # Trend toggle
        self._btn_trend = QPushButton("📊 Xu hướng")
        self._btn_trend.setCheckable(True)
        self._btn_trend.setFixedHeight(32)
        self._btn_trend.setStyleSheet(self._tab_style(False))
        self._btn_trend.clicked.connect(self._toggle_trend)
        layout.addWidget(self._btn_trend)

        # Phân bổ toggle
        self._btn_dist = QPushButton("🥧 Phân bổ")
        self._btn_dist.setCheckable(True)
        self._btn_dist.setChecked(True)
        self._btn_dist.setFixedHeight(32)
        self._btn_dist.setStyleSheet(self._tab_style(True))
        self._btn_dist.clicked.connect(self._toggle_dist)
        layout.addWidget(self._btn_dist)
        return bar

    # ── Summary (thu chi + điều hướng) ───────────────────────────────────────

    def _build_summary_section(self):
        w = QFrame()
        w.setStyleSheet(f"QFrame {{ background:{CARD_WHITE}; border:none; }}")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Month nav
        nav = QHBoxLayout()
        self._btn_prev_m = QPushButton("‹")
        self._btn_prev_m.setFixedSize(32, 32)
        self._btn_prev_m.setStyleSheet(self._nav_btn_style())
        self._btn_prev_m.clicked.connect(self._prev_month)
        nav.addWidget(self._btn_prev_m)
        nav.addStretch()

        self._month_lbl = QLabel("Tháng này")
        self._month_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        nav.addWidget(self._month_lbl)
        nav.addStretch()

        self._btn_next_m = QPushButton("›")
        self._btn_next_m.setFixedSize(32, 32)
        self._btn_next_m.setStyleSheet(self._nav_btn_style())
        self._btn_next_m.clicked.connect(self._next_month)
        nav.addWidget(self._btn_next_m)
        layout.addLayout(nav)

        # Chi tiêu / Thu nhập cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        self._expense_card = self._summary_card("💸 Chi tiêu", "0đ", selected=True)
        self._income_card  = self._summary_card("💰 Thu nhập", "0đ", selected=False)
        cards_row.addWidget(self._expense_card)
        cards_row.addWidget(self._income_card)
        layout.addLayout(cards_row)

        # Warning banner
        self._warning_banner = QFrame()
        self._warning_banner.setStyleSheet("""
            QFrame {
                background: #FFF3E0;
                border-radius: 10px;
                border: 1px solid #FFE0B2;
            }
        """)
        wb_l = QHBoxLayout(self._warning_banner)
        wb_l.setContentsMargins(12, 8, 12, 8)
        wb_l.setSpacing(8)
        fire = QLabel("🔥")
        fire.setFont(QFont("Segoe UI Emoji", 14))
        fire.setStyleSheet("border:none;")
        wb_l.addWidget(fire)
        self._warning_lbl = QLabel("")
        self._warning_lbl.setFont(QFont("Segoe UI", 11))
        self._warning_lbl.setStyleSheet(f"color:{ORANGE_WARN}; border:none;")
        self._warning_lbl.setWordWrap(True)
        wb_l.addWidget(self._warning_lbl, stretch=1)
        arrow = QLabel("›")
        arrow.setFont(QFont("Segoe UI", 18))
        arrow.setStyleSheet("color:#FFB74D; border:none;")
        wb_l.addWidget(arrow)
        self._warning_banner.hide()
        layout.addWidget(self._warning_banner)

        self._body.addWidget(w)

    def _summary_card(self, label: str, value: str,
                      selected: bool = False) -> QFrame:
        card = QFrame()
        border = PINK_ACCENT if selected else "#E0E0E0"
        bg     = PINK_LIGHT   if selected else CARD_WHITE
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 14px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(4)

        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet("color:#9E9E9E; border:none; background:transparent;")
        cl.addWidget(lbl)

        # value + arrow
        row = QHBoxLayout()
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        val.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        row.addWidget(val)
        row.addStretch()
        arrow = QLabel("↑")
        arrow.setFont(QFont("Segoe UI", 12))
        arrow.setStyleSheet(f"color:{PINK_ACCENT}; border:none; background:transparent;")
        row.addWidget(arrow)
        cl.addLayout(row)

        # Store refs
        card._val_lbl   = val
        card._arrow_lbl = arrow
        return card

    # ── Chart section ─────────────────────────────────────────────────────────

    def _build_chart_section(self):
        self._chart_container = QWidget()
        self._chart_container.setStyleSheet(
            f"background:{CARD_WHITE}; border-top:1px solid {PINK_BORDER}; "
            f"border-bottom:1px solid {PINK_BORDER};")
        chart_l = QVBoxLayout(self._chart_container)
        chart_l.setContentsMargins(0, 12, 0, 12)
        chart_l.setSpacing(0)

        # Stacked: donut vs bar
        self._chart_stack = QStackedWidget()
        self._chart_stack.setStyleSheet("background:transparent;")

        # Page 0: donut
        donut_page = QWidget()
        donut_page.setStyleSheet("background:transparent;")
        donut_l = QHBoxLayout(donut_page)
        donut_l.setContentsMargins(8, 0, 8, 0)
        donut_l.setSpacing(0)

        self._donut = DonutChartWidget()
        self._donut.setFixedSize(220, 220)
        donut_l.addWidget(self._donut)

        # Legend
        self._legend_w = QWidget()
        self._legend_w.setStyleSheet("background:transparent;")
        self._legend_l = QVBoxLayout(self._legend_w)
        self._legend_l.setContentsMargins(4, 10, 8, 10)
        self._legend_l.setSpacing(4)
        donut_l.addWidget(self._legend_w, stretch=1)
        self._chart_stack.addWidget(donut_page)

        # Page 1: trend bars
        trend_page = QWidget()
        trend_page.setStyleSheet("background:transparent;")
        trend_l = QVBoxLayout(trend_page)
        trend_l.setContentsMargins(16, 8, 16, 8)
        self._trend_canvas = TrendBarCanvas()
        trend_l.addWidget(self._trend_canvas)
        self._chart_stack.addWidget(trend_page)

        chart_l.addWidget(self._chart_stack)
        self._body.addWidget(self._chart_container)

    # ── Category section ──────────────────────────────────────────────────────

    def _build_category_section(self):
        self._cat_section = QFrame()
        self._cat_section.setStyleSheet(
            f"QFrame {{ background:{CARD_WHITE}; border:none; }}")
        cat_l = QVBoxLayout(self._cat_section)
        cat_l.setContentsMargins(0, 0, 0, 0)
        cat_l.setSpacing(0)

        # Tab bar
        tab_bar = QWidget()
        tab_bar.setFixedHeight(44)
        tab_bar.setStyleSheet(f"background:{CARD_WHITE}; border-bottom:1px solid {PINK_BORDER};")
        tb_l = QHBoxLayout(tab_bar)
        tb_l.setContentsMargins(0, 0, 0, 0)
        tb_l.setSpacing(0)

        self._btn_sub = QPushButton("Danh mục con")
        self._btn_sub.setCheckable(True)
        self._btn_sub.setChecked(True)
        self._btn_sub.clicked.connect(lambda: self._switch_cat_view("sub"))
        self._btn_sub.setStyleSheet(self._cat_tab_style(True))
        self._btn_sub.setFixedHeight(44)

        self._btn_parent = QPushButton("Danh mục cha")
        self._btn_parent.setCheckable(True)
        self._btn_parent.clicked.connect(lambda: self._switch_cat_view("parent"))
        self._btn_parent.setStyleSheet(self._cat_tab_style(False))
        self._btn_parent.setFixedHeight(44)

        tb_l.addWidget(self._btn_sub)
        tb_l.addWidget(self._btn_parent)
        cat_l.addWidget(tab_bar)

        # Category list
        self._cat_list_w = QWidget()
        self._cat_list_w.setStyleSheet("background:transparent;")
        self._cat_list_l = QVBoxLayout(self._cat_list_w)
        self._cat_list_l.setContentsMargins(0, 0, 0, 0)
        self._cat_list_l.setSpacing(0)
        cat_l.addWidget(self._cat_list_w)

        # Show more / less
        self._btn_toggle_cat = QPushButton("Xem thêm ∨")
        self._btn_toggle_cat.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {PINK_ACCENT};
                border: none;
                font-size: 13px;
                font-weight: 600;
                padding: 10px;
            }}
            QPushButton:hover {{ color: #C2185B; }}
        """)
        self._cat_expanded = False
        self._btn_toggle_cat.clicked.connect(self._toggle_cat_expand)
        cat_l.addWidget(self._btn_toggle_cat, alignment=Qt.AlignmentFlag.AlignCenter)

        self._body.addWidget(self._cat_section)
        self._body.addSpacing(8)

    # ── Budget section ────────────────────────────────────────────────────────

    def _build_budget_section(self):
        self._budget_section = QWidget()
        self._budget_section.setStyleSheet("background:transparent;")
        bsl = QVBoxLayout(self._budget_section)
        bsl.setContentsMargins(16, 0, 16, 0)
        bsl.setSpacing(10)

        header_row = QHBoxLayout()
        hdr = QLabel("Ngân sách chi tiêu")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        header_row.addWidget(hdr)
        header_row.addStretch()
        see_all = QPushButton("Xem tất cả  ›")
        see_all.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{PINK_ACCENT};
                border:none; font-size:12px; font-weight:500; }}
            QPushButton:hover {{ color:#C2185B; }}
        """)
        if self.main_window:
            see_all.clicked.connect(lambda: self.main_window._navigate("Ngân sách"))
        header_row.addWidget(see_all)
        bsl.addLayout(header_row)

        self._budget_scroll_w = QWidget()
        self._budget_scroll_w.setStyleSheet("background:transparent;")
        self._budget_scroll_l = QHBoxLayout(self._budget_scroll_w)
        self._budget_scroll_l.setContentsMargins(0, 0, 0, 0)
        self._budget_scroll_l.setSpacing(10)
        self._budget_scroll_l.addStretch()
        bsl.addWidget(self._budget_scroll_w)

        self._body.addWidget(self._budget_section)

    # ── Refresh (data load) ───────────────────────────────────────────────────

    def refresh(self):
        month = self._current_month
        self._update_month_label()
        self._load_summary(month)
        self._load_chart(month)
        self._load_categories(month)
        self._load_budgets(month)
        self._check_warning(month)

    def _update_month_label(self):
        now = datetime.now().strftime("%Y-%m")
        try:
            dt = datetime.strptime(self._current_month, "%Y-%m")
            label = f"Tháng {dt.month}/{dt.year}"
            if self._current_month == now:
                label = "Tháng này"
        except Exception:
            label = self._current_month
        self._month_lbl.setText(f"📅 {label}")
        # Disable next button if at current month
        self._btn_next_m.setEnabled(self._current_month < now)

    def _load_summary(self, month: str):
        summary = self.tm.get_monthly_summary(month)
        expense = summary.get("total_expense", 0) or 0
        income  = summary.get("total_income", 0) or 0

        self._expense_card._val_lbl.setText(self._fmt(expense))
        self._income_card._val_lbl.setText(self._fmt(income))

        # arrow direction
        prev = self._prev_month_str(month)
        prev_s = self.tm.get_monthly_summary(prev)
        prev_exp = prev_s.get("total_expense", 0) or 0

        if prev_exp > 0:
            delta = expense - prev_exp
            arrow = "↑" if delta > 0 else "↓"
            color = PINK_ACCENT if delta > 0 else GREEN_OK
            self._expense_card._arrow_lbl.setText(arrow)
            self._expense_card._arrow_lbl.setStyleSheet(
                f"color:{color}; border:none; background:transparent;")

    def _load_chart(self, month: str):
        conn = get_connection()
        rows = conn.execute("""
            SELECT c.name, c.color, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type='expense' AND strftime('%Y-%m', t.date)=?
            GROUP BY c.id ORDER BY total DESC
        """, (month,)).fetchall()
        conn.close()

        if self._show_trend:
            self._load_trend_chart()
        else:
            # Donut
            data = []
            for i, r in enumerate(rows[:8]):
                color = r["color"] if r["color"] else CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
                data.append({"name": r["name"], "value": float(r["total"]),
                              "color": color})
            self._donut.set_data(data)

            # Legend
            while self._legend_l.count():
                item = self._legend_l.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            total = sum(d["value"] for d in data) or 1
            for seg in data[:6]:
                pct = seg["value"] / total * 100
                row_w = QWidget()
                row_w.setStyleSheet("background:transparent;")
                rl = QHBoxLayout(row_w)
                rl.setContentsMargins(0, 2, 0, 2)
                rl.setSpacing(6)

                dot = QFrame()
                dot.setFixedSize(10, 10)
                dot.setStyleSheet(f"background:{seg['color']}; border-radius:5px; border:none;")
                rl.addWidget(dot)

                pct_lbl = QLabel(f"{pct:.0f}%")
                pct_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                pct_lbl.setStyleSheet(f"color:{seg['color']}; border:none;")
                pct_lbl.setFixedWidth(34)
                rl.addWidget(pct_lbl)

                name_lbl = QLabel(seg["name"][:10])
                name_lbl.setFont(QFont("Segoe UI", 9))
                name_lbl.setStyleSheet("color:#757575; border:none;")
                rl.addWidget(name_lbl)
                rl.addStretch()
                self._legend_l.addWidget(row_w)
            self._legend_l.addStretch()

    def _load_trend_chart(self):
        """Load 3-month trend for bar chart."""
        now = datetime.now()
        months = []
        for i in range(2, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12; y -= 1
            months.append(f"{y}-{m:02d}")

        values = []
        for m in months:
            s = self.tm.get_monthly_summary(m)
            values.append(s.get("total_expense", 0) or 0)

        current_idx = months.index(self._current_month) if self._current_month in months else -1
        self._trend_canvas.plot(months, values, current_idx)

    def _load_categories(self, month: str):
        while self._cat_list_l.count():
            item = self._cat_list_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        conn = get_connection()
        if self._view_mode == "sub":
            rows = conn.execute("""
                SELECT c.id, c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type='expense' AND strftime('%Y-%m', t.date)=?
                GROUP BY c.id ORDER BY total DESC
            """, (month,)).fetchall()
        else:
            # Group by parent (danh mục cha) — simplified grouping
            rows = conn.execute("""
                SELECT c.id, c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type='expense' AND strftime('%Y-%m', t.date)=?
                GROUP BY c.id ORDER BY total DESC
            """, (month,)).fetchall()

        # Count unclassified
        unclassified_count = conn.execute("""
            SELECT COUNT(*) as n FROM transactions
            WHERE type='expense' AND category_id IS NULL
            AND strftime('%Y-%m', date)=?
        """, (month,)).fetchone()["n"]
        unclassified_amt = conn.execute("""
            SELECT COALESCE(SUM(amount),0) as s FROM transactions
            WHERE type='expense' AND category_id IS NULL
            AND strftime('%Y-%m', date)=?
        """, (month,)).fetchone()["s"]
        conn.close()

        all_cats = [dict(r) for r in rows]
        limit = len(all_cats) if self._cat_expanded else min(5, len(all_cats))

        for i, cat in enumerate(all_cats[:limit]):
            color = cat["color"] if cat["color"] else CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
            row = CategoryRow({
                "name": cat["name"],
                "color": color,
                "total": cat["total"] or 0,
            })
            self._cat_list_l.addWidget(row)

        # Unclassified row
        if unclassified_count > 0:
            row = CategoryRow({
                "name": "Chưa phân loại",
                "color": "#BDBDBD",
                "total": unclassified_amt or 0,
                "unclassified_count": unclassified_count,
            })
            self._cat_list_l.addWidget(row)

        # Toggle button
        has_more = len(all_cats) > 5
        self._btn_toggle_cat.setVisible(has_more)
        self._btn_toggle_cat.setText("Thu gọn ∧" if self._cat_expanded else "Xem thêm ∨")

    def _load_budgets(self, month: str):
        # Clear
        while self._budget_scroll_l.count():
            item = self._budget_scroll_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        conn = get_connection()
        budgets = conn.execute("""
            SELECT b.*, c.name as cat_name, c.color
            FROM budgets b JOIN categories c ON b.category_id = c.id
            WHERE b.month=? ORDER BY b.limit_amount DESC LIMIT 4
        """, (month,)).fetchall()
        conn.close()

        # Total budget card
        total_limit = sum(b["limit_amount"] for b in budgets)
        total_spent = sum(b["spent_amount"] or 0 for b in budgets)
        pct = (total_spent / total_limit * 100) if total_limit > 0 else 0

        if total_limit > 0:
            over = total_spent > total_limit
            total_card = BudgetMiniCard({
                "name": "Ngân sách tổng",
                "limit_amount": total_limit,
                "suggest": 0,
                "pct": pct,
            })
            self._budget_scroll_l.addWidget(total_card)

        # Individual budget cards
        for b in budgets:
            limit = b["limit_amount"]
            spent = b["spent_amount"] or 0
            b_pct = (spent / limit * 100) if limit > 0 else 0

            # AI suggest (nếu chưa có ngân sách — simplified)
            suggest_card = BudgetMiniCard({
                "name": b["cat_name"],
                "limit_amount": limit,
                "suggest": spent * 1.1,
                "pct": b_pct,
            })
            self._budget_scroll_l.addWidget(suggest_card)

        # If no budgets — suggest card
        if not budgets:
            conn = get_connection()
            top_cats = conn.execute("""
                SELECT c.name, SUM(t.amount) as total
                FROM transactions t JOIN categories c ON t.category_id=c.id
                WHERE t.type='expense' AND strftime('%Y-%m',t.date)=?
                GROUP BY c.id ORDER BY total DESC LIMIT 2
            """, (month,)).fetchall()
            conn.close()

            for cat in top_cats:
                suggest_card = BudgetMiniCard({
                    "name": cat["name"],
                    "limit_amount": 0,
                    "suggest": cat["total"] * 1.1,
                    "pct": 0,
                })
                self._budget_scroll_l.addWidget(suggest_card)

        self._budget_scroll_l.addStretch()

    def _check_warning(self, month: str):
        summary = self.tm.get_monthly_summary(month)
        expense = summary.get("total_expense", 0) or 0
        prev = self._prev_month_str(month)
        prev_s = self.tm.get_monthly_summary(prev)
        prev_exp = prev_s.get("total_expense", 0) or 0

        if prev_exp > 0:
            delta = expense - prev_exp
            pct = delta / prev_exp * 100
            if pct > 10:
                msg = (f"Tăng bất thường {self._fmt(delta)} "
                       f"({pct:+.0f}%) so với cùng kỳ tháng trước")
                self._warning_lbl.setText(msg)
                self._warning_banner.show()
            else:
                self._warning_banner.hide()
        else:
            self._warning_banner.hide()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _prev_month(self):
        try:
            dt = datetime.strptime(self._current_month, "%Y-%m")
            m, y = dt.month - 1, dt.year
            if m == 0:
                m, y = 12, y - 1
            self._current_month = f"{y}-{m:02d}"
            self.refresh()
        except Exception:
            pass

    def _next_month(self):
        try:
            dt = datetime.strptime(self._current_month, "%Y-%m")
            m, y = dt.month + 1, dt.year
            if m == 13:
                m, y = 1, y + 1
            now = datetime.now().strftime("%Y-%m")
            candidate = f"{y}-{m:02d}"
            if candidate <= now:
                self._current_month = candidate
                self.refresh()
        except Exception:
            pass

    def _toggle_trend(self):
        self._show_trend = True
        self._btn_trend.setStyleSheet(self._tab_style(True))
        self._btn_dist.setChecked(False)
        self._btn_dist.setStyleSheet(self._tab_style(False))
        self._chart_stack.setCurrentIndex(1)
        self._load_trend_chart()

    def _toggle_dist(self):
        self._show_trend = False
        self._btn_dist.setStyleSheet(self._tab_style(True))
        self._btn_trend.setChecked(False)
        self._btn_trend.setStyleSheet(self._tab_style(False))
        self._chart_stack.setCurrentIndex(0)
        self._load_chart(self._current_month)

    def _switch_cat_view(self, mode: str):
        self._view_mode = mode
        self._btn_sub.setChecked(mode == "sub")
        self._btn_parent.setChecked(mode == "parent")
        self._btn_sub.setStyleSheet(self._cat_tab_style(mode == "sub"))
        self._btn_parent.setStyleSheet(self._cat_tab_style(mode == "parent"))
        self._load_categories(self._current_month)

    def _toggle_cat_expand(self):
        self._cat_expanded = not self._cat_expanded
        self._load_categories(self._current_month)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _prev_month_str(month: str) -> str:
        try:
            dt = datetime.strptime(month, "%Y-%m")
            m, y = dt.month - 1, dt.year
            if m == 0:
                m, y = 12, y - 1
            return f"{y}-{m:02d}"
        except Exception:
            return month

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f}đ".replace(",", ".")

    @staticmethod
    def _nav_btn_style() -> str:
        return f"""
            QPushButton {{
                background:{CARD_WHITE};
                color:{TEXT_DARK};
                border:1px solid {PINK_BORDER};
                border-radius:10px;
                font-size:18px;
                font-weight:bold;
            }}
            QPushButton:hover {{ background:{PINK_LIGHT}; border-color:{PINK_ACCENT}; }}
            QPushButton:disabled {{ color:#E0E0E0; border-color:#F0F0F0; }}
        """

    @staticmethod
    def _tab_style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background:{PINK_LIGHT};
                    color:{PINK_ACCENT};
                    border:1px solid {PINK_BORDER};
                    border-radius:8px;
                    font-size:11px;
                    font-weight:600;
                    padding:4px 12px;
                }}
            """
        return f"""
            QPushButton {{
                background:{CARD_WHITE};
                color:{TEXT_MUTED};
                border:1px solid #E0E0E0;
                border-radius:8px;
                font-size:11px;
                padding:4px 12px;
            }}
            QPushButton:hover {{ background:{PINK_LIGHT}; }}
        """

    @staticmethod
    def _cat_tab_style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background:transparent;
                    color:{PINK_ACCENT};
                    border:none;
                    border-bottom:3px solid {PINK_ACCENT};
                    font-size:13px;
                    font-weight:600;
                    padding:8px 0;
                }}
            """
        return f"""
            QPushButton {{
                background:transparent;
                color:{TEXT_MUTED};
                border:none;
                border-bottom:3px solid transparent;
                font-size:13px;
                padding:8px 0;
            }}
            QPushButton:hover {{ color:{TEXT_DARK}; }}
        """
