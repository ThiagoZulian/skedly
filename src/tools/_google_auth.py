"""Google OAuth helper — manages credentials and creates the Calendar API service.

On first run the user must authorise the app via browser (OAuth flow).
The resulting token is cached in credentials/token.json and refreshed automatically
on subsequent runs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Resolved relative to the project root (two levels above this file: src/tools → src → root)
_PROJECT_ROOT = Path(__file__).parents[2]
_CREDENTIALS_PATH = _PROJECT_ROOT / "credentials" / "google_oauth.json"
_TOKEN_PATH = _PROJECT_ROOT / "credentials" / "token.json"


def get_calendar_service():
    """Return an authenticated Google Calendar API resource.

    Handles the full OAuth lifecycle:
    - If ``credentials/token.json`` exists and is valid, uses it directly.
    - If the token is expired but has a refresh token, refreshes it silently.
    - If no token exists, launches the browser-based OAuth flow (first run only).

    Returns:
        A ``googleapiclient.discovery.Resource`` for the Calendar v3 API.

    Raises:
        FileNotFoundError: If ``credentials/google_oauth.json`` is missing.
        google.auth.exceptions.GoogleAuthError: On authentication failure.
    """
    if not _CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials not found at {_CREDENTIALS_PATH}. "
            "Download them from https://console.cloud.google.com/ and place the file there."
        )

    creds: Credentials | None = None

    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)
        logger.debug("Loaded cached Google credentials from %s", _TOKEN_PATH)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Google credentials…")
            creds.refresh(Request())
        else:
            logger.info("Starting Google OAuth flow — browser will open…")
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_PATH), _SCOPES)
            creds = flow.run_local_server(port=0)

        _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Google credentials saved to %s", _TOKEN_PATH)

    return build("calendar", "v3", credentials=creds)
