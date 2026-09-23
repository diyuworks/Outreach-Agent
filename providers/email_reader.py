"""
Gmail inbox reader — fetches recent unread replies using the Gmail API (read-only).

Requires a one-time OAuth setup:
  1. Google Cloud Console project with Gmail API enabled
  2. OAuth 2.0 consent screen configured
  3. credentials.json downloaded to the project root

On first run the user is prompted in the browser to authorise the app;
a token.json file is saved locally so subsequent runs are non-interactive.

This module does NOT send mail — sending uses SMTP via email_provider.py.
"""
import os
import base64
import re
from datetime import datetime
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only scope — we only read the inbox, never modify or send
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Paths for OAuth artefacts (relative to project root)
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials. "
                    "See README.md for full setup steps."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _extract_plain_text(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Multipart — recurse into parts
    for part in payload.get("parts", []):
        text = _extract_plain_text(part)
        if text:
            return text
    return ""


def _header_value(headers: list, name: str) -> str:
    """Get a header value by name (case-insensitive)."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch_replies(known_lead_emails: set[str],
                  after_timestamp: Optional[str] = None) -> list[dict]:
    """
    Fetch unread inbox messages that are replies from known lead email addresses.

    Args:
        known_lead_emails: Set of lowercase email addresses for leads we've contacted.
        after_timestamp: ISO timestamp string — only fetch messages newer than this.
                         If None, fetches recent unread messages (last 50).

    Returns:
        List of dicts with keys: sender, subject, body, received_at, message_id
    """
    service = _get_gmail_service()

    # Build Gmail search query
    query_parts = ["is:unread", "in:inbox"]
    if after_timestamp:
        # Gmail accepts after: as epoch seconds
        try:
            dt = datetime.fromisoformat(after_timestamp)
            epoch = int(dt.timestamp())
            query_parts.append(f"after:{epoch}")
        except (ValueError, OSError):
            pass  # skip date filter if timestamp is invalid

    query = " ".join(query_parts)

    results = service.users().messages().list(
        userId="me", q=query, maxResults=50
    ).execute()

    messages = results.get("messages", [])
    replies = []

    for msg_stub in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_stub["id"], format="full"
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        from_header = _header_value(headers, "From")
        subject = _header_value(headers, "Subject")

        # Extract email address from "Name <email>" format
        match = re.search(r"<([^>]+)>", from_header)
        sender_email = (match.group(1) if match else from_header).strip().lower()

        # Only process replies from known lead emails
        if sender_email not in known_lead_emails:
            continue

        body = _extract_plain_text(msg.get("payload", {}))
        internal_date = msg.get("internalDate", "0")
        received_at = datetime.fromtimestamp(
            int(internal_date) / 1000
        ).isoformat()

        replies.append({
            "sender": sender_email,
            "subject": subject,
            "body": body.strip(),
            "received_at": received_at,
            "message_id": msg_stub["id"],
        })

    return replies
