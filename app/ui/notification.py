# app/ui/notification.py
"""
Toast notification system — thay thế QMessageBox blocking.
Hiển thị thông báo overlay góc phải màn hình, tự biến mất sau timeout.
Có notification center để xem lại lịch sử.

Cách dùng:
    from app.ui.notification import notifier

    notifier.success("Đã lưu", "Giao dịch thêm thành công")
    notifier.warning("Ngân sách", "Ăn uống đã dùng 85%")
    notifier.error("Lỗi", "Không kết nối được database")
    notifier.info("AI", "Phân loại hoàn tất 12 giao dịch")

    # Tích hợp với event bus (trong main_window):
    from app.core.event_bus import bus
    bus.notify_success.connect(notifier.success)
    bus.notify_warning.connect(notifier.warning)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QScrollArea, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRect
from PyQt6.QtGui import QFont, QColor


# ── Toast item ────────────────────────────────────────────────────────────────

@dataclass
class NotificationItem:
    kind: str           # "success" | "warning" | "error" | "info"
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    read: bool = False


COLORS = {
    "success": ("#EAF3DE", "#27500A", "#639922"),
    "warning": ("#FAEEDA", "#633806", "#BA7517"),
    "error":   ("#FCEBEB", "#791F1F", "#E24B4A"),
    "info":    ("#E6F1FB", "#0C447C", "#378ADD"),
}

ICONS = {
    "success": "✓",
    "warning": "!",
    "error":   "✕",
    "info":    "i",
}


class ToastWidget(QFrame):
    """Một toast card. Tự xóa sau duration_ms ms."""

    def __init__(self, item: NotificationItem, parent: QWidget,
                 duration_ms: int = 4000):
        super().__init__(parent)
        self._item = item
        bg, text, border = COLORS.get(item.kind, COLORS["info"])

        self.setFixedWidth(320)
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon = QLabel(ICONS.get(item.kind, "i"))
        icon.setFixedSize(24, 24)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        icon.setStyleSheet(f"""
            background: {border};
            color: white;
            border-radius: 12px;
            border: none;
        """)
        layout.addWidget(icon)

        text_col = QWidget()
        text_col.setStyleSheet("background: transparent;")
        tc = QVBoxLayout(text_col)
        tc.setContentsMargins(0, 0, 0, 0)
        tc.setSpacing(2)

        title_lbl = QLabel(item.title)
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {text}; border: none; background: transparent;")
        tc.addWidget(title_lbl)

        if item.message:
            msg_lbl = QLabel(item.message)
            msg_lbl.setFont(QFont("Segoe UI", 10))
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(f"color: {text}; border: none; background: transparent; opacity: 0.8;")
            tc.addWidget(msg_lbl)

        layout.addWidget(text_col, stretch=1)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {text};
                border: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: rgba(0,0,0,0.1); }}
        """)
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

        self.adjustSize()

        # Auto-dismiss timer
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self._dismiss)

    def _dismiss(self) -> None:
        self.hide()
        self.deleteLater()


# ── Toast container (overlay) ─────────────────────────────────────────────────

class ToastContainer(QWidget):
    """
    Container trong suốt ở góc phải dưới màn hình.
    Stack nhiều toast theo chiều dọc.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch()

        self._reposition()

    def _reposition(self) -> None:
        if self.parent():
            pw = self.parent()
            self.setGeometry(
                pw.width() - 340,
                pw.height() - 500,
                330, 480
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

    def add_toast(self, item: NotificationItem, duration_ms: int = 4000) -> None:
        toast = ToastWidget(item, self, duration_ms)
        self._layout.addWidget(toast)
        self._reposition()


# ── Notification center dialog ────────────────────────────────────────────────

class NotificationCenter(QDialog):
    """Xem lại lịch sử notification. Mở từ bell icon trong sidebar."""

    def __init__(self, history: list[NotificationItem], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thông báo")
        self.setFixedSize(420, 500)
        self.setStyleSheet("QDialog { background: #f5f5f5; }")
        self._build(history)

    def _build(self, history: list[NotificationItem]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet("background: #fff; border-bottom: 1px solid #e8e8e8;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Thông báo")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        hl.addWidget(title)
        hl.addStretch()
        count = QLabel(f"{len(history)} thông báo")
        count.setStyleSheet("color: #aaa; font-size: 11px; border: none;")
        hl.addWidget(count)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f5f5f5; }")

        content = QWidget()
        content.setStyleSheet("background: #f5f5f5;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(8)

        if not history:
            empty = QLabel("Chưa có thông báo nào")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #bbb; font-size: 13px; padding: 40px; border: none;")
            cl.addWidget(empty)
        else:
            for item in reversed(history[-50:]):
                card = self._make_card(item)
                cl.addWidget(card)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _make_card(self, item: NotificationItem) -> QFrame:
        bg, text, border = COLORS.get(item.kind, COLORS["info"])
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #fff;
                border: 1px solid #e8e8e8;
                border-left: 3px solid {border};
                border-radius: 0;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(3)

        row = QHBoxLayout()
        title = QLabel(item.title)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("border: none; color: #222;")
        row.addWidget(title)
        row.addStretch()
        ts = time.strftime("%H:%M %d/%m", time.localtime(item.timestamp))
        time_lbl = QLabel(ts)
        time_lbl.setStyleSheet("color: #aaa; font-size: 10px; border: none;")
        row.addWidget(time_lbl)
        cl.addLayout(row)

        if item.message:
            msg = QLabel(item.message)
            msg.setFont(QFont("Segoe UI", 10))
            msg.setWordWrap(True)
            msg.setStyleSheet("color: #555; border: none;")
            cl.addWidget(msg)

        return card


# ── Notifier (singleton) ──────────────────────────────────────────────────────

class Notifier:
    """
    Singleton facade. Emit toast và lưu history.
    Phải gọi notifier.set_parent(main_window) sau khi main_window sẵn sàng.
    """

    def __init__(self):
        self._parent: Optional[QWidget] = None
        self._container: Optional[ToastContainer] = None
        self._history: list[NotificationItem] = []
        self.max_history = 200
        self.default_duration = 4000

    def set_parent(self, parent: QWidget) -> None:
        """Gọi một lần trong MainWindow.__init__ sau khi build xong."""
        self._parent = parent
        self._container = ToastContainer(parent)
        self._container.show()
        self._container.raise_()

    def _notify(self, kind: str, title: str, message: str = "",
                duration_ms: int = 0) -> None:
        item = NotificationItem(kind=kind, title=title, message=message)
        self._history.append(item)
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
        if self._container:
            self._container.add_toast(
                item, duration_ms or self.default_duration
            )
            self._container.raise_()

    def success(self, title: str, message: str = "") -> None:
        self._notify("success", title, message)

    def warning(self, title: str, message: str = "") -> None:
        self._notify("warning", title, message, duration_ms=6000)

    def error(self, title: str, message: str = "") -> None:
        self._notify("error", title, message, duration_ms=8000)

    def info(self, title: str, message: str = "") -> None:
        self._notify("info", title, message)

    def show_center(self, parent=None) -> None:
        """Mở notification center dialog."""
        dialog = NotificationCenter(self._history, parent or self._parent)
        dialog.exec()

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self._history if not n.read)

    @property
    def history(self) -> list[NotificationItem]:
        return self._history.copy()

    def on_parent_resize(self) -> None:
        """Gọi trong MainWindow.resizeEvent để reposition container."""
        if self._container and self._parent:
            pw = self._parent
            self._container.setGeometry(
                pw.width() - 340,
                pw.height() - 500,
                330, 480
            )


# Singleton
notifier = Notifier()
