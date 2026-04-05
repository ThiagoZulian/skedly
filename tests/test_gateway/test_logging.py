"""Tests for structured JSON logging configuration."""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest.mock import patch


def test_json_logging_format_produces_valid_json() -> None:
    """When LOG_FORMAT=json the handler emits valid JSON lines."""
    from src.config import settings
    from pythonjsonlogger import json as jsonlogger

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)

    test_logger = logging.getLogger("test_json_format")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    test_logger.info("hello world", extra={"user_id": "42", "chat_id": 99})

    output = stream.getvalue().strip()
    assert output, "Expected log output but got nothing"

    record = json.loads(output)
    assert record["level"] == "INFO"
    assert record["logger"] == "test_json_format"
    assert record["message"] == "hello world"
    assert "timestamp" in record


def test_text_logging_does_not_use_json_formatter() -> None:
    """When LOG_FORMAT=text the formatter is the standard text format."""
    from src.config import settings

    with patch.object(settings, "log_format", "text"):
        # Re-running _configure_logging with handlers cleared to test isolation.
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers = []

        try:
            from src.gateway.app import _configure_logging
            _configure_logging()

            # With text format, no JsonFormatter should be on root handlers.
            from pythonjsonlogger import json as jsonlogger
            for h in root.handlers:
                assert not isinstance(h.formatter, jsonlogger.JsonFormatter), (
                    "JsonFormatter should NOT be used in text mode"
                )
        finally:
            root.handlers = original_handlers


def test_json_logging_configures_json_formatter() -> None:
    """When LOG_FORMAT=json, _configure_logging installs a JsonFormatter."""
    from pythonjsonlogger import json as jsonlogger

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    root.handlers = []

    try:
        from src.config import settings
        with patch.object(settings, "log_format", "json"):
            from src.gateway.app import _configure_logging
            _configure_logging()

            assert root.handlers, "Expected at least one handler"
            assert isinstance(root.handlers[0].formatter, jsonlogger.JsonFormatter)
    finally:
        root.handlers = original_handlers


def test_json_logging_propagates_to_library_loggers() -> None:
    """When LOG_FORMAT=json, uvicorn and apscheduler loggers use the JSON handler."""
    from pythonjsonlogger import json as jsonlogger

    root = logging.getLogger()
    original_root_handlers = root.handlers[:]
    root.handlers = []

    # Save and reset library loggers
    lib_names = ("uvicorn", "uvicorn.access", "uvicorn.error", "apscheduler")
    originals = {n: (logging.getLogger(n).handlers[:], logging.getLogger(n).propagate)
                 for n in lib_names}
    for n in lib_names:
        logging.getLogger(n).handlers = []

    try:
        from src.config import settings
        with patch.object(settings, "log_format", "json"):
            from src.gateway.app import _configure_logging
            _configure_logging()

            for name in lib_names:
                lib_logger = logging.getLogger(name)
                assert lib_logger.handlers, f"{name} should have a handler"
                assert isinstance(lib_logger.handlers[0].formatter, jsonlogger.JsonFormatter), (
                    f"{name} handler should use JsonFormatter"
                )
    finally:
        root.handlers = original_root_handlers
        for n, (handlers, propagate) in originals.items():
            lib_logger = logging.getLogger(n)
            lib_logger.handlers = handlers
            lib_logger.propagate = propagate
