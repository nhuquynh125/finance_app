import unittest
from app.ai.classifier import TransactionClassifier
from app.ai.anomaly_detector import AnomalyDetector
from app.data.models import init_database, DatabaseManager, get_connection
import os
from pathlib import Path

class TestAI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db = "test_ai.db"
        import config
        config.DB_PATH = Path(cls.test_db)
        DatabaseManager._instance = None
        init_database()
        cls.classifier = TransactionClassifier()
        cls.detector = AnomalyDetector()

    @classmethod
    def tearDownClass(cls):
        DatabaseManager().close()
        if os.path.exists("test_ai.db"):
            try:
                os.remove("test_ai.db")
            except:
                pass
        if os.path.exists("app/data/classifier_model.pkl"):
             # Không xóa model thật của người dùng nếu đang chạy test chung
             pass

    def test_classifier_basic(self):
        # Kiểm tra predict trả về đúng loại mong muốn
        # Lưu ý: Kết quả có thể phụ thuộc vào model hiện tại, 
        # chúng ta kiểm tra tính ổn định của hàm hơn là độ chính xác tuyệt đối ở đây.
        cat = self.classifier.predict_category_name("ăn bún bò")
        self.assertIsInstance(cat, str)
        self.assertTrue(len(cat) > 0)

    def test_anomaly_detection_logic(self):
        # Kiểm tra hàm explain_anomaly (cần có dữ liệu trong DB test)
        conn = get_connection()
        # Chèn tài khoản, danh mục và giao dịch mẫu
        conn.execute("INSERT OR IGNORE INTO accounts (id, name, balance) VALUES (1, 'Test Acc', 10000)")
        conn.execute("INSERT OR IGNORE INTO categories (id, name, type) VALUES (99, 'Test', 'expense')")
        conn.execute("INSERT INTO transactions (account_id, category_id, amount, date, type) VALUES (1, 99, 100, '2024-01-01', 'expense')")
        conn.execute("INSERT INTO transactions (account_id, category_id, amount, date, type) VALUES (1, 99, 100, '2024-01-02', 'expense')")
        conn.execute("INSERT INTO transactions (account_id, category_id, amount, date, type, created_at) VALUES (1, 99, 5000, '2024-01-03', 'expense', '2024-01-03 14:00:00')")
        conn.commit()
        
        # Lấy ID của giao dịch cuối
        tx_id = conn.execute("SELECT id FROM transactions WHERE amount=5000").fetchone()["id"]
        
        explanation = self.detector.explain_anomaly(tx_id)
        self.assertIsInstance(explanation, str)
        self.assertIn("Cao hơn", explanation) # Vì 5000 >> 100

if __name__ == "__main__":
    unittest.main()
