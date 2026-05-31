# app/core/report_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Wedge, Circle
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
from datetime import datetime
from pathlib import Path

from app.data.models import get_connection
from config import EXPORTS_DIR


# ── Màu sắc thương hiệu ───────────────────────────────────────────────────────
C_BLUE      = colors.HexColor("#378ADD")
C_GREEN     = colors.HexColor("#1D9E75")
C_RED       = colors.HexColor("#E24B4A")
C_AMBER     = colors.HexColor("#BA7517")
C_PURPLE    = colors.HexColor("#7F77DD")
C_GRAY      = colors.HexColor("#888780")
C_LIGHT     = colors.HexColor("#F5F5F5")
C_DARK      = colors.HexColor("#222222")
C_MUTED     = colors.HexColor("#888888")
C_BORDER    = colors.HexColor("#E0E0E0")

CAT_COLORS = [
    colors.HexColor("#E24B4A"),
    colors.HexColor("#378ADD"),
    colors.HexColor("#1D9E75"),
    colors.HexColor("#BA7517"),
    colors.HexColor("#7F77DD"),
    colors.HexColor("#D4537E"),
    colors.HexColor("#888780"),
]


class ReportGenerator:

    def __init__(self):
        self.page_width, self.page_height = A4
        self.margin = 2 * cm

    def generate_monthly_report(self, month: str, output_path: str | None = None) -> str:
        """
        Tạo báo cáo PDF tháng.
        month: định dạng 'YYYY-MM'
        Trả về đường dẫn file PDF đã tạo.
        """
        if output_path is None:
            filename = f"bao_cao_{month}.pdf"
            output_path = str(EXPORTS_DIR / filename)

        data = self._collect_data(month)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
            title=f"Báo cáo tài chính {month}",
            author="Finance AI",
        )

        story = []
        story += self._build_header(month, data)
        story += self._build_summary_cards(data)
        story.append(Spacer(1, 0.4 * cm))
        story += self._build_category_section(data)
        story.append(Spacer(1, 0.4 * cm))
        story += self._build_transaction_table(data)
        story.append(Spacer(1, 0.4 * cm))
        story += self._build_forecast_section(data, month)
        story += self._build_footer()

        doc.build(story)
        return output_path

    # ── Thu thập dữ liệu ─────────────────────────────────────────────────────
    def _collect_data(self, month: str) -> dict:
        conn = get_connection()

        summary = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as expense,
                COUNT(*) as count
            FROM transactions WHERE strftime('%Y-%m', date)=?
        """, (month,)).fetchone()

        cat_expense = conn.execute("""
            SELECT c.name, c.color, SUM(t.amount) as total
            FROM transactions t JOIN categories c ON t.category_id=c.id
            WHERE t.type='expense' AND strftime('%Y-%m',t.date)=?
            GROUP BY c.id ORDER BY total DESC
        """, (month,)).fetchall()

        cat_income = conn.execute("""
            SELECT c.name, SUM(t.amount) as total
            FROM transactions t JOIN categories c ON t.category_id=c.id
            WHERE t.type='income' AND strftime('%Y-%m',t.date)=?
            GROUP BY c.id ORDER BY total DESC
        """, (month,)).fetchall()

        transactions = conn.execute("""
            SELECT t.date, t.description, t.amount, t.type,
                   t.is_anomaly, c.name as cat_name, a.name as acc_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id=c.id
            LEFT JOIN accounts   a ON t.account_id=a.id
            WHERE strftime('%Y-%m', t.date)=?
            ORDER BY t.date DESC
        """, (month,)).fetchall()

        anomalies = [t for t in transactions if t["is_anomaly"]]

        balance = conn.execute(
            "SELECT COALESCE(SUM(balance),0) as b FROM accounts"
        ).fetchone()

        forecast = conn.execute("""
            SELECT c.name, p.predicted_amount, p.confidence
            FROM ai_predictions p JOIN categories c ON p.category_id=c.id
            WHERE p.month=?
            ORDER BY p.predicted_amount DESC LIMIT 5
        """, (month,)).fetchall()

        history = conn.execute("""
            SELECT strftime('%Y-%m', date) as month,
                   SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) as income,
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
            FROM transactions
            GROUP BY month ORDER BY month DESC LIMIT 6
        """).fetchall()

        conn.close()
        return {
            "summary":     dict(summary),
            "cat_expense": [dict(r) for r in cat_expense],
            "cat_income":  [dict(r) for r in cat_income],
            "transactions":[dict(r) for r in transactions],
            "anomalies":   [dict(r) for r in anomalies],
            "balance":     balance["b"],
            "forecast":    [dict(r) for r in forecast],
            "history":     [dict(r) for r in reversed(history)],
        }

    # ── Sections ─────────────────────────────────────────────────────────────
    def _build_header(self, month: str, data: dict) -> list:
        styles = self._styles()
        try:
            dt = datetime.strptime(month, "%Y-%m")
            month_label = f"Tháng {dt.month}/{dt.year}"
        except Exception:
            month_label = month

        elements = []

        header_data = [[
            Paragraph(f"<b>BÁO CÁO TÀI CHÍNH</b>", styles["title"]),
            Paragraph(f"{month_label}", styles["title_right"]),
        ]]
        header_table = Table(header_data, colWidths=[10 * cm, 7 * cm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, -1), C_BLUE),
            ("TEXTCOLOR",   (0, 0), (-1, -1), colors.white),
            ("PADDING",     (0, 0), (-1, -1), 14),
            ("ROUNDEDCORNERS", [6]),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.3 * cm))

        generated = datetime.now().strftime("%d/%m/%Y %H:%M")
        sub = Paragraph(
            f'<font color="#888888" size="9">Tạo lúc {generated} · Finance AI v1.0 · '
            f'Tổng {data["summary"]["count"]} giao dịch</font>',
            styles["normal"]
        )
        elements.append(sub)
        elements.append(Spacer(1, 0.5 * cm))
        return elements

    def _build_summary_cards(self, data: dict) -> list:
        s = data["summary"]
        income  = s["income"]
        expense = s["expense"]
        saving  = income - expense
        balance = data["balance"]

        styles = self._styles()
        card_data = [
            [
                self._metric_cell("THU NHẬP",    income,  C_GREEN, styles),
                self._metric_cell("CHI TIÊU",    expense, C_RED,   styles),
                self._metric_cell("TIẾT KIỆM",   saving,
                                  C_BLUE if saving >= 0 else C_RED, styles),
                self._metric_cell("SỐ DƯ TỔNG",  balance, C_AMBER, styles),
            ]
        ]
        card_table = Table(card_data, colWidths=[4.25 * cm] * 4,
                           rowHeights=[2.5 * cm])
        card_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (0, 0), colors.HexColor("#E8F5EE")),
            ("BACKGROUND",  (1, 0), (1, 0), colors.HexColor("#FEF0F0")),
            ("BACKGROUND",  (2, 0), (2, 0), colors.HexColor("#EAF3FB")),
            ("BACKGROUND",  (3, 0), (3, 0), colors.HexColor("#FEF3E0")),
            ("BOX",    (0, 0), (0, 0), 0.5, C_GREEN),
            ("BOX",    (1, 0), (1, 0), 0.5, C_RED),
            ("BOX",    (2, 0), (2, 0), 0.5, C_BLUE),
            ("BOX",    (3, 0), (3, 0), 0.5, C_AMBER),
            ("LEFTPADDING",  (0, 0), (-1, -1), 10),
            ("TOPPADDING",   (0, 0), (-1, -1), 10),
            ("COLPADDING",   (0, 0), (-1, -1), 6),
            ("ROUNDEDCORNERS", [4]),
        ]))
        return [card_table]

    def _metric_cell(self, label: str, value: float,
                     color, styles: dict) -> list:
        lbl = Paragraph(f'<font size="8" color="#888888"><b>{label}</b></font>',
                        styles["normal"])
        try:
            hex_c = "#{:02X}{:02X}{:02X}".format(
                int(color.red * 255),
                int(color.green * 255),
                int(color.blue * 255),
            )
        except Exception:
            hex_c = "#333333"
        val = Paragraph(
            f'<font size="14" color="{hex_c}"><b>{self._fmt(value)}</b></font>',
            styles["normal"]
        )
        return [lbl, val]

    def _build_category_section(self, data: dict) -> list:
        styles = self._styles()
        elements = [
            Paragraph("<b>CHI TIÊU THEO DANH MỤC</b>", styles["section"]),
            Spacer(1, 0.2 * cm),
        ]

        cats = data["cat_expense"]
        if not cats:
            elements.append(Paragraph("Chưa có dữ liệu chi tiêu.", styles["normal"]))
            return elements

        total_expense = sum(c["total"] for c in cats)

        rows = [
            [
                Paragraph("<b>Danh mục</b>", styles["th"]),
                Paragraph("<b>Số tiền</b>", styles["th_right"]),
                Paragraph("<b>Tỷ lệ</b>", styles["th_right"]),
                Paragraph("<b>Biểu đồ</b>", styles["th"]),
            ]
        ]
        for i, cat in enumerate(cats[:8]):
            pct = (cat["total"] / total_expense * 100) if total_expense > 0 else 0
            bar_color = CAT_COLORS[i % len(CAT_COLORS)]
            bar_w = max(4, int(pct * 1.2))
            d = Drawing(120, 10)
            d.add(Rect(0, 2, 120, 6, fillColor=colors.HexColor("#F0F0F0"),
                       strokeColor=None))
            d.add(Rect(0, 2, bar_w, 6, fillColor=bar_color, strokeColor=None))

            rows.append([
                Paragraph(cat["name"], styles["td"]),
                Paragraph(self._fmt(cat["total"]), styles["td_right"]),
                Paragraph(f"{pct:.1f}%", styles["td_right"]),
                d,
            ])

        rows.append([
            Paragraph("<b>Tổng chi tiêu</b>", styles["td_bold"]),
            Paragraph(f"<b>{self._fmt(total_expense)}</b>", styles["td_right_bold"]),
            Paragraph("<b>100%</b>", styles["td_right_bold"]),
            "",
        ])

        t = Table(rows, colWidths=[5 * cm, 3.5 * cm, 2 * cm, 6.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  C_LIGHT),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  C_MUTED),
            ("LINEBELOW",    (0, 0), (-1, 0),  0.5, C_BORDER),
            ("LINEBELOW",    (0, 1), (-1, -2), 0.3, C_BORDER),
            ("BACKGROUND",   (0, -1), (-1, -1), C_LIGHT),
            ("LINEABOVE",    (0, -1), (-1, -1), 0.5, C_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2),
             [colors.white, colors.HexColor("#FAFAFA")]),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(t)
        return elements

    def _build_transaction_table(self, data: dict) -> list:
        styles = self._styles()
        txs = data["transactions"]
        elements = [
            Spacer(1, 0.2 * cm),
            Paragraph(
                f"<b>DANH SÁCH GIAO DỊCH</b>"
                f' <font size="9" color="#888888">({len(txs)} giao dịch)</font>',
                styles["section"]
            ),
            Spacer(1, 0.2 * cm),
        ]

        if not txs:
            elements.append(Paragraph("Chưa có giao dịch.", styles["normal"]))
            return elements

        rows = [[
            Paragraph("<b>Ngày</b>",      styles["th"]),
            Paragraph("<b>Mô tả</b>",     styles["th"]),
            Paragraph("<b>Danh mục</b>",  styles["th"]),
            Paragraph("<b>Tài khoản</b>", styles["th"]),
            Paragraph("<b>Số tiền</b>",   styles["th_right"]),
        ]]

        for tx in txs[:50]:
            try:
                d = datetime.strptime(tx["date"], "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                d = tx["date"]

            sign  = "+" if tx["type"] == "income" else "-"
            color = "#1D9E75" if tx["type"] == "income" else "#E24B4A"
            desc  = tx.get("description") or ""
            if tx.get("is_anomaly"):
                desc += " ⚠"

            rows.append([
                Paragraph(d, styles["td_small"]),
                Paragraph(desc[:35], styles["td_small"]),
                Paragraph(tx.get("cat_name") or "—", styles["td_small"]),
                Paragraph(tx.get("acc_name") or "—", styles["td_small"]),
                Paragraph(
                    f'<font color="{color}"><b>{sign}{self._fmt(tx["amount"])}</b></font>',
                    styles["td_right_small"]
                ),
            ])

        if len(txs) > 50:
            rows.append([
                Paragraph(
                    f'<font color="#888888"><i>... và {len(txs)-50} giao dịch khác</i></font>',
                    styles["td_small"]
                ),
                "", "", "", ""
            ])

        t = Table(rows, colWidths=[1.5 * cm, 5.5 * cm, 3 * cm, 2.5 * cm, 4.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  C_LIGHT),
            ("LINEBELOW",    (0, 0), (-1, 0),  0.5, C_BORDER),
            ("LINEBELOW",    (0, 1), (-1, -1), 0.2, C_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#FAFAFA")]),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("SPAN",         (0, -1), (-1, -1)) if len(txs) > 50 else ("NOP", (0,0),(0,0), None),
        ]))
        elements.append(t)

        anomalies = data["anomalies"]
        if anomalies:
            elements.append(Spacer(1, 0.3 * cm))
            elements.append(
                Paragraph(
                    f'<b>⚠ CẢNH BÁO: {len(anomalies)} giao dịch bất thường</b>',
                    styles["warning"]
                )
            )
            for tx in anomalies[:5]:
                try:
                    d = datetime.strptime(tx["date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    d = tx["date"]
                elements.append(Paragraph(
                    f'• {d} — {tx.get("description","")} — '
                    f'<font color="#E24B4A"><b>{self._fmt(tx["amount"])}</b></font>',
                    styles["normal"]
                ))

        return elements

    def _build_forecast_section(self, data: dict, month: str) -> list:
        styles = self._styles()
        forecast = data["forecast"]
        elements = [
            Spacer(1, 0.2 * cm),
            Paragraph("<b>DỰ BÁO THÁNG TỚI (AI)</b>", styles["section"]),
            Spacer(1, 0.2 * cm),
        ]

        if not forecast:
            elements.append(
                Paragraph(
                    'Chưa có dữ liệu dự báo. Vào tab "Dự báo" và nhấn "Chạy dự báo AI".',
                    styles["normal"]
                )
            )
            return elements

        total_fc = sum(r["predicted_amount"] or 0 for r in forecast)
        elements.append(
            Paragraph(
                f'Tổng chi tiêu dự báo: '
                f'<font color="#378ADD"><b>{self._fmt(total_fc)}</b></font>',
                styles["normal"]
            )
        )
        elements.append(Spacer(1, 0.2 * cm))

        rows = [[
            Paragraph("<b>Danh mục</b>",    styles["th"]),
            Paragraph("<b>Dự báo</b>",      styles["th_right"]),
            Paragraph("<b>Độ tin cậy</b>",  styles["th_right"]),
        ]]
        for r in forecast:
            conf = r.get("confidence") or 0
            rows.append([
                Paragraph(r["name"], styles["td"]),
                Paragraph(self._fmt(r["predicted_amount"] or 0), styles["td_right"]),
                Paragraph(f"{conf*100:.0f}%", styles["td_right"]),
            ])

        t = Table(rows, colWidths=[8 * cm, 5 * cm, 4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), C_LIGHT),
            ("LINEBELOW",   (0, 0), (-1, 0), 0.5, C_BORDER),
            ("LINEBELOW",   (0, 1), (-1, -1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#FAFAFA")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0,0), (-1, -1), 5),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(t)
        return elements

    def _build_footer(self) -> list:
        styles = self._styles()
        return [
            Spacer(1, 0.5 * cm),
            HRFlowable(width="100%", thickness=0.5, color=C_BORDER),
            Spacer(1, 0.2 * cm),
            Paragraph(
                f'<font size="8" color="#AAAAAA">'
                f'Finance AI · Báo cáo được tạo tự động · '
                f'{datetime.now().strftime("%d/%m/%Y %H:%M")}'
                f'</font>',
                styles["center"]
            ),
        ]

    # ── Styles ────────────────────────────────────────────────────────────────
    def _styles(self) -> dict:
        """
        FIX: Each ParagraphStyle is created with the base font via `fontName`
        positional kwarg ONE time only.  Previously `fontName` appeared both as
        an explicit kwarg and as a duplicate positional arg inside some styles,
        causing:
            TypeError: ParagraphStyle() got multiple values for keyword argument 'fontName'

        Resolution: pass font name exclusively through the `fontName` kwarg and
        never via the positional `name` + a separate `fontName=` duplication.
        """
        # Base fonts — referenced by name only in each style definition below.
        FONT_NORMAL = "Helvetica"
        FONT_BOLD   = "Helvetica-Bold"

        def ps(name: str, font: str = FONT_NORMAL, **kwargs) -> ParagraphStyle:
            """Helper that creates a ParagraphStyle without duplicating fontName."""
            return ParagraphStyle(name, fontName=font, **kwargs)

        return {
            # Title styles — bold font passed via `font` arg (becomes fontName once)
            "title":       ps("title",       FONT_BOLD,
                              fontSize=16, textColor=colors.white,
                              leading=20),
            "title_right": ps("title_right", FONT_BOLD,
                              fontSize=14, textColor=colors.white,
                              alignment=TA_RIGHT, leading=20),

            # Section / body styles
            "section":     ps("section",     FONT_BOLD,
                              fontSize=11, textColor=C_DARK,
                              spaceBefore=4, leading=16, borderPad=4),
            "normal":      ps("normal",      FONT_NORMAL,
                              fontSize=9, textColor=C_DARK, leading=14),
            "center":      ps("center",      FONT_NORMAL,
                              fontSize=9, textColor=C_MUTED,
                              alignment=TA_CENTER, leading=14),
            "warning":     ps("warning",     FONT_BOLD,
                              fontSize=10, textColor=C_RED, leading=14),

            # Table header / data styles
            "th":          ps("th",          FONT_BOLD,
                              fontSize=8, textColor=C_MUTED, leading=12),
            "th_right":    ps("th_right",    FONT_BOLD,
                              fontSize=8, textColor=C_MUTED,
                              alignment=TA_RIGHT, leading=12),
            "td":          ps("td",          FONT_NORMAL,
                              fontSize=9, textColor=C_DARK, leading=13),
            "td_small":    ps("td_small",    FONT_NORMAL,
                              fontSize=8, textColor=C_DARK, leading=11),
            "td_bold":     ps("td_bold",     FONT_BOLD,
                              fontSize=9, textColor=C_DARK, leading=13),
            "td_right":    ps("td_right",    FONT_NORMAL,
                              fontSize=9, textColor=C_DARK,
                              alignment=TA_RIGHT, leading=13),
            "td_right_small": ps("td_right_small", FONT_NORMAL,
                                  fontSize=8, textColor=C_DARK,
                                  alignment=TA_RIGHT, leading=11),
            "td_right_bold":  ps("td_right_bold",  FONT_BOLD,
                                  fontSize=9, textColor=C_DARK,
                                  alignment=TA_RIGHT, leading=13),
        }

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{value:,.0f} d".replace(",", ".")