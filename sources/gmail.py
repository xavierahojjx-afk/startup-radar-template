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
import re
from datetime import datetime
from pathlib import Path

from models import Startup

BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
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


_AMOUNT_RE = re.compile(r"\$\s*[\d,.]+\s*(?:B|M|billion|million)\b", re.IGNORECASE)
_STAGE_RE = re.compile(r"\b(Pre-?Seed|Seed|Series\s+[A-F]\d?\+?)\b", re.IGNORECASE)
_COMPANY_RE = re.compile(
    r"\b([A-Z][\w\-.&']{1,40}?)\s+(?:raises|raised|secures|closes|nabs|announces)\s+",
    re.IGNORECASE,
)


def _parse_body(text: str, subject: str) -> list[Startup]:
    """Generic regex extraction. The /setup skill can replace this with
    per-newsletter parsers tailored to the user's specific subscriptions."""
    found: list[Startup] = []
    for m in _COMPANY_RE.finditer(text):
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 200)
        snippet = text[start:end]

        amount = _AMOUNT_RE.search(snippet)
        stage = _STAGE_RE.search(snippet)

        found.append(Startup(
            company_name=m.group(1).strip(),
            description=snippet.strip()[:300],
            funding_stage=stage.group(0) if stage else "",
            amount_raised=amount.group(0) if amount else "",
            source=f"Gmail: {subject[:40]}",
        ))
    return found


def fetch(gmail_cfg: dict) -> list[Startup]:
    import database

    service = _get_service()
    label_name = gmail_cfg.get("label", "Startup Funding")

    labels_resp = service.users().labels().list(userId="me").execute()
    label_id = None
    for lbl in labels_resp.get("labels", []):
        if lbl["name"] == label_name:
            label_id = lbl["id"]
            break
    if not label_id:
        print(f"  Gmail label '{label_name}' not found")
        return []

    results = service.users().messages().list(
        userId="me", labelIds=[label_id], maxResults=50,
    ).execute()
    messages = results.get("messages", [])

    startups: list[Startup] = []
    new_ids: list[str] = []

    for msg_meta in messages:
        msg_id = msg_meta["id"]
        if database.is_processed("gmail", msg_id):
            continue

        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full",
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "")
        body = _extract_body(msg.get("payload", {}))
        startups.extend(_parse_body(body, subject))
        new_ids.append(msg_id)

    database.mark_processed("gmail", new_ids)
    return startups
