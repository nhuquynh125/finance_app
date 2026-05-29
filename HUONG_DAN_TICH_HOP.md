# Hướng Dẫn Tích Hợp Các File Đã Sửa / Mới Tạo

## Tổng quan

| File | Loại | Vị trí trong project | Ghi chú |
|---|---|---|---|
| `goal_tracker.py` | Sửa | `app/core/goal_tracker.py` | Viết lại hoàn toàn |
| `family_manager.py` | **Mới** | `app/core/family_manager.py` | Tạo mới |
| `error_handler.py` | Sửa | `app/core/error_handler.py` | Sửa timestamp |
| `logger.py` | **Mới** | `app/core/logger.py` | Tạo mới |
| `transaction_frame.py` | Sửa | `app/ui/transaction_frame.py` | Sửa bug + thêm tính năng |
| `family_frame.py` | Sửa | `app/ui/family_frame.py` | Dùng FamilyManager thực |
| `repositories.py` | Sửa | `app/data/repositories.py` | validate() chặt hơn |
| `test_finance_ai.py` | **Mới** | `tests/test_finance_ai.py` | Unit tests |

---

## Chi tiết từng file

---

### 1. `goal_tracker.py` → `app/core/goal_tracker.py`

**Thay thế hoàn toàn** file cũ.

**Những gì đã sửa:**
- Bỏ `self.conn` (giữ connection mở mãi → lỗi)
- `avg_savings_per_month = 5000000` hardcode → tính từ transactions thực tế
- `get_prediction()` trả về `dict` có cấu trúc thay vì `str` đơn giản
- Thêm `delete_goal()`, `get_goal_by_id()`, `get_summary()`
- Thêm validation trong `add_goal()` và `update_progress()`

**Không cần sửa gì thêm** — import vẫn như cũ:
```python
from app.core.goal_tracker import GoalTracker
```

---

### 2. `family_manager.py` → `app/core/family_manager.py` *(file mới)*

**Tạo file mới** trong `app/core/`.

**Chức năng:**
- `create_group(name)` → tạo nhóm, lưu DB, trả về invite_code
- `join_group(invite_code)` → tham gia nhóm bằng mã 6 ký tự
- `leave_group()` → rời nhóm (member)
- `disband_group()` → giải tán nhóm (owner)
- `get_my_group()` → thông tin nhóm hiện tại
- `get_members(group_id)` → danh sách thành viên

**Cách import:**
```python
from app.core.family_manager import FamilyManager
```

---

### 3. `error_handler.py` → `app/core/error_handler.py`

**Thay thế** file cũ.

**Những gì đã sửa:**
```python
# CŨ (sai) — mtime là thời điểm sửa file, không phải lúc lỗi
f.write(f"Timestamp: {Path('data/error.log').stat().st_mtime}\n")

# MỚI (đúng)
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
f.write(f"Timestamp : {timestamp}\n")
```

**Cải thiện thêm:**
- Tích hợp `logging` module
- Log rotate tự động khi > 5MB
- Hiển thị tên user đang đăng nhập khi có lỗi

**Import trong `main.py` không đổi:**
```python
from app.core.error_handler import setup_global_handler
```

---

### 4. `logger.py` → `app/core/logger.py` *(file mới)*

**Tạo file mới** trong `app/core/`.

**Mục đích:** Thay tất cả `print()` debug bằng logging chuẩn.

**Cách dùng trong các module khác:**
```python
from app.core.logger import get_logger

logger = get_logger(__name__)

# Thay print(f"[AI Worker] {e}")  bằng:
logger.error(f"Lỗi phân loại AI: {e}", exc_info=True)

# Thay print(f"[DB] Initialized: {db_path}")  bằng:
logger.info(f"Database khởi tạo: {db_path}")
```

**Hoặc dùng logger có sẵn:**
```python
from app.core.logger import ai_logger, db_logger, ui_logger

ai_logger.warning("Model chưa được train")
db_logger.info("Kết nối DB thành công")
```

---

### 5. `transaction_frame.py` → `app/ui/transaction_frame.py`

**Thay thế** file cũ.

**Những gì đã sửa:**

**(a) Sửa bug nghiêm trọng:**
```python
# CŨ (lỗi runtime) — add_transaction() trả về int, không có .get()
alert = self.tm.add_transaction(**data)
if alert and alert.get("type") == "budget_alert":  # ERROR!

# MỚI (đúng)
self.tm.add_transaction(**data)
# Budget alert tự động phát qua bus.notify_warning
```

**(b) TransactionDialog — thêm dropdown chọn tài khoản:**
```python
# CŨ — hardcode
"account_id": 1,

# MỚI — dropdown từ DB
self.cb_account = QComboBox()
# ... load từ accounts table ...
"account_id": self.cb_account.currentData() or 1,
```

**(c) Thêm phân trang (pagination):**
- 100 dòng/trang
- Nút "◀ Trước" / "Tiếp ▶" ở statusbar
- Hiển thị "Trang X / Y"
- Reset về trang 1 khi filter thay đổi

---

### 6. `family_frame.py` → `app/ui/family_frame.py`

**Thay thế** file cũ.

**Những gì đã sửa:**
- Dùng `FamilyManager` thực thay vì `QMessageBox` giả lập
- Hiển thị thông tin nhóm, danh sách thành viên
- Nút "Rời nhóm" và "Giải tán nhóm" có logic thật
- Tự load trạng thái nhóm khi mở trang

---

### 7. `repositories.py` → `app/data/repositories.py`

**Thay thế** file cũ.

**Những gì đã sửa trong `TransactionModel.validate()`:**

| Kiểm tra | Cũ | Mới |
|---|---|---|
| Amount âm | ✅ | ✅ |
| Amount > 10 tỷ | ❌ | ✅ |
| Type hợp lệ | ✅ | ✅ |
| Date format | ✅ | ✅ |
| Date tương lai > 1 năm | ❌ | ✅ |
| Date quá cũ > 50 năm | ❌ | ✅ |
| Description trống | ✅ | ✅ |
| Description > 200 ký tự | ❌ | ✅ |
| Note > 500 ký tự | ❌ | ✅ |
| account_id hợp lệ | ❌ | ✅ |

---

### 8. `test_finance_ai.py` → `tests/test_finance_ai.py` *(file mới)*

**Tạo thư mục `tests/`** trong thư mục gốc project, rồi đặt file vào.

**Cấu trúc thư mục sau khi thêm:**
```
finance-ai/
├── tests/
│   ├── __init__.py          ← tạo file rỗng này
│   └── test_finance_ai.py   ← file test
```

**Tạo file `tests/__init__.py` rỗng:**
```bash
# Windows
type nul > tests\__init__.py

# macOS/Linux
touch tests/__init__.py
```

**Cài pytest và chạy:**
```bash
pip install pytest
pytest tests/test_finance_ai.py -v
```

**Kết quả mong đợi:**
```
tests/test_finance_ai.py::TestNlpParser::test_parse_amount_k PASSED
tests/test_finance_ai.py::TestNlpParser::test_parse_amount_nghìn PASSED
...
31 passed in X.XXs
```

---

## Thứ tự tích hợp khuyến nghị

```
Bước 1: Copy các file vào đúng vị trí
Bước 2: Tạo tests/__init__.py (file rỗng)
Bước 3: Chạy pytest để kiểm tra
Bước 4: Chạy app và test thủ công:
         - Thêm giao dịch → kiểm tra dropdown tài khoản
         - Trang Gia đình → tạo nhóm → xem mã mời
         - Trang Gia đình → tham gia nhóm bằng mã
```

---

## Lưu ý quan trọng

**`family_manager.py` dùng bảng `family_groups` và `group_members`** đã có sẵn trong `init_database()` (file `models.py`). Không cần migration thêm.

**Nếu chạy app và báo lỗi thiếu bảng**, chạy lại `init_database()` một lần:
```python
from app.data.models import init_database
init_database()
```

Hoặc đơn giản hơn: xóa `finance.db` của user (ở `data/users/{username}/finance.db`) và đăng nhập lại — app sẽ tự tạo DB mới với đầy đủ bảng.
