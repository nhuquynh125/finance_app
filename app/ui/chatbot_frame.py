# app/ui/chatbot_frame.py  (cập nhật: check fine-tuned model per-user)
"""
Thay đổi: _check_engine_status() cho engine "embedded"
dùng user_session để tìm model của user hiện tại.

Fix: MessageBubble now uses QSizePolicy.Minimum so each bubble
     shrinks to fit its text instead of stretching full-row width.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QScrollArea, QFrame,
    QComboBox, QDialog, QProgressBar, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from app.core.settings_manager import get_setting
from app.data.models import get_connection
from datetime import datetime, timedelta
#from app.ai.base_plugin import registry
from app.ai.nlp_parser import parse_quick_add


def _get_user_ai_dir():
    try:
        from user_session import session
        if session.is_logged_in:
            return session.ai_dir
    except ImportError:
        pass
    try:
        from config import DATA_DIR
        from pathlib import Path
        return Path(DATA_DIR)
    except ImportError:
        from pathlib import Path
        return Path("data")


class MessageBubble(QFrame):
    # Fallback absolute cap when no viewport width is known yet.
    _FALLBACK_MAX_PX = 560

    def __init__(self, text, is_user, max_width: int = _FALLBACK_MAX_PX,
                 parent=None):
        super().__init__(parent)
        self._is_user = is_user

        # The outer frame spans the full row width so addStretch() can align
        # the bubble, but is visually transparent — colour lives on the label.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(0)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setFont(QFont("Segoe UI", 12))

        # Minimum policy: label shrinks to text width rather than expanding.
        # max_width is set dynamically by ChatbotFrame (≈72 % of viewport).
        self.label.setMaximumWidth(max_width)
        self.label.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Minimum,
        )

        if is_user:
            self.label.setStyleSheet(
                "QLabel { background:#E6F1FB; color:#0C447C; "
                "border-radius:12px; padding:10px 14px; }")
            layout.addStretch()           # pushes bubble to the RIGHT
            layout.addWidget(self.label)
        else:
            self.label.setStyleSheet(
                "QLabel { background:#f5f5f5; color:#222; "
                "border-radius:12px; padding:10px 14px; "
                "border:1px solid #e8e8e8; }")
            layout.addWidget(self.label)
            layout.addStretch()           # pushes bubble to the LEFT

    def set_max_bubble_width(self, max_width: int) -> None:
        """Called by ChatbotFrame.resizeEvent to keep the cap up-to-date."""
        self.label.setMaximumWidth(max_width)

    def append_text(self, text):
        cur = self.label.text()
        self.label.setText(text if cur == "..." else cur + text)


class TrainWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def run(self):
        try:
            from app.ai.fine_tuner import fine_tune_model
            path = fine_tune_model(
                epochs=3,
                progress_callback=lambda msg: self.progress.emit(msg)
            )
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class TrainModelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fine-tune model AI")
        self.setFixedSize(460, 320)
        self.setStyleSheet(
            "QDialog { background:#fff; } "
            "QLabel { font-size:12px; color:#444; }")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Huấn luyện model AI với dữ liệu của bạn")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#111;")
        layout.addWidget(title)

        desc = QLabel(
            "App tự động tạo câu hỏi-trả lời từ lịch sử giao dịch\n"
            "và dùng để train model DistilGPT2 nhỏ gọn.\n\n"
            "Thời gian: ~5-15 phút (CPU) hoặc ~2 phút (GPU)\n"
            "RAM cần: ~4-6 GB\n"
            "Cần cài: pip install transformers torch datasets"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#555;")
        layout.addWidget(desc)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        self.progress_bar.setStyleSheet(
            "QProgressBar { border:none; border-radius:3px; background:#e8e8e8; } "
            "QProgressBar::chunk { background:#7F77DD; border-radius:3px; }")
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#7F77DD; font-size:11px;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        layout.addStretch()
        btn_layout = QHBoxLayout()

        self.btn_cancel = QPushButton("Đóng")
        self.btn_cancel.setStyleSheet(
            "QPushButton { background:#fff; color:#888; "
            "border:1px solid #ddd; border-radius:6px; padding:6px 14px; }")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_train = QPushButton("Bắt đầu huấn luyện")
        self.btn_train.setStyleSheet(
            "QPushButton { background:#EEEDFE; color:#3C3489; "
            "border:1px solid #AFA9EC; border-radius:6px; "
            "padding:6px 18px; font-size:12px; font-weight:500; } "
            "QPushButton:hover { background:#AFA9EC; } "
            "QPushButton:disabled { background:#eee; color:#bbb; border-color:#eee; }")
        self.btn_train.clicked.connect(self._start_training)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_train)
        layout.addLayout(btn_layout)

    def _start_training(self):
        self.btn_train.setEnabled(False)
        self.progress_bar.show()
        self.status_lbl.setText("Đang chuẩn bị...")
        self.train_thread = TrainWorker()
        self.train_thread.progress.connect(self.status_lbl.setText)
        self.train_thread.finished.connect(self._on_done)
        self.train_thread.error.connect(self._on_error)
        self.train_thread.start()

    def _on_done(self, path):
        self.progress_bar.hide()
        self.status_lbl.setText(f"Hoàn tất! Model lưu tại:\n{path}")
        self.status_lbl.setStyleSheet("color:#1D9E75; font-size:11px;")
        QMessageBox.information(
            self, "Thành công",
            "Model đã được huấn luyện!\n"
            "Chọn 'Model nhúng (transformers)' để sử dụng.")

    def _on_error(self, msg):
        self.progress_bar.hide()
        self.btn_train.setEnabled(True)
        self.status_lbl.setText(f"Lỗi: {msg}")
        self.status_lbl.setStyleSheet("color:#E24B4A; font-size:11px;")


class ChatbotFrame(QWidget):

    ENGINES = {
        "Gemini API (Google)":          "gemini",
        "Ollama — chạy offline (khuyến dùng)": "ollama",
        "Model nhúng (transformers)":   "embedded",
    }

    QUICK_PROMPTS = [
        "Tháng này tôi chi nhiều nhất ở đâu?",
        "Tôi có tiết kiệm được không?",
        "Gợi ý cắt giảm chi tiêu",
        "Tháng tới nên đặt ngân sách bao nhiêu?",
    ]

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window     = main_window
        self._history        = []
        self._current_bubble = None
        self._engine         = get_setting("chat_engine", "gemini")
        self._bubbles: list[MessageBubble] = []   # kept so resizeEvent can update caps
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(
            "background:#fff; border-bottom:1px solid #e8e8e8;")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(10)

        title = QLabel("Chatbot AI")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        tb.addWidget(title)

        self.status_badge = QLabel("Đang kiểm tra...")
        self.status_badge.setStyleSheet(
            "QLabel { background:#f0f0f0; color:#888; border:none; "
            "border-radius:10px; padding:3px 10px; font-size:11px; }")
        tb.addWidget(self.status_badge)
        tb.addStretch()

        engine_lbl = QLabel("Engine:")
        engine_lbl.setStyleSheet("color:#888; font-size:12px; border:none;")
        tb.addWidget(engine_lbl)

        self.engine_combo = QComboBox()
        self.engine_combo.setFixedWidth(260)
        self.engine_combo.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:6px; "
            "padding:4px 8px; font-size:12px; background:#fff; }")
        for label in self.ENGINES:
            self.engine_combo.addItem(label)
        for idx in range(self.engine_combo.count()):
            if self.ENGINES[self.engine_combo.itemText(idx)] == self._engine:
                self.engine_combo.setCurrentIndex(idx)
                break
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        tb.addWidget(self.engine_combo)

        btn_train = QPushButton("Train model")
        btn_train.setStyleSheet(
            "QPushButton { background:#EEEDFE; color:#3C3489; "
            "border:1px solid #AFA9EC; border-radius:6px; "
            "padding:5px 12px; font-size:12px; } "
            "QPushButton:hover { background:#AFA9EC; }")
        btn_train.clicked.connect(self._open_train_dialog)
        tb.addWidget(btn_train)

        btn_clear = QPushButton("Xóa")
        btn_clear.setStyleSheet(
            "QPushButton { background:#fff; color:#888; "
            "border:1px solid #ddd; border-radius:6px; "
            "padding:5px 10px; font-size:12px; } "
            "QPushButton:hover { background:#f5f5f5; }")
        btn_clear.clicked.connect(self._clear_chat)
        tb.addWidget(btn_clear)
        layout.addWidget(toolbar)

        # Chat area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border:none; background:#fafafa; }")
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background:#fafafa;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(16, 16, 16, 16)
        self.chat_layout.setSpacing(4)
        self.chat_layout.addStretch()
        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area)

        # Quick prompts
        quick_bar = QWidget()
        quick_bar.setStyleSheet(
            "background:#fff; border-top:1px solid #e8e8e8;")
        ql = QHBoxLayout(quick_bar)
        ql.setContentsMargins(12, 8, 12, 8)
        ql.setSpacing(6)
        for prompt in self.QUICK_PROMPTS:
            btn = QPushButton(prompt)
            btn.setStyleSheet(
                "QPushButton { background:#f0f0f0; color:#555; "
                "border:none; border-radius:14px; "
                "padding:5px 12px; font-size:11px; } "
                "QPushButton:hover { background:#E6F1FB; color:#0C447C; }")
            btn.clicked.connect(lambda _, p=prompt: self._send(p))
            ql.addWidget(btn)
        ql.addStretch()
        layout.addWidget(quick_bar)

        # Input
        input_w = QWidget()
        input_w.setStyleSheet(
            "background:#fff; border-top:1px solid #e8e8e8;")
        il = QHBoxLayout(input_w)
        il.setContentsMargins(16, 10, 16, 10)
        il.setSpacing(10)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Hỏi AI về tài chính của bạn...")
        self.input_box.setStyleSheet(
            "QLineEdit { border:1px solid #ddd; border-radius:20px; "
            "padding:8px 16px; font-size:13px; background:#f7f7f7; } "
            "QLineEdit:focus { border-color:#378ADD; background:#fff; }")
        self.input_box.returnPressed.connect(
            lambda: self._send(self.input_box.text()))
        il.addWidget(self.input_box)

        self.btn_send = QPushButton("Gửi")
        self.btn_send.setFixedSize(60, 36)
        self.btn_send.setStyleSheet(
            "QPushButton { background:#378ADD; color:#fff; "
            "border:none; border-radius:18px; "
            "font-size:12px; font-weight:500; } "
            "QPushButton:hover { background:#185FA5; } "
            "QPushButton:disabled { background:#ccc; }")
        self.btn_send.clicked.connect(
            lambda: self._send(self.input_box.text()))
        il.addWidget(self.btn_send)
        layout.addWidget(input_w)

        # Welcome message
        self._add_assistant_message(
            "Xin chào! Tôi là chatbot AI tài chính.\n"
            "Chọn engine ở góc trên phải:\n"
            "  - Gemini API: cần internet và GEMINI_API_KEY (miễn phí tại aistudio.google.com)\n"
            "  - Ollama: tốt nhất offline, cần cài ollama.com và chạy: ollama pull qwen2.5:3b\n"
            "  - Model nhúng: tự động tải TinyLlama lần đầu\n\n"
            "Sau đó hỏi tôi bất cứ điều gì về chi tiêu!")
        QTimer.singleShot(500, self._check_engine_status)

    # ── Engine handling ───────────────────────────────────────────────────

    def _on_engine_changed(self, _):
        label = self.engine_combo.currentText()
        self._engine = self.ENGINES[label]
        QTimer.singleShot(100, self._check_engine_status)

    def _check_engine_status(self):
        if self._engine == "gemini":
            import os
            if os.getenv("GEMINI_API_KEY"):
                self._set_badge("Gemini API sẵn sàng", "ok")
            else:
                self._set_badge("Chưa có GEMINI_API_KEY — xem hướng dẫn", "err")

        elif self._engine == "ollama":
            from app.ai.local_llm import check_ollama_running, get_available_models
            if check_ollama_running():
                models = get_available_models()
                local_models = [m for m in models if "cloud" not in m.lower()]
                if local_models:
                    self._set_badge(f"Ollama sẵn sàng · {local_models[0]}", "ok")
                else:
                    self._set_badge("Chưa có model — chạy: ollama pull qwen2.5:3b", "warn")
            else:
                self._set_badge("Ollama chưa chạy — mở app Ollama trước", "err")

        elif self._engine == "embedded":
            ai_dir = _get_user_ai_dir()
            finetuned_dir = ai_dir / "fine_tuned_model"
            if finetuned_dir.exists():
                self._set_badge("Model fine-tuned sẵn sàng", "ok")
            else:
                self._set_badge("Sẽ dùng TinyLlama (tự tải ~600MB lần đầu)", "info")

    def _set_badge(self, text: str, level: str):
        colors = {
            "ok":   "background:#EAF3DE; color:#3B6D11;",
            "warn": "background:#FAEEDA; color:#633806;",
            "err":  "background:#FCEBEB; color:#A32D2D;",
            "info": "background:#EEEDFE; color:#3C3489;",
        }
        c = colors.get(level, colors["info"])
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"QLabel {{ {c} border:none; "
            f"border-radius:10px; padding:3px 10px; font-size:11px; }}")

    # ── Send / receive ────────────────────────────────────────────────────

    def _send(self, text: str):
        text = text.strip()
        if not text:
            return

        parsed = parse_quick_add(text)
        if parsed:
            self.input_box.clear()
            self._add_user_message(text)
            self._add_assistant_message(
                f"Tôi hiểu: bạn muốn thêm chi phí {parsed['amount']:,.0f}đ "
                f"cho '{parsed['description']}'.\n"
                f"Tính năng xác nhận và thêm tự động đang được phát triển."
            )
            return

        self.input_box.clear()
        self._add_user_message(text)
        self._history.append({"role": "user", "content": text})
        self._current_bubble = self._add_assistant_message("...")
        self.btn_send.setEnabled(False)
        self.input_box.setEnabled(False)

        system = self._build_system_prompt()
        plugin = registry.get(self._engine)
        if not plugin:
            self._on_error(f"Engine '{self._engine}' không khả dụng")
            return

        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            try:
                self.worker.terminate()
                self.worker.wait(100)
            except Exception:
                pass

        self.worker = plugin.create_worker(self._history.copy(), system)
        if self._engine == "embedded" and hasattr(self.worker, 'progress'):
            self.worker.progress.connect(self._on_progress)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, msg: str):
        if self._current_bubble:
            self._current_bubble.label.setText(msg)

    def _on_token(self, token: str):
        if self._current_bubble:
            self._current_bubble.append_text(token)
            QTimer.singleShot(10, self._scroll_to_bottom)

    def _on_finished(self, full_text: str):
        self._history.append({"role": "assistant", "content": full_text})
        self.btn_send.setEnabled(True)
        self.input_box.setEnabled(True)
        self.input_box.setFocus()
        self._current_bubble = None

    def _on_error(self, msg: str):
        if self._current_bubble:
            self._current_bubble.label.setText(f"Lỗi: {msg}")
            self._current_bubble.label.setStyleSheet(
                "QLabel { background:#FCEBEB; color:#A32D2D; "
                "border-radius:12px; padding:10px 14px; "
                "border:1px solid #E24B4A; }")
        self.btn_send.setEnabled(True)
        self.input_box.setEnabled(True)
        self._current_bubble = None

    def _open_train_dialog(self):
        dialog = TrainModelDialog(parent=self)
        dialog.exec()
        QTimer.singleShot(300, self._check_engine_status)

    def _clear_chat(self):
        self._history.clear()
        self._bubbles.clear()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._add_assistant_message("Hội thoại đã xóa. Hỏi tôi bất cứ điều gì!")

    def refresh(self):
        QTimer.singleShot(100, self._check_engine_status)

    # ── UI helpers ────────────────────────────────────────────────────────

    def _bubble_max_width(self) -> int:
        """72 % of the scroll-area viewport width, clamped to [260, 900] px."""
        vp_w = self.scroll_area.viewport().width()
        if vp_w < 10:          # not yet laid out — use a safe default
            vp_w = 780
        return max(260, min(900, int(vp_w * 0.72)))

    def resizeEvent(self, event) -> None:
        """Keep every existing bubble's cap in sync when the window is resized."""
        super().resizeEvent(event)
        new_max = self._bubble_max_width()
        # Prune dead references (deleted widgets) while we iterate
        self._bubbles = [b for b in self._bubbles if not b.isHidden() or True]
        for bubble in self._bubbles:
            try:
                bubble.set_max_bubble_width(new_max)
            except RuntimeError:
                pass   # widget already deleted by Qt

    def _add_user_message(self, text: str) -> MessageBubble:
        bubble = MessageBubble(text, is_user=True, max_width=self._bubble_max_width())
        self._bubbles.append(bubble)
        self.chat_layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def _add_assistant_message(self, text: str) -> MessageBubble:
        bubble = MessageBubble(text, is_user=False, max_width=self._bubble_max_width())
        self._bubbles.append(bubble)
        self.chat_layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def _scroll_to_bottom(self):
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum())

    # ── System prompt ─────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        now = datetime.now()
        month = now.strftime("%Y-%m")
        prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        conn = get_connection()
        s = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END),0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as expense,
                COUNT(*) as count
            FROM transactions WHERE strftime('%Y-%m', date)=?
        """, (month,)).fetchone()

        prev_s = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as expense
            FROM transactions WHERE strftime('%Y-%m', date)=?
        """, (prev_month,)).fetchone()

        top = conn.execute("""
            SELECT c.name, SUM(t.amount) as total
            FROM transactions t JOIN categories c ON t.category_id=c.id
            WHERE t.type='expense' AND strftime('%Y-%m', t.date)=?
            GROUP BY c.id ORDER BY total DESC LIMIT 3
        """, (month,)).fetchall()

        over_budgets = conn.execute("""
            SELECT c.name, b.limit_amount, SUM(t.amount) as spent
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            JOIN transactions t ON t.category_id = c.id
            WHERE b.month = ? AND t.type = 'expense'
              AND strftime('%Y-%m', t.date) = ?
            GROUP BY c.id HAVING spent > b.limit_amount
        """, (month, month)).fetchall()
        conn.close()

        top_str = ", ".join(
            f"{r['name']} ({r['total']:,.0f}đ)" for r in top
        ) or "chưa có"
        over_str = ", ".join(r["name"] for r in over_budgets)

        diff_msg = ""
        if prev_s and prev_s["expense"] > 0:
            diff = s["expense"] - prev_s["expense"]
            pct  = (diff / prev_s["expense"]) * 100
            diff_msg = (f"So với tháng trước: "
                        f"{'tăng' if diff > 0 else 'giảm'} {abs(pct):.1f}%.")

        try:
            from user_session import session
            user_name = session.full_name or "bạn"
        except Exception:
            user_name = "bạn"

        prompt = (
            f"Bạn là chuyên gia tư vấn tài chính cá nhân AI của {user_name}. "
            f"Trả lời bằng tiếng Việt, thân thiện, chuyên nghiệp.\n"
            f"Bối cảnh hiện tại (tháng {month}):\n"
            f"- Thu nhập: {s['income']:,.0f}đ\n"
            f"- Chi tiêu: {s['expense']:,.0f}đ ({s['count']} giao dịch). {diff_msg}\n"
            f"- Top chi tiêu: {top_str}.\n"
        )
        if over_str:
            prompt += (f"- CẢNH BÁO: {user_name} đang chi vượt ngân sách ở: {over_str}.\n")
        prompt += (
            "\nNhiệm vụ của bạn:\n"
            "1. Phân tích xu hướng chi tiêu dựa trên dữ liệu trên.\n"
            "2. Đưa ra lời khuyên cụ thể để tiết kiệm hoặc tối ưu hóa ngân sách.\n"
            "3. Nếu người dùng hỏi về đầu tư, dựa vào số dư (Thu - Chi) để gợi ý.\n"
            "Luôn giữ câu trả lời ngắn gọn, có cấu trúc (dùng bullet points)."
        )
        return prompt
