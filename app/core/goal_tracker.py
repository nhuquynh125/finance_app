# app/core/goal_tracker.py  (viết lại hoàn chỉnh)
"""
Quản lý mục tiêu tiết kiệm.

Thay đổi so với phiên bản cũ:
  - Không dùng self.conn (giữ connection mở) — dùng context manager
  - avg_savings_per_month tính từ dữ liệu THỰC TẾ của user thay vì hardcode
  - get_prediction() trả về dict có cấu trúc thay vì string
  - Thêm delete_goal(), get_goal_by_id()
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from app.data.models import get_connection


class GoalTracker:
    """Quản lý mục tiêu tiết kiệm cá nhân."""

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def get_all_goals(self) -> list[dict]:
        """Lấy tất cả mục tiêu, sắp xếp theo ngày đến hạn gần nhất."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT *,
                    ROUND(current_amount * 100.0 / NULLIF(target_amount, 0), 1)
                        AS progress_pct
                FROM savings_goals
                ORDER BY
                    CASE WHEN target_date IS NULL THEN 1 ELSE 0 END,
                    target_date ASC
            """).fetchall()
        return [dict(r) for r in rows]

    def get_goal_by_id(self, goal_id: int) -> Optional[dict]:
        """Lấy một mục tiêu theo id."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM savings_goals WHERE id=?", (goal_id,)
            ).fetchone()
        return dict(row) if row else None

    def add_goal(self, name: str, target_amount: float,
                 target_date: Optional[str] = None,
                 color: str = "#1D9E75") -> dict:
        """
        Tạo mục tiêu tiết kiệm mới.
        Trả về {'success': bool, 'goal_id': int, 'message': str}
        """
        # Validate
        if not name.strip():
            return {"success": False, "message": "Tên mục tiêu không được để trống"}
        if target_amount <= 0:
            return {"success": False, "message": "Số tiền mục tiêu phải lớn hơn 0"}
        if target_date:
            try:
                dt = datetime.strptime(target_date, "%Y-%m-%d")
                if dt < datetime.now():
                    return {"success": False, "message": "Ngày đến hạn phải là ngày trong tương lai"}
            except ValueError:
                return {"success": False, "message": "Ngày không đúng định dạng YYYY-MM-DD"}

        with get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO savings_goals (name, target_amount, current_amount, target_date, color)
                VALUES (?, ?, 0, ?, ?)
            """, (name.strip(), target_amount, target_date, color))
            goal_id = cur.lastrowid

        return {
            "success": True,
            "goal_id": goal_id,
            "message": f"Đã tạo mục tiêu '{name}'"
        }

    def update_progress(self, goal_id: int, amount_to_add: float) -> dict:
        """
        Cộng thêm tiền vào mục tiêu (không ghi đè toàn bộ).
        Không cho vượt target_amount.
        Trả về {'success': bool, 'message': str, 'completed': bool}
        """
        if amount_to_add <= 0:
            return {"success": False, "message": "Số tiền phải lớn hơn 0"}

        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return {"success": False, "message": "Không tìm thấy mục tiêu"}

        new_amount = min(
            goal["current_amount"] + amount_to_add,
            goal["target_amount"]
        )
        completed = new_amount >= goal["target_amount"]

        with get_connection() as conn:
            conn.execute(
                "UPDATE savings_goals SET current_amount=? WHERE id=?",
                (new_amount, goal_id)
            )

        return {
            "success": True,
            "completed": completed,
            "new_amount": new_amount,
            "message": (
                f"Hoàn thành mục tiêu '{goal['name']}'! 🎉"
                if completed
                else f"Đã cập nhật: {new_amount:,.0f}đ / {goal['target_amount']:,.0f}đ"
            )
        }

    def set_progress(self, goal_id: int, current_amount: float) -> dict:
        """Đặt số tiền hiện tại (ghi đè)."""
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return {"success": False, "message": "Không tìm thấy mục tiêu"}
        if current_amount < 0:
            return {"success": False, "message": "Số tiền không được âm"}

        clamped = min(current_amount, goal["target_amount"])
        with get_connection() as conn:
            conn.execute(
                "UPDATE savings_goals SET current_amount=? WHERE id=?",
                (clamped, goal_id)
            )
        return {"success": True, "new_amount": clamped}

    def delete_goal(self, goal_id: int) -> dict:
        """Xóa mục tiêu."""
        with get_connection() as conn:
            affected = conn.execute(
                "DELETE FROM savings_goals WHERE id=?", (goal_id,)
            ).rowcount
        if affected:
            return {"success": True, "message": "Đã xóa mục tiêu"}
        return {"success": False, "message": "Không tìm thấy mục tiêu"}

    # ── Dự báo dựa trên dữ liệu thực ─────────────────────────────────────────

    def get_prediction(self, goal_id: int) -> dict:
        """
        Dự báo ngày/tháng hoàn thành dựa trên lịch sử tiết kiệm THỰC TẾ.

        Logic:
          1. Lấy tiết kiệm ròng (thu - chi) của 3 tháng gần nhất
          2. Tính trung bình → avg_monthly_saving
          3. Ước tính số tháng cần để đạt mục tiêu

        Trả về dict:
          {
            "status": "on_track" | "completed" | "no_data" | "negative" | "slow",
            "message": str,
            "remaining": float,
            "avg_monthly_saving": float,   # chỉ có khi status != "no_data"
            "months_needed": float,        # chỉ có khi on_track/slow
            "est_completion_date": str,    # YYYY-MM, chỉ khi on_track/slow
            "data_months": int,            # số tháng dữ liệu dùng để tính
          }
        """
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return {"status": "error", "message": "Không tìm thấy mục tiêu"}

        remaining = goal["target_amount"] - goal["current_amount"]

        # Đã hoàn thành
        if remaining <= 0:
            return {
                "status": "completed",
                "message": f"🎉 Đã hoàn thành mục tiêu '{goal['name']}'!",
                "remaining": 0,
            }

        # Lấy tiết kiệm ròng từ DB (3 tháng gần nhất)
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    strftime('%Y-%m', date) AS month,
                    SUM(CASE WHEN type = 'income'  THEN amount ELSE 0 END) AS income,
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expense,
                    SUM(CASE WHEN type = 'income'  THEN amount ELSE 0 END) -
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS saving
                FROM transactions
                GROUP BY month
                ORDER BY month DESC
                LIMIT 3
            """).fetchall()

        # Chưa có dữ liệu
        if not rows:
            return {
                "status": "no_data",
                "message": "Chưa có dữ liệu giao dịch để dự báo. Hãy thêm giao dịch trước.",
                "remaining": remaining,
            }

        data_months = len(rows)
        savings_list = [r["saving"] for r in rows]
        positive_savings = [s for s in savings_list if s > 0]

        # Chi tiêu luôn vượt thu nhập
        if not positive_savings:
            avg_saving = sum(savings_list) / len(savings_list)
            return {
                "status": "negative",
                "message": (
                    f"Chi tiêu đang vượt thu nhập trung bình "
                    f"{abs(avg_saving):,.0f}đ/tháng. "
                    "Cần cắt giảm chi tiêu để đạt mục tiêu."
                ),
                "remaining": remaining,
                "avg_monthly_saving": avg_saving,
                "data_months": data_months,
            }

        avg_monthly_saving = sum(positive_savings) / len(positive_savings)
        months_needed = remaining / avg_monthly_saving

        # Ước tính ngày hoàn thành
        now = datetime.now()
        total_months = int(months_needed)
        est_month = now.month + total_months
        est_year  = now.year + (est_month - 1) // 12
        est_month = ((est_month - 1) % 12) + 1
        est_date  = f"{est_year}-{est_month:02d}"

        # Cảnh báo nếu quá chậm (> 24 tháng)
        status = "slow" if months_needed > 24 else "on_track"

        return {
            "status": status,
            "message": (
                f"Với tốc độ tiết kiệm TB {avg_monthly_saving:,.0f}đ/tháng "
                f"(dựa trên {data_months} tháng gần nhất), "
                f"bạn cần thêm khoảng {months_needed:.1f} tháng. "
                f"Dự kiến hoàn thành: {est_month}/{est_year}."
            ),
            "remaining": remaining,
            "avg_monthly_saving": avg_monthly_saving,
            "months_needed": round(months_needed, 1),
            "est_completion_date": est_date,
            "data_months": data_months,
        }

    # ── Thống kê tổng hợp ────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        """
        Thống kê nhanh tất cả mục tiêu.
        Dùng để hiển thị trên dashboard hoặc family frame.
        """
        goals = self.get_all_goals()
        if not goals:
            return {
                "total_goals": 0,
                "completed": 0,
                "in_progress": 0,
                "total_target": 0,
                "total_saved": 0,
                "overall_pct": 0,
            }

        completed   = [g for g in goals if g["current_amount"] >= g["target_amount"]]
        in_progress = [g for g in goals if g["current_amount"] <  g["target_amount"]]
        total_target = sum(g["target_amount"]  for g in goals)
        total_saved  = sum(g["current_amount"] for g in goals)

        return {
            "total_goals": len(goals),
            "completed":   len(completed),
            "in_progress": len(in_progress),
            "total_target": total_target,
            "total_saved":  total_saved,
            "overall_pct":  round(total_saved / total_target * 100, 1) if total_target else 0,
        }
