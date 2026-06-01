# 💰 Finance AI - Quản Lý Tài Chính Thông Minh

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt-6-green?logo=qt)
![Machine Learning](https://img.shields.io/badge/Machine%20Learning-Scikit--Learn%20%7C%20Prophet-orange)
![AI Chatbot](https://img.shields.io/badge/AI-Self--Trained%20Model-purple)
![License](https://img.shields.io/badge/license-MIT-green)

**Ứng dụng quản lý tài chính cá nhân đa nền tảng, tích hợp Trí tuệ Nhân tạo (AI) giúp bạn theo dõi, phân loại và dự báo chi tiêu một cách tự động và thông minh.**

</div>

---

## 📑 Mục lục

- [Giới thiệu](#-giới-thiệu)
- [Tính năng nổi bật](#-tính-năng-nổi-bật)
- [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Cơ sở dữ liệu & Đa người dùng](#-cơ-sở-dữ-liệu--đa-người-dùng)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Hướng dẫn cài đặt](#-hướng-dẫn-cài-đặt)
- [Hướng dẫn sử dụng chi tiết](#-hướng-dẫn-sử-dụng-chi-tiết)
- [Phím tắt (Hotkeys)](#-phím-tắt-hotkeys)
- [Phát triển & Đóng góp](#-phát-triển--đóng-góp)
- [Roadmap (Định hướng tương lai)](#-roadmap-định-hướng-tương-lai)
- [Thông tin nhóm](#-thông-tin-nhóm)

---

## 🚀 Giới thiệu

**Finance AI** không chỉ là một ứng dụng ghi chép thu chi thông thường. Bằng cách kết hợp sức mạnh của **Giao diện trực quan (PyQt6)** và **Machine Learning / LLM**, hệ thống giúp tự động hoá tối đa quy trình quản lý tài chính của bạn: từ việc tự động nhận diện danh mục giao dịch qua file sao kê ngân hàng, phát hiện các khoản chi tiêu bất thường, cho đến việc tư vấn tài chính trực tiếp qua Chatbot AI.

Ứng dụng được thiết kế tối ưu cho trải nghiệm người dùng với tốc độ phản hồi nhanh, giao diện thân thiện, hỗ trợ Dark Mode và bảo mật dữ liệu tuyệt đối với cơ sở dữ liệu lưu trữ cục bộ cho từng người dùng.

---

## 🌟 Tính năng nổi bật

### 📊 1. Dashboard & Báo Cáo Trực Quan
- **Tổng quan theo thời gian thực:** 4 thẻ KPI động (Thu nhập, Chi tiêu, Tiết kiệm, Dự báo xu hướng).
- **Phân tích đa chiều:**
  - Biểu đồ cột (Bar Chart) thể hiện biến động thu/chi trong 6 tháng gần nhất.
  - Biểu đồ tròn/donut (Pie/Donut Chart) phân bổ tỷ trọng chi tiêu theo từng danh mục.
- **Theo dõi dòng tiền:** Bảng danh sách giao dịch gần đây được cập nhật realtime, với hiệu ứng làm nổi bật (highlight) đỏ đối với các khoản chi tiêu bất thường.

### 💳 2. Quản lý Giao dịch & Nhập liệu Thông Minh
- **Quản lý CRUD:** Thêm, Sửa, Xóa giao dịch dễ dàng với form nhập liệu tối ưu.
- **Smart Import (Nhập từ CSV):** Tự động nhận diện cấu trúc file sao kê từ các ngân hàng phổ biến (Vietcombank, BIDV, Techcombank, MB Bank, VPBank).
- **Phân loại AI (Auto Categorization):** Sử dụng mô hình **TF-IDF kết hợp Random Forest** học hỏi từ thói quen của người dùng để tự động gán nhãn danh mục cho các giao dịch mới.
- **Bộ lọc mạnh mẽ:** Lọc theo tháng, năm, loại giao dịch (Thu/Chi), danh mục, hoặc tìm kiếm toàn văn bản. Phân trang tự động giúp xử lý hàng vạn giao dịch mượt mà.

### 💰 3. Quản lý Ngân sách & Mục tiêu Tiết Kiệm
- **Ngân sách thông minh:** Thiết lập hạn mức chi tiêu cho từng danh mục theo tháng. Thanh Progress bar trực quan hiển thị các trạng thái: *Bình thường*, *Sắp hết*, và cảnh báo đỏ khi *Vượt ngân sách*.
- **Mục tiêu tài chính:** Theo dõi tiến trình các quỹ tiết kiệm dài hạn (Mua xe, Du lịch, Quỹ khẩn cấp,...).

### 📈 4. Trí Tuệ Nhân Tạo (AI) Chuyên Sâu
- **Dự báo chi tiêu (Forecasting):** 
  - Tích hợp **Facebook Prophet** cho phân tích chuỗi thời gian chuyên sâu.
  - Hỗ trợ mô hình **Moving Average** làm phương án dự phòng, giúp vẽ ra biểu đồ dự báo chi tiêu trong 1-3 tháng tới cùng khoảng tin cậy.
- **Phát hiện bất thường (Anomaly Detection):** 
  - Ứng dụng thuật toán **Isolation Forest** (Scikit-learn) tự động quét và đánh dấu các giao dịch có dấu hiệu bất thường về số tiền so với lịch sử chi tiêu.
  - Phân loại mức độ rủi ro (Low, Medium, High).

### 🤖 5. Chatbot Tư Vấn Tài Chính
Hệ thống Chatbot sử dụng Engine AI tự huấn luyện (Self-trained Model) giúp đáp ứng nhu cầu tư vấn tài chính một cách nhanh chóng, thông minh và bảo mật hoàn toàn:
- **Tự động phân tích & Tư vấn:** Xử lý ngôn ngữ tự nhiên để hiểu các câu hỏi về tài chính cá nhân, từ đó đưa ra lời khuyên phù hợp dựa trên thói quen chi tiêu của bạn.
- **Local Engine (Offline 100%):** Mọi dữ liệu tài chính và cuộc hội thoại đều được xử lý cục bộ trên máy tính của bạn, không gửi qua bất kỳ API bên thứ 3 nào, đảm bảo quyền riêng tư tuyệt đối.

### 📄 6. Trích Xuất Báo Cáo
- **Xuất file PDF:** Tạo báo cáo tài chính chuyên nghiệp (sử dụng ReportLab), đi kèm bảng biểu, hình ảnh biểu đồ và các cảnh báo rủi ro.
- **Xuất Excel/CSV:** Backup toàn bộ dữ liệu ra file `.xlsx` hoặc `.csv` để lưu trữ hoặc phân tích trên các công cụ khác.

### 🎨 7. Giao diện (UI/UX) Tối Ưu
- **Giao diện tương thích (Responsive):** Các thành phần giao diện tự động co giãn theo kích thước cửa sổ.
- **Chủ đề (Themes):** Hỗ trợ Dark Mode, Light Mode và 6 màu sắc chủ đạo (Accent Colors).
- **Sidebar thông minh:** Thanh menu bên trái có khả năng thu gọn mở rộng (Collapsible Sidebar) với hiệu ứng animation mượt mà.
- **Command Palette (`Ctrl+K`):** Tích hợp thanh tìm kiếm nhanh (tương tự VS Code) giúp điều hướng mọi tính năng trong chớp mắt.

---

## 🛠 Công nghệ sử dụng

| Lớp (Layer) | Công nghệ / Thư viện |
| :--- | :--- |
| **Giao diện (Frontend)** | Python, PyQt6, PyQt6-Charts |
| **Backend & Logic** | Python 3.10+ |
| **Cơ sở dữ liệu** | SQLite3 (Tối ưu hóa WAL mode) |
| **Machine Learning (AI)** | Scikit-learn, Pandas, Numpy, Facebook Prophet |
| **LLM & Chatbot** | Self-Trained AI Model, Regex NLP |
| **Báo cáo & Xuất File** | ReportLab (PDF), OpenPyXL (Excel) |

---

## 🏗 Kiến trúc hệ thống

Ứng dụng tuân thủ mô hình **Phân lớp (Layered Architecture)** kết hợp với **Event-Driven Architecture**:

```text
finance-ai/
├── main.py                          # Điểm khởi chạy ứng dụng
├── config.py                        # Quản lý hằng số, đường dẫn
├── user_session.py                  # Quản lý phiên đăng nhập (Singleton Pattern)
├── app/
│   ├── ai/                          # Lớp Trí tuệ nhân tạo
│   │   ├── anomaly_detector.py      # Tìm điểm dị thường: Isolation Forest
│   │   ├── classifier.py            # Phân loại danh mục: TF-IDF + Random Forest
│   │   ├── fine_tuner.py            # Huấn luyện mô hình cá nhân hoá
│   │   ├── forecaster.py            # Dự báo: Prophet / Moving Average
│   │   ├── goal_tracker.py          # AI theo dõi tiến độ mục tiêu
│   │   ├── local_chatbot_engine.py  # Xử lý ngôn ngữ tự nhiên offline
│   │   └── nlp_parser.py            # Phân tích cú pháp NLP
│   ├── core/                        # Lớp Logic nghiệp vụ (Business Layer)
│   │   ├── csv_importer.py          # Import dữ liệu sao kê
│   │   ├── error_handler.py         # Xử lý lỗi tập trung
│   │   ├── event_bus.py             # Hệ thống Pub/Sub bằng PyQt Signals
│   │   ├── fund_manager.py          # Quản lý quỹ chung (Groups)
│   │   ├── goal_tracker.py          # Logic nghiệp vụ mục tiêu
│   │   ├── logger.py                # Ghi log hệ thống
│   │   ├── report_generator.py      # Sinh báo cáo PDF/Excel
│   │   ├── settings_manager.py      # Quản lý cấu hình người dùng
│   │   ├── sync_manager.py          # Đồng bộ dữ liệu
│   │   ├── theme_engine.py          # Quản lý giao diện Sáng/Tối
│   │   └── transaction_manager.py   # Quản lý CRUD giao dịch
│   ├── data/                        # Lớp Truy cập dữ liệu (Data Access Layer)
│   │   ├── auth_manager.py          # Quản lý xác thực
│   │   ├── models.py                # Giao tiếp SQLite Database
│   │   └── repositories.py          # Các repository xử lý query
│   └── ui/                          # Lớp Hiển thị (Presentation Layer - PyQt6)
│       ├── budget_frame.py          # Giao diện ngân sách
│       ├── chatbot_frame.py         # Giao diện Chatbot
│       ├── command_palette.py       # Tính năng tìm kiếm siêu tốc
│       ├── dashboard_frame.py       # Giao diện Tổng quan
│       ├── forecast_frame.py        # Giao diện Dự báo
│       ├── fund_frame.py            # Giao diện Quỹ chung
│       ├── login_window.py          # Cửa sổ đăng nhập/đăng ký
│       ├── main_window.py           # Window chính điều phối các Frame
│       ├── notification.py          # UI thông báo (Toast/Popup)
│       ├── profile_frame.py         # Giao diện hồ sơ cá nhân
│       ├── report_frame.py          # Giao diện báo cáo
│       ├── settings_frame.py        # Giao diện cài đặt
│       ├── spending_frame.py        # Giao diện chi tiêu
│       └── transaction_frame.py     # Giao diện giao dịch
└── data/                            # Thư mục chứa CSDL & Cấu hình (Tự động sinh)
```

**Ưu điểm kiến trúc:**
- **Decoupled:** Giao diện không gọi trực tiếp database mà thông qua Core Managers.
- **Event Bus:** Khi một giao dịch được thêm, Event Bus phát tín hiệu để Dashboard, Budget, và Forecaster tự động làm mới dữ liệu mà không cần tải lại toàn bộ trang.

---

## 🗄 Cơ sở dữ liệu & Đa người dùng

Tính năng Đa người dùng (Multi-user) được thiết kế ưu tiên sự riêng tư:
- **`data/shared/auth.db`**: Chứa thông tin tài khoản chung. Mật khẩu được mã hóa an toàn bằng thuật toán SHA-256 kèm theo cơ chế Salt.
- **`data/users/{username}/finance.db`**: Mỗi người dùng có một tệp SQLite độc lập. Dữ liệu tài chính không bao giờ bị trộn lẫn.
- **Cấu hình & Model AI Cá nhân hóa:** Mô hình AI phân loại giao dịch (`classifier_model.pkl`) và file cài đặt (`settings.json`) được huấn luyện và lưu riêng cho từng người dùng dựa trên thói quen của chính họ.
- **Hiệu suất SQLite:** Áp dụng các Pragmas như `PRAGMA journal_mode=WAL;`, `PRAGMA temp_store=MEMORY;` để đảm bảo thao tác đọc ghi siêu tốc.

---

## 💻 Yêu cầu hệ thống

- **Hệ điều hành:** Windows 10/11, macOS 12+, hoặc các bản phân phối Linux phổ biến.
- **Python:** Khuyến nghị **Python 3.10** đến **3.12**.
- **Phần cứng:** 
  - Tối thiểu: CPU 2 nhân, 2GB RAM.
  - Khuyến nghị: 4GB+ RAM (Rất cần thiết nếu bạn muốn chạy thư viện Prophet hoặc triển khai Ollama LLM tại máy local).

---

## 🚀 Hướng dẫn cài đặt

### Bước 1: Tải mã nguồn
Clone dự án từ repository về máy tính:
```bash
git clone https://github.com/your-username/finance-ai-app.git
cd finance-ai-app
```

### Bước 2: Thiết lập Môi trường ảo (Virtual Environment)
Việc sử dụng môi trường ảo giúp tránh xung đột thư viện:
```bash
python -m venv venv

# Kích hoạt trên Windows:
venv\Scripts\activate

# Kích hoạt trên macOS / Linux:
source venv/bin/activate
```

### Bước 3: Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```
*Lưu ý: Quá trình cài đặt có thể mất vài phút tuỳ thuộc vào tốc độ mạng của bạn.*

*(Tùy chọn) Cài đặt thư viện Prophet nếu bạn muốn tính năng dự báo chính xác cao:*
```bash
pip install prophet
```

### Bước 4: Khởi chạy ứng dụng
```bash
python main.py
```
*Trong lần chạy đầu tiên, hệ thống sẽ tự động khởi tạo cấu trúc thư mục `data/` và các tệp cơ sở dữ liệu cần thiết.*

---

## 📖 Hướng dẫn sử dụng chi tiết

1. **Đăng nhập / Đăng ký:** Tạo một tài khoản để hệ thống thiết lập phân vùng dữ liệu riêng cho bạn.
2. **Quản lý Giao dịch:** 
   - Truy cập màn hình `Giao dịch`.
   - Nhấn **+ Thêm Mới** hoặc dùng phím tắt `Ctrl+N` để ghi nhận khoản thu chi mới.
   - Hoặc chọn **Nhập từ CSV** để import hàng trăm giao dịch từ file sao kê. Hãy để mô hình AI của ứng dụng tự động phân loại danh mục cho bạn.
3. **Thiết lập Ngân sách:** Sang tab `Ngân sách`, thiết lập hạn mức cho các danh mục (VD: Ăn uống 3.000.000đ). Trở lại Dashboard để xem thanh tiến độ cảnh báo.
4. **Phân tích Dự báo:** Vào `Dự báo AI`, nhấn nút *Chạy phân tích*. Đợi vài giây để hệ thống tính toán và vẽ đồ thị dự kiến dòng tiền tháng tới.
5. **Chat với AI:** Gõ các câu lệnh tiếng Việt tự nhiên vào `Chatbot AI`:
   - *"Tháng này tôi tiêu bao nhiêu tiền ăn uống rồi?"*
   - *"Phân tích các khoản chi tiêu bất thường của tôi trong tháng trước"*
   - *"Làm sao để tiết kiệm tiền mua laptop mới?"*
6. **Command Palette:** Nhấn `Ctrl+K` bất kỳ lúc nào để mở thanh công cụ tìm kiếm, gõ "Báo cáo" để đi tới trang xuất PDF, hoặc "Cài đặt" để đổi giao diện sáng/tối.

---

## ⌨️ Phím tắt (Hotkeys)

Nhằm tối ưu hoá trải nghiệm, Finance AI hỗ trợ hệ thống phím tắt chuyên nghiệp:

| Phím Tắt | Chức năng | Phân hệ |
|:---:|:---|:---|
| <kbd>Ctrl</kbd> + <kbd>K</kbd> | Mở Command Palette (Tìm kiếm nhanh) | Global |
| <kbd>Ctrl</kbd> + <kbd>N</kbd> | Mở cửa sổ Thêm giao dịch mới | Global |
| <kbd>Ctrl</kbd> + <kbd>1</kbd> | Mở màn hình Dashboard | Điều hướng |
| <kbd>Ctrl</kbd> + <kbd>2</kbd> | Mở màn hình Quản lý Giao dịch | Điều hướng |
| <kbd>Ctrl</kbd> + <kbd>3</kbd> | Mở màn hình Ngân sách | Điều hướng |
| <kbd>Ctrl</kbd> + <kbd>4</kbd> | Mở màn hình Phân tích & Dự báo | Điều hướng |
| <kbd>Ctrl</kbd> + <kbd>5</kbd> | Mở Chatbot Trí tuệ Nhân tạo | Điều hướng |
| <kbd>Ctrl</kbd> + <kbd>6</kbd> | Mở trang Báo cáo & Xuất dữ liệu | Điều hướng |
| <kbd>Ctrl</kbd> + <kbd>,</kbd> | Mở Cài đặt hệ thống | Global |
| <kbd>F5</kbd> | Làm mới (Refresh) toàn bộ dữ liệu | Global |
| <kbd>Esc</kbd> | Đóng các hộp thoại (Dialog/Popup) | Dialog |

---

## 🛠 Phát triển & Đóng góp

Chúng tôi luôn hoan nghênh các đóng góp từ cộng đồng (Pull Requests, Bug Reports, Feature Requests). 

### Luồng Phát triển (Development Workflow):
1. **Fork** repository này về tài khoản của bạn.
2. Tạo một branch mới cho tính năng (`git checkout -b feature/your-amazing-feature`).
3. Thực hiện thay đổi, đảm bảo code tuân thủ quy tắc PEP8.
4. **Commit** thay đổi (`git commit -m 'Thêm tính năng XYZ'`).
5. **Push** lên branch (`git push origin feature/your-amazing-feature`).
6. Tạo một **Pull Request** trên Github để chúng tôi có thể review.

### Scripts tiện ích cho Nhà phát triển:
- Nếu bạn cần chuyển đổi CSDL từ bản v0.9 (Cũ) sang v1.0 (Đa người dùng):
  ```bash
  python scripts/migrate_to_per_user_db.py
  ```
- Chạy hệ thống unit test:
  ```bash
  python -m unittest discover tests/
  ```

---

## 👥 Thông tin nhóm phát triển

| Tên Sinh Viên | Mã Sinh Viên | Vai Trò |
|:---|:---|:---|
| **Như Quỳnh** | 25AI043 | AI Model, Backend Logic, Data Processing |
| **Hưng Phú** | 25AI034 | UI/UX Design (PyQt6), Cấu trúc Database |

---
<div align="center">
<i>Finance AI v1.0 — Được phát triển với 💖 bằng Python.</i>
</div>
