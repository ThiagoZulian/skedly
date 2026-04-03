"""Config package — exposes a lazy singleton Settings instance.

The settings object is constructed on first access, not at import time.
This allows tests to inject environment variables before Settings is
instantiated (no .env file required in the test environment).
"""

from __future__ import annotations

from src.config.settings import Settings

_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


class _LazySettings:
    """Proxy that defers Settings() construction until first attribute access."""

    def __getattr__(self, name: str):  # type: ignore[override]
        return getattr(_get_settings(), name)

    def __repr__(self) -> str:
        return repr(_get_settings())


settings = _LazySettings()

__all__ = ["settings"]
