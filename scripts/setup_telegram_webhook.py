"""Register (or remove) the Telegram Bot API webhook.

Usage:
    # Register:
    python scripts/setup_telegram_webhook.py https://your-public-domain.com

    # Remove (reset):
    python scripts/setup_telegram_webhook.py --remove

DO NOT run this script locally unless your server is publicly reachable.
The webhook URL must be HTTPS and return 200 on POST /webhook/telegram.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

# Ensure project root is importable.
sys.path.insert(0, str(Path(__file__).parents[1]))

from src.config import settings  # noqa: E402

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def set_webhook(url: str) -> None:
    """Register the webhook URL with Telegram.

    Args:
        url: Public HTTPS base URL of the server (e.g. https://example.com).
    """
    webhook_url = f"{url.rstrip('/')}/webhook/telegram"
    payload = {
        "url": webhook_url,
        "secret_token": settings.telegram_webhook_secret,
        "allowed_updates": ["message", "edited_message"],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{TELEGRAM_API}/setWebhook", json=payload)
        data = resp.json()
        if data.get("ok"):
            print(f"Webhook registered: {webhook_url}")
        else:
            print(f"Error: {data}")
            sys.exit(1)


async def delete_webhook() -> None:
    """Remove the currently registered Telegram webhook."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{TELEGRAM_API}/deleteWebhook")
        data = resp.json()
        if data.get("ok"):
            print("Webhook removed.")
        else:
            print(f"Error: {data}")
            sys.exit(1)


def main() -> None:
    """Parse CLI arguments and run the appropriate async action."""
    parser = argparse.ArgumentParser(description="Manage Telegram webhook registration")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("url", nargs="?", help="Public HTTPS base URL of the server")
    group.add_argument("--remove", action="store_true", help="Remove the current webhook")
    args = parser.parse_args()

    if args.remove:
        asyncio.run(delete_webhook())
    else:
        asyncio.run(set_webhook(args.url))


if __name__ == "__main__":
    main()
