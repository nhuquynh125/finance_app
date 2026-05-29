import os
import json
import base64
import logging
import urllib.request
import urllib.error
from pathlib import Path
from app.data.models import _get_current_db_path
from app.core.settings_manager import get_env_value

logger = logging.getLogger(__name__)

class SyncManager:
    """
    Quản lý việc đồng bộ hóa dữ liệu (database) lên đám mây.
    Hiện tại hỗ trợ giả lập hoặc API đồng bộ file đơn giản.
    """
    
    @staticmethod
    def sync_to_cloud() -> tuple[bool, str]:
        """
        Đẩy database hiện tại lên cloud.
        Hỗ trợ: Supabase Storage (nếu cấu hình), ngược lại dùng giả lập.
        """
        DB_PATH = _get_current_db_path()
        if not DB_PATH.exists():
            return False, "Không tìm thấy file dữ liệu để đồng bộ."
            
        supabase_url = get_env_value("SUPABASE_URL", "")
        supabase_key = get_env_value("SUPABASE_KEY", "")
        
        if supabase_url and supabase_key:
            # Logic đồng bộ lên Supabase Storage qua REST API
            try:
                with open(DB_PATH, "rb") as f:
                    file_data = f.read()
                
                # Ví dụ: Bucket tên là 'backups', file là 'finance.db'
                bucket = "backups"
                file_path = "finance.db"
                url = f"{supabase_url}/storage/v1/object/{bucket}/{file_path}"
                
                # Header cho Supabase
                headers = {
                    "Authorization": f"Bearer {supabase_key}",
                    "apikey": supabase_key,
                    "Content-Type": "application/x-sqlite3",
                    "x-upsert": "true"
                }
                
                req = urllib.request.Request(url, data=file_data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status in (200, 201):
                        return True, "Đã đồng bộ dữ liệu lên Supabase Storage thành công!"
                    else:
                        return False, f"Lỗi Supabase: {resp.status}"
            except Exception as e:
                logger.error(f"Supabase sync error: {e}")
                return False, f"Lỗi Supabase: {str(e)}"

        # Nếu không có Supabase, dùng API cũ hoặc giả lập
        api_url = get_env_value("SYNC_API_URL", "")
        if not api_url:
            return True, "Đã sao lưu dữ liệu lên hệ thống đám mây (Chế độ giả lập)."

        try:
            # Đọc file database và encode base64 để gửi qua JSON
            with open(DB_PATH, "rb") as f:
                db_content = base64.b64encode(f.read()).decode("utf-8")
                
            payload = json.dumps({
                "file_name": "finance.db",
                "content": db_content,
                "timestamp": os.path.getmtime(DB_PATH)
            }).encode("utf-8")
            
            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    return True, "Đồng bộ dữ liệu thành công!"
                else:
                    return False, f"Lỗi từ máy chủ: {resp.status}"
                    
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False, f"Lỗi khi đồng bộ: {str(e)}"

    @staticmethod
    def download_from_cloud() -> tuple[bool, str]:
        """
        Tải database từ cloud về máy.
        """
        DB_PATH = _get_current_db_path()
        api_url = get_env_value("SYNC_API_URL", "")
        if not api_url:
            return False, "Chưa cấu hình URL máy chủ đồng bộ."
            
        try:
            req = urllib.request.Request(api_url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = base64.b64decode(data["content"])
                    
                    # Backup database cũ trước khi ghi đè
                    if DB_PATH.exists():
                        backup_path = DB_PATH.with_suffix(".db.bak")
                        import shutil
                        shutil.copy2(DB_PATH, backup_path)
                        
                    with open(DB_PATH, "wb") as f:
                        f.write(content)
                    return True, "Đã khôi phục dữ liệu từ đám mây."
                else:
                    return False, f"Lỗi từ máy chủ: {resp.status}"
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, f"Lỗi khi tải dữ liệu: {str(e)}"
