"""Google Sheets sink (optional) — mirrors SQLite data to a sheet.

Requires Google Cloud OAuth setup (same credentials.json as the Gmail source).
"""

from pathlib import Path

from startup_radar.models import Startup

BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


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
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("sheets", "v4", credentials=creds)


def append_startups(sheet_id: str, startups: list[Startup]) -> int:
    service = _get_service()
    values = [
        [
            s.company_name,
            s.description,
            s.funding_stage,
            s.amount_raised,
            s.location,
            s.source,
            s.source_url,
            s.date_found.strftime("%Y-%m-%d") if s.date_found else "",
        ]
        for s in startups
    ]
    body = {"values": values}
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Startups!A:H",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()
    return len(values)
