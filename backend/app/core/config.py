from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), extra="ignore")

    app_name: str = "QScope Test Case Generator"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    local_data_dir: Path = REPO_ROOT / "local_data"

    gemini_api_key: str | None = None
    gemini_default_model: str = "gemini-3.8-flash"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_host: str = "http://localhost:11434"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    max_upload_size_mb: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
