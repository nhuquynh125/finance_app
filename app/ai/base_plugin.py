# base_plugin.py  (cập nhật: EmbeddedPlugin dùng per-user AI dir)
"""
Plugin interface cho AI chat engine.

Thay đổi: EmbeddedPlugin.check_status() và create_worker()
dùng user_session để tìm fine-tuned model của user hiện tại.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    pass


def _get_user_ai_dir():
    """Thư mục AI của user hiện tại."""
    try:
        from user_session import session
        if session.is_logged_in:
            return session.ai_dir
    except ImportError:
        pass
    try:
        from config import DATA_DIR
        from pathlib import Path
        return Path(DATA_DIR)
    except ImportError:
        from pathlib import Path
        return Path("data")


# ── Base worker interface ─────────────────────────────────────────────────────

class BaseAIWorker(QThread):
    token_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)
    progress       = pyqtSignal(str)

    def run(self) -> None:
        raise NotImplementedError


# ── Base plugin interface ─────────────────────────────────────────────────────

class BaseAIPlugin(ABC):
    engine_id: str = ""
    engine_label: str = ""
    requires_internet: bool = True

    @abstractmethod
    def create_worker(self, messages: list[dict],
                      system_prompt: str) -> BaseAIWorker: ...

    @abstractmethod
    def check_status(self) -> tuple[bool, str]: ...

    def get_badge_level(self, is_ready: bool) -> str:
        return "ok" if is_ready else "err"

    def on_settings_changed(self, settings: dict) -> None:
        pass


# ── Concrete plugin implementations ──────────────────────────────────────────

class GeminiPlugin(BaseAIPlugin):
    engine_id         = "gemini"
    engine_label      = "Gemini API (Google)"
    requires_internet = True

    def create_worker(self, messages: list[dict],
                      system_prompt: str) -> BaseAIWorker:
        from app.ai.gemini_worker import GeminiWorker
        return GeminiWorker(messages, system_prompt)  # type: ignore

    def check_status(self) -> tuple[bool, str]:
        from app.core.settings_manager import get_env_value
        key = get_env_value("GEMINI_API_KEY")
        if key:
            return True, "Gemini API sẵn sàng"
        return False, "Chưa có GEMINI_API_KEY — xem hướng dẫn"

    def get_badge_level(self, is_ready: bool) -> str:
        return "ok" if is_ready else "err"


class OllamaPlugin(BaseAIPlugin):
    engine_id         = "ollama"
    engine_label      = "Ollama — chạy offline (khuyến dùng)"
    requires_internet = False

    def create_worker(self, messages: list[dict],
                      system_prompt: str) -> BaseAIWorker:
        from app.ai.local_llm import OllamaWorker, get_available_models
        models = [m for m in get_available_models() if "cloud" not in m.lower()]
        model = models[0] if models else "qwen2.5:3b"
        return OllamaWorker(messages, system_prompt, model=model)  # type: ignore

    def check_status(self) -> tuple[bool, str]:
        from app.ai.local_llm import check_ollama_running, get_available_models
        if not check_ollama_running():
            return False, "Ollama chưa chạy — mở app Ollama trước"
        models = get_available_models()
        local = [m for m in models if "cloud" not in m.lower()]
        if local:
            return True, f"Ollama sẵn sàng · {local[0]}"
        return False, "Chưa có model offline — chạy: ollama pull qwen2.5:3b"

    def get_badge_level(self, is_ready: bool) -> str:
        if is_ready:
            return "ok"
        from app.ai.local_llm import check_ollama_running
        return "err" if not check_ollama_running() else "warn"


class EmbeddedPlugin(BaseAIPlugin):
    engine_id         = "embedded"
    engine_label      = "Model nhúng (transformers)"
    requires_internet = False

    def create_worker(self, messages: list[dict],
                      system_prompt: str) -> BaseAIWorker:
        from app.ai.embedded_llm import EmbeddedLLMWorker

        # Dùng fine-tuned model của user nếu có
        ai_dir = _get_user_ai_dir()
        finetuned_dir = ai_dir / "fine_tuned_model"
        has_ft = finetuned_dir.exists()

        prompt = messages[-1]["content"] if messages else ""
        return EmbeddedLLMWorker(  # type: ignore
            prompt, system_context=system_prompt, use_finetuned=has_ft
        )

    def check_status(self) -> tuple[bool, str]:
        ai_dir = _get_user_ai_dir()
        finetuned_dir = ai_dir / "fine_tuned_model"
        has_ft = finetuned_dir.exists()
        if has_ft:
            return True, "Model fine-tuned sẵn sàng"
        return True, "Sẽ dùng TinyLlama (tự tải ~600MB lần đầu)"

    def get_badge_level(self, is_ready: bool) -> str:
        return "ok" if is_ready else "info"


# ── Registry ──────────────────────────────────────────────────────────────────

class AIPluginRegistry:
    def __init__(self):
        self._plugins: dict[str, BaseAIPlugin] = {}

    def register(self, plugin: BaseAIPlugin) -> None:
        self._plugins[plugin.engine_id] = plugin

    def unregister(self, engine_id: str) -> None:
        self._plugins.pop(engine_id, None)

    def get(self, engine_id: str) -> Optional[BaseAIPlugin]:
        return self._plugins.get(engine_id)

    def all(self) -> list[BaseAIPlugin]:
        return list(self._plugins.values())

    def labels(self) -> dict[str, str]:
        return {p.engine_id: p.engine_label for p in self._plugins.values()}

    def check_all_status(self) -> dict[str, tuple[bool, str]]:
        return {
            eid: plugin.check_status()
            for eid, plugin in self._plugins.items()
        }


# Singleton registry
registry = AIPluginRegistry()
registry.register(GeminiPlugin())
registry.register(OllamaPlugin())
registry.register(EmbeddedPlugin())
