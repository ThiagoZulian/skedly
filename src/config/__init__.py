"""Config package — exposes a singleton Settings instance."""

from src.config.settings import Settings

settings = Settings()

__all__ = ["settings"]
