# embedded_llm.py  (cập nhật: per-user AI model path)
"""
Chạy LLM nhỏ trực tiếp trong app bằng HuggingFace Transformers.

Thay đổi: FINETUNED_DIR lấy từ user_session.session.ai_dir
thay vì DATA_DIR cố định — mỗi user có model fine-tune riêng.
"""

from PyQt6.QtCore import QThread, pyqtSignal


def _get_finetuned_dir():
    """Đường dẫn thư mục fine-tuned model của user hiện tại."""
    try:
        from user_session import session
        if session.is_logged_in:
            return session.ai_dir / "fine_tuned_model"
    except ImportError:
        pass
    try:
        from config import DATA_DIR
        from pathlib import Path
        return Path(DATA_DIR) / "fine_tuned_model"
    except ImportError:
        from pathlib import Path
        return Path("data") / "fine_tuned_model"


class EmbeddedLLMWorker(QThread):
    token_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)
    progress       = pyqtSignal(str)

    def __init__(self, prompt: str, system_context: str = "",
                 use_finetuned: bool = True,
                 max_new_tokens: int = 300):
        super().__init__()
        self.prompt         = prompt
        self.system_context = system_context
        self.use_finetuned  = use_finetuned
        self.max_new_tokens = max_new_tokens

    def run(self):
        try:
            import torch
            from transformers import (
                AutoTokenizer, AutoModelForCausalLM,
                TextIteratorStreamer
            )
            from threading import Thread

            finetuned_dir = _get_finetuned_dir()

            # Chọn model nguồn
            if self.use_finetuned and finetuned_dir.exists():
                model_path = str(finetuned_dir)
                self.progress.emit("Đang tải model đã fine-tune...")
            else:
                model_path = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
                self.progress.emit(
                    "Đang tải TinyLlama lần đầu (~600MB)...\n"
                    "Lần sau sẽ dùng offline.")

            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if torch.cuda.is_available()
                            else torch.float32,
                device_map="auto",
                low_cpu_mem_usage=True,
            )

            # Format prompt theo từng model
            if finetuned_dir.exists() and self.use_finetuned:
                full_prompt = (
                    f"Nguoi dung: {self.prompt}\n"
                    f"Tra loi:"
                )
            else:
                full_prompt = (
                    f"<|system|>\n{self.system_context}</s>\n"
                    f"<|user|>\n{self.prompt}</s>\n"
                    f"<|assistant|>\n"
                )

            inputs = tokenizer(
                full_prompt, return_tensors="pt"
            ).to(model.device)

            streamer = TextIteratorStreamer(
                tokenizer,
                skip_prompt=True,
                skip_special_tokens=True
            )

            gen_kwargs = {
                **inputs,
                "streamer":           streamer,
                "max_new_tokens":     self.max_new_tokens,
                "temperature":        0.7,
                "do_sample":          True,
                "repetition_penalty": 1.1,
                "pad_token_id":       tokenizer.eos_token_id,
            }

            thread = Thread(target=model.generate, kwargs=gen_kwargs)
            thread.start()

            full_text = ""
            for token in streamer:
                full_text += token
                self.token_received.emit(token)

            thread.join()
            self.finished.emit(full_text)

        except ImportError:
            self.error.emit(
                "Thiếu thư viện! Chạy lệnh:\n\n"
                "pip install transformers torch accelerate"
            )
        except Exception as e:
            self.error.emit(str(e))
