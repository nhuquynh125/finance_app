# app/ui/chatbot_frame.py  (viết lại: chatbot thuần giải thuật, không cần API)
"""
Chatbot tài chính — hoạt động hoàn toàn offline, không cần API hay internet.
Sử dụng LocalChatbotEngine với pattern matching + phân tích dữ liệu thực.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QFontMetrics

from app.ai.local_chatbot_engine import get_engine
from app.ai.nlp_parser import parse_quick_add
from datetime import datetime


# ── Worker thread — tránh block UI khi query DB ──────────────────────────────

class ChatWorker(QThread):
    response_ready = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def run(self):
        try:
            engine   = get_engine()
            response = engine.chat(self.message)
            self.response_ready.emit(response)
        except Exception as e:
            self.error.emit(f"Lỗi xử lý: {str(e)}")


# ── Shrinkable bubble label ───────────────────────────────────────────────────

class _BubbleLabel(QLabel):
    """
    QLabel subclass that reports its *natural* (unwrapped) text width as the
    preferred width so that short messages produce a narrow bubble.

    When the text is too long the label word-wraps inside whatever max-width
    the parent enforces via setMaximumWidth(), just like a normal QLabel.
    """

    # Horizontal padding (left + right) defined in the stylesheet (10px each side
    # → 14px in stylesheet → account for both sides).
    _H_PAD = 28   # matches padding:10px 14px → 14 * 2 = 28px

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        # Measure plain text width with the current font so the bubble only
        # grows as wide as the longest line of text (up to maxWidth).
        plain = self._strip_html(self.text())
        if not plain:
            return base
        fm = QFontMetrics(self.font())
        # widthF sums all lines; for multi-line html we check each line
        lines = plain.splitlines() or [plain]
        natural_w = max(fm.horizontalAdvance(ln) for ln in lines) + self._H_PAD
        natural_w = max(natural_w, self.minimumWidth())
        natural_w = min(natural_w, self.maximumWidth())
        return QSize(natural_w, base.height())

    @staticmethod
    def _strip_html(html: str) -> str:
        """Very small HTML stripper — good enough for our markdown-lite output."""
        import re
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return text


# ── Message bubble widget ─────────────────────────────────────────────────────

class MessageBubble(QFrame):
    """
    Một tin nhắn trong cuộc hội thoại.

    Bubble width behaviour
    ──────────────────────
    • Short messages  → bubble shrinks to hug the text (fit-content).
    • Long messages   → bubble expands up to MAX_WIDTH_RATIO of the chat
                        container width, then word-wraps.
    • resizeEvent updates the hard max-width whenever the container is resized
      so the cap always tracks ~75 % of available width.
    """

    # Fraction of the MessageBubble's own width used as the bubble cap.
    # The bubble's parent row is the full chat-container width minus margins,
    # so 0.78 ≈ "don't let the bubble exceed ~78 % of the chat width".
    MAX_WIDTH_RATIO = 0.78

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Let the outer row always fill the scroll-area width.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 3, 12, 3)
        outer.setSpacing(8)

        # Avatar chỉ cho bot
        if not is_user:
            avatar = QLabel("🤖")
            avatar.setFixedSize(32, 32)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setFont(QFont("Segoe UI Emoji", 19))
            avatar.setStyleSheet(
                "background:#E6F1FB; border-radius:16px; border:none;")
            outer.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        # Bubble — use the shrinkable label so short messages stay narrow
        self.bubble = _BubbleLabel()
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        # Horizontal size: preferred = natural text width, but can grow/shrink
        self.bubble.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.bubble.setMinimumWidth(60)
        # Hard max set initially; resizeEvent keeps it up-to-date.
        self.bubble.setMaximumWidth(560)

        if is_user:
            self.bubble.setStyleSheet("""
                QLabel {
                    background: #378ADD;
                    color: #ffffff;
                    border-radius: 14px;
                    border-bottom-right-radius: 4px;
                    padding: 10px 14px;
                    font-size:18px;
                    font-family: 'Segoe UI';
                    line-height: 1.5;
                }
            """)
            outer.addStretch()
            outer.addWidget(self.bubble)
        else:
            self.bubble.setStyleSheet("""
                QLabel {
                    background: #ffffff;
                    color: #1A2B45;
                    border-radius: 14px;
                    border-bottom-left-radius: 4px;
                    border: 1px solid #e0e8f0;
                    padding: 10px 14px;
                    font-size:18px;
                    font-family: 'Segoe UI';
                    line-height: 1.5;
                }
            """)
            outer.addWidget(self.bubble)
            outer.addStretch()

        self.set_text(text)

    # ── Percentage-based max-width ─────────────────────────────────────────────

    def resizeEvent(self, event):
        """Keep bubble max-width at MAX_WIDTH_RATIO of this row's width."""
        super().resizeEvent(event)
        available = self.width() - 24   # subtract outer horizontal margins (12+12)
        if not self.is_user:
            available -= 40             # subtract avatar width (32) + spacing (8)
        cap = max(200, int(available * self.MAX_WIDTH_RATIO))
        self.bubble.setMaximumWidth(cap)

    # ── Text helpers ───────────────────────────────────────────────────────────

    def set_text(self, text: str):
        """Render text với markdown-lite: **bold**, bullet points"""
        rendered = self._render_markdown(text)
        self.bubble.setText(rendered)

    def _render_markdown(self, text: str) -> str:
        """Chuyển markdown đơn giản thành rich text HTML"""
        import re
        # Bold: **text**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Newlines → <br>
        text = text.replace("\n", "<br>")
        return f"<span>{text}</span>"

    def append_text(self, chunk: str):
        current = self.bubble.text()
        # Strip outer span tags để nối thêm
        if current.startswith("<span>") and current.endswith("</span>"):
            inner = current[6:-7]
        else:
            inner = current
        # Thêm chunk mới
        if inner == "...":
            new_inner = chunk
        else:
            new_inner = inner + chunk
        self.bubble.setText(f"<span>{new_inner}</span>")


# ── Typing indicator ──────────────────────────────────────────────────────────

class TypingIndicator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 3, 12, 3)
        layout.setSpacing(8)

        avatar = QLabel("🤖")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI Emoji", 19))
        avatar.setStyleSheet(
            "background:#E6F1FB; border-radius:16px; border:none;")
        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        self.dots_lbl = QLabel("● ● ●")
        self.dots_lbl.setStyleSheet("""
            QLabel {
                background: #ffffff;
                color: #8BAEC8;
                border-radius: 14px;
                border: 1px solid #e0e8f0;
                padding: 10px 18px;
                font-size:23px;
                letter-spacing: 4px;
            }
        """)
        layout.addWidget(self.dots_lbl)
        layout.addStretch()

        self._dot_state = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(400)

    def _animate(self):
        states = ["●   ●   ●", "  ●   ●  ", "    ●    "]
        self._dot_state = (self._dot_state + 1) % 3
        self.dots_lbl.setText(states[self._dot_state])

    def stop(self):
        self._timer.stop()


# ══════════════════════════════════════════════════════════════════════════════
# Main ChatbotFrame
# ══════════════════════════════════════════════════════════════════════════════

class ChatbotFrame(QWidget):

    QUICK_PROMPTS = [
        "Tháng này chi bao nhiêu?",
        "Danh mục tốn nhiều nhất?",
        "Lời khuyên tài chính",
        "Dự báo tháng tới",
        "So với tháng trước",
        "Số dư tài khoản?",
    ]

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window      = main_window
        self._typing_widget   = None
        self._worker          = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_chat_area())
        layout.addWidget(self._build_quick_prompts())
        layout.addWidget(self._build_input_bar())

        # Tin nhắn chào mừng
        QTimer.singleShot(300, self._send_welcome)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Bot avatar + name
        bot_icon = QLabel("🤖")
        bot_icon.setFont(QFont("Segoe UI Emoji", 23))
        bot_icon.setStyleSheet("border:none;")
        layout.addWidget(bot_icon)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name_lbl = QLabel("Trợ lý Tài chính AI")
        name_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color:#1A2B45; border:none;")
        name_col.addWidget(name_lbl)
        status_lbl = QLabel("● Hoạt động — Không cần internet")
        status_lbl.setFont(QFont("Segoe UI", 15))
        status_lbl.setStyleSheet("color:#1D9E75; border:none;")
        name_col.addWidget(status_lbl)
        layout.addLayout(name_col)

        layout.addStretch()

        # Badge offline
        badge = QLabel("🔒 Offline")
        badge.setStyleSheet("""
            QLabel {
                background: #EAF3DE;
                color: #3B6D11;
                border: none;
                border-radius: 10px;
                padding: 3px 12px;
                font-size:16px;
                font-weight: 600;
            }
        """)
        layout.addWidget(badge)

        btn_clear = QPushButton("Xóa chat")
        btn_clear.setStyleSheet("""
            QPushButton {
                background: #fff;
                color: #888;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 5px 12px;
                font-size:17px;
            }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_clear.clicked.connect(self._clear_chat)
        layout.addWidget(btn_clear)
        return bar

    # ── Chat area ─────────────────────────────────────────────────────────────

    def _build_chat_area(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border:none; background:#f0f4f8; }")
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background:#f0f4f8;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 12, 0, 12)
        self.chat_layout.setSpacing(2)
        self.chat_layout.addStretch()

        self.scroll.setWidget(self.chat_container)
        return self.scroll

    # ── Quick prompts ─────────────────────────────────────────────────────────

    def _build_quick_prompts(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            "background:#fff; border-top:1px solid #e8e8e8;")
        bar.setFixedHeight(46)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        hint = QLabel("Gợi ý:")
        hint.setStyleSheet("color:#bbb; font-size:16px; border:none;")
        layout.addWidget(hint)

        for prompt in self.QUICK_PROMPTS:
            btn = QPushButton(prompt)
            btn.setStyleSheet("""
                QPushButton {
                    background: #f0f4f8;
                    color: #3A6B9A;
                    border: 1px solid #D0E4F7;
                    border-radius: 14px;
                    padding: 4px 12px;
                    font-size:16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #E6F1FB;
                    border-color: #378ADD;
                    color: #0C447C;
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, p=prompt: self._send_message(p))
            layout.addWidget(btn)

        layout.addStretch()
        return bar

    # ── Input bar ─────────────────────────────────────────────────────────────

    def _build_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(64)
        bar.setStyleSheet(
            "background:#fff; border-top:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText(
            "Hỏi về tài chính của bạn... (VD: Tháng này chi bao nhiêu?)")
        self.input_box.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #D0E4F7;
                border-radius: 22px;
                padding: 8px 18px;
                font-size:18px;
                background: #F5F9FF;
                color: #1A2B45;
                font-family: 'Segoe UI';
            }
            QLineEdit:focus {
                border-color: #378ADD;
                background: #ffffff;
            }
        """)
        self.input_box.returnPressed.connect(
            lambda: self._send_message(self.input_box.text()))
        layout.addWidget(self.input_box)

        self.btn_send = QPushButton("Gửi ▶")
        self.btn_send.setFixedSize(72, 40)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #378ADD, stop:1 #0B2A4A);
                color: #ffffff;
                border: none;
                border-radius: 20px;
                font-size:17px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #185FA5, stop:1 #0B2A4A);
            }
            QPushButton:disabled {
                background: #B5D4F4;
                color: #fff;
            }
        """)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(
            lambda: self._send_message(self.input_box.text()))
        layout.addWidget(self.btn_send)
        return bar

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _send_welcome(self):
        """Hiển thị tin nhắn chào mừng khi mở chatbot"""
        from app.ai.local_chatbot_engine import LocalChatbotEngine
        engine = get_engine()
        month  = datetime.now().strftime("%Y-%m")
        welcome = engine.chat("xin chào")
        self._add_bot_message(welcome)

    def _send_message(self, text: str):
        text = text.strip()
        if not text:
            return

        # Xử lý quick-add giao dịch
        parsed = parse_quick_add(text)
        if parsed and parsed.get("amount", 0) > 0:
            self._add_user_message(text)
            self.input_box.clear()
            self._add_bot_message(
                f"Tôi nhận ra bạn muốn thêm chi phí "
                f"**{parsed['amount']:,.0f}đ** cho '{parsed['description']}'.\n\n"
                "Để thêm giao dịch, vui lòng dùng tab **Giao dịch** ở menu bên trái "
                "hoặc nhấn **Ctrl+N**."
            )
            return

        self.input_box.clear()
        self._add_user_message(text)
        self._set_loading(True)

        # Chạy trên thread riêng
        self._worker = ChatWorker(text)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_response(self, response: str):
        self._set_loading(False)
        self._add_bot_message(response)

    def _on_error(self, error_msg: str):
        self._set_loading(False)
        self._add_bot_message(
            f"Xin lỗi, có lỗi xảy ra: {error_msg}\n"
            "Vui lòng thử lại."
        )

    def _add_user_message(self, text: str):
        bubble = MessageBubble(text, is_user=True)
        self.chat_layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _add_bot_message(self, text: str):
        bubble = MessageBubble(text, is_user=False)
        self.chat_layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def _set_loading(self, loading: bool):
        if loading:
            self.btn_send.setEnabled(False)
            self.input_box.setEnabled(False)
            self._typing_widget = TypingIndicator()
            self.chat_layout.addWidget(self._typing_widget)
            QTimer.singleShot(50, self._scroll_to_bottom)
        else:
            self.btn_send.setEnabled(True)
            self.input_box.setEnabled(True)
            self.input_box.setFocus()
            if self._typing_widget:
                self._typing_widget.stop()
                self.chat_layout.removeWidget(self._typing_widget)
                self._typing_widget.deleteLater()
                self._typing_widget = None

    def _scroll_to_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_chat(self):
        # Xóa tất cả widget trong chat_layout (giữ stretch ở cuối)
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Reset engine history
        engine = get_engine()
        engine.reset()

        # Gửi lại lời chào
        QTimer.singleShot(200, self._send_welcome)

    def refresh(self):
        """Gọi khi navigate đến tab này"""
        pass  # Engine tự cập nhật từ DB mỗi lần chat