# backend/app/config.py
# ============================================================
# Settings — same concept as your Streamlit config.py
# but without the APP_ prefix for simplicity
# ============================================================

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 1500


settings = Settings()
