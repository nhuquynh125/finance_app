# app/core/event_bus.py
"""
Event bus nội bộ dùng PyQt6 signal/slot.
Thay thế chuỗi main_window.refresh_all() gọi tất cả frame cùng lúc.

Lợi ích:
  - Frame không cần biết về nhau
  - Thêm frame mới không sửa MainWindow
  - Có thể debounce, filter event theo loại

Cách dùng (emit):
    from app.core.event_bus import bus
    bus.transaction_added.emit()
    bus.budget_updated.emit("2025-01")

Cách dùng (subscribe):
    from app.core.event_bus import bus
    bus.transaction_added.connect(self.refresh)
    bus.theme_changed.connect(self._apply_theme)
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class _EventBus(QObject):
    """Singleton signal hub — chỉ có một instance toàn app."""

    # ── Transaction events ────────────────────────────────────────────────────
    transaction_added   = pyqtSignal()
    transaction_updated = pyqtSignal(int)      # tx_id
    transaction_deleted = pyqtSignal(int)      # tx_id
    transactions_imported = pyqtSignal(int)    # count

    # ── Budget events ─────────────────────────────────────────────────────────
    budget_updated = pyqtSignal(str)           # month "YYYY-MM"
    budget_alert   = pyqtSignal(str, str, int) # cat_name, month, pct

    # ── AI events ─────────────────────────────────────────────────────────────
    ai_classification_done = pyqtSignal()
    ai_forecast_done       = pyqtSignal(list)  # results
    ai_anomaly_done        = pyqtSignal(list)  # anomalies

    # ── Account/balance events ────────────────────────────────────────────────
    balance_changed = pyqtSignal()

    # ── Settings events ───────────────────────────────────────────────────────
    settings_saved  = pyqtSignal(dict)         # new settings dict
    theme_changed   = pyqtSignal(str)          # "light" | "dark" | "auto"
    currency_changed = pyqtSignal(str)         # "VND" | "USD" | ...

    # ── Navigation events ─────────────────────────────────────────────────────
    navigate_to = pyqtSignal(str)              # page name

    # ── User / family events ──────────────────────────────────────────────────
    user_switched  = pyqtSignal(dict)          # user dict
    profile_updated = pyqtSignal(str)          # username

    # ── Notification events ───────────────────────────────────────────────────
    notify_info    = pyqtSignal(str, str)      # title, message
    notify_warning = pyqtSignal(str, str)
    notify_success = pyqtSignal(str, str)
    notify_error   = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._debounce_timers: dict[str, QTimer] = {}

    def emit_debounced(self, signal_name: str, delay_ms: int = 300,
                       *args) -> None:
        """
        Phát signal sau delay, bỏ qua các lần gọi trước đó trong cùng window.
        Hữu ích khi nhiều thao tác nhanh liên tiếp (import CSV) chỉ cần
        refresh UI một lần.

        Ví dụ:
            bus.emit_debounced("transaction_added", 500)
        """
        if signal_name in self._debounce_timers:
            self._debounce_timers[signal_name].stop()

        timer = QTimer()
        timer.setSingleShot(True)
        sig = getattr(self, signal_name, None)
        if sig is None:
            return

        if args:
            timer.timeout.connect(lambda: sig.emit(*args))
        else:
            timer.timeout.connect(sig.emit)

        timer.start(delay_ms)
        self._debounce_timers[signal_name] = timer


# Singleton instance — import và dùng trực tiếp
bus = _EventBus()


# ── Helper mixin cho QWidget để tự disconnect khi bị destroy ─────────────────

class BusConnectMixin:
    """
    Mixin cho QWidget. Override _connect_bus() để đăng ký signals.
    Tự disconnect khi widget bị destroy — không còn dangling connections.

    Ví dụ:
        class DashboardFrame(QWidget, BusConnectMixin):
            def __init__(self):
                super().__init__()
                self._connect_bus()

            def _connect_bus(self):
                bus.transaction_added.connect(self.refresh)
                bus.balance_changed.connect(self._update_balance_card)
    """

    def _connect_bus(self) -> None:
        raise NotImplementedError("Override _connect_bus() để đăng ký signals")

    def _disconnect_bus(self) -> None:
        """Gọi trong closeEvent hoặc kết nối với destroyed signal."""
        pass   # override nếu cần cleanup thủ công
