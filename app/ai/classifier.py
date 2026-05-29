# classifier.py  (cập nhật: per-user model path)
"""
AI Classifier phân loại giao dịch.

Thay đổi: MODEL_PATH lấy động từ user_session.session.ai_dir
mỗi user có classifier_model.pkl riêng, được train từ dữ liệu của họ.
"""

import re
import threading
from pathlib import Path
from app.data.models import get_connection


SEED_DATA = [
    ("Grab Food", "Ăn uống"),       ("ShopeeFood", "Ăn uống"),
    ("bún bò", "Ăn uống"),          ("cơm văn phòng", "Ăn uống"),
    ("cafe", "Ăn uống"),            ("trà sữa", "Ăn uống"),
    ("highlands coffee", "Ăn uống"),("KFC", "Ăn uống"),
    ("McDonald", "Ăn uống"),        ("Lotteria", "Ăn uống"),
    ("phở", "Ăn uống"),             ("cơm tấm", "Ăn uống"),
    ("Grab xe", "Di chuyển"),       ("taxi", "Di chuyển"),
    ("xăng xe", "Di chuyển"),       ("bus", "Di chuyển"),
    ("Gojek", "Di chuyển"),         ("Be", "Di chuyển"),
    ("vé máy bay", "Di chuyển"),    ("vé xe", "Di chuyển"),
    ("Shopee", "Mua sắm"),          ("Lazada", "Mua sắm"),
    ("Tiki", "Mua sắm"),            ("siêu thị", "Mua sắm"),
    ("quần áo", "Mua sắm"),         ("giày dép", "Mua sắm"),
    ("Winmart", "Mua sắm"),         ("Co.opmart", "Mua sắm"),
    ("Netflix", "Giải trí"),        ("Spotify", "Giải trí"),
    ("rạp phim", "Giải trí"),       ("game", "Giải trí"),
    ("YouTube Premium", "Giải trí"),("karaoke", "Giải trí"),
    ("tiền điện", "Hóa đơn"),       ("tiền nước", "Hóa đơn"),
    ("internet", "Hóa đơn"),        ("điện thoại", "Hóa đơn"),
    ("thuê nhà", "Hóa đơn"),        ("EVN", "Hóa đơn"),
    ("viện phí", "Y tế"),           ("thuốc", "Y tế"),
    ("khám bệnh", "Y tế"),          ("nhà thuốc", "Y tế"),
    ("học phí", "Giáo dục"),        ("sách", "Giáo dục"),
    ("khóa học", "Giáo dục"),       ("Udemy", "Giáo dục"),
    ("lương", "Lương"),             ("thưởng", "Thưởng"),
    ("freelance", "Lương"),         ("salary", "Lương"),
]


def _get_model_path() -> Path:
    """Đường dẫn classifier model của user hiện tại."""
    try:
        from user_session import session
        if session.is_logged_in:
            return session.ai_dir / "classifier_model.pkl"
    except ImportError:
        pass
    try:
        from config import DATA_DIR
        return Path(DATA_DIR) / "classifier_model.pkl"
    except ImportError:
        return Path("data") / "classifier_model.pkl"


class TransactionClassifier:
    """
    Singleton per-user: mỗi user có instance riêng với model riêng.
    Key = username (hoặc "__default__" nếu chưa đăng nhập).
    """

    _instances: dict = {}
    _lock = threading.Lock()

    def __new__(cls):
        # Key theo username để mỗi user có instance riêng
        key = cls._current_user_key()
        with cls._lock:
            if key not in cls._instances:
                inst = super(TransactionClassifier, cls).__new__(cls)
                inst.pipeline = None
                inst._user_key = key
                inst._load_or_train()
                cls._instances[key] = inst
        return cls._instances[key]

    def __init__(self):
        pass  # đã khởi tạo trong __new__

    @staticmethod
    def _current_user_key() -> str:
        try:
            from user_session import session
            return session.username if session.is_logged_in else "__default__"
        except Exception:
            return "__default__"

    @classmethod
    def reset_for_user(cls, username: str = None):
        """
        Xóa cached instance khi user đăng xuất / đổi user.
        Gọi trong AuthManager.logout().
        """
        with cls._lock:
            if username:
                cls._instances.pop(username, None)
            else:
                key = cls._current_user_key()
                cls._instances.pop(key, None)

    def predict_category_id(self, description: str):
        if self.pipeline is None:
            return None
        cat_name = self._predict_name(description)
        return self._name_to_id(cat_name)

    def predict_category_name(self, description: str) -> str:
        if self.pipeline is None:
            return "Không xác định"
        return self._predict_name(description)

    def retrain(self):
        self.pipeline = self._train()
        self._save()
        print(f"[Classifier] Retrained for user: {self._user_key}")

    def accuracy_report(self) -> str:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score

        texts, labels = self._load_training_data()
        if len(texts) < 10:
            return "Chưa đủ dữ liệu (cần ≥ 10 mẫu)"
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42)
        p = self._build_pipeline()
        p.fit(X_train, y_train)
        acc = accuracy_score(y_test, p.predict(X_test))
        return f"Accuracy: {acc:.1%} trên {len(X_test)} mẫu test"

    def _load_or_train(self):
        import pickle
        model_path = _get_model_path()
        if model_path.exists():
            try:
                with open(model_path, "rb") as f:
                    self.pipeline = pickle.load(f)
                return
            except Exception:
                pass
        self.pipeline = self._train()
        self._save()

    def _train(self):
        texts, labels = self._load_training_data()
        p = self._build_pipeline()
        p.fit(texts, labels)
        return p

    def _build_pipeline(self):
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline

        return Pipeline([
            ("tfidf", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(2, 4),
                min_df=1, max_features=5000, lowercase=True,
            )),
            ("clf", RandomForestClassifier(
                n_estimators=200, random_state=42, n_jobs=-1,
            )),
        ])

    def _load_training_data(self):
        texts  = [self._preprocess(t) for t, _ in SEED_DATA]
        labels = [label for _, label in SEED_DATA]

        # Lấy dữ liệu từ DB của user hiện tại
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT t.description, c.name as cat_name
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.description IS NOT NULL AND t.description != ''
            """).fetchall()
        for row in rows:
            texts.append(self._preprocess(row["description"]))
            labels.append(row["cat_name"])
        return texts, labels

    def _predict_name(self, description: str) -> str:
        return self.pipeline.predict([self._preprocess(description)])[0]

    def _preprocess(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _name_to_id(self, name: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM categories WHERE name=?", (name,)
            ).fetchone()
        return row["id"] if row else None

    def _save(self):
        import pickle
        model_path = _get_model_path()
        try:
            model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(model_path, "wb") as f:
                pickle.dump(self.pipeline, f)
        except Exception as e:
            print(f"[Classifier] Could not save model: {e}")
