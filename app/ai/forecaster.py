import numpy as np
from datetime import datetime
from app.data.models import get_connection
from app.core.settings_manager import get_setting


class SpendingForecaster:

    MIN_MONTHS_FOR_PROPHET = 3
    _prophet_available = None

    @classmethod
    def is_prophet_available(cls):
        if cls._prophet_available is None:
            try:
                import prophet
                import pandas as pd
                cls._prophet_available = True
            except ImportError:
                cls._prophet_available = False
        return cls._prophet_available

    def forecast_next_month(self, category_id=None) -> dict:
        df = self._load_monthly_data(category_id)
        method = get_setting("forecast_method", "auto")
        
        # Thêm logic giải thích
        explanation = ""
        if len(df) == 0:
            explanation = "Chưa có dữ liệu chi tiêu để thực hiện dự báo."
        elif len(df) < self.MIN_MONTHS_FOR_PROPHET:
            explanation = f"Dữ liệu ít ({len(df)} tháng), đang sử dụng phương pháp Trung bình trượt (Moving Average)."
        else:
            explanation = f"Sử dụng mô hình Prophet với dữ liệu từ {len(df)} tháng gần nhất."

        result = {}
        if method == "moving_average" and len(df) >= 1:
            result = self._moving_average_forecast(df)
        elif len(df) >= self.MIN_MONTHS_FOR_PROPHET and method in ("auto", "prophet"):
            result = self._prophet_forecast(df)
        elif len(df) >= 1:
            result = self._moving_average_forecast(df)
        else:
            result = {"predicted": 0, "lower": 0, "upper": 0,
                    "method": "no_data", "months_used": 0}
        
        result["explanation"] = explanation
        return result

    def forecast_all_categories(self) -> list:
        conn = get_connection()
        cats = conn.execute(
            "SELECT id, name FROM categories WHERE type='expense'"
        ).fetchall()
        conn.close()
        results = []
        next_month = self._next_month_str()
        conn = get_connection()
        conn.execute("DELETE FROM ai_predictions WHERE month=?", (next_month,))
        for cat in cats:
            result = self.forecast_next_month(category_id=cat["id"])
            result["category_id"]   = cat["id"]
            result["category_name"] = cat["name"]
            result["month"]         = next_month
            conn.execute("""
                INSERT INTO ai_predictions
                    (category_id, predicted_amount, month, confidence)
                VALUES (?, ?, ?, ?)
            """, (cat["id"], result["predicted"], next_month,
                  result.get("confidence", 0)))
            results.append(result)
        conn.commit()
        conn.close()
        return results

    def get_forecast_chart_data(self, category_id=None, months_back=6) -> dict:
        df = self._load_monthly_data(category_id)
        historical = df.tail(months_back).to_dict("records")
        method = get_setting("forecast_method", "auto")
        if method == "moving_average":
            single = self._moving_average_forecast(df)
            forecast_rows = [{"month": self._next_month_str(), **single}]
        elif len(df) >= self.MIN_MONTHS_FOR_PROPHET and method in ("auto", "prophet"):
            forecast_rows = self._prophet_multi_forecast(df, periods=3)
            if not forecast_rows:
                single = self._moving_average_forecast(df)
                forecast_rows = [{"month": self._next_month_str(), **single}]
        else:
            single = self._moving_average_forecast(df)
            forecast_rows = [{"month": self._next_month_str(), **single}]
        return {"historical": historical, "forecast": forecast_rows}

    def _prophet_forecast(self, df) -> dict:
        if not self.is_prophet_available():
            return self._moving_average_forecast(df)
        
        from prophet import Prophet
        import pandas as pd
        prophet_df = df.rename(columns={"month_date": "ds", "total": "y"})
        model = Prophet(
            yearly_seasonality=False, weekly_seasonality=False,
            daily_seasonality=False, changepoint_prior_scale=0.3,
            interval_width=0.8,
        )
        model.fit(prophet_df)
        future   = model.make_future_dataframe(periods=1, freq="MS")
        forecast = model.predict(future)
        last = forecast.iloc[-1]
        predicted = max(0, float(last["yhat"]))
        lower     = max(0, float(last["yhat_lower"]))
        upper     = max(0, float(last["yhat_upper"]))
        conf = 1 - (upper - lower) / (predicted + 1)
        conf = round(max(0, min(1, conf)), 2)
        return {
            "predicted": round(predicted), "lower": round(lower),
            "upper": round(upper), "confidence": conf,
            "method": "prophet", "months_used": len(df),
        }

    def _prophet_multi_forecast(self, df, periods=3) -> list:
        if not self.is_prophet_available():
            return []
            
        from prophet import Prophet
        import pandas as pd
        prophet_df = df.rename(columns={"month_date": "ds", "total": "y"})
        model = Prophet(yearly_seasonality=False, weekly_seasonality=False,
                        daily_seasonality=False, interval_width=0.8)
        model.fit(prophet_df)
        future   = model.make_future_dataframe(periods=periods, freq="MS")
        forecast = model.predict(future)
        return [{
            "month":     row["ds"].strftime("%Y-%m"),
            "predicted": max(0, round(float(row["yhat"]))),
            "lower":     max(0, round(float(row["yhat_lower"]))),
            "upper":     max(0, round(float(row["yhat_upper"]))),
        } for _, row in forecast.tail(periods).iterrows()]

    def _moving_average_forecast(self, df) -> dict:
        import pandas as pd
        window = min(3, len(df))
        values = df["total"].tail(window).values
        predicted = float(np.mean(values))
        std = float(np.std(values)) if len(values) > 1 else predicted * 0.2
        return {
            "predicted": round(predicted),
            "lower":     round(max(0, predicted - std)),
            "upper":     round(predicted + std),
            "confidence": round(0.5 + 0.1 * window, 2),
            "method":    "moving_average", "months_used": len(df),
        }

    def _load_monthly_data(self, category_id=None):
        import pandas as pd
        from app.data.models import get_connection
        conn = get_connection()
        if category_id:
            rows = conn.execute("""
                SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
                FROM transactions
                WHERE type='expense' AND category_id=?
                GROUP BY month ORDER BY month
            """, (category_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
                FROM transactions WHERE type='expense'
                GROUP BY month ORDER BY month
            """).fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame(columns=["month", "total", "month_date"])
        df = pd.DataFrame([dict(r) for r in rows])
        df["month_date"] = pd.to_datetime(df["month"] + "-01")
        df["total"] = df["total"].fillna(0)
        return df

    @staticmethod
    def _next_month_str() -> str:
        now = datetime.now()
        if now.month == 12:
            return f"{now.year + 1}-01"
        return f"{now.year}-{now.month + 1:02d}"
