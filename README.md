# Finance AI 💰

Ứng dụng quản lý tài chính cá nhân thông minh, xây dựng bằng **Python + PyQt6**, tích hợp AI phân loại giao dịch, dự báo chi tiêu, phát hiện giao dịch bất thường và chatbot tư vấn tài chính hoạt động hoàn toàn offline.

---

## Mục lục

- [Tính năng chính](#tính-năng-chính)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Hệ thống tài khoản người dùng](#hệ-thống-tài-khoản-người-dùng)
- [Module AI](#module-ai)
- [Cơ sở dữ liệu](#cơ-sở-dữ-liệu)
- [API & Tích hợp bên ngoài](#api--tích-hợp-bên-ngoài)
- [Cấu hình nâng cao](#cấu-hình-nâng-cao)
- [Phím tắt](#phím-tắt)
- [Migration dữ liệu](#migration-dữ-liệu)
- [Phát triển & Đóng góp](#phát-triển--đóng-góp)
- [Thông tin nhóm](#thông-tin-nhóm)

---

## Tính năng chính

### 📊 Dashboard
- Tổng quan thu chi tháng với 4 KPI card (Thu nhập, Chi tiêu, Tiết kiệm, Dự báo AI)
- Biểu đồ thu chi 6 tháng gần nhất (bar chart)
- Biểu đồ phân bổ danh mục chi tiêu (pie chart)
- Danh sách giao dịch gần đây với hiệu ứng highlight bất thường
- Chọn tháng để xem lịch sử

### 💳 Quản lý Giao dịch
- Thêm/Sửa/Xóa giao dịch với form đầy đủ (loại, mô tả, số tiền, ngày, danh mục, tài khoản, ghi chú)
- Nhập hàng loạt từ file CSV của các ngân hàng Việt Nam (Vietcombank, BIDV, Techcombank, MB Bank, VPBank, và định dạng chung)
- Xuất báo cáo ra Excel
- Bộ lọc đa chiều: tháng, loại giao dịch, danh mục, tìm kiếm theo mô tả
- Phân trang tự động (100 giao dịch/trang) cho bộ dữ liệu lớn
- Phản hồi AI (xác nhận/bỏ qua) cho giao dịch bất thường
- Phân loại AI tự động khi nhập CSV

### 💸 Quản lý Chi tiêu
- Biểu đồ donut thuần PyQt không cần matplotlib — hiển thị phân bổ chi tiêu theo danh mục
- Xu hướng chi tiêu 3 tháng (bar chart)
- Điều hướng tháng (quay lại/tiến tới)
- Danh sách danh mục con / cha, xem thêm / thu gọn
- Cảnh báo tăng chi tiêu bất thường so với tháng trước
- Mini card ngân sách inline với gợi ý AI

### 💰 Ngân sách
- Đặt hạn mức ngân sách theo danh mục và tháng
- Progress bar trực quan với badge trạng thái (Bình thường / Sắp hết / Vượt ngân sách)
- Ngưỡng cảnh báo tùy chỉnh (mặc định 80%)
- Đồng bộ chi tiêu thực tế từ giao dịch tự động
- AI Tips gợi ý tối ưu ngân sách dựa trên dữ liệu thực

### 📈 Dự báo AI
- Dự báo chi tiêu tháng tới theo từng danh mục
- Hỗ trợ 2 phương pháp: **Facebook Prophet** (nếu đã cài) hoặc **Trung bình trượt (Moving Average)**
- Biểu đồ lịch sử & dự báo với khoảng tin cậy
- Thanh bar phân bổ danh mục dự báo
- Phát hiện giao dịch bất thường bằng **Isolation Forest** (sklearn)
- Điểm rủi ro (risk score) và giải thích lý do bất thường

### 🤖 Chatbot AI (Offline)
- Hoàn toàn không cần internet hay API key
- Nhận dạng ý định (intent recognition) bằng regex pattern matching
- Trả lời các câu hỏi: thu nhập, chi tiêu, tiết kiệm, số dư, xu hướng, dự báo, ngân sách, bất thường
- Tạo lời khuyên tài chính cá nhân hoá từ dữ liệu thực
- Chấm điểm sức khoẻ tài chính (0–100) theo tháng
- Trích xuất tháng từ câu hỏi tự nhiên ("tháng 3", "tháng trước", "2025-03")
- Quick prompts gợi ý câu hỏi phổ biến
- Typing indicator animation khi đang xử lý

### 👥 Quỹ
- Tạo nhóm quỹ với mã mời 6 ký tự
- Quản lý các khoản đóng góp và theo dõi số dư quỹ sách thành viên và vai trò
- Rời/Giải tán nhóm
- Mỗi thành viên giữ database riêng tư, nhóm chỉ chia sẻ thống kê

### 📄 Báo cáo PDF
- Xuất báo cáo tài chính tháng ra file PDF chất lượng cao (ReportLab)
- Bao gồm: Header tháng, Summary cards (Thu/Chi/Tiết kiệm/Số dư), Bảng chi tiêu theo danh mục với inline bar chart, Danh sách toàn bộ giao dịch (tối đa 50 dòng), Cảnh báo giao dịch bất thường, Bảng dự báo AI tháng tới
- Xem lịch sử file PDF đã tạo
- Xem trước nội dung báo cáo trước khi xuất

### ⚙️ Cài đặt
- Cài đặt ứng dụng: tiền tệ, định dạng ngày, chủ đề (sáng/tối/theo hệ thống), accent color, chế độ cửa sổ
- Cài đặt AI: phương pháp dự báo, auto phân loại, phát hiện bất thường, engine chatbot
- Cấu hình API: Gemini API Key, Supabase URL/Key
- Công cụ dữ liệu: Backup/Restore database, xuất Excel, mở thư mục dữ liệu
- Đồng bộ đám mây (Cloud Sync) với Supabase Storage

### 👤 Hồ sơ cá nhân
- Upload và hiển thị ảnh đại diện tròn
- Sửa họ tên, số điện thoại (định danh chính), giới thiệu bản thân
- Chọn màu accent avatar (8 màu)
- Đổi mật khẩu inline với progress bar độ mạnh
- Thống kê nhanh: số dư, số giao dịch, số danh mục, số mục tiêu
- Thông tin phiên đăng nhập

---

## Kiến trúc hệ thống

```
Finance AI
├── main.py                          # Entry point
├── user_session.py                  # Singleton quản lý phiên đăng nhập
├── config.py                        # Cấu hình đường dẫn
│
├── app/
│   ├── ai/                          # Module AI
│   │   ├── classifier.py            # Phân loại giao dịch (TF-IDF + Random Forest)
│   │   ├── anomaly_detector.py      # Phát hiện bất thường (Isolation Forest)
│   │   ├── forecaster.py            # Dự báo chi tiêu (Prophet / Moving Average)
│   │   ├── local_chatbot_engine.py  # Chatbot offline (Intent + Pattern Matching)
│   │   ├── fine_tuner.py            # Fine-tune DistilGPT2 (tùy chọn)
│   │   ├── nlp_parser.py            # Parser nhanh "ăn phở 45k"
│   │   └── goal_tracker.py          # Theo dõi mục tiêu tiết kiệm
│   │
│   ├── core/                        # Business logic
│   │   ├── transaction_manager.py   # CRUD giao dịch + cập nhật số dư
│   │   ├── report_generator.py      # Xuất PDF (ReportLab)
│   │   ├── csv_importer.py          # Nhập CSV ngân hàng
│   │   ├── fund_manager.py        # Quản lý quỹ chung
│   │   ├── goal_tracker.py          # Mục tiêu tiết kiệm (version cải tiến)
│   │   ├── settings_manager.py      # Cài đặt per-user
│   │   ├── sync_manager.py          # Cloud sync (Supabase)
│   │   ├── event_bus.py             # PyQt6 signal/slot event bus
│   │   ├── theme_engine.py          # Dark/Light/Auto theme + accent color
│   │   ├── error_handler.py         # Global exception handler
│   │   └── logger.py                # Logging factory
│   │
│   ├── data/                        # Data layer
│   │   ├── models.py                # DatabaseManager (per-user SQLite)
│   │   ├── repositories.py          # Repository pattern (CRUD)
│   │   ├── auth_manager.py          # Xác thực, đăng ký, đổi mật khẩu
│   │   └── session.json             # Lưu phiên "ghi nhớ đăng nhập"
│   │
│   └── ui/                          # Giao diện PyQt6
│       ├── main_window.py           # MainWindow + Sidebar
│       ├── login_window.py          # Màn hình đăng nhập/đăng ký
│       ├── dashboard_frame.py       # Dashboard
│       ├── transaction_frame.py     # Quản lý giao dịch
│       ├── spending_frame.py        # Quản lý chi tiêu (donut chart)
│       ├── budget_frame.py          # Ngân sách
│       ├── forecast_frame.py        # Dự báo AI
│       ├── chatbot_frame.py         # Chatbot AI
│       ├── fund_frame.py          # Quỹ
│       ├── report_frame.py          # Báo cáo PDF
│       ├── profile_frame.py         # Hồ sơ cá nhân
│       ├── settings_frame.py        # Cài đặt
│       ├── command_palette.py       # Command Palette (Ctrl+K)
│       └── notification.py          # Toast notification system
│
└── data/
    ├── shared/
    │   ├── auth.db                  # Database xác thực dùng chung
    │   └── session.json             # Phiên "ghi nhớ đăng nhập"
    └── users/
        └── {username}/
            ├── finance.db           # Database riêng của từng user
            ├── settings.json        # Cài đặt riêng
            ├── backups/             # Backup database
            ├── exports/             # File PDF, Excel đã xuất
            └── ai/                  # Model AI per-user
                ├── classifier_model.pkl
                └── fine_tuned_model/
```

---

## Yêu cầu hệ thống

- **Python**: 3.10 trở lên
- **OS**: Windows 10/11, macOS 12+, Ubuntu 20.04+
- **RAM**: Tối thiểu 2GB (khuyến nghị 4GB nếu dùng Prophet/DistilGPT2)
- **Disk**: ~500MB cho ứng dụng + không gian cho database và model AI

---

## Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/your-repo/finance-ai.git
cd finance-ai
```

### 2. Tạo môi trường ảo

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

**Danh sách package bắt buộc:**

```
PyQt6>=6.5.0
matplotlib>=3.7.0
pandas>=2.0.0
scikit-learn>=1.3.0
reportlab>=4.0.0
openpyxl>=3.1.0
numpy>=1.24.0
```

**Package tùy chọn (nâng cao độ chính xác dự báo):**

```bash
# Prophet — dự báo chuỗi thời gian chính xác hơn
pip install prophet

# PyTorch + Transformers — fine-tune DistilGPT2
pip install torch transformers datasets accelerate
```

### 4. Chạy ứng dụng

```bash
python main.py
```

### 5. Đăng nhập lần đầu

- **Tài khoản mặc định**: `admin` / `admin123`
- Đổi mật khẩu ngay sau khi đăng nhập lần đầu trong **Hồ sơ → Đổi mật khẩu**

---

## Cấu trúc dự án

```
finance-ai/
├── main.py                  # Entry point
├── user_session.py          # Session management singleton
├── config.py                # Paths & constants
├── requirements.txt         # Python dependencies
├── migrate_to_per_user_db.py  # Script migration từ DB cũ
├── app/
│   ├── ai/
│   ├── core/
│   ├── data/
│   └── ui/
├── assets/
│   └── logo.png             # Logo ứng dụng
└── data/                    # Được tạo tự động khi chạy
    ├── shared/
    └── users/
```

---

## Hướng dẫn sử dụng

### Thêm giao dịch

**Cách 1 — Thủ công:**
1. Vào tab **Giao dịch** → nhấn **+ Thêm mới** (hoặc `Ctrl+N`)
2. Chọn loại (Chi tiêu / Thu nhập), nhập mô tả, số tiền, ngày, danh mục, tài khoản
3. Nhấn **Thêm giao dịch**

**Cách 2 — Nhập CSV ngân hàng:**
1. Vào tab **Giao dịch** → nhấn **Nhập CSV**
2. Chọn file sao kê từ ngân hàng (Vietcombank, BIDV, Techcombank, MB Bank, VPBank)
3. Hệ thống tự nhận diện định dạng và import

### Xem dự báo

1. Vào tab **Dự báo**
2. Nhấn **Chạy dự báo AI** → hệ thống phân tích dữ liệu lịch sử và dự báo tháng tới
3. Nhấn **Phát hiện bất thường** → AI quét và đánh dấu giao dịch đáng ngờ

### Xuất báo cáo PDF

1. Vào tab **Báo cáo**
2. Chọn tháng cần xuất
3. Nhấn **Tạo & Tải PDF** → chọn nơi lưu file
4. PDF được tạo với đầy đủ biểu đồ, bảng và dự báo AI

### Chat với AI

1. Vào tab **Chatbot AI**
2. Nhập câu hỏi bằng tiếng Việt tự nhiên, ví dụ:
   - *"Tháng này tôi chi bao nhiêu?"*
   - *"Danh mục ăn uống tháng 3 hết bao nhiêu?"*
   - *"Cho lời khuyên tài chính tháng này"*
   - *"So sánh chi tiêu với tháng trước"*
   - *"Dự báo tháng tới tôi sẽ chi bao nhiêu?"*
3. Hoặc nhấn một trong các **Quick Prompts** gợi ý

---

## Hệ thống tài khoản người dùng

Ứng dụng hỗ trợ đa người dùng với database hoàn toàn riêng biệt cho mỗi người.

### Cơ chế bảo mật

- Mật khẩu được hash bằng **SHA-256 + salt ngẫu nhiên** (16 bytes)
- Database xác thực (`auth.db`) tách biệt khỏi database tài chính
- Mỗi user có thư mục riêng: `data/users/{username}/`
- Session "ghi nhớ đăng nhập" lưu ở `data/shared/session.json`

### Phân quyền

| Quyền | User | Admin |
|---|---|---|
| Xem/sửa dữ liệu cá nhân | ✅ | ✅ |
| Xuất báo cáo | ✅ | ✅ |
| Xem danh sách user | ❌ | ✅ |
| Thêm/Khoá/Xóa user | ❌ | ✅ |
| Đặt lại mật khẩu user khác | ❌ | ✅ |

### Đăng ký tài khoản mới

1. Tại màn hình đăng nhập → nhấn **Đăng ký ngay**
2. Điền họ tên, **số điện thoại** (dùng làm định danh chính), tên đăng nhập, mật khẩu
3. Số điện thoại phải là số Việt Nam 10 chữ số, bắt đầu bằng 0 và không được trùng với tài khoản khác

---

## Module AI

### Phân loại giao dịch (`classifier.py`)

- Thuật toán: **TF-IDF (char n-gram 2–4) + Random Forest (200 cây)**
- Dữ liệu seed: 50+ mẫu giao dịch thường gặp ở Việt Nam
- Tự động retrain khi người dùng sửa danh mục
- Model lưu tại `data/users/{username}/ai/classifier_model.pkl`
- Mỗi user có model riêng, được cải thiện theo thời gian

### Phát hiện bất thường (`anomaly_detector.py`)

- Thuật toán: **Isolation Forest** (contamination = 8%)
- Feature engineering: log_amount, z-score theo danh mục, tỷ lệ so với trung bình, giờ giao dịch, ngày trong tuần
- Điểm rủi ro (risk_score) 0–99
- Phân loại mức độ: low / medium / high
- Giải thích lý do: so sánh phần trăm với trung bình, z-score, giờ bất thường

### Dự báo chi tiêu (`forecaster.py`)

**Facebook Prophet** (khi đã cài và có ≥ 3 tháng dữ liệu):
- Mô hình chuỗi thời gian additive
- Khoảng tin cậy 80%
- Changepoint prior scale = 0.3

**Moving Average** (fallback):
- Trung bình trượt 3 tháng gần nhất
- Khoảng tin cậy ± 1 độ lệch chuẩn

### Chatbot AI offline (`local_chatbot_engine.py`)

Kiến trúc 4 lớp:
1. **NLP Parser** — nhận diện intent bằng regex (14 intent types)
2. **Data Fetcher** — truy vấn SQLite thực tế
3. **Analyzer** — tính toán xu hướng, điểm sức khoẻ tài chính, lời khuyên
4. **Responder** — tạo câu trả lời tiếng Việt tự nhiên

### Fine-tuning DistilGPT2 (tùy chọn, `fine_tuner.py`)

```bash
# Chạy từ trong ứng dụng: Cài đặt → AI → Fine-tune model
```

- Sinh dữ liệu huấn luyện Q&A tự động từ database thực của user
- Huấn luyện DistilGPT2 trong 3 epoch
- Model lưu tại `data/users/{username}/ai/fine_tuned_model/`
- Yêu cầu: `pip install transformers datasets torch accelerate`

---

## Cơ sở dữ liệu

Ứng dụng sử dụng **SQLite** với 2 database tách biệt:

### `data/shared/auth.db` — Xác thực (dùng chung)

| Bảng | Mô tả |
|---|---|
| `users` | Tài khoản đăng nhập (username, password_hash, salt, phone, role) |

### `data/users/{username}/finance.db` — Tài chính (per-user)

| Bảng | Mô tả |
|---|---|
| `accounts` | Tài khoản tài chính (tiền mặt, ngân hàng, thẻ) |
| `categories` | Danh mục thu/chi (tên, màu, icon, cha-con) |
| `transactions` | Giao dịch (số tiền, loại, mô tả, ngày, is_anomaly) |
| `budgets` | Ngân sách theo danh mục và tháng |
| `ai_predictions` | Dự báo chi tiêu AI theo tháng |
| `savings_goals` | Mục tiêu tiết kiệm |
| `family_groups` | Quỹ chung |
| `group_members` | Thành viên quỹ |
| `chat_history` | Lịch sử hội thoại chatbot |
| `user_profiles` | Hồ sơ người dùng (màu accent, bio) |

### PRAGMA tối ưu hiệu năng

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -8000;
PRAGMA temp_store = MEMORY;
```

### Index hiệu năng

```sql
CREATE INDEX idx_tx_date ON transactions(date);
CREATE INDEX idx_tx_category ON transactions(category_id);
CREATE INDEX idx_tx_type ON transactions(type);
CREATE INDEX idx_tx_date_type ON transactions(date, type);
CREATE INDEX idx_budget_month ON budgets(month);
CREATE INDEX idx_pred_month ON ai_predictions(month);
```

---

## API & Tích hợp bên ngoài

### Gemini API (tùy chọn)

Dùng để nâng cao khả năng chatbot khi có internet.

1. Lấy API key tại [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Vào **Cài đặt → Gemini Key** → nhập key
3. Hoặc thêm vào file `.env`:

```env
GEMINI_API_KEY=your_api_key_here
```

### Supabase (tùy chọn — Cloud Sync)

Đồng bộ database lên cloud.

1. Tạo project tại [supabase.com](https://supabase.com)
2. Tạo bucket `backups` trong Storage
3. Vào **Cài đặt → Supabase URL / Supabase Key** → nhập thông tin
4. Nhấn **Đồng bộ ngay** trong tab Cloud Sync

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_or_service_key
```

---

## Cấu hình nâng cao

### File `.env`

Tạo file `.env` ở thư mục gốc dự án:

```env
GEMINI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
SYNC_API_URL=
```

### `config.py`

```python
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH  = DATA_DIR / "finance.db"          # Legacy fallback
EXPORTS_DIR = DATA_DIR / "exports"
APP_NAME    = "Finance AI"
APP_VERSION = "1.0"
```

### Chủ đề & màu sắc

Ứng dụng hỗ trợ 3 chế độ màu và 6 accent color:

| Accent | Màu |
|---|---|
| Xanh logo (mặc định) | `#1A6BAF` |
| Cam logo | `#E8921A` |
| Xanh mint | `#1D9E75` |
| Tím | `#7F77DD` |
| Hồng | `#D4537E` |
| Đỏ cam | `#E85020` |

---

## Phím tắt

| Phím tắt | Chức năng |
|---|---|
| `Ctrl+K` | Mở Command Palette |
| `Ctrl+N` | Thêm giao dịch mới |
| `Ctrl+1` | Dashboard |
| `Ctrl+2` | Giao dịch |
| `Ctrl+3` | Ngân sách |
| `Ctrl+4` | Dự báo |
| `Ctrl+5` | Chatbot AI |
| `Ctrl+6` | Báo cáo |
| `Ctrl+7` / `Ctrl+,` | Cài đặt |
| `F5` | Làm mới trang hiện tại |

---

## Migration dữ liệu

Nếu bạn đang nâng cấp từ phiên bản cũ dùng một database chung (`data/finance.db`):

```bash
python migrate_to_per_user_db.py
```

Script sẽ tự động:
1. Backup database cũ sang `data/finance.db.bak`
2. Tạo `data/shared/auth.db` với bảng users
3. Tách dữ liệu từng user ra `data/users/{username}/finance.db`
4. Copy model AI classifier nếu có
5. In báo cáo migration ra console

**Lưu ý:** Chạy script một lần duy nhất. Kiểm tra dữ liệu sau migration trước khi xóa backup.

---

## Phát triển & Đóng góp

### Thêm trang UI mới

1. Tạo file `app/ui/your_frame.py` với class kế thừa `QWidget`
2. Implement method `refresh(self)` để load dữ liệu
3. Đăng ký trong `MainWindow._create_page()` tại `app/ui/main_window.py`:

```python
if page == "Trang mới":
    from app.ui.your_frame import YourFrame
    return YourFrame(main_window=self)
```

4. Thêm button vào sidebar trong `Sidebar._build()`:

```python
sections = {
    "CHÍNH": ["Dashboard", "Trang mới", ...],
    ...
}
icons = {"Trang mới": "🆕", ...}
```

### Sử dụng Event Bus

```python
from app.core.event_bus import bus

# Phát sự kiện
bus.transaction_added.emit()
bus.balance_changed.emit()
bus.notify_success.emit("Tiêu đề", "Nội dung thông báo")

# Lắng nghe sự kiện (trong __init__ của QWidget)
bus.transaction_added.connect(self.refresh)
bus.theme_changed.connect(self._apply_theme)
```

### Thêm Intent vào Chatbot

Mở `app/ai/local_chatbot_engine.py`, thêm vào dict `INTENTS`:

```python
INTENTS = {
    "your_intent": [
        r"pattern_1",
        r"pattern_2",
    ],
    ...
}
```

Sau đó thêm handler trong class `Responder` và đăng ký trong `LocalChatbotEngine.chat()`.

### Logging

```python
from app.core.logger import get_logger

logger = get_logger(__name__)
logger.info("Thông tin")
logger.warning("Cảnh báo")
logger.error("Lỗi nghiêm trọng", exc_info=True)
```

Log file: `data/app.log` (tự rotate khi > 5MB, giữ 3 file backup)

---

## Thông tin nhóm

| Thành viên | Mã sinh viên |
|---|---|
| Như Quỳnh | 25AI043 |
| Hưng Phú | 25AI034 |

---

## Giấy phép

Dự án được phát triển cho mục đích học thuật. Mọi quyền được bảo lưu.

---

*Finance AI v1.0 — Được tạo bằng Python + PyQt6 + AI*
