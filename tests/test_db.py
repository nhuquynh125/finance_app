import unittest
import os
import sqlite3
from pathlib import Path
from app.data.models import get_connection, init_database, DatabaseManager

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Sử dụng database tạm thời cho test
        self.test_db = "test_finance.db"
        import config
        config.DB_PATH = Path(self.test_db)
        # Reset singleton cho mỗi test nếu cần
        DatabaseManager._instance = None
        init_database()

    def tearDown(self):
        # Không đóng connection ở đây nếu nó dùng chung Singleton
        pass

    @classmethod
    def tearDownClass(cls):
        DatabaseManager().close()
        if os.path.exists("test_finance.db"):
            try:
                os.remove("test_finance.db")
            except:
                pass

    def test_connection_singleton(self):
        conn1 = get_connection()
        conn2 = get_connection()
        self.assertIs(conn1, conn2)

    def test_initial_categories(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM categories")
        count = cursor.fetchone()[0]
        self.assertGreater(count, 0)

if __name__ == "__main__":
    unittest.main()
