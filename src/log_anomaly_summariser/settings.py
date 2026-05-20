from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "log-anomaly-summariser"
    database_url: str = Field(alias="DATABASE_URL")

    ollama_base_url: str = Field(default="http://host.docker.internal:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")

    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")

    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_pass: str | None = Field(default=None, alias="SMTP_PASS")
    smtp_from: str | None = Field(default=None, alias="SMTP_FROM")
    smtp_to: str | None = Field(default=None, alias="SMTP_TO")

    incident_error_count_threshold: int = Field(default=10, alias="INCIDENT_ERROR_COUNT_THRESHOLD")
    incident_keywords: str = Field(
        default="traceback,panic,out of memory,connection refused,segmentation fault",
        alias="INCIDENT_KEYWORDS",
    )


def get_settings() -> Settings:
    return Settings()

