# app/ai/gemini_worker.py
# Gọi Gemini API dùng urllib (có sẵn trong Python, không cần cài thêm gì)

import json
import logging
import os
import urllib.request
import urllib.error

from PyQt6.QtCore import QThread, pyqtSignal

# Thử import từ config nếu có thể, nếu không dùng mặc định
try:
    from config import GEMINI_MODEL
except (ImportError, AttributeError):
    GEMINI_MODEL = "gemini-1.5-flash"

logger = logging.getLogger(__name__)


class GeminiWorker(QThread):
    token_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self, messages: list[dict], system_prompt: str):
        super().__init__()
        self.messages      = messages
        self.system_prompt = system_prompt
        self._is_cancelled = False

    def stop(self):
        """Dừng worker an toàn."""
        self._is_cancelled = True

    def run(self):
        # Lấy key từ environment — KHÔNG bao giờ hardcode
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            logger.error("Thiếu GEMINI_API_KEY trong biến môi trường.")
            self.error.emit(
                "Chưa có GEMINI_API_KEY!\n\n"
                "Lấy key miễn phí tại: https://aistudio.google.com/app/apikey\n"
                "Sau đó mở Cài đặt và lưu key trong mục API key."
            )
            return

        try:
            if self._is_cancelled: return

            contents = []
            for msg in self.messages:
                # Chuyển đổi role cho đúng định dạng Gemini API
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })

            payload_dict = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                }
            }

            # Thêm system instruction nếu có
            if self.system_prompt:
                payload_dict["system_instruction"] = {
                    "parts": [{"text": self.system_prompt}]
                }

            payload = json.dumps(payload_dict).encode("utf-8")

            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{GEMINI_MODEL}:streamGenerateContent?alt=sse&key={api_key}"
            )

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            logger.info(f"Đang gửi yêu cầu streaming tới Gemini API (model: {GEMINI_MODEL})...")
            
            full_text = ""
            with urllib.request.urlopen(req, timeout=45) as resp:
                for line in resp:
                    if self._is_cancelled:
                        break
                    
                    line_str = line.decode("utf-8").strip()
                    if not line_str or line_str == "data: [DONE]":
                        continue
                    
                    if line_str.startswith("data: "):
                        try:
                            json_str = line_str[6:]
                            data = json.loads(json_str)
                            
                            # Cấu trúc của stream response hơi khác một chút
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    token = parts[0].get("text", "")
                                    if token:
                                        full_text += token
                                        self.token_received.emit(token)
                        except Exception as e:
                            logger.error(f"Lỗi phân tích chunk: {e}")
                            continue

            if not full_text and not self._is_cancelled:
                self.error.emit("Gemini trả về phản hồi rỗng. Thử lại sau.")
                return

            if not self._is_cancelled:
                self.finished.emit(full_text)
                logger.info("Hoàn thành xử lý yêu cầu Gemini.")

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            try:
                error_data = json.loads(body)
                msg = error_data.get("error", {}).get("message", body)
                status_code = error_data.get("error", {}).get("code", e.code)
            except Exception:
                msg = body
                status_code = e.code
            
            logger.error(f"Gemini HTTP Error {status_code}: {msg}")
            
            if status_code == 429:
                self.error.emit("Bạn đã vượt quá giới hạn lượt truy vấn (Rate limit). Vui lòng đợi một lát.")
            elif status_code == 400:
                self.error.emit(f"Yêu cầu không hợp lệ: {msg}")
            else:
                self.error.emit(f"Lỗi Gemini API ({status_code}): {msg}")

        except urllib.error.URLError as e:
            logger.error(f"Lỗi kết nối mạng: {e.reason}")
            self.error.emit("Không thể kết nối tới máy chủ Gemini. Vui lòng kiểm tra internet.")

        except Exception as e:
            logger.exception("Lỗi không mong muốn trong GeminiWorker")
            self.error.emit(f"Đã xảy ra lỗi: {str(e)}")
