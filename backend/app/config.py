"""
AI Resume Search Engine - Backend Configuration
"""
import secrets
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./resume_search.db"

    # Groq API
    groq_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"

    # Plagiarism
    rapidapi_key: str = ""
    plagiarism_threshold: float = 30.0

    # AI authorship signal (uses the same RapidAPI app key by default)
    rapidapi_ai_detector_key: str = ""
    rapidapi_ai_detector_host: str = "ai-generated-content-detector.p.rapidapi.com"
    rapidapi_ai_detector_url: str = "https://ai-generated-content-detector.p.rapidapi.com/data"

    # JWT
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48), min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # File Upload
    upload_dir: str = "./uploads"
    max_file_size: int = 10 * 1024 * 1024

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Email (Resend)
    resend_api_key: str = ""
    resend_from_email: str = "noreply@yourdomain.com"
    email_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
