# app/ui/spending_frame.py  (cập nhật: đổi sang theme Navy/Blue của app, biểu đồ riêng cho Chi tiêu/Thu nhập và Danh mục cha/con)
"""
Trang Quản lý Chi tiêu — Finance AI
Thay đổi:
  - Đổi toàn bộ màu từ pink sang Navy/Blue/Mint phù hợp theme app
  - Chi tiêu và Thu nhập: 2 nút toggle → 2 biểu đồ donut riêng biệt
  - Danh mục con và Danh mục cha: mỗi tab tạo biểu đồ donut riêng
  - Cảnh báo tăng chi tiêu style phù hợp app
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app.data.models import get_connection
from app.core.transaction_manager import TransactionManager


# ── Bảng màu theo theme app (Navy/Blue/Mint) ─────────────────────────────────
NAVY        = "#0B2A4A"
NAVY_MID    = "#1A6BAF"
NAVY_LIGHT  = "#378ADD"
MINT        = "#1D9E75"
ORANGE      = "#E8921A"
RED_SOFT    = "#E85020"
BG_PAGE     = "#F0F6FF"
BORDER_BLUE = "#D0E4F7"
CARD_WHITE  = "#FFFFFF"
TEXT_MUTED  = "#8BAEC8"
TEXT_DARK   = "#0B2A4A"
ACCENT_BLUE = "#E6F1FB"

# Màu cho biểu đồ danh mục
CATEGORY_PALETTE = [
    "#378ADD",   # Xanh dương chính
    "#1D9E75",   # Mint
    "#E8921A",   # Cam
    "#7F77DD",   # Tím
    "#E85020",   # Đỏ cam
    "#D4537E",   # Hồng đậm
    "#1A6BAF",   # Navy mid
    "#888780",   # Xám
    "#639922",   # Xanh lá
]


# ══════════════════════════════════════════════════════════════════════════════
# ── Donut Chart Widget (thuần PyQt) ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class DonutChartWidget(QWidget):
    """
    Biểu đồ donut thuần PyQt — theme Navy/Blue.
    Có thể hiển thị cho Chi tiêu HOẶC Thu nhập tùy trạng thái.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._data: list[dict] = []
        self._hovered: int = -1
        self._total: float = 0
        self._center_label = "Chi tiêu"
        self._center_color = RED_SOFT
        self.setMouseTracking(True)

    def set_data(self, data: list[dict], center_label: str = "Chi tiêu",
                 center_color: str = RED_SOFT):
        total = sum(d["value"] for d in data) or 1
        self._total = total
        self._center_label = center_label
        self._center_color = center_color
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
        size = min(w, h) - 16
        cx = w / 2
        cy = h / 2

        outer_r = size / 2
        inner_r = outer_r * 0.60

        rect_outer = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
        rect_inner = QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        start_angle = 90 * 16

        for i, seg in enumerate(self._data):
            span = -int(seg["pct"] / 100 * 360 * 16)
            color = QColor(seg["color"])
            if i == self._hovered:
                color = color.lighter(130)

            path = QPainterPath()
            path.moveTo(cx, cy)
            path.arcTo(rect_outer, start_angle / 16, span / 16)
            path.arcTo(rect_inner, (start_angle + span) / 16, -span / 16)
            path.closeSubpath()

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

            # Separator line trắng giữa các segment
            pen = QPen(QColor(BG_PAGE), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            start_angle += span

        # Lỗ trống center
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(CARD_WHITE)))
        painter.drawEllipse(rect_inner)

        # Text trung tâm
        painter.setPen(QColor(TEXT_MUTED))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(cx - inner_r, cy - 22, inner_r * 2, 18),
                         Qt.AlignmentFlag.AlignCenter, self._center_label)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.setPen(QColor(self._center_color))
        total_str = self._fmt(self._total)
        painter.drawText(QRectF(cx - inner_r, cy - 4, inner_r * 2, 22),
                         Qt.AlignmentFlag.AlignCenter, total_str)

        painter.end()

    def mouseMoveEvent(self, event):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        dx = event.position().x() - cx
        dy = event.position().y() - cy
        dist = math.sqrt(dx * dx + dy * dy)
        size = min(w, h) - 16
        outer_r = size / 2
        inner_r = outer_r * 0.60

        if inner_r < dist < outer_r:
            angle = math.degrees(math.atan2(-dy, dx))
            if angle < 0:
                angle += 360
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
    def __init__(self):
        self.fig = Figure(figsize=(4, 2.2), facecolor="none")
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(160)

    def plot(self, months: list[str], values: list[float], current_idx: int = -1,
             color: str = RED_SOFT, label: str = "Chi tiêu"):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.18)
        ax.set_facecolor("#FFFFFF")

        max_v = max(values) if values else 1
        bar_colors = []
        for i in range(len(values)):
            if i == current_idx or (current_idx == -1 and i == len(values) - 1):
                bar_colors.append(color)
            else:
                c = QColor(color)
                bar_colors.append(f"#{c.red():02x}{c.green():02x}{c.blue():02x}55")

        x = list(range(len(months)))
        bars = ax.bar(x, [v / 1e6 for v in values], color=bar_colors,
                      width=0.55, zorder=3, linewidth=0, edgecolor="none")

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
        for i, tick in enumerate(ax.get_xticklabels()):
            if i == len(months) - 1 or i == current_idx:
                tick.set_color(color)
                tick.set_fontweight("bold")

        ax.set_yticks([])
        ax.set_ylim(0, max_v / 1e6 * 1.35)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="x", bottom=False, length=0)

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
    clicked = pyqtSignal(dict)

    def __init__(self, cat_data: dict, parent=None):
        super().__init__(parent)
        self._data = cat_data
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QWidget {{
                background: {CARD_WHITE};
                border-bottom: 1px solid {BORDER_BLUE};
            }}
            QWidget:hover {{
                background: {ACCENT_BLUE};
            }}
        """)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 12, 8)
        layout.setSpacing(12)

        dot = QFrame()
        dot.setFixedSize(36, 36)
        dot.setStyleSheet(f"""
            QFrame {{
                background: {self._data.get('color', NAVY_LIGHT)};
                border-radius: 10px;
                border: none;
            }}
        """)
        layout.addWidget(dot)

        name_lbl = QLabel(self._data.get("name", ""))
        name_lbl.setFont(QFont("Segoe UI", 12))
        name_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        layout.addWidget(name_lbl, stretch=1)

        # Badge "unclassified"
        if self._data.get("unclassified_count", 0):
            tag = QLabel(f"  {self._data['unclassified_count']}  ")
            tag.setStyleSheet(f"""
                QLabel {{
                    background: {ORANGE};
                    color: white;
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: bold;
                    border: none;
                    padding: 2px 6px;
                }}
            """)
            layout.addWidget(tag)

        amt_lbl = QLabel(self._fmt(self._data.get("total", 0)))
        amt_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        amt_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        layout.addWidget(amt_lbl)

        arrow = QLabel("›")
        arrow.setFont(QFont("Segoe UI", 16))
        arrow.setStyleSheet(f"color:{BORDER_BLUE}; border:none; background:transparent;")
        layout.addWidget(arrow)

    def mousePressEvent(self, event):
        self.clicked.emit(self._data)

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f}đ".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
# ── Budget Mini Card (Navy theme) ────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class BudgetMiniCard(QWidget):
    def __init__(self, budget_data: dict, parent=None):
        super().__init__(parent)
        self.setFixedSize(170, 140)
        self._data = budget_data
        self.setStyleSheet(f"""
            QWidget {{
                background: {CARD_WHITE};
                border-radius: 12px;
                border: 1px solid {BORDER_BLUE};
            }}
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        name = self._data.get("name", "Ngân sách")
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"border:none; color:{TEXT_DARK};")
        layout.addWidget(name_lbl)

        pct = self._data.get("pct", 0)
        over = pct >= 100

        if over:
            bar_color  = RED_SOFT
            status_text  = "Đã vượt"
            status_style = f"color:{RED_SOFT}; font-weight:bold;"
        elif pct >= 80:
            bar_color  = ORANGE
            status_text  = "Sắp hết"
            status_style = f"color:{ORANGE}; font-weight:bold;"
        else:
            bar_color  = MINT
            status_text  = "Bình thường"
            status_style = f"color:{MINT};"

        prog_track = QFrame()
        prog_track.setFixedHeight(6)
        prog_track.setStyleSheet(f"background:{ACCENT_BLUE}; border-radius:3px; border:none;")
        prog_inner = QFrame(prog_track)
        prog_inner.setFixedHeight(6)
        prog_width = max(4, min(142, int(min(pct, 100) / 100 * 142)))
        prog_inner.setFixedWidth(prog_width)
        prog_inner.setStyleSheet(f"background:{bar_color}; border-radius:3px; border:none;")
        layout.addWidget(prog_track)

        status_lbl = QLabel(status_text)
        status_lbl.setFont(QFont("Segoe UI", 9))
        status_lbl.setStyleSheet(f"border:none; {status_style}")
        layout.addWidget(status_lbl)

        limit   = self._data.get("limit_amount", 0)
        suggest = self._data.get("suggest", 0)
        show_amount = limit if limit > 0 else suggest

        amount_lbl = QLabel(self._fmt(show_amount))
        amount_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        amount_lbl.setStyleSheet(f"color:{bar_color}; border:none;")
        layout.addWidget(amount_lbl)

        if not limit:
            btn = QPushButton("Đặt ngân sách →")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {NAVY_MID};
                    border: none;
                    font-size: 11px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{ color: {NAVY}; }}
            """)
            layout.addWidget(btn)

    @staticmethod
    def _fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M đ"
        return f"{v:,.0f}đ".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
# ── SpendingFrame (Main) — Navy/Blue Theme ────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class SpendingFrame(QWidget):
    """
    Trang Quản lý Chi tiêu — theme Navy/Blue.
    - Toggle Chi tiêu / Thu nhập → 2 biểu đồ donut riêng
    - Tab Danh mục con / Danh mục cha → 2 biểu đồ donut riêng
    """

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self._current_month = datetime.now().strftime("%Y-%m")
        self._view_mode   = "sub"       # "sub" | "parent"
        self._data_mode   = "expense"   # "expense" | "income"
        self._show_trend  = False
        self._cat_expanded = False
        self._build()
        QTimer.singleShot(100, self.refresh)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(f"QWidget {{ background: {BG_PAGE}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{BG_PAGE}; }}")

        self._content = QWidget()
        self._content.setStyleSheet(f"background:{BG_PAGE};")
        self._body = QVBoxLayout(self._content)
        self._body.setContentsMargins(0, 0, 0, 20)
        self._body.setSpacing(0)

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
        bar.setStyleSheet(
            f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        title = QLabel("Quản lý chi tiêu")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        layout.addWidget(title)
        layout.addStretch()

        self._btn_trend = QPushButton("📊 Xu hướng")
        self._btn_trend.setCheckable(True)
        self._btn_trend.setFixedHeight(32)
        self._btn_trend.setStyleSheet(self._tab_style(False))
        self._btn_trend.clicked.connect(self._toggle_trend)
        layout.addWidget(self._btn_trend)

        self._btn_dist = QPushButton("🥧 Phân bổ")
        self._btn_dist.setCheckable(True)
        self._btn_dist.setChecked(True)
        self._btn_dist.setFixedHeight(32)
        self._btn_dist.setStyleSheet(self._tab_style(True))
        self._btn_dist.clicked.connect(self._toggle_dist)
        layout.addWidget(self._btn_dist)
        return bar

    # ── Summary section ───────────────────────────────────────────────────────

    def _build_summary_section(self):
        w = QFrame()
        w.setStyleSheet(f"QFrame {{ background:{CARD_WHITE}; border:none; }}")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

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

        # Cards Chi tiêu / Thu nhập — click để switch biểu đồ
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._expense_card = self._summary_card("💸 Chi tiêu",  "0đ", selected=True,  click_mode="expense")
        self._income_card  = self._summary_card("💰 Thu nhập",  "0đ", selected=False, click_mode="income")
        cards_row.addWidget(self._expense_card)
        cards_row.addWidget(self._income_card)
        layout.addLayout(cards_row)

        # Warning banner (Navy style)
        self._warning_banner = QFrame()
        self._warning_banner.setStyleSheet(f"""
            QFrame {{
                background: {ACCENT_BLUE};
                border-radius: 10px;
                border: 1px solid {BORDER_BLUE};
            }}
        """)
        wb_l = QHBoxLayout(self._warning_banner)
        wb_l.setContentsMargins(12, 8, 12, 8)
        wb_l.setSpacing(8)
        fire = QLabel("⚠")
        fire.setFont(QFont("Segoe UI", 14))
        fire.setStyleSheet("border:none;")
        wb_l.addWidget(fire)
        self._warning_lbl = QLabel("")
        self._warning_lbl.setFont(QFont("Segoe UI", 11))
        self._warning_lbl.setStyleSheet(f"color:{ORANGE}; border:none;")
        self._warning_lbl.setWordWrap(True)
        wb_l.addWidget(self._warning_lbl, stretch=1)
        arrow2 = QLabel("›")
        arrow2.setFont(QFont("Segoe UI", 18))
        arrow2.setStyleSheet(f"color:{NAVY_MID}; border:none;")
        wb_l.addWidget(arrow2)
        self._warning_banner.hide()
        layout.addWidget(self._warning_banner)

        self._body.addWidget(w)

    def _summary_card(self, label: str, value: str,
                      selected: bool = False, click_mode: str = "expense") -> QFrame:
        """Card tóm tắt có thể click để đổi biểu đồ."""
        card = QFrame()
        border = NAVY_MID if selected else BORDER_BLUE
        bg     = ACCENT_BLUE if selected else CARD_WHITE
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {NAVY_MID};
                background: {ACCENT_BLUE};
            }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card._mode = click_mode

        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(4)

        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color:{TEXT_MUTED}; border:none; background:transparent;")
        cl.addWidget(lbl)

        row = QHBoxLayout()
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        val.setStyleSheet(
            f"color:{RED_SOFT if click_mode == 'expense' else MINT}; "
            f"border:none; background:transparent;"
        )
        row.addWidget(val)
        row.addStretch()
        arrow = QLabel("↑")
        arrow.setFont(QFont("Segoe UI", 12))
        arrow.setStyleSheet(f"color:{NAVY_MID}; border:none; background:transparent;")
        row.addWidget(arrow)
        cl.addLayout(row)

        card._val_lbl   = val
        card._arrow_lbl = arrow

        # Click handler
        def on_click(event, mode=click_mode):
            self._switch_data_mode(mode)
        card.mousePressEvent = on_click

        return card

    # ── Chart section — stack: donut hoặc bar ─────────────────────────────────

    def _build_chart_section(self):
        self._chart_container = QWidget()
        self._chart_container.setStyleSheet(
            f"background:{CARD_WHITE}; border-top:1px solid {BORDER_BLUE}; "
            f"border-bottom:1px solid {BORDER_BLUE};")
        chart_l = QVBoxLayout(self._chart_container)
        chart_l.setContentsMargins(0, 12, 0, 12)
        chart_l.setSpacing(0)

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

        # Tab bar (Danh mục con / Danh mục cha — mỗi tab có biểu đồ riêng)
        tab_bar = QWidget()
        tab_bar.setFixedHeight(44)
        tab_bar.setStyleSheet(
            f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
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

        self._btn_toggle_cat = QPushButton("Xem thêm ∨")
        self._btn_toggle_cat.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {NAVY_MID};
                border: none;
                font-size: 13px;
                font-weight: 600;
                padding: 10px;
            }}
            QPushButton:hover {{ color: {NAVY}; }}
        """)
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
            QPushButton {{ background:transparent; color:{NAVY_MID};
                border:none; font-size:12px; font-weight:500; }}
            QPushButton:hover {{ color:{NAVY}; }}
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

    # ── Refresh ───────────────────────────────────────────────────────────────

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
        self._btn_next_m.setEnabled(self._current_month < now)

    def _load_summary(self, month: str):
        summary = self.tm.get_monthly_summary(month)
        expense = summary.get("total_expense", 0) or 0
        income  = summary.get("total_income", 0) or 0

        self._expense_card._val_lbl.setText(self._fmt(expense))
        self._income_card._val_lbl.setText(self._fmt(income))

        prev = self._prev_month_str(month)
        prev_s = self.tm.get_monthly_summary(prev)
        prev_exp = prev_s.get("total_expense", 0) or 0
        prev_inc = prev_s.get("total_income", 0) or 0

        if prev_exp > 0:
            delta_e = expense - prev_exp
            arrow_e = "↑" if delta_e > 0 else "↓"
            color_e = RED_SOFT if delta_e > 0 else MINT
            self._expense_card._arrow_lbl.setText(arrow_e)
            self._expense_card._arrow_lbl.setStyleSheet(
                f"color:{color_e}; border:none; background:transparent;")

        if prev_inc > 0:
            delta_i = income - prev_inc
            arrow_i = "↑" if delta_i > 0 else "↓"
            color_i = MINT if delta_i > 0 else ORANGE
            self._income_card._arrow_lbl.setText(arrow_i)
            self._income_card._arrow_lbl.setStyleSheet(
                f"color:{color_i}; border:none; background:transparent;")

    def _load_chart(self, month: str):
        """Load biểu đồ donut theo mode hiện tại (expense/income) + view_mode (sub/parent)."""
        if self._show_trend:
            self._load_trend_chart()
            return

        conn = get_connection()
        tx_type = "expense" if self._data_mode == "expense" else "income"

        if self._view_mode == "sub":
            # Danh mục con
            rows = conn.execute("""
                SELECT c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                GROUP BY c.id ORDER BY total DESC
            """, (tx_type, month)).fetchall()
        else:
            # Danh mục cha (gộp theo parent) — trả về cùng schema như view 'sub' (name, color, total)
            rows = conn.execute("""
                SELECT
                    COALESCE(cp.name, c.name) as name,
                    COALESCE(cp.color, c.color) as color,
                    SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                LEFT JOIN categories cp ON c.parent_id = cp.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                GROUP BY COALESCE(cp.id, c.id)
                ORDER BY total DESC
            """, (tx_type, month)).fetchall()
        conn.close()

        # Xóa legend cũ
        while self._legend_l.count():
            item = self._legend_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = []
        for i, r in enumerate(rows[:9]):
            color = r["color"] if r["color"] else CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
            name  = r[0]  # parent_name hoặc name
            data.append({"name": name, "value": float(r["total"]), "color": color})

        if self._data_mode == "expense":
            center_label = "Chi tiêu"
            center_color = RED_SOFT
        else:
            center_label = "Thu nhập"
            center_color = MINT

        self._donut.set_data(data, center_label, center_color)

        # Build legend
        total = sum(d["value"] for d in data) or 1
        for seg in data[:7]:
            pct = seg["value"] / total * 100
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(6)

            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                f"background:{seg['color']}; border-radius:5px; border:none;")
            rl.addWidget(dot)

            pct_lbl = QLabel(f"{pct:.0f}%")
            pct_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            pct_lbl.setStyleSheet(f"color:{seg['color']}; border:none;")
            pct_lbl.setFixedWidth(34)
            rl.addWidget(pct_lbl)

            name_lbl = QLabel(seg["name"][:12])
            name_lbl.setFont(QFont("Segoe UI", 9))
            name_lbl.setStyleSheet(f"color:{TEXT_MUTED}; border:none;")
            rl.addWidget(name_lbl)
            rl.addStretch()
            self._legend_l.addWidget(row_w)
        self._legend_l.addStretch()

    def _load_trend_chart(self):
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
            if self._data_mode == "expense":
                values.append(s.get("total_expense", 0) or 0)
            else:
                values.append(s.get("total_income", 0) or 0)

        color = RED_SOFT if self._data_mode == "expense" else MINT
        label = "Chi tiêu" if self._data_mode == "expense" else "Thu nhập"
        current_idx = months.index(self._current_month) if self._current_month in months else -1
        self._trend_canvas.plot(months, values, current_idx, color, label)

    def _load_categories(self, month: str):
        while self._cat_list_l.count():
            item = self._cat_list_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tx_type = "expense" if self._data_mode == "expense" else "income"
        conn = get_connection()

        if self._view_mode == "sub":
            rows = conn.execute("""
                SELECT c.id, c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                GROUP BY c.id ORDER BY total DESC
            """, (tx_type, month)).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    COALESCE(cp.id, c.id) as grp_id,
                    COALESCE(cp.name, c.name) as name,
                    COALESCE(cp.color, c.color) as color,
                    SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                LEFT JOIN categories cp ON c.parent_id = cp.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                GROUP BY grp_id ORDER BY total DESC
            """, (tx_type, month)).fetchall()

        unclassified_count = conn.execute("""
            SELECT COUNT(*) as n FROM transactions
            WHERE type=? AND category_id IS NULL
            AND strftime('%Y-%m', date)=?
        """, (tx_type, month)).fetchone()["n"]
        unclassified_amt = conn.execute("""
            SELECT COALESCE(SUM(amount),0) as s FROM transactions
            WHERE type=? AND category_id IS NULL
            AND strftime('%Y-%m', date)=?
        """, (tx_type, month)).fetchone()["s"]
        conn.close()

        all_cats = [dict(r) for r in rows]
        limit = len(all_cats) if self._cat_expanded else min(5, len(all_cats))

        for i, cat in enumerate(all_cats[:limit]):
            color = cat["color"] if cat.get("color") else CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
            row = CategoryRow({
                "name":  cat["name"],
                "color": color,
                "total": cat["total"] or 0,
            })
            self._cat_list_l.addWidget(row)

        if unclassified_count > 0:
            row = CategoryRow({
                "name":  "Chưa phân loại",
                "color": "#888780",
                "total": unclassified_amt or 0,
                "unclassified_count": unclassified_count,
            })
            self._cat_list_l.addWidget(row)

        has_more = len(all_cats) > 5
        self._btn_toggle_cat.setVisible(has_more)
        self._btn_toggle_cat.setText("Thu gọn ∧" if self._cat_expanded else "Xem thêm ∨")

    def _load_budgets(self, month: str):
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

        total_limit = sum(b["limit_amount"] for b in budgets)
        total_spent = sum(b["spent_amount"] or 0 for b in budgets)
        pct = (total_spent / total_limit * 100) if total_limit > 0 else 0

        if total_limit > 0:
            total_card = BudgetMiniCard({
                "name": "Ngân sách tổng",
                "limit_amount": total_limit,
                "suggest": 0,
                "pct": pct,
            })
            self._budget_scroll_l.addWidget(total_card)

        for b in budgets:
            limit = b["limit_amount"]
            spent = b["spent_amount"] or 0
            b_pct = (spent / limit * 100) if limit > 0 else 0
            card = BudgetMiniCard({
                "name": b["cat_name"],
                "limit_amount": limit,
                "suggest": spent * 1.1,
                "pct": b_pct,
            })
            self._budget_scroll_l.addWidget(card)

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
                card = BudgetMiniCard({
                    "name": cat["name"],
                    "limit_amount": 0,
                    "suggest": cat["total"] * 1.1,
                    "pct": 0,
                })
                self._budget_scroll_l.addWidget(card)

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

    def _switch_data_mode(self, mode: str):
        """Chuyển giữa Chi tiêu / Thu nhập → cập nhật card highlight + biểu đồ."""
        self._data_mode = mode

        # Highlight card được chọn
        for card, m in [(self._expense_card, "expense"), (self._income_card, "income")]:
            active = (m == mode)
            border = NAVY_MID if active else BORDER_BLUE
            bg     = ACCENT_BLUE if active else CARD_WHITE
            card.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 2px solid {border};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    border-color: {NAVY_MID};
                    background: {ACCENT_BLUE};
                }}
            """)

        # Reload chart và categories
        self._load_chart(self._current_month)
        self._load_categories(self._current_month)

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
        """Chuyển Danh mục con / Danh mục cha → cập nhật biểu đồ riêng."""
        self._view_mode = mode
        self._btn_sub.setChecked(mode == "sub")
        self._btn_parent.setChecked(mode == "parent")
        self._btn_sub.setStyleSheet(self._cat_tab_style(mode == "sub"))
        self._btn_parent.setStyleSheet(self._cat_tab_style(mode == "parent"))
        # Reload cả biểu đồ (vì donut thay đổi theo sub/parent) lẫn danh sách
        self._load_chart(self._current_month)
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
                border:1px solid {BORDER_BLUE};
                border-radius:10px;
                font-size:18px;
                font-weight:bold;
            }}
            QPushButton:hover {{ background:{ACCENT_BLUE}; border-color:{NAVY_MID}; }}
            QPushButton:disabled {{ color:#C0D4E8; border-color:{BORDER_BLUE}; }}
        """

    @staticmethod
    def _tab_style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background:{ACCENT_BLUE};
                    color:{NAVY_MID};
                    border:1px solid {BORDER_BLUE};
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
                border:1px solid {BORDER_BLUE};
                border-radius:8px;
                font-size:11px;
                padding:4px 12px;
            }}
            QPushButton:hover {{ background:{ACCENT_BLUE}; }}
        """

    @staticmethod
    def _cat_tab_style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background:transparent;
                    color:{NAVY_MID};
                    border:none;
                    border-bottom:3px solid {NAVY_MID};
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