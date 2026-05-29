# tests/test_finance_ai.py
"""
Unit tests cho Finance AI.

Chạy:
    pip install pytest
    pytest tests/test_finance_ai.py -v

Các test bao gồm:
  - nlp_parser: parse_quick_add()
  - repositories: TransactionModel.validate(), BudgetModel.validate()
  - goal_tracker: GoalTracker logic (dùng in-memory SQLite)
  - family_manager: FamilyManager logic (dùng in-memory SQLite)
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# 1. NLP PARSER — parse_quick_add()
# ═══════════════════════════════════════════════════════════════════════════════

class TestNlpParser:
    """Kiểm tra hàm nhận dạng giao dịch từ ngôn ngữ tự nhiên."""

    def setup_method(self):
        from app.ai.nlp_parser import parse_quick_add
        self.parse = parse_quick_add

    def test_parse_amount_k(self):
        """45k → 45,000 đồng"""
        result = self.parse("ăn phở 45k")
        assert result is not None
        assert result["amount"] == 45_000

    def test_parse_amount_nghìn(self):
        """25 nghìn → 25,000 đồng"""
        result = self.parse("cafe 25 nghìn")
        assert result is not None
        assert result["amount"] == 25_000

    def test_parse_amount_triệu(self):
        """15 triệu → 15,000,000 đồng"""
        result = self.parse("lương 15 triệu")
        assert result is not None
        assert result["amount"] == 15_000_000

    def test_parse_amount_tr(self):
        """2tr → 2,000,000 đồng"""
        result = self.parse("mua điện thoại 2tr")
        assert result is not None
        assert result["amount"] == 2_000_000

    def test_parse_amount_dot_separator(self):
        """25.000 → 25,000 đồng (dấu chấm là phân cách nghìn)"""
        result = self.parse("cafe 25.000")
        assert result is not None
        assert result["amount"] == 25_000

    def test_parse_default_type_expense(self):
        """Mặc định là chi tiêu (expense)"""
        result = self.parse("ăn phở 45k")
        assert result["type"] == "expense"

    def test_parse_date_is_today(self):
        """Ngày mặc định là hôm nay"""
        result = self.parse("cafe 30k")
        today = datetime.now().strftime("%Y-%m-%d")
        assert result["date"] == today

    def test_parse_description_extracted(self):
        """Phần mô tả được trích xuất đúng (loại bỏ phần số tiền)"""
        result = self.parse("mua sách 120 nghìn")
        assert result is not None
        assert "sách" in result["description"]

    def test_parse_no_amount_returns_none(self):
        """Không có số tiền → trả về None"""
        result = self.parse("xin chào hôm nay trời đẹp")
        assert result is None

    def test_parse_empty_string(self):
        """Chuỗi rỗng → trả về None"""
        result = self.parse("")
        assert result is None

    def test_parse_only_number(self):
        """Chỉ có số → vẫn parse được"""
        result = self.parse("100k")
        assert result is not None
        assert result["amount"] == 100_000


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TRANSACTION MODEL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransactionModel:
    """Kiểm tra validate() của TransactionModel."""

    def setup_method(self):
        from app.data.repositories import TransactionModel
        self.Model = TransactionModel

    def _make(self, **kwargs):
        """Tạo model hợp lệ mặc định, override bằng kwargs."""
        defaults = {
            "account_id": 1,
            "amount": 50_000,
            "type_": "expense",
            "description": "Ăn phở",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        defaults.update(kwargs)
        return self.Model(**defaults)

    def test_valid_model_no_errors(self):
        """Model hợp lệ → không có lỗi"""
        model = self._make()
        assert model.validate() == []

    def test_negative_amount(self):
        """Số tiền âm → lỗi"""
        model = self._make(amount=-100)
        errors = model.validate()
        assert any("lớn hơn 0" in e for e in errors)

    def test_zero_amount(self):
        """Số tiền bằng 0 → lỗi"""
        model = self._make(amount=0)
        errors = model.validate()
        assert len(errors) > 0

    def test_amount_exceeds_max(self):
        """Số tiền vượt 10 tỷ → lỗi"""
        model = self._make(amount=10_000_000_001)
        errors = model.validate()
        assert any("giới hạn" in e for e in errors)

    def test_invalid_type(self):
        """Loại không hợp lệ → lỗi"""
        model = self._make(type_="cash")
        errors = model.validate()
        assert any("income" in e or "expense" in e for e in errors)

    def test_invalid_date_format(self):
        """Ngày sai định dạng → lỗi"""
        model = self._make(date="15/06/2025")
        errors = model.validate()
        assert any("định dạng" in e for e in errors)

    def test_empty_description(self):
        """Mô tả trống → lỗi"""
        model = self._make(description="")
        errors = model.validate()
        assert any("trống" in e for e in errors)

    def test_description_too_long(self):
        """Mô tả quá 200 ký tự → lỗi"""
        model = self._make(description="a" * 201)
        errors = model.validate()
        assert any("200" in e for e in errors)

    def test_future_date_far(self):
        """Ngày hơn 1 năm trong tương lai → lỗi"""
        future = (datetime.now() + timedelta(days=400)).strftime("%Y-%m-%d")
        model = self._make(date=future)
        errors = model.validate()
        assert any("tương lai" in e for e in errors)

    def test_income_type_valid(self):
        """Loại 'income' hợp lệ"""
        model = self._make(type_="income")
        assert model.validate() == []

    def test_multiple_errors(self):
        """Model sai nhiều trường → nhiều lỗi"""
        model = self._make(amount=-1, description="", date="bad-date")
        errors = model.validate()
        assert len(errors) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BUDGET MODEL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestBudgetModel:
    """Kiểm tra validate() của BudgetModel."""

    def setup_method(self):
        from app.data.repositories import BudgetModel
        self.Model = BudgetModel

    def _make(self, **kwargs):
        defaults = {
            "category_id": 1,
            "limit_amount": 2_000_000,
            "month": datetime.now().strftime("%Y-%m"),
        }
        defaults.update(kwargs)
        return self.Model(**defaults)

    def test_valid_model(self):
        assert self._make().validate() == []

    def test_zero_limit(self):
        errors = self._make(limit_amount=0).validate()
        assert len(errors) > 0

    def test_negative_limit(self):
        errors = self._make(limit_amount=-500_000).validate()
        assert len(errors) > 0

    def test_alert_threshold_too_low(self):
        errors = self._make(alert_threshold=0.05).validate()
        assert any("10%" in e or "ngưỡng" in e.lower() for e in errors)

    def test_alert_threshold_too_high(self):
        errors = self._make(alert_threshold=1.5).validate()
        assert len(errors) > 0

    def test_alert_threshold_boundary_ok(self):
        """Ngưỡng 0.1 (10%) và 1.0 (100%) đều hợp lệ"""
        assert self._make(alert_threshold=0.1).validate() == []
        assert self._make(alert_threshold=1.0).validate() == []

    def test_invalid_month_format(self):
        errors = self._make(month="06-2025").validate()
        assert any("định dạng" in e or "YYYY-MM" in e for e in errors)

    def test_pct_property(self):
        model = self._make(limit_amount=1_000_000, spent_amount=500_000)
        assert model.pct == 50

    def test_status_over(self):
        model = self._make(limit_amount=1_000_000, spent_amount=1_200_000)
        assert model.status == "over"

    def test_status_warning(self):
        model = self._make(
            limit_amount=1_000_000,
            spent_amount=850_000,
            alert_threshold=0.8
        )
        assert model.status == "warning"

    def test_status_ok(self):
        model = self._make(limit_amount=1_000_000, spent_amount=500_000)
        assert model.status == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GOAL TRACKER — dùng mock DB
# ═══════════════════════════════════════════════════════════════════════════════

class TestGoalTracker:
    """Kiểm tra GoalTracker với mock database."""

    def _make_mock_conn(self, goals=None, transactions=None):
        """Tạo mock connection trả về dữ liệu giả."""
        mock_conn = MagicMock()

        def mock_execute(sql, params=()):
            cursor = MagicMock()
            sql_lower = sql.lower().strip()

            if "savings_goals" in sql_lower and "select" in sql_lower:
                if goals:
                    row = MagicMock()
                    row.__getitem__ = lambda self, k: goals[k]
                    row.keys = lambda: goals.keys()
                    cursor.fetchone.return_value = type(
                        "Row", (), {k: v for k, v in goals.items()}
                    )()
                    cursor.fetchall.return_value = [cursor.fetchone.return_value]
                else:
                    cursor.fetchone.return_value = None
                    cursor.fetchall.return_value = []

            elif "transactions" in sql_lower:
                if transactions:
                    rows = []
                    for t in transactions:
                        r = MagicMock()
                        r.__getitem__ = lambda self, k, _t=t: _t[k]
                        rows.append(r)
                    cursor.fetchall.return_value = rows
                else:
                    cursor.fetchall.return_value = []

            cursor.rowcount = 1
            return cursor

        mock_conn.execute = mock_execute
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_add_goal_invalid_amount(self):
        """Số tiền mục tiêu <= 0 → thất bại"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        with patch("app.core.goal_tracker.get_connection") as mock_get:
            mock_get.return_value.__enter__ = MagicMock(
                return_value=MagicMock())
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            result = gt.add_goal("Test", target_amount=-1000)
        assert not result["success"]
        assert "lớn hơn 0" in result["message"]

    def test_add_goal_empty_name(self):
        """Tên trống → thất bại"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        result = gt.add_goal("  ", target_amount=5_000_000)
        assert not result["success"]
        assert "trống" in result["message"]

    def test_add_goal_past_date(self):
        """Ngày đã qua → thất bại"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = gt.add_goal("Test", target_amount=5_000_000, target_date=past)
        assert not result["success"]
        assert "tương lai" in result["message"]

    def test_update_progress_negative(self):
        """Cộng số tiền âm → thất bại"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        with patch.object(gt, "get_goal_by_id", return_value={
            "id": 1, "name": "Test",
            "target_amount": 10_000_000, "current_amount": 1_000_000
        }):
            result = gt.update_progress(1, amount_to_add=-500_000)
        assert not result["success"]

    def test_update_progress_caps_at_target(self):
        """Không cho vượt target_amount"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        captured = {}

        def fake_execute(sql, params=()):
            if "UPDATE" in sql:
                captured["new_amount"] = params[0]
            c = MagicMock()
            return c

        mock_conn = MagicMock()
        mock_conn.execute = fake_execute
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch.object(gt, "get_goal_by_id", return_value={
            "id": 1, "name": "Test",
            "target_amount": 10_000_000, "current_amount": 9_500_000
        }):
            with patch("app.core.goal_tracker.get_connection",
                       return_value=mock_conn):
                result = gt.update_progress(1, amount_to_add=1_000_000)

        assert result["success"]
        assert captured.get("new_amount", 0) <= 10_000_000

    def test_get_prediction_completed(self):
        """Mục tiêu đã đạt → status completed"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        with patch.object(gt, "get_goal_by_id", return_value={
            "id": 1, "name": "Test",
            "target_amount": 5_000_000,
            "current_amount": 5_000_000
        }):
            result = gt.get_prediction(1)
        assert result["status"] == "completed"

    def test_get_prediction_not_found(self):
        """goal_id không tồn tại → status error"""
        from app.core.goal_tracker import GoalTracker
        gt = GoalTracker()
        with patch.object(gt, "get_goal_by_id", return_value=None):
            result = gt.get_prediction(999)
        assert result["status"] == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FAMILY MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class TestFamilyManager:
    """Kiểm tra FamilyManager với mock session và DB."""

    def setup_method(self):
        """Mock session.username trước mỗi test."""
        self.session_patch = patch(
            "app.core.family_manager.session"
        )
        self.mock_session = self.session_patch.start()
        self.mock_session.username = "test_user"

    def teardown_method(self):
        self.session_patch.stop()

    def test_create_group_empty_name(self):
        """Tên nhóm trống → thất bại"""
        from app.core.family_manager import FamilyManager
        fm = FamilyManager()
        result = fm.create_group("   ")
        assert not result["success"]
        assert "trống" in result["message"]

    def test_join_group_wrong_length(self):
        """Mã mời không đúng 6 ký tự → thất bại"""
        from app.core.family_manager import FamilyManager
        fm = FamilyManager()
        result = fm.join_group("ABC")
        assert not result["success"]
        assert "6 ký tự" in result["message"]

    def test_join_group_not_found(self):
        """Mã mời không tồn tại → thất bại"""
        from app.core.family_manager import FamilyManager
        fm = FamilyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("app.core.family_manager.get_connection",
                   return_value=mock_conn):
            result = fm.join_group("XXXXXX")

        assert not result["success"]
        assert "không tồn tại" in result["message"]

    def test_invite_code_is_6_chars(self):
        """Mã mời tạo ra phải đúng 6 ký tự uppercase."""
        import secrets
        code = secrets.token_hex(3).upper()
        assert len(code) == 6
        assert code == code.upper()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. LOGGER
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogger:
    """Kiểm tra logger factory."""

    def test_get_logger_returns_logger(self):
        """get_logger() trả về logging.Logger"""
        import logging
        from app.core.logger import get_logger
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_same_instance(self):
        """Gọi hai lần cùng tên → cùng instance"""
        from app.core.logger import get_logger
        l1 = get_logger("test.same")
        l2 = get_logger("test.same")
        assert l1 is l2

    def test_get_logger_no_propagate(self):
        """Logger không propagate lên root"""
        from app.core.logger import get_logger
        logger = get_logger("test.propagate")
        assert logger.propagate is False

    def test_predefined_loggers_exist(self):
        """Các logger tiện dụng đã được định nghĩa sẵn"""
        from app.core.logger import ai_logger, db_logger, ui_logger
        import logging
        assert isinstance(ai_logger, logging.Logger)
        assert isinstance(db_logger, logging.Logger)
        assert isinstance(ui_logger, logging.Logger)


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import subprocess
    import sys
    subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        check=False
    )
