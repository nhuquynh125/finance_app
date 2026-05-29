# app/ui/command_palette.py
"""
Command palette (Ctrl+K) và keyboard shortcuts toàn app.
Inspired by VS Code / Linear command palette.

Shortcuts mặc định:
  Ctrl+N  — Thêm giao dịch mới
  Ctrl+F  — Focus search (trong transaction frame)
  Ctrl+K  — Mở command palette
  Ctrl+1  — Dashboard
  Ctrl+2  — Giao dịch
  Ctrl+3  — Ngân sách
  Ctrl+4  — Dự báo
  Ctrl+5  — Chatbot AI
  Ctrl+6  — Báo cáo
  Ctrl+7  — Cài đặt
  Ctrl+,  — Cài đặt (alias)
  Ctrl+Z  — Undo (nếu implement)
  F5      — Refresh trang hiện tại

Cách dùng trong MainWindow:
    from app.ui.command_palette import ShortcutManager
    self.shortcut_mgr = ShortcutManager(self)
    self.shortcut_mgr.setup()
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QLabel, QWidget,
    QFrame, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QColor

from app.core.event_bus import bus


# ── Command model ─────────────────────────────────────────────────────────────

class Command:
    def __init__(self, title: str, subtitle: str,
                 action: Callable[[], None],
                 keywords: list[str] | None = None,
                 shortcut: str = ""):
        self.title    = title
        self.subtitle = subtitle
        self.action   = action
        self.keywords = keywords or []
        self.shortcut = shortcut

    def matches(self, query: str) -> bool:
        if not query:
            return True
        q = query.lower()
        haystack = (self.title + " " + self.subtitle + " " +
                    " ".join(self.keywords)).lower()
        return q in haystack

    def score(self, query: str) -> int:
        """Higher = better match. Used for sorting."""
        if not query:
            return 0
        q = query.lower()
        title_lower = self.title.lower()
        if title_lower.startswith(q):
            return 100
        if q in title_lower:
            return 50
        return 10


# ── Command palette dialog ────────────────────────────────────────────────────

class CommandPalette(QDialog):
    """Popup command palette. Đóng khi Escape hoặc chọn command."""

    command_selected = pyqtSignal(object)  # Command object

    def __init__(self, commands: list[Command], parent=None):
        super().__init__(parent)
        self._commands = commands
        self._filtered: list[Command] = commands[:]

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(520)
        self.setStyleSheet("""
            QDialog { background: transparent; }
        """)
        self._build()
        self._filter("")
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        if self.parent():
            pw = self.parent()
            self.move(
                pw.x() + (pw.width() - self.width()) // 2,
                pw.y() + 120
            )

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
        """)
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Search input
        input_row = QWidget()
        input_row.setStyleSheet("background: transparent; border-bottom: 1px solid #f0f0f0;")
        ir = QHBoxLayout(input_row)
        ir.setContentsMargins(14, 10, 14, 10)
        ir.setSpacing(8)

        search_icon = QLabel("⌘")
        search_icon.setFont(QFont("Segoe UI", 14))
        search_icon.setStyleSheet("color: #aaa; border: none; background: transparent;")
        ir.addWidget(search_icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Tìm lệnh hoặc trang...")
        self._input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 14px;
                color: #222;
                padding: 0;
            }
        """)
        self._input.textChanged.connect(self._filter)
        self._input.returnPressed.connect(self._execute_selected)
        ir.addWidget(self._input)

        shortcut_hint = QLabel("Esc để đóng")
        shortcut_hint.setStyleSheet("color: #ccc; font-size: 11px; border: none; background: transparent;")
        ir.addWidget(shortcut_hint)
        cl.addWidget(input_row)

        # Results list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                border-radius: 8px;
                padding: 0px;
                margin: 2px 4px;
            }
            QListWidget::item:selected {
                background: #E6F1FB;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self._list.setMaximumHeight(360)
        self._list.itemDoubleClicked.connect(self._execute_selected)
        cl.addWidget(self._list)

        # Footer
        footer = QWidget()
        footer.setStyleSheet("background: transparent; border-top: 1px solid #f0f0f0;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 6, 12, 6)
        hints = QLabel("↑↓ di chuyển  ·  Enter chọn  ·  Ctrl+K đóng/mở")
        hints.setStyleSheet("color: #ccc; font-size: 10px; border: none; background: transparent;")
        fl.addWidget(hints)
        cl.addWidget(footer)

        layout.addWidget(container)
        self.adjustSize()

    def _filter(self, query: str) -> None:
        self._filtered = sorted(
            [c for c in self._commands if c.matches(query)],
            key=lambda c: c.score(query),
            reverse=True
        )
        self._list.clear()
        for cmd in self._filtered[:12]:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            widget = self._make_row(cmd)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self.adjustSize()

    def _make_row(self, cmd: Command) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        text_col = QWidget()
        text_col.setStyleSheet("background: transparent;")
        tc = QVBoxLayout(text_col)
        tc.setContentsMargins(0, 0, 0, 0)
        tc.setSpacing(1)

        title = QLabel(cmd.title)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #222; border: none; background: transparent;")
        tc.addWidget(title)

        if cmd.subtitle:
            sub = QLabel(cmd.subtitle)
            sub.setFont(QFont("Segoe UI", 10))
            sub.setStyleSheet("color: #888; border: none; background: transparent;")
            tc.addWidget(sub)

        layout.addWidget(text_col, stretch=1)

        if cmd.shortcut:
            sc_lbl = QLabel(cmd.shortcut)
            sc_lbl.setStyleSheet("""
                color: #888;
                background: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-family: monospace;
            """)
            layout.addWidget(sc_lbl)

        return w

    def _execute_selected(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._filtered):
            cmd = self._filtered[row]
            self.accept()
            QTimer.singleShot(50, cmd.action)   # đóng trước, chạy action sau

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
        elif key == Qt.Key.Key_Up:
            row = max(0, self._list.currentRow() - 1)
            self._list.setCurrentRow(row)
        elif key == Qt.Key.Key_Down:
            row = min(self._list.count() - 1, self._list.currentRow() + 1)
            self._list.setCurrentRow(row)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._execute_selected()
        else:
            self._input.setFocus()
            super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._input.setFocus()


# ── Shortcut manager ──────────────────────────────────────────────────────────

class ShortcutManager:
    """
    Đăng ký tất cả keyboard shortcuts cho MainWindow.
    Cũng build danh sách commands cho palette.
    """

    PAGES = [
        ("Dashboard",   "Ctrl+1"),
        ("Giao dịch",   "Ctrl+2"),
        ("Ngân sách",   "Ctrl+3"),
        ("Dự báo",      "Ctrl+4"),
        ("Chatbot AI",  "Ctrl+5"),
        ("Báo cáo",     "Ctrl+6"),
        ("Cài đặt",     "Ctrl+7"),
    ]

    def __init__(self, main_window):
        self._win = main_window
        self._commands: list[Command] = []
        self._palette: Optional[CommandPalette] = None

    def setup(self) -> None:
        """Gọi một lần trong MainWindow sau khi build xong."""
        self._build_commands()
        self._register_shortcuts()

    def _build_commands(self) -> None:
        win = self._win

        # Navigation commands
        for page, sc in self.PAGES:
            _page = page
            self._commands.append(Command(
                title=f"Đến {_page}",
                subtitle=f"Mở trang {_page}",
                action=lambda p=_page: bus.navigate_to.emit(p),
                keywords=["trang", "navigate", _page.lower()],
                shortcut=sc,
            ))

        # Action commands
        self._commands += [
            Command(
                title="Thêm giao dịch mới",
                subtitle="Mở dialog thêm giao dịch",
                action=self._open_add_transaction,
                keywords=["thêm", "giao dịch", "add", "new"],
                shortcut="Ctrl+N",
            ),
            Command(
                title="Chạy dự báo AI",
                subtitle="Dự báo chi tiêu tháng tới",
                action=lambda: bus.navigate_to.emit("Dự báo"),
                keywords=["dự báo", "forecast", "ai"],
                shortcut="",
            ),
            Command(
                title="Xuất báo cáo PDF",
                subtitle="Tạo báo cáo tháng này",
                action=lambda: bus.navigate_to.emit("Báo cáo"),
                keywords=["pdf", "báo cáo", "report", "xuất"],
                shortcut="",
            ),
            Command(
                title="Sao lưu database",
                subtitle="Backup dữ liệu ngay bây giờ",
                action=self._backup_db,
                keywords=["backup", "sao lưu", "database"],
                shortcut="",
            ),
            Command(
                title="Đổi theme sáng/tối",
                subtitle="Toggle dark mode",
                action=self._toggle_theme,
                keywords=["theme", "dark", "light", "tối", "sáng"],
                shortcut="",
            ),
            Command(
                title="Mở notification center",
                subtitle="Xem lịch sử thông báo",
                action=self._open_notifications,
                keywords=["thông báo", "notification", "bell"],
                shortcut="",
            ),
        ]

    def _register_shortcuts(self) -> None:
        win = self._win

        # Ctrl+K — command palette
        ck = QShortcut(QKeySequence("Ctrl+K"), win)
        ck.activated.connect(self.open_palette)

        # Navigation shortcuts
        for i, (page, sc) in enumerate(self.PAGES, 1):
            _page = page
            s = QShortcut(QKeySequence(sc), win)
            s.activated.connect(lambda p=_page: bus.navigate_to.emit(p))

        # Ctrl+, → Settings
        cs = QShortcut(QKeySequence("Ctrl+,"), win)
        cs.activated.connect(lambda: bus.navigate_to.emit("Cài đặt"))

        # Ctrl+N → add transaction
        cn = QShortcut(QKeySequence("Ctrl+N"), win)
        cn.activated.connect(self._open_add_transaction)

        # F5 → refresh
        f5 = QShortcut(QKeySequence("F5"), win)
        f5.activated.connect(self._refresh_current)

    def open_palette(self) -> None:
        if self._palette and self._palette.isVisible():
            self._palette.close()
            return
        self._palette = CommandPalette(self._commands, self._win)
        self._palette.exec()

    def _open_add_transaction(self) -> None:
        from app.ui.transaction_frame import TransactionDialog
        from PyQt6.QtWidgets import QDialog as _QD
        dialog = TransactionDialog(parent=self._win)
        if dialog.exec() == _QD.DialogCode.Accepted:
            from app.data.repositories import TransactionRepo, TransactionModel
            data = dialog.get_data()
            try:
                repo = TransactionRepo()
                model = TransactionModel(
                    account_id=data["account_id"],
                    amount=data["amount"],
                    type_=data["type_"],
                    description=data["description"],
                    date=data["date"],
                    category_id=data.get("category_id"),
                    note=data.get("note", ""),
                )
                repo.add(model)
                bus.transaction_added.emit()
                bus.balance_changed.emit()
                bus.notify_success.emit("Đã thêm", data["description"])
            except ValueError as e:
                bus.notify_error.emit("Lỗi", str(e))

    def _backup_db(self) -> None:
        from app.core.settings_manager import backup_database
        try:
            path = backup_database()
            bus.notify_success.emit("Sao lưu thành công", str(path.name))
        except Exception as e:
            bus.notify_error.emit("Lỗi sao lưu", str(e))

    def _toggle_theme(self) -> None:
        from app.core.theme_engine import theme_engine
        new_mode = "dark" if not theme_engine.is_dark else "light"
        theme_engine.set_mode(new_mode)
        bus.notify_info.emit("Theme", f"Đã chuyển sang chế độ {'tối' if new_mode == 'dark' else 'sáng'}")

    def _open_notifications(self) -> None:
        from app.ui.notification import notifier
        notifier.show_center(self._win)

    def _refresh_current(self) -> None:
        if hasattr(self._win, "_current_page") and hasattr(self._win, "_pages"):
            frame = self._win._pages.get(self._win._current_page)
            if frame and hasattr(frame, "refresh"):
                frame.refresh()
