"""Configuración centralizada de Gwen OS.

Carga variables de entorno desde .env usando pydantic-settings.
Todas las variables usan el prefijo GWEN_ para evitar colisiones.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del sistema completo."""

    model_config = SettingsConfigDict(
        env_prefix="GWEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Notion ---
    notion_token: str = ""
    notion_database_id: str = ""

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_keep_alive: str = "30m"

    # --- Obsidian ---
    obsidian_vault_path: str = ""

    # --- ChromaDB ---
    chroma_persist_dir: str = "./data/chroma"

    # --- n8n ---
    n8n_base_url: str = "http://localhost:5678"

    # --- API Gateway ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- HUD ---
    hud_port: int = 8501

    # --- Telegram (Fase 4) ---
    telegram_bot_token: str = ""

    # --- Google (Fase 3) ---
    google_client_id: str = ""
    google_client_secret: str = ""

    # --- Todoist (Fase 3) ---
    todoist_token: str = ""

    # --- Canvas (Fase 5) ---
    canvas_base_url: str = ""
    canvas_token: str = ""

    # --- Gemini (opcional) ---
    gemini_api_key: str = ""

    @property
    def vault_path(self) -> Path:
        """Path del vault de Obsidian como objeto Path."""
        return Path(self.obsidian_vault_path)

    @property
    def chroma_path(self) -> Path:
        """Path de persistencia de ChromaDB."""
        return Path(self.chroma_persist_dir)


@lru_cache
def get_settings() -> Settings:
    """Singleton de Settings (cacheado)."""
    return Settings()
