import numpy as np
from datetime import datetime
from app.data.models import get_connection


class AnomalyDetector:

    CONTAMINATION = 0.08

    def detect_and_mark(self, month=None) -> list:
        import pandas as pd
        df = self._load_data(month)
        if len(df) < 5:
            return []
        df = self._engineer_features(df)
        scores = self._run_isolation_forest(df)
        df["anomaly_score"] = scores
        df["is_anomaly"]    = (scores < 0).astype(int)
        conn = get_connection()
        for _, row in df.iterrows():
            conn.execute(
                "UPDATE transactions SET is_anomaly=? WHERE id=?",
                (int(row["is_anomaly"]), int(row["id"]))
            )
        conn.commit()
        conn.close()
        anomalies = df[df["is_anomaly"] == 1].copy()
        return self._build_anomaly_report(anomalies, df)

    def get_anomalies(self, month=None) -> list:
        conn = get_connection()
        query = """
            SELECT t.*, c.name as category_name, c.color,
                   a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts   a ON t.account_id  = a.id
            WHERE t.is_anomaly = 1
        """
        params = []
        if month:
            query += " AND strftime('%Y-%m', t.date) = ?"
            params.append(month)
        query += " ORDER BY t.date DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def explain_anomaly(self, transaction_id: int) -> str:
        conn = get_connection()
        tx = conn.execute("""
            SELECT t.*, c.name as cat_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.id = ?
        """, (transaction_id,)).fetchone()
        if not tx:
            conn.close()
            return "Không tìm thấy giao dịch."
        amounts_rows = conn.execute("""
            SELECT amount FROM transactions
            WHERE category_id=? AND type='expense' AND id!=?
        """, (tx["category_id"], transaction_id)).fetchall()
        conn.close()

        reasons = []
        amount = tx["amount"]
        if amounts_rows:
            vals = [r["amount"] for r in amounts_rows]
            avg  = np.mean(vals)
            std  = np.std(vals) if len(vals) > 1 else avg * 0.3
            pct  = ((amount - avg) / avg * 100) if avg > 0 else 0
            if pct > 100:
                reasons.append(
                    f"Cao hơn {pct:.0f}% so với trung bình ({avg:,.0f} đ)")
            if std > 0 and (amount - avg) / (std + 1) > 2:
                reasons.append(f"Z-score = {(amount - avg) / (std + 1):.1f}")
        if tx["created_at"]:
            try:
                hour = datetime.strptime(
                    tx["created_at"], "%Y-%m-%d %H:%M:%S").hour
                if hour < 6:
                    reasons.append(f"Giao dịch lúc {hour:02d}:xx SA")
            except Exception:
                pass
        if not reasons:
            reasons.append("AI phát hiện mẫu bất thường")
        return " · ".join(reasons)

    def _load_data(self, month):
        import pandas as pd
        conn = get_connection()
        query = """
            SELECT t.id, t.amount, t.date, t.created_at,
                   t.category_id, t.type, c.name as category_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense'
        """
        params = []
        if month:
            query += " AND strftime('%Y-%m', t.date)=?"
            params.append(month)
        else:
            query += " AND t.date >= date('now','-6 months')"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return pd.DataFrame([dict(r) for r in rows])

    def _engineer_features(self, df) -> "pd.DataFrame":
        import pandas as pd
        df = df.copy()
        df["date_dt"]    = pd.to_datetime(df["date"], errors="coerce")
        df["created_dt"] = pd.to_datetime(
            df["created_at"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df["hour"]       = df["created_dt"].dt.hour.fillna(12)
        df["dayofweek"]  = df["date_dt"].dt.dayofweek.fillna(2)
        df["hour_anomaly"] = df["hour"].apply(lambda h: 1.0 if h < 6 else 0.0)

        def cat_zscore(group):
            mean = group["amount"].mean()
            std  = group["amount"].std()
            if pd.isna(std) or std == 0:
                group = group.copy()
                group["amount_zscore"] = 0.0
            else:
                group = group.copy()
                group["amount_zscore"] = (group["amount"] - mean) / std
            return group

        if "category_id" in df.columns and not df.empty:
            df = df.groupby("category_id", group_keys=False).apply(cat_zscore)
        else:
            df["amount_zscore"] = 0.0

        global_mean = df["amount"].mean() or 1
        df["amount_ratio"] = df["amount"] / global_mean
        df["log_amount"]   = np.log1p(df["amount"])
        return df

    def _run_isolation_forest(self, df) -> "np.ndarray":
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        features = ["log_amount", "amount_zscore", "amount_ratio",
                    "hour_anomaly", "dayofweek"]
        X = df[features].fillna(0).values
        X_scaled = StandardScaler().fit_transform(X)
        model = IsolationForest(
            n_estimators=200, contamination=self.CONTAMINATION,
            random_state=42, n_jobs=-1)
        model.fit(X_scaled)
        return model.score_samples(X_scaled)

    def _build_anomaly_report(self, anomalies, all_df) -> list:
        results = []
        cat_stats = all_df.groupby("category_id")["amount"].agg(
            ["mean", "std"]).to_dict("index")
        for _, row in anomalies.iterrows():
            cat_id  = row.get("category_id")
            amount  = row["amount"]
            reasons = []
            severity = "medium"
            if cat_id and cat_id in cat_stats:
                avg = cat_stats[cat_id]["mean"]
                std = cat_stats[cat_id]["std"] or avg * 0.3
                pct = ((amount - avg) / avg * 100) if avg > 0 else 0
                if pct > 200:
                    reasons.append(f"Cao hơn {pct:.0f}% trung bình danh mục")
                    severity = "high"
                elif pct > 80:
                    reasons.append(f"Cao hơn {pct:.0f}% trung bình danh mục")
                z = (amount - avg) / (std + 1)
                if z > 2:
                    reasons.append(f"Z-score = {z:.1f}")
                    if z > 3:
                        severity = "high"
            if row.get("hour_anomaly", 0) > 0:
                h = int(row.get("hour", 0))
                reasons.append(f"Giao dịch lúc {h:02d}:xx SA")
                severity = "high"
            if not reasons:
                reasons.append("Mẫu chi tiêu bất thường")
            risk_score = min(99, int(abs(row.get("anomaly_score", 0.1)) * 500))
            results.append({
                "id":            int(row["id"]),
                "amount":        float(amount),
                "date":          str(row["date"]),
                "category_name": str(row.get("category_name") or ""),
                "reasons":       reasons,
                "risk_score":    risk_score,
                "severity":      severity,
            })
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results
