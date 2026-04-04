"""Register ClickUp webhooks for the workspace.

Usage:
    python scripts/setup_clickup_webhooks.py https://your-public-domain.com

DO NOT run locally unless your server is publicly reachable.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.config import settings  # noqa: E402

_BASE = "https://api.clickup.com/api/v2"
_EVENTS = [
    "taskCreated", "taskUpdated", "taskDeleted",
    "taskStatusUpdated", "taskDueDateUpdated",
]


async def register(base_url: str) -> None:
    """Register all event webhooks with ClickUp."""
    endpoint = f"{base_url.rstrip('/')}/webhook/clickup"
    headers = {"Authorization": settings.clickup_api_token, "Content-Type": "application/json"}
    body = {"endpoint": endpoint, "events": _EVENTS}
    if settings.clickup_webhook_secret:
        body["secret"] = settings.clickup_webhook_secret

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_BASE}/team/{settings.clickup_team_id}/webhook", headers=headers, json=body
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            print(f"Webhook registered: {data.get('id')} → {endpoint}")
        else:
            print(f"Error {resp.status_code}: {data}")
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Public HTTPS base URL")
    args = parser.parse_args()
    asyncio.run(register(args.url))
