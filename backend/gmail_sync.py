"""Optional, local-only Gmail bridge for outreach.py. Creates DRAFTS (never sends) and reads replies back.

One-time setup (free, your own Google Cloud project, never committed or run in CI):
  1. Google Cloud console -> enable the Gmail API -> OAuth client ID (Desktop app) -> download the JSON.
  2. Save it as ~/.config/cali/gmail_client.json
  3. uv sync --extra gmail && uv run python outreach.py push   (first run opens a browser for consent)
The token lands in ~/.config/cali/gmail_token.json. Scopes: gmail.compose (drafts) and gmail.readonly (replies).
"""

import base64
import re
from email.message import EmailMessage
from pathlib import Path

import outreach

CONFIG_DIR = Path.home() / ".config" / "cali"
SCOPES = ["https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.readonly"]
OPT_OUT_WORDS = re.compile(r"\b(unsubscribe|remove me|stop emailing|do not contact|not interested)\b", re.I)
BOUNCE_SENDERS = ("mailer-daemon", "postmaster")


def service():
    """Authorised Gmail API client. Imports Google libraries lazily so the rest of the backend never needs them."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = CONFIG_DIR / "gmail_token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(CONFIG_DIR / "gmail_client.json"), SCOPES).run_local_server(port=0)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json())
        token.chmod(0o600)
    return build("gmail", "v1", credentials=creds)


def classify_thread(messages: list[dict]) -> str | None:
    """Status implied by a thread's messages ({"labelIds", "from", "snippet"}): bounced / opted_out / replied / sent."""
    theirs = [m for m in messages if "SENT" not in m.get("labelIds", [])]
    if any(any(b in m.get("from", "").lower() for b in BOUNCE_SENDERS) for m in theirs):
        return "bounced"
    if any(OPT_OUT_WORDS.search(m.get("snippet", "")) for m in theirs):
        return "opted_out"
    if theirs:
        return "replied"
    return "sent" if messages else None


def _raw(item: dict) -> dict:
    msg = EmailMessage()
    msg["To"], msg["Subject"] = item["to"], item["subject"]
    msg.set_content(item["body"])
    return {"message": {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}}


def push(data_dir: Path = outreach.DB_DIR, svc=None) -> str:
    """Create a Gmail draft for every queued item. You review and send them yourself."""
    if not outreach.enabled():
        return "CALI_OUTREACH=0: disabled"
    svc = svc or service()
    outbox = outreach.load_outbox(data_dir)
    pushed = 0
    for item in outbox.values():
        if item["status"] != "queued" or outreach.is_suppressed(item["to"], outreach.load_suppressed(data_dir)):
            continue
        draft = svc.users().drafts().create(userId="me", body=_raw(item)).execute()
        item.update(status="drafted", gmail_draft_id=draft["id"], gmail_thread_id=draft["message"].get("threadId", ""))
        pushed += 1
    outreach.save_outbox(outbox, data_dir)
    return f"created {pushed} Gmail draft(s); review and send them from Gmail"


def sync(data_dir: Path = outreach.DB_DIR, svc=None) -> str:
    """Read threads for drafted/sent items and record sent / replied / bounced / opted_out."""
    svc = svc or service()
    changed = 0
    for item in list(outreach.load_outbox(data_dir).values()):
        if item["status"] not in ("drafted", "sent") or not item["gmail_thread_id"]:
            continue
        thread = svc.users().threads().get(userId="me", id=item["gmail_thread_id"], format="metadata", metadataHeaders=["From"]).execute()
        messages = [
            {
                "labelIds": m.get("labelIds", []),
                "snippet": m.get("snippet", ""),
                "from": next((h["value"] for h in m.get("payload", {}).get("headers", []) if h["name"] == "From"), ""),
            }
            for m in thread.get("messages", [])
            # a still-unsent draft shows up as a DRAFT-labelled message: not sent yet
            if "DRAFT" not in m.get("labelIds", [])
        ]
        status = classify_thread(messages)
        if status and status != item["status"]:
            outreach.set_status(item["company"], item["kind"], status, data_dir)
            changed += 1
    return f"updated {changed} item(s)"
