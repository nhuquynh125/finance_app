# app/ai/local_llm.py
"""
Gọi Ollama local API — chạy LLM hoàn toàn offline trên máy.
Cài Ollama: https://ollama.com
Tải model: ollama pull qwen2.5:3b
"""
import requests
import json
from PyQt6.QtCore import QThread, pyqtSignal


class OllamaWorker(QThread):
    token_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)

    OLLAMA_URL = "http://localhost:11434/api/chat"

    def __init__(self, messages: list, system_prompt: str,
                 model: str = "qwen2.5:3b"):
        super().__init__()
        self.messages      = messages
        self.system_prompt = system_prompt
        self.model         = model

    def run(self):
        try:
            payload = {
                "model":  self.model,
                "stream": True,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    *self.messages
                ],
                "options": {
                    "temperature": 0.7,
                    "num_ctx":     4096,
                }
            }
            response = requests.post(
                self.OLLAMA_URL, json=payload,
                stream=True, timeout=120)
            response.raise_for_status()

            full_text = ""
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_text += token
                    self.token_received.emit(token)
                if chunk.get("done"):
                    break

            self.finished.emit(full_text)

        except requests.ConnectionError:
            self.error.emit(
                "Ollama chưa chạy!\n\n"
                "Mở Command Prompt và chạy:\n"
                "  ollama serve\n\n"
                "Hoặc mở app Ollama trên máy."
            )
        except requests.HTTPError as e:
            if "404" in str(e):
                self.error.emit(
                    f"Model '{self.model}' chưa được tải.\n\n"
                    f"Chạy lệnh:\n  ollama pull {self.model}"
                )
            else:
                self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))


def check_ollama_running() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def get_available_models() -> list:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
