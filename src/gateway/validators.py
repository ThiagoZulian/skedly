"""Request validation helpers for incoming webhooks."""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def validate_clickup_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate a ClickUp webhook HMAC-SHA256 signature.

    ClickUp sends the signature in the ``X-Signature`` header as a hex digest.

    Args:
        payload: Raw request body bytes.
        signature: Value from the ``X-Signature`` header.
        secret: The HMAC secret configured in ClickUp.

    Returns:
        True if the signature is valid, False otherwise.
    """
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def validate_telegram_secret(header_value: str | None, expected_secret: str) -> bool:
    """Validate the Telegram webhook secret token header.

    Telegram sends the token set during ``setWebhook`` in the
    ``X-Telegram-Bot-Api-Secret-Token`` header.

    Args:
        header_value: Value from the ``X-Telegram-Bot-Api-Secret-Token`` header.
        expected_secret: The secret configured when registering the webhook.

    Returns:
        True if the header matches the expected secret.
    """
    if header_value is None:
        logger.warning("Missing Telegram webhook secret header")
        return False
    return hmac.compare_digest(header_value, expected_secret)
