"""Shared SlowAPI limiter instance for rate limiting."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# SlowAPI does not support async key_func — the function must be synchronous.
# For a single-user personal assistant, rate limiting by remote IP is equivalent
# to per-chat limiting and avoids the coroutine-never-awaited RuntimeWarning.
limiter = Limiter(key_func=get_remote_address)
