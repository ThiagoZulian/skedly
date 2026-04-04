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
    clickup_default_list_id: str | None = Field(
        default=None, description="Default ClickUp list ID for task creation/listing"
    )

    # ── Google AI (Gemini) ────────────────────────────────────────────────────
    google_ai_api_key: str = Field(
        ..., description="Google AI Studio API key (used for Gemini Flash and Gemini Pro)"
    )

    # ── Google Calendar ───────────────────────────────────────────────────────
    google_calendar_id: str = Field(
        default="primary", description="Google Calendar ID to use (default: primary)"
    )

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
        default="gemini-pro",
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

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(
        default=30, description="Max requests per minute per chat_id on the Telegram webhook"
    )

    # ── Proactive features ────────────────────────────────────────────────────
    telegram_chat_id: str | None = Field(
        default=None, description="Default Telegram chat ID for proactive outbound messages"
    )
    briefing_hour: int = Field(
        default=8, description="Hour (0-23, America/Sao_Paulo) to send daily briefing"
    )
    deadline_alert_days: int = Field(
        default=2, description="How many days ahead to look for upcoming ClickUp deadlines"
    )
