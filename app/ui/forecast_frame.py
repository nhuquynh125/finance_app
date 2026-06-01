from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QScrollArea,
    QGridLayout, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app.ai.forecaster import SpendingForecaster
from app.ai.anomaly_detector import AnomalyDetector
from app.data.models import get_connection
from datetime import datetime


class ForecastWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)
    def run(self):
        try:
            self.finished.emit(SpendingForecaster().forecast_all_categories())
        except Exception as e:
            self.error.emit(str(e))


class AnomalyWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)
    def __init__(self, month=None):
        super().__init__()
        self.month = month
    def run(self):
        try:
            self.finished.emit(AnomalyDetector().detect_and_mark(self.month))
        except Exception as e:
            self.error.emit(str(e))


class ForecastCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.fig = Figure(figsize=(6, 2.8), facecolor="none")
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def plot(self, historical, forecast):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#ffffff")
        self.fig.subplots_adjust(left=0.12, right=0.97, top=0.92, bottom=0.18)

        hist_months = [d["month"] for d in historical]
        hist_vals   = [d["total"] / 1e6 for d in historical]
        fc_months   = [d["month"] for d in forecast]
        fc_vals     = [d["predicted"] / 1e6 for d in forecast]
        fc_lower    = [d.get("lower", d["predicted"]) / 1e6 for d in forecast]
        fc_upper    = [d.get("upper", d["predicted"]) / 1e6 for d in forecast]

        n_hist = len(hist_months)
        n_all  = n_hist + len(fc_months)
        x_hist = list(range(n_hist))
        x_fc   = list(range(n_hist - 1, n_all))

        if hist_vals:
            ax.plot(x_hist, hist_vals, color="#378ADD", linewidth=2.2,
                    marker="o", markersize=5, markerfacecolor="#fff",
                    markeredgecolor="#378ADD", markeredgewidth=1.8, label="Thực tế", zorder=3)

        if fc_vals:
            y_band = ([hist_vals[-1]] if hist_vals else []) + fc_lower
            y_top  = ([hist_vals[-1]] if hist_vals else []) + fc_upper
            ax.fill_between(x_fc, y_band, y_top, color="#E6F1FB", alpha=0.7, zorder=1)
            y_line = ([hist_vals[-1]] if hist_vals else []) + fc_vals
            ax.plot(x_fc, y_line, color="#378ADD", linewidth=2, linestyle="--",
                    marker="o", markersize=6, markerfacecolor="#378ADD",
                    markeredgecolor="#fff", markeredgewidth=1.5, label="Dự báo", zorder=3)

        all_months = hist_months + fc_months
        ax.set_xticks(range(n_all))
        labels = []
        for i, m in enumerate(all_months):
            try:
                dt = datetime.strptime(m, "%Y-%m")
                lbl = f"T{dt.month}"
            except Exception:
                lbl = m
            labels.append(lbl)
        ax.set_xticklabels(labels, fontsize=14)
        for i, tick in enumerate(ax.get_xticklabels()):
            if i >= n_hist:
                tick.set_color("#378ADD")
                tick.set_fontweight("bold")

        ax.set_ylabel("Triệu đồng", fontsize=14)
        ax.yaxis.grid(True, color="#eeeeee", linewidth=0.5)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.legend(fontsize=14, framealpha=0, loc="upper left")
        self.draw()


class ForecastFrame(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window     = main_window
        self.forecaster      = SpendingForecaster()
        self.detector        = AnomalyDetector()
        self._forecast_data  = []
        self._current_month  = datetime.now().strftime("%Y-%m")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f5f5f5; }")
        content = QWidget()
        content.setStyleSheet("background:#f5f5f5;")
        self.cl = QVBoxLayout(content)
        self.cl.setContentsMargins(16, 14, 16, 16)
        self.cl.setSpacing(12)

        self._build_cards()
        self._build_chart_row()
        self._build_anomaly_panel()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)
        title = QLabel("Dự báo chi tiêu")
        title.setFont(QFont("Segoe UI", 21, QFont.Weight.Bold))
        title.setStyleSheet("color: #222222;")
        layout.addWidget(title)
        layout.addStretch()

        self.cb_month = QComboBox()
        self.cb_month.setFixedWidth(140)
        self.cb_month.setStyleSheet(self._combo_style())
        self._populate_months()
        self.cb_month.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.cb_month)

        self.btn_forecast = QPushButton("Chạy dự báo AI")
        self.btn_forecast.setStyleSheet(self._btn_primary())
        self.btn_forecast.clicked.connect(self._run_forecast)
        layout.addWidget(self.btn_forecast)

        self.btn_anomaly = QPushButton("Phát hiện bất thường")
        self.btn_anomaly.setStyleSheet(self._btn_normal())
        self.btn_anomaly.clicked.connect(self._run_anomaly)
        layout.addWidget(self.btn_anomaly)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedSize(100, 4)
        self.progress.hide()
        self.progress.setStyleSheet("QProgressBar { border:none; border-radius:2px; background:#e8e8e8; } QProgressBar::chunk { background:#378ADD; border-radius:2px; }")
        layout.addWidget(self.progress)
        return bar

    def _build_cards(self):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(10)
        self.card_labels = {}
        defs = [
            ("Dự báo tháng tới",    "--", "#378ADD"),
            ("Tháng này (thực tế)", "--", "#333"),
            ("Độ tin cậy",          "--", "#1D9E75"),
            ("Bất thường",          "--", "#E24B4A"),
        ]
        for i, (label, val, color) in enumerate(defs):
            card = QFrame()
            card.setStyleSheet("QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
            lbl.setStyleSheet("color:#555555; border:none;")
            cl.addWidget(lbl)
            val_lbl = QLabel(val)
            val_lbl.setFont(QFont("Segoe UI", 23, QFont.Weight.Bold))
            val_lbl.setStyleSheet(f"color:{color}; border:none;")
            cl.addWidget(val_lbl)
            g.addWidget(card, 0, i)
            self.card_labels[label] = val_lbl
        self.cl.addWidget(w)

    def _build_chart_row(self):
        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(12)

        # Chart
        self.chart_panel = QFrame()
        self.chart_panel.setStyleSheet("QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        cp_l = QVBoxLayout(self.chart_panel)
        cp_l.setContentsMargins(14, 12, 14, 12)
        ch = QHBoxLayout()
        t = QLabel("Lịch sử & dự báo chi tiêu")
        t.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t.setStyleSheet("color:#222222; border:none;")
        ch.addWidget(t)
        ch.addStretch()
        self.method_badge = QLabel("Chưa chạy")
        self.method_badge.setStyleSheet("QLabel { background:#EAF3DE; color:#3B6D11; border:none; border-radius:10px; padding:2px 10px; font-size:16px; font-weight:500; }")
        ch.addWidget(self.method_badge)
        cp_l.addLayout(ch)
        self.chart_placeholder = QLabel("Nhấn 'Chạy dự báo AI' để xem biểu đồ")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_placeholder.setFixedHeight(220)
        self.chart_placeholder.setStyleSheet("color:#bbb; font-size:18px; border:none;")
        cp_l.addWidget(self.chart_placeholder)
        self.chart_canvas = ForecastCanvas()
        self.chart_canvas.setFixedHeight(220)
        self.chart_canvas.hide()
        cp_l.addWidget(self.chart_canvas)
        row_l.addWidget(self.chart_panel, stretch=2)

        # Category bars
        self.cat_panel = QFrame()
        self.cat_panel.setStyleSheet("QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        self.cat_layout = QVBoxLayout(self.cat_panel)
        self.cat_layout.setContentsMargins(14, 12, 14, 12)
        self.cat_layout.setSpacing(4)
        t2 = QLabel("Dự báo theo danh mục")
        t2.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t2.setStyleSheet("color:#222222; border:none;")
        self.cat_layout.addWidget(t2)
        self.cat_placeholder = QLabel("Chưa có dữ liệu")
        self.cat_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cat_placeholder.setStyleSheet("color:#bbb; font-size:17px; border:none;")
        self.cat_layout.addWidget(self.cat_placeholder)
        self.cat_layout.addStretch()
        row_l.addWidget(self.cat_panel, stretch=1)
        self.cl.addWidget(row_w)

    def _build_anomaly_panel(self):
        self.anom_panel = QFrame()
        self.anom_panel.setStyleSheet("QFrame { background:#fff; border:1px solid #e8e8e8; border-radius:10px; }")
        self.anom_layout = QVBoxLayout(self.anom_panel)
        self.anom_layout.setContentsMargins(14, 12, 14, 12)
        self.anom_layout.setSpacing(4)
        h = QHBoxLayout()
        t = QLabel("Giao dịch bất thường phát hiện bởi AI")
        t.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t.setStyleSheet("color:#222222; border:none;")
        h.addWidget(t)
        h.addStretch()
        badge = QLabel("Isolation Forest")
        badge.setStyleSheet("QLabel { background:#f0f0f0; color:#888; border:none; border-radius:10px; padding:2px 10px; font-size:16px; }")
        h.addWidget(badge)
        self.anom_layout.addLayout(h)
        self.anom_placeholder = QLabel("Nhấn 'Phát hiện bất thường' để phân tích")
        self.anom_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anom_placeholder.setFixedHeight(60)
        self.anom_placeholder.setStyleSheet("color:#bbb; font-size:17px; border:none;")
        self.anom_layout.addWidget(self.anom_placeholder)
        self.cl.addWidget(self.anom_panel)

    def refresh(self):
        month = self.cb_month.currentData()
        self._current_month = month
        from app.core.transaction_manager import TransactionManager
        summary = TransactionManager().get_monthly_summary(month)
        expense = summary.get("total_expense") or 0
        self.card_labels["Tháng này (thực tế)"].setText(self._fmt(expense))
        anomalies = self.detector.get_anomalies(month)
        self.card_labels["Bất thường"].setText(str(len(anomalies)))
        if anomalies:
            self._render_anomalies(anomalies)

    def _run_forecast(self):
        self.btn_forecast.setEnabled(False)
        self.progress.show()
        self.fc_worker = ForecastWorker()
        self.fc_worker.finished.connect(self._on_forecast_done)
        self.fc_worker.error.connect(self._on_error)
        self.fc_worker.start()

    def _on_forecast_done(self, results):
        self._forecast_data = results
        self.progress.hide()
        self.btn_forecast.setEnabled(True)
        total = sum(r.get("predicted", 0) for r in results)
        avg_c = sum(r.get("confidence", 0) for r in results) / len(results) if results else 0
        method = results[0].get("method", "") if results else ""
        self.card_labels["Dự báo tháng tới"].setText(self._fmt(total))
        self.card_labels["Độ tin cậy"].setText(f"{avg_c*100:.0f}%")
        m_text = {"prophet": "Prophet", "moving_average": "Trung bình động"}.get(method, method)
        self.method_badge.setText(m_text or "OK")
        self._update_chart()
        self._render_cat_bars(results)

    def _run_anomaly(self):
        self.btn_anomaly.setEnabled(False)
        self.progress.show()
        self.anom_worker = AnomalyWorker(month=self._current_month)
        self.anom_worker.finished.connect(self._on_anomaly_done)
        self.anom_worker.error.connect(self._on_error)
        self.anom_worker.start()

    def _on_anomaly_done(self, results):
        self.progress.hide()
        self.btn_anomaly.setEnabled(True)
        anomalies_db = self.detector.get_anomalies(self._current_month)
        self.card_labels["Bất thường"].setText(str(len(anomalies_db)))
        self._render_anomalies(anomalies_db)

    def _on_error(self, msg):
        self.progress.hide()
        self.btn_forecast.setEnabled(True)
        self.btn_anomaly.setEnabled(True)
        print(f"[ForecastFrame Error] {msg}")

    def _update_chart(self):
        if not self._forecast_data:
            return
        chart_data = self.forecaster.get_forecast_chart_data(months_back=6)
        historical = chart_data.get("historical", [])
        forecast   = chart_data.get("forecast", [])
        if not historical and not forecast:
            return
        self.chart_placeholder.hide()
        self.chart_canvas.show()
        self.chart_canvas.plot(historical, forecast)

    def _render_cat_bars(self, results):
        while self.cat_layout.count() > 1:
            item = self.cat_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        if not results:
            self.cat_layout.addWidget(self.cat_placeholder)
            self.cat_layout.addStretch()
            return
        max_val = max((r.get("predicted", 0) for r in results), default=1) or 1
        colors = self._get_cat_colors()
        sorted_r = sorted(results, key=lambda x: x.get("predicted", 0), reverse=True)[:7]
        for r in sorted_r:
            name  = r.get("category_name", "")
            val   = r.get("predicted", 0)
            color = colors.get(name, "#888888")
            ratio = val / max_val

            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(8)

            n_lbl = QLabel(name[:10])
            n_lbl.setFixedWidth(72)
            n_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
            n_lbl.setStyleSheet("color:#444444; border:none;")
            rl.addWidget(n_lbl)

            track = QFrame()
            track.setFixedHeight(6)
            track.setStyleSheet("background:#f0f0f0; border-radius:3px; border:none;")
            track.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            fill = QFrame(track)
            fill.setFixedHeight(6)
            fill.setStyleSheet(f"background:{color}; border-radius:3px; border:none;")

            def set_w(f=fill, t=track, ratio=ratio):
                f.setFixedWidth(max(4, int(t.width() * ratio)))
            QTimer.singleShot(120, set_w)
            rl.addWidget(track)

            v_lbl = QLabel(self._fmt_short(val))
            v_lbl.setFixedWidth(62)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            v_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            v_lbl.setStyleSheet("color:#111111; border:none;")
            rl.addWidget(v_lbl)
            self.cat_layout.addWidget(row_w)

            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet("background:#f0f0f0; border:none; max-height:1px;")
            self.cat_layout.addWidget(div)
        self.cat_layout.addStretch()

    def _render_anomalies(self, anomalies):
        while self.anom_layout.count() > 1:
            item = self.anom_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        if not anomalies:
            ok_lbl = QLabel("Không phát hiện giao dịch bất thường")
            ok_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ok_lbl.setStyleSheet("color:#1D9E75; font-size:17px; padding:16px; border:none;")
            self.anom_layout.addWidget(ok_lbl)
            return
        for tx in anomalies[:8]:
            risk = tx.get("risk_score", 75)
            if not isinstance(risk, int):
                risk = 75
            if risk >= 85:   bg, tc = "#FCEBEB", "#A32D2D"
            elif risk >= 60: bg, tc = "#FAEEDA", "#633806"
            else:            bg, tc = "#F1EFE8", "#5F5E5A"

            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 6, 0, 6)
            rl.setSpacing(12)

            score_lbl = QLabel(str(risk))
            score_lbl.setFixedSize(38, 38)
            score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            score_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            score_lbl.setStyleSheet(f"background:{bg}; color:{tc}; border-radius:8px; border:none;")
            rl.addWidget(score_lbl)

            desc_w = QWidget()
            desc_w.setStyleSheet("background:transparent;")
            dl = QVBoxLayout(desc_w)
            dl.setContentsMargins(0, 0, 0, 0)
            dl.setSpacing(1)

            name_str = tx.get("description") or "Không có mô tả"
            cat = tx.get("category_name") or ""
            if cat:
                name_str += f"  —  {cat}"
            n = QLabel(name_str)
            n.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
            n.setStyleSheet("color:#222; border:none;")
            dl.addWidget(n)

            reasons = tx.get("reasons", [])
            meta_parts = [tx.get("date", "")]
            if reasons:
                meta_parts.append(reasons[0])
            meta = QLabel("  ·  ".join(filter(None, meta_parts)))
            meta.setFont(QFont("Segoe UI", 15))
            meta.setStyleSheet("color:#aaa; border:none;")
            dl.addWidget(meta)
            rl.addWidget(desc_w)
            rl.addStretch()

            amt = QLabel(f"-{self._fmt(tx.get('amount', 0))}")
            amt.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
            amt.setStyleSheet("color:#E24B4A; border:none;")
            rl.addWidget(amt)
            self.anom_layout.addWidget(row)

            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet("background:#f5f5f5; border:none; max-height:1px;")
            self.anom_layout.addWidget(div)

    def _populate_months(self):
        now = datetime.now()
        for i in range(11, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12; y -= 1
            self.cb_month.addItem(f"Tháng {m}/{y}", userData=f"{y}-{m:02d}")
        self.cb_month.setCurrentIndex(self.cb_month.count() - 1)

    def _get_cat_colors(self):
        conn = get_connection()
        rows = conn.execute("SELECT name, color FROM categories").fetchall()
        conn.close()
        return {r["name"]: r["color"] for r in rows}

    @staticmethod
    def _fmt(v):        return f"{v:,.0f} đ".replace(",", ".")
    @staticmethod
    def _fmt_short(v):
        if v >= 1e6: return f"{v/1e6:.1f}M đ"
        if v >= 1e3: return f"{v/1e3:.0f}K đ"
        return f"{v:.0f} đ"
    @staticmethod
    def _btn_primary(): return "QPushButton { background:#E6F1FB; color:#0C447C; border:1px solid #B5D4F4; border-radius:6px; padding:6px 14px; font-size:17px; font-weight:500; } QPushButton:hover { background:#B5D4F4; } QPushButton:disabled { background:#eee; color:#bbb; border-color:#eee; }"
    @staticmethod
    def _btn_normal():  return "QPushButton { background:#fff; color:#555; border:1px solid #ddd; border-radius:6px; padding:6px 12px; font-size:17px; } QPushButton:hover { background:#f5f5f5; } QPushButton:disabled { color:#bbb; }"
    @staticmethod
    def _combo_style(): return "QComboBox { border:1px solid #ddd; border-radius:5px; padding:4px 8px; font-size:17px; background:#fff; color:#333; }"
