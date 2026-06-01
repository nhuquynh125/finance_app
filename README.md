# Finance AI 💰

Ứng dụng quản lý tài chính cá nhân thông minh, xây dựng bằng **Python + PyQt6**, tích hợp AI phân loại giao dịch, dự báo chi tiêu, phát hiện giao dịch bất thường và chatbot tư vấn tài chính hỗ trợ đa nền tảng (Hoạt động Offline, Gemini API, Ollama).

---

## 📑 Mục lục

- [Tính năng chính](#-tính-năng-chính)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Cơ sở dữ liệu & Đa người dùng](#-cơ-sở-dữ-liệu--đa-người-dùng)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Cài đặt](#-cài-đặt)
- [Cấu hình AI (Gemini / Ollama)](#-cấu-hình-ai-gemini--ollama)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
- [Phím tắt](#-phím-tắt)
- [Phát triển & Đóng góp](#-phát-triển--đóng-góp)
- [Thông tin nhóm](#-thông-tin-nhóm)

---

## 🌟 Tính năng chính

### 📊 Dashboard Cực Kỳ Trực Quan
- **Tổng quan thu chi:** 4 KPI card (Thu nhập, Chi tiêu, Tiết kiệm, Dự báo AI).
- **Biểu đồ đa dạng:** Biểu đồ thu chi 6 tháng gần nhất (bar chart) và biểu đồ phân bổ danh mục (pie chart/donut chart thuần PyQt).
- **Lịch sử & Bất thường:** Danh sách giao dịch gần đây với hiệu ứng highlight (cảnh báo đỏ) cho các giao dịch bất thường.

### 💳 Quản lý Giao dịch Thông Minh
- **Quản lý toàn diện:** Thêm/Sửa/Xóa giao dịch (loại, mô tả, số tiền, ngày, danh mục, tài khoản, ghi chú).
- **Import hàng loạt từ CSV:** Hỗ trợ đọc sao kê từ các ngân hàng lớn tại Việt Nam (Vietcombank, BIDV, Techcombank, MB Bank, VPBank). AI tự động nhận diện định dạng và phân loại danh mục.
- **Phân trang & Lọc:** Bộ lọc đa chiều (tháng, loại, danh mục, tìm kiếm text), tự động phân trang (100 giao dịch/trang) cho bộ dữ liệu lớn.

### 💰 Quản lý Ngân sách & Mục tiêu
- **Ngân sách:** Đặt hạn mức theo danh mục/tháng với thanh Progress bar trực quan (Badge: Bình thường / Sắp hết / Vượt ngân sách).
- **Mục tiêu tiết kiệm:** Theo dõi tiến độ mục tiêu tài chính dài hạn.

### 📈 AI: Dự báo & Phát hiện Bất thường
- **Dự báo chi tiêu (Forecaster):** Sử dụng **Facebook Prophet** hoặc **Trung bình trượt (Moving Average)** để dự báo chi tiêu tháng tới, kèm biểu đồ khoảng tin cậy.
- **Phát hiện bất thường (Anomaly Detection):** Ứng dụng **Isolation Forest** (scikit-learn) phân tích thói quen để đánh dấu giao dịch bất thường (cảnh báo mức Low/Medium/High với giải thích chi tiết).
- **Phân loại tự động (Classifier):** Dùng **TF-IDF + Random Forest** tự động gắn thẻ danh mục cho các giao dịch mới nhập, mô hình học hỏi thói quen của người dùng theo thời gian.

### 🤖 Chatbot AI Đa Nền Tảng
Hệ thống Chatbot tích hợp 3 Engine khác nhau:
1. **Local Engine (Offline 100%):** Hoạt động không cần internet, sử dụng Regex Pattern Matching (14 intents) để truy vấn CSDL, chấm điểm sức khoẻ tài chính, và đưa ra lời khuyên.
2. **Gemini API:** Kết nối API Google Gemini để tư vấn tự nhiên, thông minh và phân tích sâu sắc hơn.
3. **Ollama Offline:** Tích hợp với các model LLM cục bộ (ví dụ: Llama3, Mistral) cho người dùng muốn bảo mật 100% dữ liệu nhưng vẫn cần sức mạnh LLM.

### 👥 Quản lý Quỹ Chung
- Tạo và tham gia Quỹ (nhóm) thông qua mã mời 6 ký tự.
- Theo dõi số dư quỹ, các khoản đóng góp của từng thành viên. Dữ liệu cá nhân hoàn toàn tách biệt, nhóm chỉ chia sẻ thống kê quỹ.

### 📄 Báo Cáo PDF & Excel
- Xuất báo cáo tài chính hàng tháng ra file PDF chuyên nghiệp (ReportLab) với đầy đủ bảng biểu, biểu đồ inline và cảnh báo rủi ro.
- Xuất toàn bộ dữ liệu hệ thống ra file Excel để backup/phân tích ngoại tuyến.

### 🎨 Giao diện (UI/UX) & Cài đặt
- **Giao diện hiện đại:** Hỗ trợ Dark Mode, Light Mode, Auto (theo hệ thống), 6 màu Accent Colors để cá nhân hoá.
- **Collapsible Sidebar:** Thanh menu bên trái có thể thu gọn mượt mà (50-60px), tối ưu không gian làm việc.
- **Command Palette (`Ctrl+K`):** Tìm kiếm và điều hướng siêu tốc trên toàn ứng dụng.

---

## 🏗 Kiến trúc hệ thống

Dự án áp dụng mô hình phân lớp rõ ràng (Layered Architecture):

```text
finance-ai/
├── main.py                          # Entry point
├── config.py                        # Cấu hình hằng số, đường dẫn
├── user_session.py                  # Quản lý phiên đăng nhập (Singleton)
├── app/
│   ├── ai/                          # Module AI Logic
│   │   ├── classifier.py            # TF-IDF + Random Forest
│   │   ├── anomaly_detector.py      # Isolation Forest
│   │   ├── forecaster.py            # Prophet / Moving Average
│   │   ├── local_chatbot_engine.py  # Regex/Pattern Matching
│   │   └── ...                      
│   ├── core/                        # Business Logic & Managers
│   │   ├── transaction_manager.py
│   │   ├── settings_manager.py
│   │   ├── event_bus.py             # Event-driven system (PyQt Signals)
│   │   └── sync_manager.py          # Cloud Sync (Supabase)
│   ├── data/                        # Data Access Layer
│   │   ├── models.py                # SQLite Database Manager
│   │   └── auth_manager.py
│   └── ui/                          # Presentation Layer (PyQt6)
│       ├── main_window.py
│       ├── dashboard_frame.py
│       ├── chatbot_frame.py
│       ├── command_palette.py
│       └── ...
└── data/                            # Thư mục chứa CSDL & Settings (Tự động sinh)
```

---

## 🗄 Cơ sở dữ liệu & Đa người dùng

Ứng dụng hỗ trợ đa người dùng (Multi-user) với tính năng bảo mật cao:
- **Cơ sở dữ liệu chia tách:** 
  - `data/shared/auth.db`: Chứa thông tin đăng nhập (mật khẩu hash bằng SHA-256 + salt).
  - `data/users/{username}/finance.db`: CSDL SQLite riêng tư 100% của từng người dùng.
- **Settings & AI Models Per-User:** Mỗi tài khoản có file cấu hình (`settings.json`) và model AI (`classifier_model.pkl`) được cá nhân hóa và huấn luyện riêng biệt trên dữ liệu của người đó.
- **Tối ưu SQLite:** Bật các Pragma tối ưu tốc độ `WAL`, `MEMORY` temp store, và thiết lập Indexes cho các trường thường truy vấn.

---

## 💻 Yêu cầu hệ thống

- **Hệ điều hành:** Windows 10/11, macOS 12+, Linux.
- **Python:** Phiên bản 3.10 trở lên.
- **Phần cứng:** Tối thiểu 2GB RAM. Khuyến nghị 4GB+ nếu sử dụng thư viện Prophet dự báo hoặc Ollama LLM.

---

## 🚀 Cài đặt

### 1. Tải mã nguồn
```bash
git clone https://github.com/your-repo/finance-ai.git
cd finance-ai
```

### 2. Thiết lập môi trường ảo (Khuyến nghị)
```bash
python -m venv .venv
# Trên Windows:
.venv\Scripts\activate
# Trên macOS/Linux:
source .venv/bin/activate
```

### 3. Cài đặt các thư viện
```bash
pip install -r requirements.txt
```
*Các gói cơ bản:* `PyQt6`, `pandas`, `scikit-learn`, `reportlab`, `openpyxl`.

**(Tùy chọn) Cài đặt Prophet cho tính năng dự báo chuyên sâu:**
```bash
pip install prophet
```

### 4. Khởi chạy ứng dụng
```bash
python main.py
```
*(Lần chạy đầu tiên hệ thống sẽ tự động tạo cấu trúc thư mục CSDL trong `data/`).*

---

## ⚙️ Cấu hình AI (Gemini / Ollama)

Ứng dụng hỗ trợ các Engine AI bên ngoài, cấu hình thông qua Giao diện (`Cài đặt -> AI`) hoặc file `.env`:

**1. Gemini API:**
Lấy API Key tại [Google AI Studio](https://aistudio.google.com/). Tạo file `.env` ở thư mục gốc:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

**2. Ollama Offline:**
- Cài đặt [Ollama](https://ollama.com/) trên máy.
- Tải mô hình: `ollama run mistral` (hoặc llama3, qwen,...).
- Chọn Engine **"Ollama"** trong phần Cài đặt ứng dụng của Finance AI.

---

## 📖 Hướng dẫn sử dụng

### 1. Đăng ký & Đăng nhập
- Mở ứng dụng, chọn **Đăng ký ngay** để tạo tài khoản cá nhân.
- Mỗi người dùng có một vùng dữ liệu tách biệt an toàn.

### 2. Nhập giao dịch hàng loạt (CSV)
- Vào tab **Giao dịch**, chọn **Nhập CSV**.
- Tải lên file sao kê từ ngân hàng (Vietcombank, Techcombank, MB, v.v.). AI sẽ tự động phân loại chi tiêu dựa vào mô tả giao dịch.

### 3. Tương tác AI
- **Dự báo:** Chuyển qua tab **Dự báo**, nhấn *Chạy dự báo* để xem ước tính chi tiêu tháng sau dựa trên lịch sử dữ liệu.
- **Chatbot:** Vào tab **Chatbot AI**, bạn có thể gõ câu hỏi bằng tiếng Việt như: *"Tháng này tôi tiêu bao nhiêu tiền ăn uống?"*, *"Cho tôi lời khuyên tiết kiệm"*, *"Phân tích thu chi tháng 10"*. 

---

## ⌨️ Phím tắt (Hotkeys)

Để tối ưu hóa trải nghiệm người dùng, ứng dụng hỗ trợ các phím tắt sau:

| Phím Tắt | Chức năng |
|:---|:---|
| `Ctrl+K` | Mở Command Palette (Tìm kiếm & Điều hướng nhanh) |
| `Ctrl+N` | Mở cửa sổ Thêm giao dịch mới |
| `Ctrl+1` | Chuyển đến Dashboard |
| `Ctrl+2` | Chuyển đến Giao dịch |
| `Ctrl+3` | Chuyển đến Ngân sách |
| `Ctrl+4` | Chuyển đến Dự báo AI |
| `Ctrl+5` | Chuyển đến Chatbot AI |
| `Ctrl+6` | Chuyển đến Báo cáo |
| `Ctrl+,` | Mở Cài đặt |
| `F5` | Làm mới (Refresh) giao diện hiện tại |

---

## 🛠 Phát triển & Đóng góp

### Kiến trúc Sự Kiện (Event Bus)
Ứng dụng sử dụng mô hình Event-driven bằng PyQt Signals giúp decouple các module.
```python
from app.core.event_bus import bus

# Phát sự kiện
bus.transaction_added.emit()
bus.notify_success.emit("Thành công", "Đã lưu dữ liệu")

# Lắng nghe (Trong __init__ của các Frame)
bus.transaction_added.connect(self.refresh_data)
```

### Script Tiện Ích
Nếu bạn có phiên bản CSDL cũ, có thể chạy migration script để chuyển sang mô hình đa người dùng:
```bash
python migrate_to_per_user_db.py
```

---

## 👥 Thông tin nhóm

| Thành viên | Mã sinh viên |
|:---|:---|
| Như Quỳnh | 25AI043 |
| Hưng Phú | 25AI034 |

---

*Finance AI v1.0 — Ứng dụng quản lý tài chính xây dựng bằng Python, PyQt6 và AI.*
