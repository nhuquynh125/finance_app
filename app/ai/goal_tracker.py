from app.data.models import get_connection
from datetime import datetime

class GoalTracker:
    def __init__(self):
        self.conn = get_connection()

    def get_all_goals(self):
        return self.conn.execute("SELECT * FROM savings_goals").fetchall()

    def add_goal(self, name, target_amount, target_date, color="#1D9E75"):
        query = """
            INSERT INTO savings_goals (name, target_amount, target_date, color)
            VALUES (?, ?, ?, ?)
        """
        self.conn.execute_write(query, (name, target_amount, target_date, color))

    def update_progress(self, goal_id, current_amount):
        query = "UPDATE savings_goals SET current_amount = ? WHERE id = ?"
        self.conn.execute_write(query, (current_amount, goal_id))

    def get_prediction(self, goal_id):
        """
        Dự báo ngày hoàn thành dựa trên lịch sử tiết kiệm (giả lập logic AI).
        """
        goal = self.conn.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
        if not goal:
            return None
        
        remaining = goal['target_amount'] - goal['current_amount']
        if remaining <= 0:
            return "Đã hoàn thành"
            
        # Giả sử trung bình mỗi tháng tiết kiệm được 5 triệu (logic thực tế cần tính từ transactions)
        avg_savings_per_month = 5000000 
        months_needed = remaining / avg_savings_per_month
        
        return f"Dự kiến hoàn thành sau {months_needed:.1f} tháng nữa"
