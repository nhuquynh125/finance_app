# app/core/csv_importer.py
"""
Nhập sao kê CSV từ ngân hàng Việt Nam.
Hỗ trợ: Vietcombank, BIDV, Techcombank, MB Bank, VPBank, định dạng chung.
"""
import pandas as pd
import re
from datetime import datetime
from app.data.models import get_connection

BANK_PROFILES = {
    "vietcombank": {
        "detect_keywords": ["vietcombank", "vcb"],
        "col_date":    ["posting date", "ngày giao dịch", "transaction date"],
        "col_desc":    ["transaction description", "diễn giải", "nội dung"],
        "col_debit":   ["debit", "phát sinh nợ", "tiền ra"],
        "col_credit":  ["credit", "phát sinh có", "tiền vào"],
        "col_amount":  [],
        "col_type":    [],
        "date_formats":["'%d/%m/%Y'", "%Y-%m-%d"],
        "encoding":    "utf-8-sig",
        "skiprows":    0,
    },
    "bidv": {
        "detect_keywords": ["bidv"],
        "col_date":    ["ngày hiệu lực", "value date", "ngày gd"],
        "col_desc":    ["mô tả", "nội dung giao dịch", "description"],
        "col_debit":   ["ghi nợ", "debit amount"],
        "col_credit":  ["ghi có", "credit amount"],
        "col_amount":  [],
        "col_type":    [],
        "date_formats":["%d/%m/%Y", "%d-%m-%Y"],
        "encoding":    "utf-8-sig",
        "skiprows":    0,
    },
    "techcombank": {
        "detect_keywords": ["techcombank", "tcb"],
        "col_date":    ["ngày giao dịch", "transaction date", "ngày"],
        "col_desc":    ["mô tả giao dịch", "nội dung", "diễn giải"],
        "col_debit":   ["số tiền ghi nợ", "debit", "tiền ra"],
        "col_credit":  ["số tiền ghi có", "credit", "tiền vào"],
        "col_amount":  ["số tiền", "amount"],
        "col_type":    ["loại giao dịch", "type"],
        "date_formats":["%d/%m/%Y", "%Y-%m-%d"],
        "encoding":    "utf-8-sig",
        "skiprows":    0,
    },
    "mbbank": {
        "detect_keywords": ["mbbank", "mb bank", "military bank"],
        "col_date":    ["ngày gd", "ngày giao dịch", "transaction date"],
        "col_desc":    ["nội dung", "mô tả", "description"],
        "col_debit":   ["số tiền ghi nợ", "debit", "tiền ra"],
        "col_credit":  ["số tiền ghi có", "credit", "tiền vào"],
        "col_amount":  ["số tiền", "amount"],
        "col_type":    ["loại", "type"],
        "date_formats":["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"],
        "encoding":    "utf-8-sig",
        "skiprows":    0,
    },
    "vpbank": {
        "detect_keywords": ["vpbank"],
        "col_date":    ["ngày gd", "ngày giao dịch", "posting date"],
        "col_desc":    ["mô tả", "nội dung giao dịch", "description"],
        "col_debit":   ["tiền ra", "debit", "ghi nợ"],
        "col_credit":  ["tiền vào", "credit", "ghi có"],
        "col_amount":  ["số tiền", "amount"],
        "col_type":    ["loại", "type"],
        "date_formats":["%d/%m/%Y", "%Y-%m-%d"],
        "encoding":    "utf-8-sig",
        "skiprows":    0,
    },
    "generic": {
        "detect_keywords": [],
        "col_date":    ["date", "ngày", "ngay", "transaction_date"],
        "col_desc":    ["description", "mô tả", "mo ta", "nội dung", "content"],
        "col_debit":   ["debit", "phát sinh nợ", "chi", "tiền ra"],
        "col_credit":  ["credit", "phát sinh có", "thu", "tiền vào"],
        "col_amount":  ["amount", "số tiền", "so tien", "value"],
        "col_type":    ["type", "loại", "loai"],
        "date_formats":["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"],
        "encoding":    "utf-8-sig",
        "skiprows":    0,
    },
}


class CsvImporter:

    def import_file(self, path: str, bank: str = "auto",
                    account_id: int = 1):
        """
        Returns (count: int, warnings: list[str]).
        Raises RuntimeError on DB failure.
        """
        warnings_list = []
        if bank == "auto":
            bank = self._detect_bank(path)
            warnings_list.append(f"Phát hiện định dạng: {bank.upper()}")
        profile = BANK_PROFILES.get(bank, BANK_PROFILES["generic"])
        df = self._read_csv(path, profile)
        if df is None or df.empty:
            raise ValueError("Không đọc được file CSV hoặc file rỗng.")
        warnings_list.append(f"Đọc được {len(df)} dòng.")
        df, col_map = self._map_columns(df, profile)
        df = self._normalize(df, col_map, profile)
        valid = df.dropna(subset=["amount", "date"])
        valid = valid[valid["amount"] > 0]
        warnings_list.append(f"Hợp lệ: {len(valid)} giao dịch.")
        count = self._save_to_db(valid, account_id)
        return count, warnings_list

    def _detect_bank(self, path: str) -> str:
        filename = path.lower()
        for bank, profile in BANK_PROFILES.items():
            if bank == "generic":
                continue
            for kw in profile["detect_keywords"]:
                if kw in filename:
                    return bank
        try:
            with open(path, encoding="utf-8-sig", errors="ignore") as f:
                content = f.read(500).lower()
            for bank, profile in BANK_PROFILES.items():
                if bank == "generic":
                    continue
                for kw in profile["detect_keywords"]:
                    if kw in content:
                        return bank
        except Exception:
            pass
        return "generic"

    def _read_csv(self, path: str, profile: dict):
        for enc in [profile.get("encoding", "utf-8-sig"), "utf-8", "latin-1"]:
            try:
                df = pd.read_csv(path, encoding=enc,
                                 skiprows=profile.get("skiprows", 0),
                                 thousands=",", low_memory=False)
                df.columns = [str(c).strip().lower() for c in df.columns]
                return df.dropna(how="all")
            except Exception:
                continue
        return None

    def _map_columns(self, df, profile):
        cols = list(df.columns)
        mapping = {}

        def find_col(candidates):
            for cand in candidates:
                cl = cand.lower()
                for col in cols:
                    if cl in col or col in cl:
                        return col
            return None

        mapping["date"]   = find_col(profile["col_date"])
        mapping["desc"]   = find_col(profile["col_desc"])
        mapping["debit"]  = find_col(profile["col_debit"])
        mapping["credit"] = find_col(profile["col_credit"])
        mapping["amount"] = find_col(profile["col_amount"])
        mapping["type"]   = find_col(profile["col_type"])
        return df, mapping

    def _normalize(self, df, col_map, profile):
        result = pd.DataFrame()
        date_col = col_map.get("date")
        if date_col and date_col in df.columns:
            result["date"] = df[date_col].apply(
                lambda x: self._parse_date(str(x), profile["date_formats"]))
        else:
            result["date"] = None
        desc_col = col_map.get("desc")
        result["description"] = (
            df[desc_col].fillna("").astype(str).str.strip()
            if desc_col and desc_col in df.columns else "")
        debit_col  = col_map.get("debit")
        credit_col = col_map.get("credit")
        amount_col = col_map.get("amount")
        type_col   = col_map.get("type")
        if debit_col and credit_col and debit_col in df.columns and credit_col in df.columns:
            debit  = df[debit_col].apply(self._parse_amount)
            credit = df[credit_col].apply(self._parse_amount)
            result["amount"] = debit.where(debit > 0, credit)
            result["type"]   = "income"
            result.loc[debit > 0,  "type"] = "expense"
            result.loc[credit > 0, "type"] = "income"
        elif amount_col and amount_col in df.columns:
            result["amount"] = df[amount_col].apply(self._parse_amount)
            if type_col and type_col in df.columns:
                result["type"] = df[type_col].apply(
                    lambda x: "income"
                    if str(x).lower() in ("credit", "thu", "income", "có", "+")
                    else "expense")
            else:
                result["type"] = "expense"
        else:
            result["amount"] = 0
            result["type"]   = "expense"
        result["amount"] = result["amount"].clip(lower=0)
        return result

    def _save_to_db(self, df, account_id: int) -> int:
        """
        Insert all rows in a single transaction.
        Rolls back entirely on any error to avoid partial data.
        """
        conn = get_connection()
        count = 0
        try:
            for _, row in df.iterrows():
                conn.execute("""
                    INSERT INTO transactions (account_id, amount, type, description, date)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, float(row["amount"]), str(row["type"]),
                      str(row["description"])[:200], str(row["date"])))
                delta = row["amount"] if row["type"] == "income" else -row["amount"]
                conn.execute("UPDATE accounts SET balance=balance+? WHERE id=?",
                             (delta, account_id))
                count += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Import thất bại: {e}") from e
        finally:
            conn.close()
        return count

    @staticmethod
    def _parse_date(value: str, formats: list):
        value = re.split(r"\s+", value.strip())[0]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(value) -> float:
        if pd.isna(value):
            return 0.0
        s = re.sub(r"[^\d.,\-]", "", str(value).strip())
        if s.count(".") > 1:
            s = s.replace(".", "")
        elif "," in s and "." in s:
            if s.index(",") < s.index("."):
                s = s.replace(",", "")
            else:
                s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", "")
        try:
            return abs(float(s))
        except ValueError:
            return 0.0
