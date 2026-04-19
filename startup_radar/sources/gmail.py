"""Gmail source (optional) — pulls funding announcements from email newsletters.

Requires Google Cloud OAuth setup. See README "Optional: Gmail source" for
step-by-step instructions.

Setup summary:
  1. Create a Google Cloud project
  2. Enable Gmail API
  3. Create OAuth Desktop app credentials
  4. Download as credentials.json into the project root
  5. First run will prompt for consent and cache token.json

This file is intentionally minimal — the interactive /setup skill will
generate per-newsletter parsers tailored to whatever newsletters you
actually subscribe to.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from startup_radar.models import Startup
from startup_radar.parsing.funding import AMOUNT_RE, COMPANY_INLINE_RE, STAGE_RE
from startup_radar.sources.base import Source

# Repo-root locations preserved (credentials/token still live at the project root,
# not inside the package). Phase 4+ may relocate to ~/.config/startup-radar/.
BASE_DIR = Path(__file__).resolve().parents[2]
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

log = logging.getLogger(__name__)


def _get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "See README section 'Optional: Gmail source'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    if payload.get("body", {}).get("data"):
        return _decode(payload["body"]["data"])
    parts = payload.get("parts", [])
    for p in parts:
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            return _decode(p["body"]["data"])
    for p in parts:
        body = _extract_body(p)
        if body:
            return body
    return ""


def _parse_body(text: str, subject: str) -> list[Startup]:
    """Generic regex extraction. The /setup skill can replace this with
    per-newsletter parsers tailored to the user's specific subscriptions."""
    found: list[Startup] = []
    for m in COMPANY_INLINE_RE.finditer(text):
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 200)
        snippet = text[start:end]

        amount = AMOUNT_RE.search(snippet)
        stage = STAGE_RE.search(snippet)

        found.append(
            Startup(
                company_name=m.group(1).strip(),
                description=snippet.strip()[:300],
                funding_stage=stage.group(0) if stage else "",
                amount_raised=amount.group(0) if amount else "",
                source=f"Gmail: {subject[:40]}",
            )
        )
    return found


class GmailSource(Source):
    name = "Gmail"
    enabled_key = "gmail"

    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
        gmail_cfg = cfg.get("sources", {}).get(self.enabled_key, {})
        if not gmail_cfg.get("enabled"):
            return []

        # Function-scope import: database stays at repo root until Phase 12.
        import database

        try:
            service = _get_service()
        except Exception as e:
            log.warning("source.fetch_failed", extra={"source": self.name, "err": str(e)})
            return []

        label_name = gmail_cfg.get("label", "Startup Funding")

        try:
            labels_resp = service.users().labels().list(userId="me").execute()
        except Exception as e:
            log.warning("source.fetch_failed", extra={"source": self.name, "err": str(e)})
            return []

        label_id = None
        for lbl in labels_resp.get("labels", []):
            if lbl["name"] == label_name:
                label_id = lbl["id"]
                break
        if not label_id:
            log.warning(
                "source.label_missing",
                extra={"source": self.name, "label": label_name},
            )
            return []

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", labelIds=[label_id], maxResults=50)
                .execute()
            )
        except Exception as e:
            log.warning("source.fetch_failed", extra={"source": self.name, "err": str(e)})
            return []

        messages = results.get("messages", [])
        startups: list[Startup] = []
        new_ids: list[str] = []

        for msg_meta in messages:
            msg_id = msg_meta["id"]
            if database.is_processed("gmail", msg_id):
                continue

            try:
                msg = (
                    service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                )
            except Exception as e:
                log.warning(
                    "source.message_fetch_failed",
                    extra={"source": self.name, "msg_id": msg_id, "err": str(e)},
                )
                continue
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "")
            body = _extract_body(msg.get("payload", {}))
            startups.extend(_parse_body(body, subject))
            new_ids.append(msg_id)

        database.mark_processed("gmail", new_ids)
        return startups
