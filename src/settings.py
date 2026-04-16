from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # 스케줄
    send_hour: int = 8
    send_minute: int = 0
    timezone: str = "Asia/Seoul"

    # 아티클
    article_count: int = 5
    article_language: str = "ko"

    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # 수신자 (콤마 구분 문자열 → list)
    recipient_emails: list[str] = []

    # DB
    database_url: str = "sqlite:///./data/article_mailer.db"

    @field_validator("recipient_emails", mode="before")
    @classmethod
    def split_emails(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [e.strip() for e in v.split(",") if e.strip()]
        return v


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
