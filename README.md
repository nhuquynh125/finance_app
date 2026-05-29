# Finance AI — Ứng dụng quản lý tài chính cá nhân thông minh

> Ứng dụng desktop PyQt6 tích hợp AI để theo dõi thu chi, dự báo chi tiêu, phát hiện giao dịch bất thường và tư vấn tài chính bằng chatbot.

---

## Mục lục

- [Giới thiệu](#giới-thiệu)
- [Tính năng nổi bật](#tính-năng-nổi-bật)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Cấu hình AI Engine](#cấu-hình-ai-engine)
- [Quản lý đa người dùng](#quản-lý-đa-người-dùng)
- [API & Tích hợp bên ngoài](#api--tích-hợp-bên-ngoài)
- [Database](#database)
- [Phát triển & Đóng góp](#phát-triển--đóng-góp)
- [Tác giả](#tác-giả)

---

## Giới thiệu

**Finance AI** là ứng dụng quản lý tài chính cá nhân được xây dựng bằng Python + PyQt6, tích hợp nhiều mô hình AI để hỗ trợ người dùng:

- Theo dõi thu nhập và chi tiêu theo danh mục
- Dự báo chi tiêu tháng tới bằng Prophet hoặc Moving Average
- Phát hiện giao dịch bất thường bằng Isolation Forest
- Chatbot AI tư vấn tài chính (Gemini API / Ollama / TinyLlama nhúng)
- Phân loại giao dịch tự động bằng ML (TF-IDF + Random Forest)
- Xuất báo cáo PDF chuyên nghiệp hàng tháng
- Quản lý nhiều tài khoản người dùng, mỗi người có database riêng biệt

---

## Tính năng nổi bật

### Dashboard
- Tổng quan thu nhập, chi tiêu, tiết kiệm theo tháng
- Biểu đồ cột thu chi 6 tháng gần nhất
- Biểu đồ tròn chi tiêu theo danh mục
- Danh sách giao dịch gần đây
- So sánh tự động với tháng trước (% tăng/giảm)

### Quản lý giao dịch
- Thêm, sửa, xóa giao dịch thủ công
- Nhập sao kê ngân hàng từ file CSV (hỗ trợ Vietcombank, BIDV, Techcombank, MB Bank, VPBank, định dạng chung)
- Xuất dữ liệu ra file Excel
- Tìm kiếm và lọc theo tháng, loại, danh mục
- Phân loại AI tự động bằng một nút bấm
- Đánh dấu và xem giao dịch bất thường

### Ngân sách
- Đặt ngân sách theo danh mục và tháng
- Theo dõi % đã chi so với ngân sách
- Cảnh báo khi sắp vượt ngưỡng (có thể tùy chỉnh)
- Gợi ý AI khi ngân sách bị vượt

### Dự báo AI
- Dự báo chi tiêu tháng tới theo từng danh mục
- Sử dụng Prophet (nếu có) hoặc Moving Average tự động
- Hiển thị khoảng tin cậy (confidence interval)
- Biểu đồ lịch sử + dự báo trực quan
- Phát hiện giao dịch bất thường bằng Isolation Forest (scikit-learn)
- Giải thích lý do bất thường (z-score, giờ giao dịch, %)

### Chatbot AI
- Hỗ trợ 3 engine: Gemini API, Ollama (offline), Model nhúng (TinyLlama)
- Phân tích dữ liệu tài chính thực tế của người dùng trong system prompt
- Quick prompts gợi ý câu hỏi thường gặp
- Nhận dạng lệnh thêm giao dịch nhanh bằng ngôn ngữ tự nhiên ("ăn phở 45k")
- Fine-tune DistilGPT2 với dữ liệu Q&A sinh từ database người dùng

### Báo cáo PDF
- Tạo báo cáo tháng đầy đủ bằng ReportLab
- Bao gồm: tổng kết thu chi, phân tích danh mục, bảng giao dịch, dự báo AI
- Biểu đồ thanh bar inline trong PDF
- Cảnh báo giao dịch bất thường
- Lịch sử file báo cáo đã tạo

### Cài đặt
- Theme Sáng / Tối / Theo hệ thống với accent color tùy chỉnh
- Quản lý API keys (Gemini, Supabase) qua file .env
- Backup, restore, xuất Excel database
- Đồng bộ cloud qua Supabase Storage
- Phím tắt toàn cục (Ctrl+K command palette, Ctrl+1~7 điều hướng)

---

## Yêu cầu hệ thống

- **Python**: 3.10 trở lên
- **Hệ điều hành**: Windows 10/11, macOS 12+, Ubuntu 20.04+
- **RAM**: Tối thiểu 4 GB (8 GB khuyến nghị nếu dùng model nhúng)
- **Ổ đĩa**: ~1 GB (chưa tính model AI)

### Thư viện bắt buộc

```
PyQt6>=6.11.0
matplotlib>=3.10.9
pandas>=3.0.2
scikit-learn>=1.8.0
numpy>=2.3.3
openpyxl>=3.1.5
reportlab>=4.5.0
python-dotenv>=1.2.2
```

### Thư viện tùy chọn (để mở khóa tính năng AI nâng cao)

| Thư viện | Tính năng |
|----------|-----------|
| `prophet` | Dự báo chính xác hơn (yêu cầu ≥3 tháng dữ liệu) |
| `torch`, `transformers`, `accelerate` | Chatbot nhúng TinyLlama, fine-tune model |
| `datasets` | Fine-tune DistilGPT2 |
| `flask` | (Dự phòng cho API nội bộ) |

---

## Cài đặt

### 1. Clone dự án

```bash
git clone https://github.com/your-repo/finance-ai.git
cd finance-ai
```

### 2. Tạo môi trường ảo

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

Để bật tính năng dự báo Prophet:

```bash
pip install prophet
```

Để bật chatbot nhúng (TinyLlama):

```bash
pip install transformers torch accelerate datasets
```

### 4. Cấu hình API (tùy chọn)

Tạo file `.env` tại thư mục gốc:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SYNC_API_URL=https://your-sync-server.com/api/sync
```

Gemini API Key miễn phí tại: https://aistudio.google.com/app/apikey

### 5. Chạy ứng dụng

```bash
python main.py
```

Lần đầu chạy, ứng dụng tự động tạo tài khoản admin mặc định:
- **Username**: `admin`
- **Password**: `admin123`

> Khuyến nghị đổi mật khẩu ngay sau khi đăng nhập lần đầu.

---

## Cấu trúc dự án

```
finance-ai/
├── main.py                     # Entry point
├── user_session.py             # Quản lý phiên đăng nhập (singleton)
├── requirements.txt
├── .env                        # API keys (tạo thủ công, không commit)
│
├── app/
│   ├── ai/                     # Tầng AI & Machine Learning
│   │   ├── base_plugin.py      # Plugin interface cho chat engine
│   │   ├── classifier.py       # Phân loại giao dịch (TF-IDF + RF)
│   │   ├── anomaly_detector.py # Phát hiện bất thường (Isolation Forest)
│   │   ├── forecaster.py       # Dự báo chi tiêu (Prophet / Moving Average)
│   │   ├── fine_tuner.py       # Fine-tune DistilGPT2
│   │   ├── embedded_llm.py     # Worker chạy TinyLlama nhúng (QThread)
│   │   ├── local_llm.py        # Worker gọi Ollama local API (QThread)
│   │   ├── gemini_worker.py    # Worker gọi Gemini API qua urllib (QThread)
│   │   └── nlp_parser.py       # Parser lệnh thêm giao dịch bằng NLP
│   │
│   ├── core/                   # Business logic & tiện ích
│   │   ├── transaction_manager.py  # CRUD giao dịch + alert ngân sách
│   │   ├── settings_manager.py     # Settings per-user + .env helpers
│   │   ├── event_bus.py            # PyQt6 signal hub (singleton bus)
│   │   ├── csv_importer.py         # Import CSV ngân hàng Việt Nam
│   │   ├── report_generator.py     # Xuất PDF bằng ReportLab
│   │   ├── sync_manager.py         # Đồng bộ cloud (Supabase / custom API)
│   │   ├── error_handler.py        # Global exception handler
│   │   └── theme_engine.py         # Light/Dark theme + accent color
│   │
│   ├── data/                   # Tầng dữ liệu
│   │   ├── models.py           # DatabaseManager (per-user SQLite)
│   │   ├── repositories.py     # Repository pattern (TransactionRepo, BudgetRepo…)
│   │   └── auth_manager.py     # Đăng nhập, đăng ký, đổi mật khẩu
│   │
│   └── ui/                     # Giao diện người dùng PyQt6
│       ├── main_window.py      # Cửa sổ chính + Sidebar
│       ├── login_window.py     # Màn hình đăng nhập / đăng ký
│       ├── dashboard_frame.py  # Trang tổng quan
│       ├── transaction_frame.py# Trang quản lý giao dịch
│       ├── budget_frame.py     # Trang ngân sách
│       ├── forecast_frame.py   # Trang dự báo AI
│       ├── chatbot_frame.py    # Trang chatbot AI
│       ├── report_frame.py     # Trang báo cáo PDF
│       ├── settings_frame.py   # Trang cài đặt
│       ├── family_frame.py     # Trang quản lý nhóm gia đình
│       ├── notification.py     # Toast notification system
│       └── command_palette.py  # Command palette (Ctrl+K)
│
├── data/                       # Thư mục dữ liệu (tự sinh khi chạy)
│   ├── shared/
│   │   ├── auth.db             # Database xác thực dùng chung
│   │   └── session.json        # Phiên ghi nhớ đăng nhập
│   └── users/
│       └── {username}/
│           ├── finance.db      # Database tài chính riêng của user
│           ├── settings.json   # Cài đặt riêng của user
│           ├── backups/        # Backup database
│           ├── exports/        # File PDF, Excel xuất ra
│           └── ai/
│               ├── classifier_model.pkl    # Model phân loại đã train
│               └── fine_tuned_model/       # Model DistilGPT2 đã fine-tune
│
└── migrate_to_per_user_db.py   # Script migration từ DB chung sang per-user
```

---

## Kiến trúc hệ thống

### Tổng quan

```
┌─────────────────────────────────────────────────────┐
│                   PyQt6 UI Layer                     │
│  MainWindow → Sidebar → [Frame1, Frame2, ..., FrameN]│
└──────────────────────┬──────────────────────────────┘
                       │ signals / slots
              ┌────────▼────────┐
              │   Event Bus     │  ← bus (singleton QObject)
              │ (pub/sub hub)   │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Core Layer   │ │  AI Layer    │ │  Data Layer  │
│ TxManager    │ │ Classifier   │ │ DatabaseMgr  │
│ Settings     │ │ Forecaster   │ │ Repositories │
│ EventBus     │ │ AnomalyDet.  │ │ AuthManager  │
│ ReportGen    │ │ ChatWorkers  │ │ UserSession  │
└──────────────┘ └──────────────┘ └──────────────┘
                                         │
                              ┌──────────▼─────────┐
                              │   SQLite Database   │
                              │ data/shared/auth.db │
                              │ data/users/{u}/*.db │
                              └────────────────────┘
```

### Event Bus

Các frame UI không gọi trực tiếp vào nhau. Thay vào đó, mọi thay đổi dữ liệu được phát qua `bus` (singleton `_EventBus`):

```python
from app.core.event_bus import bus

# Phát sự kiện
bus.transaction_added.emit()
bus.budget_updated.emit("2025-06")

# Đăng ký lắng nghe
bus.transaction_added.connect(self.refresh)
bus.theme_changed.connect(self._apply_theme)
```

Danh sách signals chính:

| Signal | Kiểu | Mô tả |
|--------|------|-------|
| `transaction_added` | – | Giao dịch mới được thêm |
| `transaction_updated` | int (id) | Giao dịch được sửa |
| `transaction_deleted` | int (id) | Giao dịch bị xóa |
| `budget_updated` | str (month) | Ngân sách thay đổi |
| `ai_forecast_done` | list | Dự báo AI hoàn tất |
| `ai_anomaly_done` | list | Phát hiện bất thường xong |
| `theme_changed` | str | Theme được đổi |
| `navigate_to` | str | Điều hướng tới trang |
| `notify_success/warning/error/info` | str, str | Hiện toast notification |

### Per-user Database

Mỗi người dùng có một file SQLite riêng tại `data/users/{username}/finance.db`. `DatabaseManager` là singleton tự động chuyển connection khi đổi user:

```python
from app.data.models import get_connection

conn = get_connection()   # trả về connection của user đang đăng nhập
```

---

## Hướng dẫn sử dụng

### Đăng nhập lần đầu

1. Chạy `python main.py`
2. Đăng nhập với `admin / admin123`
3. Hoặc nhấn **Đăng ký ngay** để tạo tài khoản mới

### Thêm giao dịch

**Cách 1 — Thủ công:**
- Nhấn **+ Thêm mới** ở trang Giao dịch hoặc Dashboard
- Điền loại (Thu/Chi), mô tả, số tiền, ngày, danh mục

**Cách 2 — Nhập CSV ngân hàng:**
- Nhấn **Nhập CSV** và chọn file sao kê
- App tự nhận dạng định dạng ngân hàng (Vietcombank, BIDV, Techcombank, MB Bank, VPBank)

**Cách 3 — Lệnh nhanh qua chatbot:**
- Gõ trong chatbot: `"ăn phở 45k"`, `"mua sách 120 nghìn"`, `"lương 15 triệu"`
- App tự nhận dạng và gợi ý thêm giao dịch

### Phím tắt

| Phím tắt | Hành động |
|----------|-----------|
| `Ctrl+K` | Mở command palette |
| `Ctrl+N` | Thêm giao dịch mới |
| `Ctrl+1` | Dashboard |
| `Ctrl+2` | Giao dịch |
| `Ctrl+3` | Ngân sách |
| `Ctrl+4` | Dự báo AI |
| `Ctrl+5` | Chatbot AI |
| `Ctrl+6` | Báo cáo |
| `Ctrl+7` | Cài đặt |
| `Ctrl+,` | Cài đặt (alias) |
| `F5` | Làm mới trang hiện tại |

### Thiết lập ngân sách

1. Vào trang **Ngân sách**
2. Chọn tháng cần đặt
3. Nhấn **+ Đặt ngân sách**
4. Chọn danh mục, nhập số tiền và ngưỡng cảnh báo (mặc định 80%)
5. App sẽ tự cảnh báo khi chi tiêu vượt ngưỡng

### Chạy dự báo AI

1. Vào trang **Dự báo**
2. Nhấn **Chạy dự báo AI** — app dự báo cho tất cả danh mục chi tiêu
3. Kết quả hiển thị trên biểu đồ và bảng danh mục
4. Nhấn **Phát hiện bất thường** để quét giao dịch bất thường trong tháng

---

## Cấu hình AI Engine

App hỗ trợ 3 engine chatbot có thể chuyển đổi ngay trong giao diện:

### 1. Gemini API (Google) — Khuyến nghị cho chất lượng tốt nhất

**Yêu cầu:** Kết nối internet + Gemini API Key

```env
# .env
GEMINI_API_KEY=your_key_here
```

Lấy key miễn phí tại: https://aistudio.google.com/app/apikey

Model mặc định: `gemini-1.5-flash` (thay đổi trong `config.py`)

### 2. Ollama — Tốt nhất cho offline

**Yêu cầu:** Cài Ollama từ https://ollama.com

```bash
# Cài Ollama (Windows/macOS: tải installer)
# Ubuntu:
curl -fsSL https://ollama.com/install.sh | sh

# Tải model (3B params, ~2GB)
ollama pull qwen2.5:3b

# Khởi chạy server
ollama serve
```

App tự động phát hiện Ollama đang chạy và chọn model phù hợp.

### 3. Model nhúng (TinyLlama) — Hoàn toàn offline, tự chứa

**Yêu cầu:** Cài thư viện AI:

```bash
pip install transformers torch accelerate
```

Lần đầu chạy tự động tải TinyLlama (~600 MB). Có thể fine-tune thêm bằng dữ liệu của người dùng:

1. Cài thêm: `pip install datasets`
2. Trong chatbot, nhấn **Train model**
3. App tạo dữ liệu Q&A từ lịch sử giao dịch và train DistilGPT2 (~5-15 phút)

---

## Quản lý đa người dùng

### Kiến trúc per-user

Mỗi tài khoản có:
- Database tài chính riêng biệt (`data/users/{username}/finance.db`)
- Cài đặt riêng (`settings.json`)
- Model AI riêng (`classifier_model.pkl`, `fine_tuned_model/`)
- Thư mục backup và export riêng

Database xác thực (`data/shared/auth.db`) được dùng chung cho tất cả users.

### Đăng ký tài khoản mới

Từ màn hình đăng nhập, nhấn **Đăng ký ngay** và điền:
- Họ và tên
- Tên đăng nhập (3–30 ký tự)
- Mật khẩu (tối thiểu 6 ký tự)

### Quên mật khẩu

Nhấn **Quên mật khẩu?** trên màn hình đăng nhập, nhập tên đăng nhập và đặt mật khẩu mới.

### Migration từ phiên bản cũ (DB chung)

Nếu bạn đang nâng cấp từ phiên bản dùng một DB chung, chạy:

```bash
python migrate_to_per_user_db.py
```

Script sẽ:
1. Sao lưu `data/finance.db` → `data/finance.db.bak`
2. Tạo `data/shared/auth.db` với bảng users
3. Tạo DB riêng cho từng user tại `data/users/{username}/finance.db`
4. Copy dữ liệu giao dịch theo `owner_username` (hoặc gán toàn bộ cho admin nếu không có cột này)

---

## API & Tích hợp bên ngoài

### Gemini API

App gọi trực tiếp `generativelanguage.googleapis.com` qua `urllib` (không cần thư viện bên thứ ba):

```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent
```

Hỗ trợ streaming (SSE), system prompt, conversation history.

### Ollama Local API

```
POST http://localhost:11434/api/chat
```

App tự động phát hiện models đã cài và ưu tiên models không có từ "cloud".

### Supabase Cloud Sync

Cấu hình trong `.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_or_service_key
```

App upload toàn bộ `finance.db` lên Supabase Storage bucket `backups`.

### Custom Sync API

```env
SYNC_API_URL=https://your-server.com/api/sync
```

App gửi database dưới dạng base64 JSON qua POST.

---

## Database

### Schema chính (`finance.db` per-user)

```sql
-- Tài khoản (tiền mặt, ngân hàng...)
CREATE TABLE accounts (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    type       TEXT DEFAULT 'cash',
    balance    REAL DEFAULT 0,
    currency   TEXT DEFAULT 'VND',
    created_at TEXT
);

-- Danh mục (Ăn uống, Di chuyển, Lương...)
CREATE TABLE categories (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    type      TEXT NOT NULL,       -- 'income' | 'expense'
    color     TEXT DEFAULT '#378ADD',
    icon      TEXT DEFAULT 'circle',
    parent_id INTEGER
);

-- Giao dịch
CREATE TABLE transactions (
    id                  INTEGER PRIMARY KEY,
    account_id          INTEGER NOT NULL,
    category_id         INTEGER,
    amount              REAL NOT NULL,
    type                TEXT NOT NULL,   -- 'income' | 'expense'
    description         TEXT,
    date                TEXT NOT NULL,   -- 'YYYY-MM-DD'
    note                TEXT,
    is_anomaly          INTEGER DEFAULT 0,
    is_anomaly_feedback INTEGER DEFAULT 0,
    owner_username      TEXT,
    created_at          TEXT
);

-- Ngân sách theo tháng
CREATE TABLE budgets (
    id              INTEGER PRIMARY KEY,
    category_id     INTEGER,
    limit_amount    REAL NOT NULL,
    spent_amount    REAL DEFAULT 0,
    month           TEXT NOT NULL,  -- 'YYYY-MM'
    alert_threshold REAL DEFAULT 0.8
);

-- Dự báo AI
CREATE TABLE ai_predictions (
    id               INTEGER PRIMARY KEY,
    category_id      INTEGER,
    predicted_amount REAL,
    month            TEXT,
    confidence       REAL,
    created_at       TEXT
);

-- Lịch sử chat
CREATE TABLE chat_history (
    id         INTEGER PRIMARY KEY,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT
);

-- Mục tiêu tiết kiệm
CREATE TABLE savings_goals (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    target_amount  REAL NOT NULL,
    current_amount REAL DEFAULT 0,
    target_date    TEXT,
    color          TEXT DEFAULT '#1D9E75'
);
```

### Schema xác thực (`auth.db` dùng chung)

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    full_name     TEXT DEFAULT '',
    role          TEXT DEFAULT 'user',  -- 'user' | 'admin'
    is_active     INTEGER DEFAULT 1,
    last_login    TEXT,
    created_at    TEXT
);
```

Mật khẩu được hash bằng SHA-256 với salt ngẫu nhiên 16 bytes (hex).

### Indexes hiệu năng

```sql
CREATE INDEX idx_tx_date        ON transactions(date);
CREATE INDEX idx_tx_category    ON transactions(category_id);
CREATE INDEX idx_tx_type        ON transactions(type);
CREATE INDEX idx_tx_date_type   ON transactions(date, type);
CREATE INDEX idx_budget_month   ON budgets(month);
CREATE INDEX idx_pred_month     ON ai_predictions(month);
```

---

## Phát triển & Đóng góp

### Thêm AI Plugin mới

Tạo class kế thừa `BaseAIPlugin` trong `app/ai/base_plugin.py`:

```python
from app.ai.base_plugin import BaseAIPlugin, BaseAIWorker, registry

class MyCustomPlugin(BaseAIPlugin):
    engine_id    = "my_engine"
    engine_label = "My Custom Engine"
    requires_internet = False

    def create_worker(self, messages, system_prompt) -> BaseAIWorker:
        return MyWorker(messages, system_prompt)

    def check_status(self) -> tuple[bool, str]:
        return True, "Sẵn sàng"

# Đăng ký vào registry
registry.register(MyCustomPlugin())
```

### Thêm trang mới vào MainWindow

Trong `app/ui/main_window.py`, thêm vào `_create_page()`:

```python
#if page == "Trang mới":
#    from app.ui.my_frame import MyFrame
#    return MyFrame(main_window=self)
```

Và thêm vào dictionary `sections` trong `Sidebar._build()`.

### Sử dụng Event Bus trong Widget mới

```python
from app.core.event_bus import bus, BusConnectMixin

class MyFrame(QWidget, BusConnectMixin):
    def __init__(self):
        super().__init__()
        self._connect_bus()

    def _connect_bus(self):
        bus.transaction_added.connect(self.refresh)
        bus.balance_changed.connect(self._update_balance)
```

### Chạy tests

```bash
# Chưa có test suite chính thức — đóng góp bằng cách thêm tests
python -m pytest tests/
```

---

## Tác giả

**Finance AI** được phát triển bởi:

| Tên | Mã số sinh viên |
|-----|----------------|
| Như Quỳnh | 25AI043 |
| Hưng Phú | 25AI034 |

---

## License

Dự án này được phát triển phục vụ mục đích học tập.

---

*README cập nhật lần cuối: Tháng 5/2026*
