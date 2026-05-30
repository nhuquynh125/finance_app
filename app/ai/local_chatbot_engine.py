# app/ai/local_chatbot_engine.py
"""
Chatbot tài chính thuần giải thuật — không cần API, không cần internet.

Kiến trúc:
  1. NLP Parser   — tách từ khoá, nhận dạng ý định (intent)
  2. Data Fetcher — truy vấn DB lấy dữ liệu thực
  3. Analyzer     — tính toán thống kê, xu hướng, so sánh
  4. Responder    — tạo câu trả lời tự nhiên bằng tiếng Việt
"""

from __future__ import annotations

import re
import math
from datetime import datetime, timedelta
from typing import Optional
from app.data.models import get_connection


# ══════════════════════════════════════════════════════════════
# 1. INTENT RECOGNITION — nhận dạng ý định người dùng
# ══════════════════════════════════════════════════════════════

INTENTS = {
    "greet": [
        r"\bxin chào\b", r"\bchào\b", r"\bhello\b", r"\bhi\b",
        r"\bhey\b", r"\bchao\b", r"\bchào bot\b",
    ],
    "total_expense": [
        r"chi (tiêu|tieu|bao nhiêu|bao nhieu)",
        r"tổng chi", r"tong chi",
        r"đã chi", r"da chi",
        r"tiêu bao nhiêu", r"tieu bao nhieu",
        r"chi phí", r"chi phi",
    ],
    "total_income": [
        r"thu nhập", r"thu nhap",
        r"kiếm được", r"kiem duoc",
        r"lương", r"luong",
        r"thu bao nhiêu", r"thu bao nhieu",
        r"tổng thu", r"tong thu",
    ],
    "saving": [
        r"tiết kiệm", r"tiet kiem",
        r"để dành", r"de danh",
        r"còn lại", r"con lai",
        r"dư", r"\bdu\b",
        r"saving",
    ],
    "balance": [
        r"số dư", r"so du",
        r"tài khoản", r"tai khoan",
        r"còn bao nhiêu tiền", r"con bao nhieu tien",
        r"balance",
    ],
    "top_category": [
        r"danh mục nào nhiều nhất",
        r"chi nhiều nhất", r"chi nhieu nhat",
        r"tốn nhiều", r"ton nhieu",
        r"category nào",
        r"mục nào", r"muc nao",
        r"danh mục tốn", r"danh muc ton",
    ],
    "category_detail": [
        r"ăn uống", r"an uong",
        r"di chuyển", r"di chuyen",
        r"mua sắm", r"mua sam",
        r"giải trí", r"giai tri",
        r"y tế", r"y te",
        r"hóa đơn", r"hoa don",
        r"giáo dục", r"giao duc",
        r"điện", r"nước", r"internet",
    ],
    "trend": [
        r"xu hướng", r"xu huong",
        r"so với tháng trước", r"so voi thang truoc",
        r"tháng trước", r"thang truoc",
        r"tăng hay giảm", r"tang hay giam",
        r"so sánh", r"so sanh",
        r"trend",
    ],
    "advice": [
        r"lời khuyên", r"loi khuyen",
        r"gợi ý", r"goi y",
        r"nên làm gì", r"nen lam gi",
        r"cần làm gì", r"can lam gi",
        r"làm sao", r"lam sao",
        r"cách tiết kiệm", r"cach tiet kiem",
        r"cắt giảm", r"cat giam",
        r"tối ưu", r"toi uu",
        r"advice", r"tip",
    ],
    "forecast": [
        r"dự báo", r"du bao",
        r"tháng tới", r"thang toi",
        r"tháng sau", r"thang sau",
        r"forecast",
        r"sẽ chi", r"se chi",
        r"ước tính", r"uoc tinh",
    ],
    "anomaly": [
        r"bất thường", r"bat thuong",
        r"anomaly",
        r"lạ", r"khác thường",
        r"đáng ngờ", r"dang ngo",
        r"giao dịch lạ",
    ],
    "budget": [
        r"ngân sách", r"ngan sach",
        r"budget",
        r"hạn mức", r"han muc",
        r"vượt ngân sách", r"vuot ngan sach",
    ],
    "transaction_list": [
        r"giao dịch", r"giao dich",
        r"lịch sử", r"lich su",
        r"transaction",
        r"danh sách", r"danh sach",
        r"vừa chi", r"vua chi",
        r"gần đây", r"gan day",
    ],
    "help": [
        r"\bgiúp\b", r"\bgiup\b",
        r"\bhelp\b",
        r"có thể hỏi gì", r"co the hoi gi",
        r"hỏi gì được", r"hoi gi duoc",
        r"làm được gì", r"lam duoc gi",
        r"hướng dẫn", r"huong dan",
    ],
    "unknown": [],
}


def detect_intent(text: str) -> str:
    text_lower = text.lower()
    # Remove diacritics version for better matching
    scores = {}
    for intent, patterns in INTENTS.items():
        if intent == "unknown":
            continue
        score = 0
        for pattern in patterns:
            if re.search(pattern, text_lower):
                score += 1
        if score > 0:
            scores[intent] = score

    if not scores:
        return "unknown"
    return max(scores, key=scores.get)


def extract_month(text: str) -> Optional[str]:
    """Trích xuất tháng từ câu hỏi, VD: 'tháng 3', 'tháng 3/2025', '2025-03'"""
    now = datetime.now()

    # "tháng trước", "thang truoc"
    if re.search(r"tháng trước|thang truoc|tháng trứơc", text.lower()):
        first = now.replace(day=1)
        prev = first - timedelta(days=1)
        return prev.strftime("%Y-%m")

    # "tháng này", "thang nay"
    if re.search(r"tháng này|thang nay|tháng hiện tại", text.lower()):
        return now.strftime("%Y-%m")

    # "tháng tới", "tháng sau"
    if re.search(r"tháng tới|thang toi|tháng sau|thang sau", text.lower()):
        if now.month == 12:
            return f"{now.year + 1}-01"
        return f"{now.year}-{now.month + 1:02d}"

    # "tháng 3/2025" or "tháng 3 năm 2025"
    m = re.search(r"tháng\s*(\d{1,2})[/\-\s](\d{4})", text.lower())
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"

    # "tháng 3" (current year assumed)
    m = re.search(r"tháng\s*(\d{1,2})\b", text.lower())
    if m:
        month_num = int(m.group(1))
        if 1 <= month_num <= 12:
            return f"{now.year}-{month_num:02d}"

    # "2025-03" or "03/2025"
    m = re.search(r"(\d{4})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"

    # Default: current month
    return now.strftime("%Y-%m")


def extract_category(text: str) -> Optional[str]:
    """Trích xuất tên danh mục từ câu hỏi"""
    cat_map = {
        r"ăn uống|an uong|ăn|đồ ăn|food": "Ăn uống",
        r"di chuyển|di chuyen|xăng|grab|taxi|đi lại": "Di chuyển",
        r"mua sắm|mua sam|shopping|quần áo": "Mua sắm",
        r"giải trí|giai tri|phim|nhạc|game|netflix|spotify": "Giải trí",
        r"y tế|y te|thuốc|bệnh viện|khám bệnh": "Y tế",
        r"hóa đơn|hoa don|điện|nước|internet|tiền nhà": "Hóa đơn",
        r"giáo dục|giao duc|học phí|sách|khóa học": "Giáo dục",
        r"lương|luong|salary": "Lương",
        r"thưởng|thuong|bonus": "Thưởng",
    }
    text_lower = text.lower()
    for pattern, cat_name in cat_map.items():
        if re.search(pattern, text_lower):
            return cat_name
    return None


# ══════════════════════════════════════════════════════════════
# 2. DATA FETCHER — truy vấn dữ liệu từ DB
# ══════════════════════════════════════════════════════════════

class DataFetcher:
    def get_monthly_summary(self, month: str) -> dict:
        conn = get_connection()
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expense,
                COUNT(*) AS tx_count
            FROM transactions
            WHERE strftime('%Y-%m', date) = ?
        """, (month,)).fetchone()
        conn.close()
        return dict(row) if row else {"income": 0, "expense": 0, "tx_count": 0}

    def get_category_breakdown(self, month: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT c.name, SUM(t.amount) AS total, COUNT(*) AS cnt
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense'
              AND strftime('%Y-%m', t.date) = ?
            GROUP BY c.id
            ORDER BY total DESC
        """, (month,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_category_amount(self, month: str, category_name: str) -> dict:
        conn = get_connection()
        row = conn.execute("""
            SELECT COALESCE(SUM(t.amount), 0) AS total, COUNT(*) AS cnt
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense'
              AND strftime('%Y-%m', t.date) = ?
              AND c.name LIKE ?
        """, (month, f"%{category_name}%")).fetchone()
        conn.close()
        return dict(row) if row else {"total": 0, "cnt": 0}

    def get_last_n_months(self, n: int = 6) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', date) AS month,
                SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS income,
                SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
            FROM transactions
            GROUP BY month
            ORDER BY month DESC
            LIMIT ?
        """, (n,)).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    def get_balance(self) -> float:
        conn = get_connection()
        row = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) AS total FROM accounts"
        ).fetchone()
        conn.close()
        return row["total"] if row else 0.0

    def get_accounts(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT name, type, balance FROM accounts ORDER BY balance DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_recent_transactions(self, month: str, limit: int = 5) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.description, t.amount, t.type, t.date, t.is_anomaly,
                   c.name AS cat_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE strftime('%Y-%m', t.date) = ?
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
        """, (month, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_anomalies(self, month: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.description, t.amount, t.date, c.name AS cat_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.is_anomaly = 1
              AND strftime('%Y-%m', t.date) = ?
            ORDER BY t.amount DESC
        """, (month,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_budgets(self, month: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT b.limit_amount, b.spent_amount, c.name AS cat_name,
                   b.alert_threshold
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            WHERE b.month = ?
            ORDER BY b.spent_amount DESC
        """, (month,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_avg_monthly_expense(self, months: int = 3) -> float:
        """Trung bình chi tiêu N tháng gần nhất"""
        data = self.get_last_n_months(months)
        if not data:
            return 0
        total = sum(d["expense"] for d in data)
        return total / len(data)

    def get_top_transactions(self, month: str, tx_type: str = "expense",
                             limit: int = 5) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.description, t.amount, t.date, c.name AS cat_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.type = ?
              AND strftime('%Y-%m', t.date) = ?
            ORDER BY t.amount DESC
            LIMIT ?
        """, (tx_type, month, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. ANALYZER — phân tích thống kê, xu hướng
# ══════════════════════════════════════════════════════════════

class Analyzer:
    def trend_vs_prev_month(self, current_month: str) -> dict:
        """So sánh tháng hiện tại với tháng trước"""
        dt = datetime.strptime(current_month + "-01", "%Y-%m-%d")
        prev_dt = (dt - timedelta(days=1)).replace(day=1)
        prev_month = prev_dt.strftime("%Y-%m")

        fetcher = DataFetcher()
        cur  = fetcher.get_monthly_summary(current_month)
        prev = fetcher.get_monthly_summary(prev_month)

        result = {
            "current": cur,
            "prev": prev,
            "prev_month": prev_month,
            "expense_delta": cur["expense"] - prev["expense"],
            "income_delta":  cur["income"]  - prev["income"],
        }
        if prev["expense"] > 0:
            result["expense_pct"] = (result["expense_delta"] / prev["expense"]) * 100
        else:
            result["expense_pct"] = 0
        return result

    def forecast_next_month(self, months_back: int = 3) -> dict:
        """Dự báo đơn giản: trung bình trượt + xu hướng"""
        fetcher = DataFetcher()
        history = fetcher.get_last_n_months(months_back)

        if not history:
            return {"predicted": 0, "method": "no_data"}

        expenses = [d["expense"] for d in history if d["expense"] > 0]
        if not expenses:
            return {"predicted": 0, "method": "no_data"}

        # Trung bình trượt
        avg = sum(expenses) / len(expenses)

        # Xu hướng tuyến tính đơn giản
        if len(expenses) >= 2:
            trend = expenses[-1] - expenses[0]
            predicted = avg + (trend / len(expenses))
        else:
            predicted = avg

        predicted = max(0, predicted)

        # Khoảng tin cậy ±1 std dev
        if len(expenses) > 1:
            variance = sum((x - avg) ** 2 for x in expenses) / len(expenses)
            std = math.sqrt(variance)
        else:
            std = avg * 0.2

        return {
            "predicted": round(predicted),
            "lower": round(max(0, predicted - std)),
            "upper": round(predicted + std),
            "confidence": round(max(0.5, 1 - std / (avg + 1)), 2),
            "method": "moving_average",
            "months_used": len(expenses),
        }

    def spending_health_score(self, month: str) -> dict:
        """Chấm điểm sức khoẻ tài chính 0-100"""
        fetcher = DataFetcher()
        summary = fetcher.get_monthly_summary(month)
        income  = summary["income"]
        expense = summary["expense"]

        if income == 0:
            return {"score": 0, "grade": "F", "messages": ["Chưa có dữ liệu thu nhập"]}

        saving_rate = (income - expense) / income
        messages = []
        score = 100

        # Trừ điểm theo tỷ lệ chi/thu
        if saving_rate < 0:
            score -= 40
            messages.append("Chi tiêu vượt thu nhập")
        elif saving_rate < 0.1:
            score -= 25
            messages.append("Tỷ lệ tiết kiệm thấp (<10%)")
        elif saving_rate < 0.2:
            score -= 10
            messages.append("Tỷ lệ tiết kiệm trung bình (10-20%)")
        else:
            messages.append(f"Tỷ lệ tiết kiệm tốt ({saving_rate*100:.0f}%)")

        # Kiểm tra ngân sách vượt
        budgets = fetcher.get_budgets(month)
        over_count = sum(1 for b in budgets
                         if b["spent_amount"] > b["limit_amount"])
        if over_count > 0:
            score -= over_count * 8
            messages.append(f"{over_count} danh mục vượt ngân sách")

        # Kiểm tra giao dịch bất thường
        anomalies = fetcher.get_anomalies(month)
        if anomalies:
            score -= min(15, len(anomalies) * 5)
            messages.append(f"{len(anomalies)} giao dịch bất thường")

        score = max(0, min(100, score))

        if score >= 80:
            grade = "A"
        elif score >= 65:
            grade = "B"
        elif score >= 50:
            grade = "C"
        elif score >= 35:
            grade = "D"
        else:
            grade = "F"

        return {"score": score, "grade": grade, "messages": messages}

    def generate_advice(self, month: str) -> list[str]:
        """Tạo danh sách lời khuyên cụ thể dựa trên dữ liệu thực"""
        fetcher = DataFetcher()
        summary = fetcher.get_monthly_summary(month)
        cats    = fetcher.get_category_breakdown(month)
        budgets = fetcher.get_budgets(month)
        history = fetcher.get_last_n_months(4)

        advice = []
        income  = summary["income"]
        expense = summary["expense"]

        # Phân tích tỷ lệ tiết kiệm
        if income > 0:
            saving_rate = (income - expense) / income
            if saving_rate < 0:
                advice.append(
                    f"Chi tiêu đang vượt thu nhập {abs(income-expense):,.0f}đ. "
                    "Hãy xem xét cắt giảm các khoản chi không thiết yếu."
                )
            elif saving_rate < 0.2:
                advice.append(
                    f"Tỷ lệ tiết kiệm chỉ đạt {saving_rate*100:.0f}%. "
                    "Mục tiêu lý tưởng là 20% theo quy tắc 50-30-20."
                )
            else:
                advice.append(
                    f"Tỷ lệ tiết kiệm {saving_rate*100:.0f}% — đang rất tốt! "
                    "Cân nhắc đầu tư phần tiết kiệm để sinh lời."
                )

        # Danh mục chi nhiều nhất
        if cats:
            top = cats[0]
            total_exp = sum(c["total"] for c in cats)
            pct = (top["total"] / total_exp * 100) if total_exp > 0 else 0
            if pct > 40:
                advice.append(
                    f"Danh mục '{top['name']}' chiếm {pct:.0f}% tổng chi tiêu "
                    f"({top['total']:,.0f}đ). Xem xét cắt giảm để cân bằng hơn."
                )

        # Ngân sách vượt
        over_budgets = [b for b in budgets
                        if b["spent_amount"] > b["limit_amount"]]
        for b in over_budgets[:2]:
            over = b["spent_amount"] - b["limit_amount"]
            advice.append(
                f"Ngân sách '{b['cat_name']}' vượt {over:,.0f}đ. "
                "Cần điều chỉnh hoặc tăng hạn mức cho tháng tới."
            )

        # Xu hướng tăng chi
        if len(history) >= 3:
            expenses = [d["expense"] for d in history]
            if len(expenses) >= 2 and expenses[-1] > expenses[-2] * 1.15:
                pct_inc = (expenses[-1] / expenses[-2] - 1) * 100
                advice.append(
                    f"Chi tiêu tháng này tăng {pct_inc:.0f}% so với tháng trước. "
                    "Hãy kiểm tra lại các khoản phát sinh."
                )

        # Gợi ý tiết kiệm cụ thể
        food_cat = next((c for c in cats if "ăn" in c["name"].lower()), None)
        if food_cat and income > 0:
            food_pct = food_cat["total"] / income * 100
            if food_pct > 30:
                advice.append(
                    f"Chi phí ăn uống chiếm {food_pct:.0f}% thu nhập — khá cao. "
                    "Nấu ăn tại nhà 3-4 bữa/tuần có thể tiết kiệm 20-30%."
                )

        enter_cat = next((c for c in cats if "giải" in c["name"].lower()), None)
        if enter_cat and income > 0:
            ent_pct = enter_cat["total"] / income * 100
            if ent_pct > 15:
                advice.append(
                    f"Chi giải trí chiếm {ent_pct:.0f}% thu nhập. "
                    "Xem xét đặt giới hạn ngân sách cho danh mục này."
                )

        if not advice:
            advice.append(
                "Tài chính tháng này đang ổn định. Hãy duy trì thói quen tốt!"
            )

        return advice


# ══════════════════════════════════════════════════════════════
# 4. RESPONDER — tạo câu trả lời tự nhiên
# ══════════════════════════════════════════════════════════════

class Responder:
    def __init__(self):
        self.fetcher  = DataFetcher()
        self.analyzer = Analyzer()

    def fmt(self, value: float) -> str:
        return f"{value:,.0f}đ".replace(",", ".")

    def fmt_month(self, month: str) -> str:
        try:
            dt = datetime.strptime(month, "%Y-%m")
            return f"Tháng {dt.month}/{dt.year}"
        except Exception:
            return month

    # ── Intent handlers ──────────────────────────────────────

    def handle_greet(self, _text: str, month: str) -> str:
        summary = self.fetcher.get_monthly_summary(month)
        balance = self.fetcher.get_balance()
        return (
            f"Xin chào! Tôi là trợ lý tài chính của bạn.\n\n"
            f"Hiện tại là {self.fmt_month(month)}:\n"
            f"• Thu nhập: {self.fmt(summary['income'])}\n"
            f"• Chi tiêu: {self.fmt(summary['expense'])}\n"
            f"• Tiết kiệm: {self.fmt(summary['income'] - summary['expense'])}\n"
            f"• Số dư tổng: {self.fmt(balance)}\n\n"
            f"Bạn muốn tôi phân tích gì? Gõ 'giúp' để xem danh sách câu hỏi."
        )

    def handle_total_expense(self, _text: str, month: str) -> str:
        summary = self.fetcher.get_monthly_summary(month)
        cats    = self.fetcher.get_category_breakdown(month)
        expense = summary["expense"]

        lines = [f"**{self.fmt_month(month)}, bạn đã chi {self.fmt(expense)}** "
                 f"qua {summary['tx_count']} giao dịch.\n"]

        if cats:
            lines.append("Chi tiết theo danh mục:")
            for i, c in enumerate(cats[:5], 1):
                pct = (c["total"] / expense * 100) if expense > 0 else 0
                lines.append(f"  {i}. {c['name']}: {self.fmt(c['total'])} ({pct:.0f}%)")
            if len(cats) > 5:
                others = sum(c["total"] for c in cats[5:])
                lines.append(f"  ... và {len(cats)-5} danh mục khác: {self.fmt(others)}")

        return "\n".join(lines)

    def handle_total_income(self, _text: str, month: str) -> str:
        summary = self.fetcher.get_monthly_summary(month)
        income  = summary["income"]
        if income == 0:
            return (f"{self.fmt_month(month)} chưa ghi nhận khoản thu nhập nào.\n"
                    "Hãy thêm giao dịch loại 'Thu nhập' để theo dõi.")
        return (
            f"{self.fmt_month(month)}, thu nhập của bạn là "
            f"**{self.fmt(income)}**.\n"
            f"Số giao dịch: {summary['tx_count']}"
        )

    def handle_saving(self, _text: str, month: str) -> str:
        summary = self.fetcher.get_monthly_summary(month)
        income  = summary["income"]
        expense = summary["expense"]
        saving  = income - expense

        if income == 0:
            return "Chưa có dữ liệu thu nhập tháng này để tính tiết kiệm."

        saving_rate = saving / income * 100

        if saving > 0:
            msg = (
                f"{self.fmt_month(month)}, bạn tiết kiệm được "
                f"**{self.fmt(saving)}** ({saving_rate:.1f}% thu nhập).\n\n"
            )
            if saving_rate >= 30:
                msg += "Xuất sắc! Tỷ lệ tiết kiệm rất cao. Cân nhắc đầu tư thêm."
            elif saving_rate >= 20:
                msg += "Rất tốt! Đang đúng với mục tiêu 20% theo quy tắc 50-30-20."
            elif saving_rate >= 10:
                msg += "Ổn nhưng có thể cải thiện. Mục tiêu là tiết kiệm 20% thu nhập."
            else:
                msg += "Tỷ lệ tiết kiệm còn thấp. Hãy tìm cách tăng lên ít nhất 20%."
        else:
            msg = (
                f"{self.fmt_month(month)}, chi tiêu vượt thu nhập "
                f"**{self.fmt(abs(saving))}**!\n\n"
                "Cần kiểm soát chi tiêu ngay để tránh tình trạng này kéo dài."
            )

        return msg

    def handle_balance(self, _text: str, month: str) -> str:
        accounts = self.fetcher.get_accounts()
        total    = sum(a["balance"] for a in accounts)

        if not accounts:
            return "Chưa có tài khoản nào trong hệ thống."

        lines = [f"**Tổng số dư: {self.fmt(total)}**\n"]
        for acc in accounts:
            type_label = {
                "cash": "Tiền mặt", "bank": "Ngân hàng",
                "card": "Thẻ tín dụng", "saving": "Tiết kiệm"
            }.get(acc["type"], acc["type"])
            lines.append(f"• {acc['name']} ({type_label}): {self.fmt(acc['balance'])}")

        return "\n".join(lines)

    def handle_top_category(self, _text: str, month: str) -> str:
        cats    = self.fetcher.get_category_breakdown(month)
        summary = self.fetcher.get_monthly_summary(month)
        expense = summary["expense"]

        if not cats:
            return f"{self.fmt_month(month)} chưa có giao dịch chi tiêu nào."

        top = cats[0]
        pct = (top["total"] / expense * 100) if expense > 0 else 0

        lines = [
            f"**Danh mục chi nhiều nhất {self.fmt_month(month)}:**\n",
            f"🥇 {top['name']}: {self.fmt(top['total'])} ({pct:.0f}%)\n",
            "Top 5 danh mục:"
        ]
        for i, c in enumerate(cats[:5], 1):
            bar_len = int((c["total"] / cats[0]["total"]) * 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            p = (c["total"] / expense * 100) if expense > 0 else 0
            lines.append(f"  {i}. {c['name']}: {bar} {self.fmt(c['total'])} ({p:.0f}%)")

        return "\n".join(lines)

    def handle_category_detail(self, text: str, month: str) -> str:
        cat_name = extract_category(text)
        if not cat_name:
            return "Bạn muốn xem chi tiết danh mục nào? VD: 'ăn uống tháng này'"

        data = self.fetcher.get_category_amount(month, cat_name)
        top_txs = self.fetcher.get_top_transactions(month, "expense", 5)
        cat_txs = [t for t in top_txs
                   if cat_name.lower() in (t.get("cat_name") or "").lower()]

        if data["total"] == 0:
            return f"Không có giao dịch nào thuộc '{cat_name}' trong {self.fmt_month(month)}."

        lines = [
            f"**{cat_name} — {self.fmt_month(month)}**\n",
            f"• Tổng chi: {self.fmt(data['total'])}",
            f"• Số giao dịch: {data['cnt']}",
            f"• Trung bình/giao dịch: {self.fmt(data['total'] / data['cnt'] if data['cnt'] else 0)}",
        ]

        if cat_txs:
            lines.append("\nGiao dịch lớn nhất:")
            for t in cat_txs[:3]:
                lines.append(
                    f"  • {t['description'] or 'N/A'}: {self.fmt(t['amount'])} ({t['date']})"
                )

        return "\n".join(lines)

    def handle_trend(self, _text: str, month: str) -> str:
        trend = self.analyzer.trend_vs_prev_month(month)
        cur   = trend["current"]
        prev  = trend["prev"]
        delta = trend["expense_delta"]
        pct   = trend["expense_pct"]
        prev_label = self.fmt_month(trend["prev_month"])

        if prev["expense"] == 0:
            return (
                f"{self.fmt_month(month)}: Chi tiêu {self.fmt(cur['expense'])}.\n"
                f"Không có dữ liệu {prev_label} để so sánh."
            )

        if delta > 0:
            direction = f"tăng {self.fmt(delta)} (+{pct:.1f}%)"
            emoji = "📈"
        elif delta < 0:
            direction = f"giảm {self.fmt(abs(delta))} ({pct:.1f}%)"
            emoji = "📉"
        else:
            direction = "không thay đổi"
            emoji = "➡️"

        lines = [
            f"{emoji} **So sánh chi tiêu:**\n",
            f"• {prev_label}: {self.fmt(prev['expense'])}",
            f"• {self.fmt_month(month)}: {self.fmt(cur['expense'])}",
            f"• Chi tiêu {direction} so với tháng trước.\n",
        ]

        # Thu nhập
        inc_delta = trend["income_delta"]
        if prev["income"] > 0:
            inc_pct = (inc_delta / prev["income"]) * 100
            if inc_delta > 0:
                lines.append(f"• Thu nhập tăng {self.fmt(inc_delta)} (+{inc_pct:.1f}%)")
            elif inc_delta < 0:
                lines.append(f"• Thu nhập giảm {self.fmt(abs(inc_delta))} ({inc_pct:.1f}%)")

        return "\n".join(lines)

    def handle_advice(self, _text: str, month: str) -> str:
        advice  = self.analyzer.generate_advice(month)
        health  = self.analyzer.spending_health_score(month)

        lines = [
            f"**Điểm sức khoẻ tài chính: {health['score']}/100 (Hạng {health['grade']})**\n",
            "💡 Lời khuyên cá nhân hoá:\n",
        ]
        for i, tip in enumerate(advice, 1):
            lines.append(f"{i}. {tip}")

        return "\n".join(lines)

    def handle_forecast(self, _text: str, month: str) -> str:
        fc = self.analyzer.forecast_next_month(months_back=3)
        history = self.fetcher.get_last_n_months(3)

        if fc["method"] == "no_data":
            return "Chưa đủ dữ liệu lịch sử để dự báo. Hãy thêm giao dịch trong ít nhất 1 tháng."

        now = datetime.now()
        next_m = f"{now.year}-{now.month+1:02d}" if now.month < 12 else f"{now.year+1}-01"

        lines = [
            f"**Dự báo chi tiêu {self.fmt_month(next_m)}:**\n",
            f"• Dự kiến: {self.fmt(fc['predicted'])}",
            f"• Khoảng tin cậy: {self.fmt(fc['lower'])} — {self.fmt(fc['upper'])}",
            f"• Độ tin cậy: {fc['confidence']*100:.0f}%",
            f"• Dựa trên: {fc['months_used']} tháng gần nhất\n",
        ]

        if history:
            lines.append("Lịch sử chi tiêu:")
            for h in history:
                lines.append(f"  • {self.fmt_month(h['month'])}: {self.fmt(h['expense'])}")

        return "\n".join(lines)

    def handle_anomaly(self, _text: str, month: str) -> str:
        anomalies = self.fetcher.get_anomalies(month)
        if not anomalies:
            return (
                f"{self.fmt_month(month)} không có giao dịch bất thường nào.\n"
                "Bấm 'Phát hiện bất thường' trong tab Dự báo để AI phân tích."
            )

        lines = [f"**{self.fmt_month(month)}: {len(anomalies)} giao dịch bất thường**\n"]
        for i, a in enumerate(anomalies[:5], 1):
            lines.append(
                f"{i}. {a['description'] or 'N/A'} — {self.fmt(a['amount'])} "
                f"({a.get('cat_name','?')}) — {a['date']}"
            )
        if len(anomalies) > 5:
            lines.append(f"... và {len(anomalies)-5} giao dịch khác.")

        return "\n".join(lines)

    def handle_budget(self, _text: str, month: str) -> str:
        budgets = self.fetcher.get_budgets(month)
        if not budgets:
            return (
                f"{self.fmt_month(month)} chưa có ngân sách nào được đặt.\n"
                "Vào tab 'Ngân sách' để đặt hạn mức cho từng danh mục."
            )

        lines = [f"**Ngân sách {self.fmt_month(month)}:**\n"]
        for b in budgets:
            pct = int(b["spent_amount"] / b["limit_amount"] * 100) if b["limit_amount"] else 0
            bar_fill = min(10, pct // 10)
            bar = "█" * bar_fill + "░" * (10 - bar_fill)
            status = ""
            if pct >= 100:
                status = "❌ VƯỢT"
            elif pct >= int(b["alert_threshold"] * 100):
                status = "⚠ Sắp hết"
            else:
                status = "✓ Bình thường"
            lines.append(
                f"• {b['cat_name']}: {bar} {pct}% "
                f"({self.fmt(b['spent_amount'])}/{self.fmt(b['limit_amount'])}) {status}"
            )

        over = [b for b in budgets if b["spent_amount"] > b["limit_amount"]]
        if over:
            lines.append(f"\n{len(over)} danh mục đã vượt ngân sách!")

        return "\n".join(lines)

    def handle_transaction_list(self, _text: str, month: str) -> str:
        txs = self.fetcher.get_recent_transactions(month, limit=7)
        if not txs:
            return f"{self.fmt_month(month)} chưa có giao dịch nào."

        lines = [f"**Giao dịch gần đây — {self.fmt_month(month)}:**\n"]
        for t in txs:
            sign  = "+" if t["type"] == "income" else "-"
            anom  = " ⚠" if t.get("is_anomaly") else ""
            cat   = f" [{t['cat_name']}]" if t.get("cat_name") else ""
            lines.append(
                f"• {t['date']} | {t['description'] or 'N/A'}{cat}{anom}: "
                f"{sign}{self.fmt(t['amount'])}"
            )

        return "\n".join(lines)

    def handle_help(self, _text: str, month: str) -> str:
        return (
            "**Tôi có thể trả lời các câu hỏi sau:**\n\n"
            "💰 **Thu chi:**\n"
            "  • 'Tháng này tôi chi bao nhiêu?'\n"
            "  • 'Thu nhập tháng này là bao nhiêu?'\n"
            "  • 'Tôi tiết kiệm được bao nhiêu?'\n"
            "  • 'Số dư hiện tại?'\n\n"
            "📊 **Phân tích:**\n"
            "  • 'Danh mục nào tốn nhiều nhất?'\n"
            "  • 'Ăn uống tháng 3 hết bao nhiêu?'\n"
            "  • 'So sánh với tháng trước'\n"
            "  • 'Ngân sách tháng này thế nào?'\n\n"
            "🤖 **AI & Dự báo:**\n"
            "  • 'Dự báo tháng tới chi bao nhiêu?'\n"
            "  • 'Có giao dịch bất thường không?'\n"
            "  • 'Cho tôi lời khuyên tài chính'\n\n"
            "📋 **Khác:**\n"
            "  • 'Giao dịch gần đây'\n"
            "  • Chỉ định tháng: 'tháng 3', 'tháng trước', 'tháng 5/2025'"
        )

    def handle_unknown(self, text: str, month: str) -> str:
        # Thử tìm thông tin liên quan dựa trên từ khoá
        text_lower = text.lower()
        if any(k in text_lower for k in ["bao nhiêu", "bao nhieu", "how much"]):
            return self.handle_total_expense(text, month)
        if any(k in text_lower for k in ["cao nhất", "lớn nhất", "lon nhat"]):
            return self.handle_top_transaction(text, month)

        return (
            "Tôi chưa hiểu câu hỏi của bạn. Hãy thử:\n"
            "• 'Tháng này chi bao nhiêu?'\n"
            "• 'Cho lời khuyên tài chính'\n"
            "• 'Dự báo tháng tới'\n\n"
            "Gõ **'giúp'** để xem danh sách đầy đủ."
        )

    def handle_top_transaction(self, text: str, month: str) -> str:
        txs = self.fetcher.get_top_transactions(month, "expense", 5)
        if not txs:
            return f"Chưa có giao dịch chi tiêu trong {self.fmt_month(month)}."
        lines = [f"**Top giao dịch lớn nhất {self.fmt_month(month)}:**\n"]
        for i, t in enumerate(txs, 1):
            cat = f" [{t['cat_name']}]" if t.get("cat_name") else ""
            lines.append(f"{i}. {t['description'] or 'N/A'}{cat}: {self.fmt(t['amount'])}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 5. MAIN ENGINE — điều phối toàn bộ
# ══════════════════════════════════════════════════════════════

class LocalChatbotEngine:
    """
    Engine chatbot thuần giải thuật.
    Không cần API, không cần internet, không cần model AI.
    """

    def __init__(self):
        self.responder = Responder()
        self._history: list[dict] = []

    def chat(self, user_message: str) -> str:
        """
        Nhận tin nhắn người dùng, trả về câu trả lời.
        """
        self._history.append({"role": "user", "content": user_message})

        intent = detect_intent(user_message)
        month  = extract_month(user_message)

        # Dispatch đến handler tương ứng
        handlers = {
            "greet":            self.responder.handle_greet,
            "total_expense":    self.responder.handle_total_expense,
            "total_income":     self.responder.handle_total_income,
            "saving":           self.responder.handle_saving,
            "balance":          self.responder.handle_balance,
            "top_category":     self.responder.handle_top_category,
            "category_detail":  self.responder.handle_category_detail,
            "trend":            self.responder.handle_trend,
            "advice":           self.responder.handle_advice,
            "forecast":         self.responder.handle_forecast,
            "anomaly":          self.responder.handle_anomaly,
            "budget":           self.responder.handle_budget,
            "transaction_list": self.responder.handle_transaction_list,
            "help":             self.responder.handle_help,
            "unknown":          self.responder.handle_unknown,
        }

        handler  = handlers.get(intent, self.responder.handle_unknown)
        response = handler(user_message, month)

        self._history.append({"role": "assistant", "content": response})
        return response

    def reset(self):
        """Xóa lịch sử hội thoại"""
        self._history.clear()

    @property
    def history(self) -> list[dict]:
        return self._history.copy()


# Singleton engine — tái sử dụng giữa các lần chat
_engine_instance: Optional[LocalChatbotEngine] = None


def get_engine() -> LocalChatbotEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LocalChatbotEngine()
    return _engine_instance
