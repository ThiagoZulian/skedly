"""Application settings loaded from environment variables via Pydantic BaseSettings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for SecretarIA.

    All values are read from environment variables or the .env file.
    Fields without defaults are required; fields with None defaults are optional.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = Field(..., description="Telegram Bot API token")
    telegram_webhook_secret: str = Field(..., description="Secret header for webhook validation")

    # ── ClickUp ───────────────────────────────────────────────────────────────
    clickup_api_token: str = Field(..., description="ClickUp API v2 personal token")
    clickup_team_id: str = Field(..., description="ClickUp workspace (team) ID")
    clickup_webhook_secret: str | None = Field(
        default=None, description="HMAC secret for ClickUp webhook validation"
    )

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude Sonnet")

    # ── Google AI (Gemini) ────────────────────────────────────────────────────
    google_ai_api_key: str = Field(..., description="Google AI Studio API key for Gemini Flash")

    # ── App ───────────────────────────────────────────────────────────────────
    app_host: str = Field(default="0.0.0.0", description="Uvicorn host binding")
    app_port: int = Field(default=8000, description="Uvicorn port")
    app_secret_key: str = Field(..., description="App-level secret key for signing")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./data/secretary.db",
        description="SQLAlchemy async database URL",
    )

    # ── Model routing ─────────────────────────────────────────────────────────
    default_model: str = Field(
        default="gemini-flash",
        description="Model alias used for simple/medium intents",
    )
    complex_model: str = Field(
        default="claude-sonnet",
        description="Model alias used for complex intents",
    )

    # ── LangSmith (optional) ──────────────────────────────────────────────────
    langsmith_api_key: str | None = Field(default=None, description="LangSmith API key")
    langsmith_project: str = Field(
        default="secretaria", description="LangSmith project name"
    )
    langsmith_tracing: bool = Field(
        default=False, description="Enable LangSmith tracing"
    )
