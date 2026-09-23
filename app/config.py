from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Legal Document Analyzer"
    database_url: str = "sqlite:///./data/legal_analyzer.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 25
    ocr_enabled: bool = False
    tesseract_cmd: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    user_tokens_json: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
