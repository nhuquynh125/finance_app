# app/ui/spending_frame.py  (cập nhật: logic đúng danh mục cha/con chi tiêu, thu nhập flat)
"""
Trang Quản lý Chi tiêu — Finance AI
Thay đổi:
  - Chi tiêu: 2 tab "Danh mục con" và "Danh mục cha"
      + Danh mục cha: có thể expand/collapse ra các danh mục con (như ảnh tham chiếu)
      + Danh mục con: list phẳng từng danh mục leaf
  - Thu nhập: KHÔNG có tab cha/con, chỉ list phẳng (vì thu nhập không có phân cấp)
  - Mỗi chế độ (expense/income) tạo biểu đồ donut riêng
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy, QStackedWidget,
    QDialog, QLineEdit, QComboBox, QCheckBox, QTabWidget,
    QMessageBox, QColorDialog, QDialogButtonBox,
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
TEXT_MUTED  = "#4A6785"  # Đậm hơn để dễ đọc trên nền trắng
TEXT_DARK   = "#0B2A4A"
ACCENT_BLUE = "#E6F1FB"

CATEGORY_PALETTE = [
    "#378ADD", "#1D9E75", "#E8921A", "#7F77DD",
    "#E85020", "#D4537E", "#1A6BAF", "#888780", "#639922",
]


# ══════════════════════════════════════════════════════════════════════════════
# ── Donut Chart Widget ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class DonutChartWidget(QWidget):
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
        w, h = self.width(), self.height()
        size = min(w, h) - 16
        cx, cy = w / 2, h / 2
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
            pen = QPen(QColor(BG_PAGE), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            start_angle += span
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(CARD_WHITE)))
        painter.drawEllipse(rect_inner)
        painter.setPen(QColor(TEXT_MUTED))
        painter.setFont(QFont("Segoe UI", 14))
        painter.drawText(QRectF(cx - inner_r, cy - 22, inner_r * 2, 18),
                         Qt.AlignmentFlag.AlignCenter, self._center_label)
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.setPen(QColor(self._center_color))
        painter.drawText(QRectF(cx - inner_r, cy - 4, inner_r * 2, 22),
                         Qt.AlignmentFlag.AlignCenter, self._fmt(self._total))
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
        ax.set_xticklabels(labels, fontsize=15, color=TEXT_DARK)
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
                    ha="center", va="bottom", fontsize=13, color=TEXT_MUTED)
        self.draw()


# ══════════════════════════════════════════════════════════════════════════════
# ── Category Row (leaf / sub category) ───────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class CategoryRow(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, cat_data: dict, indent: bool = False, parent=None):
        super().__init__(parent)
        self._data = cat_data
        self._indent = indent
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48 if not indent else 42)
        bg = CARD_WHITE
        self.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border-bottom: 1px solid {BORDER_BLUE};
            }}
            QWidget:hover {{
                background: {ACCENT_BLUE};
            }}
        """)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        left_margin = 36 if self._indent else 16
        layout.setContentsMargins(left_margin, 6, 12, 6)
        layout.setSpacing(10)

        color = self._data.get("color", NAVY_LIGHT)
        dot = QFrame()
        dot.setFixedSize(28 if not self._indent else 22, 28 if not self._indent else 22)
        dot.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border-radius: {14 if not self._indent else 11}px;
                border: none;
            }}
        """)
        layout.addWidget(dot)

        name_lbl = QLabel(self._data.get("name", ""))
        font_size = 12 if not self._indent else 11
        name_lbl.setFont(QFont("Segoe UI", font_size))
        name_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        layout.addWidget(name_lbl, stretch=1)

        if self._data.get("unclassified_count", 0):
            tag = QLabel(f"  {self._data['unclassified_count']}  ")
            tag.setStyleSheet(f"""
                QLabel {{
                    background: {ORANGE};
                    color: white;
                    border-radius: 10px;
                    font-size:15px;
                    font-weight: bold;
                    border: none;
                    padding: 2px 6px;
                }}
            """)
            layout.addWidget(tag)

        amt_lbl = QLabel(self._fmt(self._data.get("total", 0)))
        font_size_amt = 12 if not self._indent else 11
        amt_lbl.setFont(QFont("Segoe UI", font_size_amt, QFont.Weight.Medium))
        amt_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        layout.addWidget(amt_lbl)

        if not self._indent:
            arrow = QLabel("›")
            arrow.setFont(QFont("Segoe UI", 21))
            arrow.setStyleSheet(f"color:{BORDER_BLUE}; border:none; background:transparent;")
            layout.addWidget(arrow)

    def mousePressEvent(self, event):
        self.clicked.emit(self._data)

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f}đ".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
# ── Parent Category Row (expandable) ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class ParentCategoryRow(QWidget):
    """Hàng danh mục cha với nút expand/collapse hiển thị danh mục con."""

    def __init__(self, parent_data: dict, children: list[dict], parent=None):
        super().__init__(parent)
        self._parent_data = parent_data
        self._children    = children
        self._expanded    = False
        self._child_widgets: list[QWidget] = []
        self._build()

    def _build(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Header row (danh mục cha)
        self._header = QWidget()
        self._header.setFixedHeight(52)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(f"""
            QWidget {{
                background: {CARD_WHITE};
                border-bottom: 1px solid {BORDER_BLUE};
            }}
            QWidget:hover {{
                background: {ACCENT_BLUE};
            }}
        """)
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(16, 8, 12, 8)
        hl.setSpacing(10)

        color = self._parent_data.get("color", NAVY_LIGHT)
        dot = QFrame()
        dot.setFixedSize(32, 32)
        dot.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border-radius: 10px;
                border: none;
            }}
        """)
        hl.addWidget(dot)

        name_lbl = QLabel(self._parent_data.get("name", ""))
        name_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        hl.addWidget(name_lbl, stretch=1)

        amt_lbl = QLabel(self._fmt(self._parent_data.get("total", 0)))
        amt_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Medium))
        amt_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        hl.addWidget(amt_lbl)

        self._arrow_lbl = QLabel("∨" if self._expanded else "∨")
        self._arrow_lbl.setFont(QFont("Segoe UI", 18))
        self._arrow_lbl.setStyleSheet(
            f"color:{NAVY_MID}; border:none; background:transparent; min-width:18px;")
        hl.addWidget(self._arrow_lbl)

        self._layout.addWidget(self._header)

        # Container danh mục con (ẩn mặc định)
        self._children_container = QWidget()
        self._children_container.setStyleSheet(
            f"background: #F8FBFF; border-bottom: 1px solid {BORDER_BLUE};")
        self._children_layout = QVBoxLayout(self._children_container)
        self._children_layout.setContentsMargins(0, 0, 0, 0)
        self._children_layout.setSpacing(0)

        for child in self._children:
            child_row = CategoryRow(child, indent=True)
            self._children_layout.addWidget(child_row)
            self._child_widgets.append(child_row)

        self._children_container.hide()
        self._layout.addWidget(self._children_container)

        # Connect click
        self._header.mousePressEvent = self._on_header_click

    def _on_header_click(self, event):
        self._expanded = not self._expanded
        if self._expanded:
            self._children_container.show()
            self._arrow_lbl.setText("∧")
        else:
            self._children_container.hide()
            self._arrow_lbl.setText("∨")

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:,.0f}đ".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════════
# ── Budget Mini Card ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class BudgetMiniCard(QWidget):
    def __init__(self, budget_data: dict, parent=None):
        super().__init__(parent)
        self.setFixedSize(210, 170)
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
        name_lbl.setFont(QFont("Segoe UI", 29, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"border:none; color:{TEXT_DARK};")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_lbl)

        pct = self._data.get("pct", 0)
        over = pct >= 100

        if over:
            bar_color   = RED_SOFT
            status_text = "Đã vượt"
            status_sty  = f"color:{RED_SOFT}; font-weight:bold;"
        elif pct >= 80:
            bar_color   = ORANGE
            status_text = "Sắp hết"
            status_sty  = f"color:{ORANGE}; font-weight:bold;"
        else:
            bar_color   = MINT
            status_text = "Bình thường"
            status_sty  = f"color:{MINT};"

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
        status_lbl.setFont(QFont("Segoe UI", 27))
        status_lbl.setStyleSheet(f"border:none; {status_sty}")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_lbl)

        limit   = self._data.get("limit_amount", 0)
        suggest = self._data.get("suggest", 0)
        show_amount = limit if limit > 0 else suggest

        amount_lbl = QLabel(self._fmt(show_amount))
        amount_lbl.setFont(QFont("Segoe UI", 31, QFont.Weight.Bold))
        amount_lbl.setStyleSheet(f"color:{bar_color}; border:none;")
        amount_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(amount_lbl)

        if not limit:
            btn = QPushButton("Đặt ngân sách →")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {NAVY_MID};
                    border: none;
                    font-size:24px;
                    text-align: center;
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
# ── Category Manager Dialog ───────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class CategoryManagerDialog(QDialog):
    """Dialog quản lý danh mục: thêm mới, nhóm, xóa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quản lý danh mục")
        self.setMinimumSize(500, 580)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_PAGE}; }}
            QLabel {{ color: {TEXT_DARK}; border: none; background: transparent; }}
            QLineEdit, QComboBox {{
                background: {CARD_WHITE};
                border: 1.5px solid {BORDER_BLUE};
                border-radius: 8px;
                padding: 8px 12px;
                font-size:18px;
                color: {TEXT_DARK};
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {NAVY_MID}; }}
            QComboBox::drop-down {{ border: none; padding-right: 8px; }}
            QComboBox QAbstractItemView {{
                background: {CARD_WHITE};
                border: 1px solid {BORDER_BLUE};
                selection-background-color: {ACCENT_BLUE};
                color: {TEXT_DARK};
            }}
        """)
        self._selected_color = CATEGORY_PALETTE[0]
        self._checkboxes: list = []
        self._build()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header banner
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{NAVY}; border:none;")
        hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("⚙  Quản lý danh mục")
        title.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        title.setStyleSheet("color:white; border:none; background:transparent;")
        hl.addWidget(title)
        root.addWidget(hdr)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background: {BG_PAGE}; border: none; }}
            QTabBar::tab {{
                background: {CARD_WHITE};
                color: {TEXT_MUTED};
                border: none;
                border-bottom: 3px solid transparent;
                padding: 10px 18px;
                font-size:17px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                color: {NAVY_MID};
                border-bottom: 3px solid {NAVY_MID};
                font-weight: 700;
            }}
            QTabBar::tab:hover {{ color: {TEXT_DARK}; }}
        """)
        self._tabs.addTab(self._build_add_tab(),   "➕  Thêm mới")
        self._tabs.addTab(self._build_group_tab(), "🔗  Nhóm danh mục")
        self._tabs.addTab(self._build_list_tab(),  "📋  Tất cả")
        root.addWidget(self._tabs)

    # ── Tab 1: Thêm danh mục ─────────────────────────────────────────────────

    def _build_add_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_PAGE};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(12)

        ly.addWidget(self._lbl("Tên danh mục *"))
        self._inp_name = QLineEdit()
        self._inp_name.setPlaceholderText("Ví dụ: Ăn uống, Chợ, Xăng xe...")
        self._inp_name.setFixedHeight(40)
        ly.addWidget(self._inp_name)

        ly.addWidget(self._lbl("Loại giao dịch"))
        self._cb_type = QComboBox()
        self._cb_type.addItems(["💸 Chi tiêu (expense)", "💰 Thu nhập (income)"])
        self._cb_type.setFixedHeight(40)
        self._cb_type.currentIndexChanged.connect(self._on_type_changed)
        ly.addWidget(self._cb_type)

        ly.addWidget(self._lbl("Thuộc danh mục cha  (bỏ trống = danh mục gốc)"))
        self._cb_parent = QComboBox()
        self._cb_parent.setFixedHeight(40)
        self._load_parent_options("expense")
        ly.addWidget(self._cb_parent)

        ly.addWidget(self._lbl("Màu sắc"))
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._btn_color = QPushButton("  Chọn màu")
        self._btn_color.setFixedHeight(38)
        self._update_color_btn()
        self._btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self._btn_color)
        for c in CATEGORY_PALETTE[:6]:
            pb = QPushButton()
            pb.setFixedSize(32, 32)
            pb.setStyleSheet(f"""
                QPushButton {{ background:{c}; border-radius:16px; border:2px solid transparent; }}
                QPushButton:hover {{ border:2px solid {NAVY}; }}
            """)
            pb.clicked.connect(lambda _=False, col=c: self._set_color(col))
            color_row.addWidget(pb)
        color_row.addStretch()
        ly.addLayout(color_row)

        ly.addStretch()

        btn_save = QPushButton("✓  Lưu danh mục")
        btn_save.setFixedHeight(44)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_MID}; color:white;
                border-radius:10px; border:none;
                font-size:19px; font-weight:700;
            }}
            QPushButton:hover {{ background:{NAVY}; }}
        """)
        btn_save.clicked.connect(self._save_new_category)
        ly.addWidget(btn_save)
        return w

    # ── Tab 2: Nhóm danh mục ─────────────────────────────────────────────────

    def _build_group_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_PAGE};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(12)

        ly.addWidget(self._lbl("Chọn danh mục muốn nhóm:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(200)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:1.5px solid {BORDER_BLUE}; border-radius:10px;
                           background:{CARD_WHITE}; }}
        """)
        self._check_container = QWidget()
        self._check_container.setStyleSheet(f"background:{CARD_WHITE};")
        self._check_layout = QVBoxLayout(self._check_container)
        self._check_layout.setContentsMargins(12, 8, 12, 8)
        self._check_layout.setSpacing(2)
        self._load_checkboxes()
        scroll.setWidget(self._check_container)
        ly.addWidget(scroll)

        ly.addWidget(self._lbl("Nhóm vào danh mục cha đã có:"))
        self._cb_target = QComboBox()
        self._cb_target.setFixedHeight(40)
        self._load_target_options()
        ly.addWidget(self._cb_target)

        or_row = QHBoxLayout()
        or_row.setSpacing(8)
        or_lbl = QLabel("— hoặc tạo cha mới:")
        or_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:17px; border:none;")
        or_row.addWidget(or_lbl)
        self._inp_new_parent = QLineEdit()
        self._inp_new_parent.setPlaceholderText("Tên danh mục cha mới...")
        self._inp_new_parent.setFixedHeight(36)
        or_row.addWidget(self._inp_new_parent, stretch=1)
        ly.addLayout(or_row)

        ly.addStretch()

        btn_group = QPushButton("🔗  Nhóm danh mục")
        btn_group.setFixedHeight(44)
        btn_group.setStyleSheet(f"""
            QPushButton {{
                background:{MINT}; color:white;
                border-radius:10px; border:none;
                font-size:19px; font-weight:700;
            }}
            QPushButton:hover {{ background:#18876A; }}
        """)
        btn_group.clicked.connect(self._do_group)
        ly.addWidget(btn_group)
        return w

    # ── Tab 3: Tất cả danh mục ───────────────────────────────────────────────

    def _build_list_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_PAGE};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        self._list_container = QWidget()
        self._list_container.setStyleSheet(f"background:{BG_PAGE};")
        self._list_l = QVBoxLayout(self._list_container)
        self._list_l.setContentsMargins(0, 8, 0, 8)
        self._list_l.setSpacing(0)
        self._refresh_list_tab()

        scroll.setWidget(self._list_container)
        ly.addWidget(scroll)
        return w

    def _refresh_list_tab(self):
        while self._list_l.count():
            item = self._list_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        conn = get_connection()
        parents = conn.execute("""
            SELECT id, name, color, type FROM categories
            WHERE parent_id IS NULL ORDER BY type, name
        """).fetchall()

        for i, p in enumerate(parents):
            children = conn.execute("""
                SELECT id, name, color FROM categories
                WHERE parent_id=? ORDER BY name
            """, (p["id"],)).fetchall()

            p_color = p["color"] or CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]

            # Hàng cha
            pr = QWidget()
            pr.setStyleSheet(
                f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
            pr.setFixedHeight(50)
            prl = QHBoxLayout(pr)
            prl.setContentsMargins(16, 6, 12, 6)
            prl.setSpacing(10)
            dot = QFrame()
            dot.setFixedSize(28, 28)
            dot.setStyleSheet(
                f"background:{p_color}; border-radius:14px; border:none;")
            prl.addWidget(dot)
            suffix = "  📁" if children else ""
            name_lbl = QLabel(f"{p['name']}{suffix}")
            name_lbl.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
            name_lbl.setStyleSheet(
                f"color:{TEXT_DARK}; border:none; background:transparent;")
            prl.addWidget(name_lbl, stretch=1)
            type_color = RED_SOFT if p["type"] == "expense" else MINT
            type_lbl = QLabel("Chi tiêu" if p["type"] == "expense" else "Thu nhập")
            type_lbl.setStyleSheet(
                f"color:{type_color}; font-size:15px; border:none; background:transparent;")
            prl.addWidget(type_lbl)
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; border:none; font-size:19px;
                               color:{TEXT_MUTED}; border-radius:14px; }}
                QPushButton:hover {{ background:#FFE5E5; color:{RED_SOFT}; }}
            """)
            del_btn.clicked.connect(
                lambda _=False, pid=p["id"], pn=p["name"]: self._delete_cat(pid, pn))
            prl.addWidget(del_btn)
            self._list_l.addWidget(pr)

            # Hàng con
            for ch in children:
                ch_color = ch["color"] or CATEGORY_PALETTE[1]
                cr = QWidget()
                cr.setStyleSheet(
                    f"background:#F8FBFF; border-bottom:1px solid {BORDER_BLUE};")
                cr.setFixedHeight(40)
                crl = QHBoxLayout(cr)
                crl.setContentsMargins(52, 4, 12, 4)
                crl.setSpacing(8)
                cdot = QFrame()
                cdot.setFixedSize(20, 20)
                cdot.setStyleSheet(
                    f"background:{ch_color}; border-radius:10px; border:none;")
                crl.addWidget(cdot)
                c_name = QLabel(ch["name"])
                c_name.setFont(QFont("Segoe UI", 16))
                c_name.setStyleSheet(
                    f"color:{TEXT_DARK}; border:none; background:transparent;")
                crl.addWidget(c_name, stretch=1)
                c_del = QPushButton("🗑")
                c_del.setFixedSize(26, 26)
                c_del.setStyleSheet(f"""
                    QPushButton {{ background:transparent; border:none; font-size:17px;
                                   color:{TEXT_MUTED}; border-radius:13px; }}
                    QPushButton:hover {{ background:#FFE5E5; color:{RED_SOFT}; }}
                """)
                c_del.clicked.connect(
                    lambda _=False, cid=ch["id"], cn=ch["name"]: self._delete_cat(cid, cn))
                crl.addWidget(c_del)
                self._list_l.addWidget(cr)

        conn.close()
        self._list_l.addStretch()

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _load_parent_options(self, tx_type: str):
        self._cb_parent.clear()
        self._cb_parent.addItem("— Không có (danh mục gốc) —", userData=None)
        conn = get_connection()
        parents = conn.execute("""
            SELECT id, name FROM categories
            WHERE type=? AND parent_id IS NULL ORDER BY name
        """, (tx_type,)).fetchall()
        conn.close()
        for p in parents:
            self._cb_parent.addItem(p["name"], userData=p["id"])

    def _load_checkboxes(self):
        while self._check_layout.count():
            item = self._check_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes = []
        conn = get_connection()
        cats = conn.execute("""
            SELECT c.id, c.name, c.type, p.name as parent_name
            FROM categories c
            LEFT JOIN categories p ON c.parent_id = p.id
            ORDER BY c.type, p.name, c.name
        """).fetchall()
        conn.close()
        for cat in cats:
            cb = QCheckBox()
            display = cat["name"]
            if cat["parent_name"]:
                display = f"  └ {cat['name']}  (thuộc: {cat['parent_name']})"
            cb.setText(display)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color:{TEXT_DARK}; font-size:17px;
                    spacing:8px; border:none; background:transparent; padding:3px 0;
                }}
                QCheckBox::indicator {{
                    width:18px; height:18px;
                    border:2px solid {BORDER_BLUE}; border-radius:4px; background:white;
                }}
                QCheckBox::indicator:checked {{
                    background:{NAVY_MID}; border-color:{NAVY_MID};
                }}
            """)
            self._check_layout.addWidget(cb)
            self._checkboxes.append((cb, cat["id"], cat["type"]))
        self._check_layout.addStretch()

    def _load_target_options(self):
        self._cb_target.clear()
        self._cb_target.addItem("— Chọn cha đã có —", userData=None)
        conn = get_connection()
        parents = conn.execute("""
            SELECT id, name, type FROM categories
            WHERE parent_id IS NULL ORDER BY type, name
        """).fetchall()
        conn.close()
        for p in parents:
            t = "Chi tiêu" if p["type"] == "expense" else "Thu nhập"
            self._cb_target.addItem(f"{p['name']} ({t})", userData=p["id"])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_type_changed(self, idx: int):
        self._load_parent_options("expense" if idx == 0 else "income")

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._selected_color), self, "Chọn màu")
        if color.isValid():
            self._set_color(color.name())

    def _set_color(self, color: str):
        self._selected_color = color
        self._update_color_btn()

    def _update_color_btn(self):
        self._btn_color.setStyleSheet(f"""
            QPushButton {{
                background:{self._selected_color}; color:white;
                border-radius:8px; border:none;
                font-size:18px; font-weight:600; padding:0 16px;
            }}
            QPushButton:hover {{ background:{self._selected_color}; opacity:0.85; }}
        """)

    def _save_new_category(self):
        name = self._inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên danh mục.")
            return
        tx_type = "expense" if self._cb_type.currentIndex() == 0 else "income"
        parent_id = self._cb_parent.currentData()
        color = self._selected_color

        conn = get_connection()

        # ── Validation: tên không được trùng với danh mục cha/con ────────────
        name_lower = name.strip().lower()

        if parent_id:
            # Đang tạo danh mục con → tên không được trùng tên cha
            parent_row = conn.execute(
                "SELECT name FROM categories WHERE id=?", (parent_id,)
            ).fetchone()
            if parent_row and parent_row["name"].strip().lower() == name_lower:
                QMessageBox.warning(
                    self, "Tên trùng lặp",
                    f'Tên danh mục con không được trùng với danh mục cha "{parent_row["name"]}".'
                )
                return
        else:
            # Đang tạo danh mục cha → tên không được trùng tên bất kỳ danh mục con nào
            conflict = conn.execute("""
                SELECT name FROM categories
                WHERE parent_id IS NOT NULL
                  AND LOWER(TRIM(name)) = LOWER(TRIM(?))
                  AND type = ?
                LIMIT 1
            """, (name, tx_type)).fetchone()
            if conflict:
                QMessageBox.warning(
                    self, "Tên trùng lặp",
                    f'Tên danh mục cha "{name}" đã tồn tại ở danh mục con. '
                    "Vui lòng chọn tên khác."
                )
                return
        # ─────────────────────────────────────────────────────────────────────

        try:
            conn.execute_write(
                "INSERT INTO categories (name, type, color, parent_id) VALUES (?,?,?,?)",
                (name, tx_type, color, parent_id)
            )
            QMessageBox.information(self, "Thành công",
                                    f'Đã thêm danh mục "{name}".')
            self._inp_name.clear()
            self._refresh_all_data()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu: {e}")

    def _do_group(self):
        selected_ids = [(cat_id, cat_type)
                        for cb, cat_id, cat_type in self._checkboxes
                        if cb.isChecked()]
        if not selected_ids:
            QMessageBox.warning(self, "Chưa chọn",
                                "Vui lòng chọn ít nhất một danh mục.")
            return

        new_parent_name = self._inp_new_parent.text().strip()
        target_id = self._cb_target.currentData()

        conn = get_connection()
        try:
            if new_parent_name:
                tx_type = selected_ids[0][1]  # type của danh mục đầu tiên

                # ── Validation: tên cha mới không được trùng tên các danh mục con đã chọn ──
                selected_cat_ids = [cid for cid, _ in selected_ids]
                placeholders = ",".join("?" * len(selected_cat_ids))
                child_rows = conn.execute(
                    f"SELECT name FROM categories WHERE id IN ({placeholders})",
                    selected_cat_ids
                ).fetchall()
                child_names_lower = [r["name"].strip().lower() for r in child_rows]
                if new_parent_name.strip().lower() in child_names_lower:
                    QMessageBox.warning(
                        self, "Tên trùng lặp",
                        f'Tên danh mục cha "{new_parent_name}" trùng với một danh mục con '
                        "đã chọn. Vui lòng đặt tên khác."
                    )
                    return

                # Kiểm tra tên cha mới có trùng với bất kỳ danh mục con nào không
                conflict = conn.execute("""
                    SELECT name FROM categories
                    WHERE parent_id IS NOT NULL
                      AND LOWER(TRIM(name)) = LOWER(TRIM(?))
                    LIMIT 1
                """, (new_parent_name,)).fetchone()
                if conflict:
                    QMessageBox.warning(
                        self, "Tên trùng lặp",
                        f'Tên "{new_parent_name}" đã tồn tại ở danh mục con. '
                        "Vui lòng chọn tên khác."
                    )
                    return
                # ────────────────────────────────────────────────────────────────

                conn.execute_write(
                    "INSERT INTO categories (name, type, color) VALUES (?,?,?)",
                    (new_parent_name, tx_type, self._selected_color)
                )
                target_id = conn.execute(
                    "SELECT last_insert_rowid() as lid").fetchone()["lid"]

            if not target_id:
                QMessageBox.warning(self, "Thiếu thông tin",
                                    "Vui lòng chọn cha đã có hoặc nhập tên cha mới.")
                return

            # ── Validation: tên cha đã chọn không được trùng tên danh mục con đã chọn ──
            if target_id:
                parent_row = conn.execute(
                    "SELECT name FROM categories WHERE id=?", (target_id,)
                ).fetchone()
                if parent_row:
                    selected_cat_ids = [cid for cid, _ in selected_ids]
                    placeholders = ",".join("?" * len(selected_cat_ids))
                    child_rows = conn.execute(
                        f"SELECT name FROM categories WHERE id IN ({placeholders})",
                        selected_cat_ids
                    ).fetchall()
                    child_names_lower = [r["name"].strip().lower() for r in child_rows]
                    if parent_row["name"].strip().lower() in child_names_lower:
                        QMessageBox.warning(
                            self, "Tên trùng lặp",
                            f'Tên danh mục cha "{parent_row["name"]}" trùng với một '
                            "danh mục con đã chọn. Vui lòng đổi tên."
                        )
                        return
            # ────────────────────────────────────────────────────────────────────

            for cat_id, _ in selected_ids:
                conn.execute_write(
                    "UPDATE categories SET parent_id=? WHERE id=?",
                    (target_id, cat_id)
                )
            QMessageBox.information(
                self, "Thành công",
                f"Đã nhóm {len(selected_ids)} danh mục vào cha.")
            self._inp_new_parent.clear()
            self._refresh_all_data()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể nhóm: {e}")

    def _delete_cat(self, cat_id: int, cat_name: str):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f'Bạn có chắc muốn xóa danh mục "{cat_name}"?\n'
            "Danh mục con sẽ trở thành danh mục gốc. Giao dịch liên quan không bị xóa.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            try:
                conn.execute_write(
                    "UPDATE categories SET parent_id=NULL WHERE parent_id=?",
                    (cat_id,))
                conn.execute_write(
                    "DELETE FROM categories WHERE id=?", (cat_id,))
                self._refresh_all_data()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa: {e}")

    def _refresh_all_data(self):
        tx_type = "expense" if self._cb_type.currentIndex() == 0 else "income"
        self._load_parent_options(tx_type)
        self._load_checkboxes()
        self._load_target_options()
        self._refresh_list_tab()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))
        lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none; background:transparent;")
        return lbl


# ══════════════════════════════════════════════════════════════════════════════
# ── SpendingFrame (Main) ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class SpendingFrame(QWidget):
    """
    Trang Quản lý Chi tiêu — Finance AI.

    Logic danh mục:
    - CHI TIÊU: có 2 tab "Danh mục con" (list phẳng) và "Danh mục cha" (expandable)
    - THU NHẬP: KHÔNG có tab, chỉ list phẳng (thu nhập không phân cấp cha/con)
    """

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.tm = TransactionManager()
        self._current_month = datetime.now().strftime("%Y-%m")
        self._view_mode   = "sub"       # "sub" | "parent" — chỉ dùng khi expense
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
        bar.setFixedHeight(65)
        bar.setStyleSheet(
            f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        title = QLabel("Quản lý chi tiêu")
        title.setFont(QFont("Segoe UI", 33, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter)
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
        nav.addStretch()
        self._btn_prev_m = QPushButton("‹")
        self._btn_prev_m.setFixedSize(40, 40)
        self._btn_prev_m.setStyleSheet(self._nav_btn_style())
        self._btn_prev_m.clicked.connect(self._prev_month)
        nav.addWidget(self._btn_prev_m)

        self._month_lbl = QLabel("Tháng này")
        self._month_lbl.setFont(QFont("Segoe UI", 31, QFont.Weight.Bold))
        self._month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        nav.addWidget(self._month_lbl)

        self._btn_next_m = QPushButton("›")
        self._btn_next_m.setFixedSize(40, 40)
        self._btn_next_m.setStyleSheet(self._nav_btn_style())
        self._btn_next_m.clicked.connect(self._next_month)
        nav.addWidget(self._btn_next_m)
        nav.addStretch()
        layout.addLayout(nav)

        # Cards Chi tiêu / Thu nhập — click để switch
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        self._expense_card = self._summary_card(
            "💸 Chi tiêu", "0đ", selected=True, click_mode="expense")
        self._income_card  = self._summary_card(
            "💰 Thu nhập", "0đ", selected=False, click_mode="income")
        cards_row.addWidget(self._expense_card)
        cards_row.addWidget(self._income_card)
        layout.addLayout(cards_row)

        # Warning banner
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
        fire.setFont(QFont("Segoe UI", 19))
        fire.setStyleSheet("border:none;")
        wb_l.addWidget(fire)
        self._warning_lbl = QLabel("")
        self._warning_lbl.setFont(QFont("Segoe UI", 16))
        self._warning_lbl.setStyleSheet(f"color:{ORANGE}; border:none;")
        self._warning_lbl.setWordWrap(True)
        wb_l.addWidget(self._warning_lbl, stretch=1)
        arrow2 = QLabel("›")
        arrow2.setFont(QFont("Segoe UI", 23))
        arrow2.setStyleSheet(f"color:{NAVY_MID}; border:none;")
        wb_l.addWidget(arrow2)
        self._warning_banner.hide()
        layout.addWidget(self._warning_banner)

        self._body.addWidget(w)

    def _summary_card(self, label: str, value: str,
                      selected: bool = False, click_mode: str = "expense") -> QFrame:
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
        lbl.setFont(QFont("Segoe UI", 28))
        lbl.setStyleSheet(f"color:{TEXT_MUTED}; border:none; background:transparent;")
        cl.addWidget(lbl)

        row = QHBoxLayout()
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 29, QFont.Weight.Bold))
        val.setStyleSheet(
            f"color:{RED_SOFT if click_mode == 'expense' else MINT}; "
            f"border:none; background:transparent;")
        
        arrow = QLabel("↑")
        arrow.setFont(QFont("Segoe UI", 20))
        arrow.setStyleSheet(f"color:{NAVY_MID}; border:none; background:transparent;")
        
        row.addWidget(val)
        row.addStretch()
        row.addWidget(arrow)
        cl.addLayout(row)

        card._val_lbl   = val
        card._arrow_lbl = arrow

        def on_click(event, mode=click_mode):
            self._switch_data_mode(mode)
        card.mousePressEvent = on_click

        return card

    # ── Chart section ─────────────────────────────────────────────────────────

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

        # ── Section header: tiêu đề + nút Quản lý ──
        sec_hdr = QWidget()
        sec_hdr.setFixedHeight(60)
        sec_hdr.setStyleSheet(
            f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
        sec_hl = QHBoxLayout(sec_hdr)
        sec_hl.setContentsMargins(16, 0, 8, 0)
        sec_hl.setSpacing(8)
        sec_title = QLabel("Danh mục")
        sec_title.setFont(QFont("Segoe UI", 35, QFont.Weight.Bold))
        sec_title.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        sec_hl.addWidget(sec_title)
        sec_hl.addStretch()
        btn_manage = QPushButton("⚙  Quản lý")
        btn_manage.setFixedHeight(28)
        btn_manage.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT_BLUE};
                color:{NAVY_MID};
                border:1px solid {BORDER_BLUE};
                border-radius:8px;
                font-size:26px;
                font-weight:600;
                padding:0 12px;
            }}
            QPushButton:hover {{ background:{BORDER_BLUE}; color:{NAVY}; }}
        """)
        btn_manage.clicked.connect(self._open_category_manager)
        sec_hl.addWidget(btn_manage)
        cat_l.addWidget(sec_hdr)

        # ── Tab bar — chỉ hiện khi expense ──
        self._tab_bar = QWidget()
        self._tab_bar.setFixedHeight(50)
        self._tab_bar.setStyleSheet(
            f"background:{CARD_WHITE}; border-bottom:1px solid {BORDER_BLUE};")
        tb_l = QHBoxLayout(self._tab_bar)
        tb_l.setContentsMargins(0, 0, 0, 0)
        tb_l.setSpacing(0)

        self._btn_sub = QPushButton("Danh mục con")
        self._btn_sub.setCheckable(True)
        self._btn_sub.setChecked(True)
        self._btn_sub.clicked.connect(lambda: self._switch_cat_view("sub"))
        self._btn_sub.setStyleSheet(self._cat_tab_style(True))
        self._btn_sub.setFixedHeight(40)

        self._btn_parent = QPushButton("Danh mục cha")
        self._btn_parent.setCheckable(True)
        self._btn_parent.clicked.connect(lambda: self._switch_cat_view("parent"))
        self._btn_parent.setStyleSheet(self._cat_tab_style(False))
        self._btn_parent.setFixedHeight(40)

        tb_l.addWidget(self._btn_sub)
        tb_l.addWidget(self._btn_parent)
        cat_l.addWidget(self._tab_bar)

        # ── Category list ──
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
                font-size:21px;
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
        hdr.setFont(QFont("Segoe UI", 31, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
        header_row.addWidget(hdr)
        header_row.addStretch()
        see_all = QPushButton("Xem tất cả  ›")
        see_all.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{NAVY_MID};
                border:none; font-size:25px; font-weight:500; }}
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
        """Load biểu đồ donut theo data_mode hiện tại."""
        if self._show_trend:
            self._load_trend_chart()
            return

        conn = get_connection()
        tx_type = "expense" if self._data_mode == "expense" else "income"

        if self._data_mode == "expense" and self._view_mode == "parent":
            # Biểu đồ theo danh mục cha:
            # Tổng tiền cha = tổng tất cả con (c.parent_id = cp.id)
            # Danh mục standalone (không có cha, không có con) → tính riêng
            rows = conn.execute("""
                SELECT
                    COALESCE(cp.id, c.id)      as grp_id,
                    COALESCE(cp.name, c.name)   as name,
                    COALESCE(cp.color, c.color)  as color,
                    SUM(t.amount)               as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                LEFT JOIN categories cp ON c.parent_id = cp.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                GROUP BY COALESCE(cp.id, c.id)
                ORDER BY total DESC
            """, (tx_type, month)).fetchall()
        else:
            # Biểu đồ theo danh mục LEAF:
            # Chỉ lấy danh mục con thực (có parent_id) hoặc standalone (không có cha, không có con)
            rows = conn.execute("""
                SELECT c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                  AND (
                    c.parent_id IS NOT NULL
                    OR NOT EXISTS (SELECT 1 FROM categories cc WHERE cc.parent_id = c.id)
                  )
                GROUP BY c.id ORDER BY total DESC
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
            data.append({"name": r["name"] or "", "value": float(r["total"]), "color": color})

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
            pct_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
            pct_lbl.setStyleSheet(f"color:{seg['color']}; border:none;")
            pct_lbl.setFixedWidth(65)
            rl.addWidget(pct_lbl)
            name_lbl = QLabel(seg["name"][:12])
            name_lbl.setFont(QFont("Segoe UI", 27))
            name_lbl.setStyleSheet(f"color:{TEXT_DARK}; border:none;")
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
        """
        Load danh sách danh mục:
        - expense + sub:    list phẳng CHỈ danh mục leaf (có parent_id, hoặc không có con)
        - expense + parent: danh mục cha với expand/collapse ra con
                            Tổng tiền cha = tổng tất cả con thuộc cha đó
        - income:           list phẳng (KHÔNG có tab cha/con)
        """
        # Xóa widgets cũ
        while self._cat_list_l.count():
            item = self._cat_list_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tx_type = "expense" if self._data_mode == "expense" else "income"
        conn = get_connection()

        if self._data_mode == "expense" and self._view_mode == "parent":
            # ----- CHẾ ĐỘ DANH MỤC CHA (expense) -----
            # Lấy tất cả danh mục cha thực (có ít nhất 1 con) trong DB, không phụ thuộc giao dịch
            all_parents = conn.execute("""
                SELECT DISTINCT cp.id, cp.name, cp.color
                FROM categories cp
                WHERE EXISTS (SELECT 1 FROM categories cc WHERE cc.parent_id = cp.id)
            """).fetchall()

            # Tính tổng tiền cho từng cha (= tổng tiền tất cả con)
            parent_totals = {}
            for p in all_parents:
                row = conn.execute("""
                    SELECT COALESCE(SUM(t.amount), 0) as total
                    FROM transactions t
                    JOIN categories c ON t.category_id = c.id
                    WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                      AND c.parent_id = ?
                """, (tx_type, month, p["id"])).fetchone()
                parent_totals[p["id"]] = {
                    "id":    p["id"],
                    "name":  p["name"],
                    "color": p["color"],
                    "total": row["total"] or 0,
                    "is_parent": True,
                }

            conn.close()

            # Chỉ hiển thị danh mục cha thực sự (có ít nhất 1 con) có tổng tiền > 0
            combined = []
            for pid, pdata in parent_totals.items():
                if pdata["total"] > 0:
                    combined.append(pdata)
            combined.sort(key=lambda x: x["total"], reverse=True)

            limit = len(combined) if self._cat_expanded else min(5, len(combined))

            for i, par in enumerate(combined[:limit]):
                parent_color = par["color"] if par["color"] else CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
                par_data = {
                    "name":  par["name"] or "",
                    "color": parent_color,
                    "total": par["total"] or 0,
                }

                # Lấy danh mục con thuộc cha này có giao dịch trong tháng
                conn2 = get_connection()
                child_rows = conn2.execute("""
                    SELECT c.id, c.name, c.color, SUM(t.amount) as total
                    FROM transactions t
                    JOIN categories c ON t.category_id = c.id
                    WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                      AND c.parent_id = ?
                    GROUP BY c.id ORDER BY total DESC
                """, (tx_type, month, par["id"])).fetchall()
                conn2.close()

                children = []
                for ch in child_rows:
                    ch_color = ch["color"] if ch["color"] else CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)]
                    children.append({"name": ch["name"], "color": ch_color, "total": ch["total"] or 0})

                if children:
                    parent_row = ParentCategoryRow(par_data, children)
                    self._cat_list_l.addWidget(parent_row)
                else:
                    row = CategoryRow(par_data)
                    self._cat_list_l.addWidget(row)

            has_more = len(combined) > 5
            self._btn_toggle_cat.setVisible(has_more)
            self._btn_toggle_cat.setText("Thu gọn ∧" if self._cat_expanded else "Xem thêm ∨")

        else:
            # ----- CHẾ ĐỘ DANH MỤC CON (expense) hoặc THU NHẬP (flat) -----
            # Chỉ lấy danh mục LEAF:
            # 1. Danh mục có parent_id (con thực sự)
            # 2. Danh mục không có parent_id VÀ không có con (standalone)
            rows = conn.execute("""
                SELECT c.id, c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type=? AND strftime('%Y-%m', t.date)=?
                  AND (
                    c.parent_id IS NOT NULL
                    OR NOT EXISTS (SELECT 1 FROM categories cc WHERE cc.parent_id = c.id)
                  )
                GROUP BY c.id ORDER BY total DESC
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
        summary  = self.tm.get_monthly_summary(month)
        expense  = summary.get("total_expense", 0) or 0
        prev     = self._prev_month_str(month)
        prev_s   = self.tm.get_monthly_summary(prev)
        prev_exp = prev_s.get("total_expense", 0) or 0

        if prev_exp > 0:
            delta = expense - prev_exp
            pct   = delta / prev_exp * 100
            if pct > 10:
                msg = (f"Tăng bất thường {self._fmt(delta)} "
                       f"({pct:+.0f}%) so với cùng kỳ tháng trước")
                self._warning_lbl.setText(msg)
                self._warning_banner.show()
            else:
                self._warning_banner.hide()
        else:
            self._warning_banner.hide()

    def _open_category_manager(self):
        """Mở dialog quản lý danh mục, sau khi đóng thì refresh."""
        dlg = CategoryManagerDialog(self)
        dlg.exec()
        self.refresh()

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
        """Chuyển giữa Chi tiêu / Thu nhập."""
        self._data_mode    = mode
        self._cat_expanded = False
        self._view_mode    = "sub"  # reset về sub khi chuyển mode

        # Highlight card
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

        # Hiện/ẩn tab bar (chỉ hiện khi expense)
        self._tab_bar.setVisible(mode == "expense")

        # Reset tab buttons về "sub"
        self._btn_sub.setChecked(True)
        self._btn_parent.setChecked(False)
        self._btn_sub.setStyleSheet(self._cat_tab_style(True))
        self._btn_parent.setStyleSheet(self._cat_tab_style(False))

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
        """Chuyển Danh mục con / Danh mục cha (chỉ cho expense)."""
        self._view_mode    = mode
        self._cat_expanded = False
        self._btn_sub.setChecked(mode == "sub")
        self._btn_parent.setChecked(mode == "parent")
        self._btn_sub.setStyleSheet(self._cat_tab_style(mode == "sub"))
        self._btn_parent.setStyleSheet(self._cat_tab_style(mode == "parent"))
        # Reload biểu đồ theo chế độ mới
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
                font-size:26px;
                font-weight:bold;
                padding-bottom: 3px;
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
                    font-size:21px;
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
                font-size:21px;
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
                    font-size:21px;
                    font-weight:600;
                    padding:8px 0;
                }}
            """
        return f"""
            QPushButton {{
                background:transparent;
                color:{NAVY_LIGHT};
                border:none;
                border-bottom:3px solid transparent;
                font-size:21px;
                padding:8px 0;
            }}
            QPushButton:hover {{ color:{TEXT_DARK}; }}
        """