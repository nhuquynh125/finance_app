from app.data.models import get_connection, DatabaseManager
from datetime import datetime
from app.data.repositories import TransactionRepo, TransactionModel  
from app.core.event_bus import bus


class TransactionManager:

    def add_transaction(self, account_id, amount, type_, description,
                        date=None, category_id=None, note=""):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        repo = TransactionRepo()
        model = TransactionModel(
            account_id=account_id,
            category_id=category_id,
            amount=amount,
            type_=type_,
            description=description,
            date=date,
            note=note
        )
        tx_id = repo.add(model)

        if type_ == "expense" and category_id:
            self._check_budget_alert(category_id, date)

        return tx_id

    def _check_budget_alert(self, category_id, date_str):
        try:
            month = date_str[:7]
            conn = get_connection()
            # Single query that fetches budget AND spent in one round-trip
            row = conn.execute("""
                SELECT b.limit_amount, b.alert_threshold, c.name as cat_name,
                       COALESCE(
                           (SELECT SUM(t.amount) FROM transactions t
                            WHERE t.category_id = b.category_id
                              AND t.type = 'expense'
                              AND strftime('%Y-%m', t.date) = b.month),
                           0
                       ) as spent
                FROM budgets b
                JOIN categories c ON b.category_id = c.id
                WHERE b.category_id = ? AND b.month = ?
            """, (category_id, month)).fetchone()

            if row:
                limit = row["limit_amount"]
                spent = row["spent"]
                ratio = spent / limit if limit > 0 else 0
                if ratio >= row["alert_threshold"]:
                    bus.notify_warning.emit(
                        f"Ngân sách '{row['cat_name']}'",
                        f"Đã dùng {ratio:.1%} — còn {max(0, limit - spent):,.0f}đ"
                    )
        except Exception as e:
            print(f"Error checking budget alert: {e}")
        return None

    def update_transaction(self, transaction_id, account_id, amount, type_,
                           description, date, category_id=None, note=""):
        db = DatabaseManager()
        conn = db.get_connection()
        old = conn.execute(
            "SELECT * FROM transactions WHERE id=?", (transaction_id,)
        ).fetchone()

        # Build all statements and execute them in ONE atomic batch —
        # previously 3 separate execute_write() calls each acquired the lock
        # and committed independently, tripling the write overhead.
        statements = []

        if old:
            old_delta = -old["amount"] if old["type"] == "income" else old["amount"]
            statements.append((
                "UPDATE accounts SET balance=balance+? WHERE id=?",
                (old_delta, old["account_id"])
            ))

        statements.append((
            """UPDATE transactions
               SET account_id=?, category_id=?, amount=?, type=?,
                   description=?, date=?, note=?
               WHERE id=?""",
            (account_id, category_id, amount, type_,
             description, date, note, transaction_id)
        ))

        new_delta = amount if type_ == "income" else -amount
        statements.append((
            "UPDATE accounts SET balance=balance+? WHERE id=?",
            (new_delta, account_id)
        ))

        db.execute_write_many(statements)

    def delete_transaction(self, transaction_id):
        db = DatabaseManager()
        conn = db.get_connection()
        tx = conn.execute(
            "SELECT * FROM transactions WHERE id=?", (transaction_id,)
        ).fetchone()

        if tx:
            delta = -tx["amount"] if tx["type"] == "income" else tx["amount"]
            # Two writes batched into one commit
            db.execute_write_many([
                ("UPDATE accounts SET balance=balance+? WHERE id=?",
                 (delta, tx["account_id"])),
                ("DELETE FROM transactions WHERE id=?", (transaction_id,)),
            ])

    def get_transactions(self, month=None, account_id=None, limit=200):
        conn = get_connection()
        query = """
            SELECT t.*, c.name as category_name, c.color,
                   a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts   a ON t.account_id  = a.id
            WHERE 1=1
        """
        params = []
        if month:
            query += " AND strftime('%Y-%m', t.date) = ?"
            params.append(month)
        if account_id:
            query += " AND t.account_id = ?"
            params.append(account_id)
        query += " ORDER BY t.date DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_monthly_summary(self, month):
        conn = get_connection()
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0) as total_income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as total_expense,
                COUNT(*) as total_count
            FROM transactions
            WHERE strftime('%Y-%m', date) = ?
        """, (month,)).fetchone()
        return dict(row)

    def get_multi_month_summary(self, months: list) -> dict:
        """
        Fetch summaries for multiple months in ONE query instead of N queries.
        Returns {month_str: {total_income, total_expense, total_count}}.

        Dashboard _draw_bar() used to call get_monthly_summary() 6 times.
        One call to this method replaces all of them.
        """
        if not months:
            return {}
        placeholders = ",".join("?" * len(months))
        conn = get_connection()
        rows = conn.execute(f"""
            SELECT
                strftime('%Y-%m', date) as month,
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0) as total_income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) as total_expense,
                COUNT(*) as total_count
            FROM transactions
            WHERE strftime('%Y-%m', date) IN ({placeholders})
            GROUP BY strftime('%Y-%m', date)
        """, months).fetchall()

        result = {m: {"total_income": 0, "total_expense": 0, "total_count": 0}
                  for m in months}
        for row in rows:
            result[row["month"]] = dict(row)
        return result
