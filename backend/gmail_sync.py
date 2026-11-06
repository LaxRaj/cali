"""Optional, local-only Gmail bridge for outreach.py: drafts, autonomous sending, and reading replies back.

One-time setup (free, your own Google Cloud project, never committed or run in CI):
  1. Google Cloud console -> enable the Gmail API -> OAuth client ID (Desktop app) -> download the JSON.
  2. Save it as ~/.config/cali/gmail_client.json
  3. uv sync --extra gmail && uv run python outreach.py run --dry-run   (first run opens a browser for consent;
     delete ~/.config/cali/gmail_token.json to re-consent after scopes change)
The token lands in ~/.config/cali/gmail_token.json. Scopes: gmail.compose, gmail.send, gmail.readonly.

Autonomous sending is OFF until you set CALI_OUTREACH_SEND=1. Schedule it on your own machine only, e.g. crontab:
  */20 * * * * cd /path/to/cali/backend && CALI_OUTREACH_SEND=1 uv run python outreach.py run >> ~/.config/cali/outreach.log 2>&1
Each tick sends at most one vetted email, inside the send window, with random gaps and a warm-up ramp.
"""

import base64
import re
from email.message import EmailMessage
from pathlib import Path

import outreach

CONFIG_DIR = Path.home() / ".config" / "cali"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]
OPT_OUT_WORDS = re.compile(r"\b(unsubscribe|remove me|stop emailing|do not (contact|email)|don'?t (contact|email)|not interested|take me off)\b", re.I)
# a bare "spam" is not a complaint ("this isn't spam", "it landed in my spam folder"): only an explicit accusation is
COMPLAINT_WORDS = re.compile(
    r"\b(mark(ed|ing)? (it |this |you |as )?(as )?spam|this is spam|(is|was) spam\b|stop spamming|spammer|"
    r"report(ed|ing)? (you|this)|harass\w*|cease and desist|legal action)", re.I)
OOO_WORDS = re.compile(
    r"\b(out of (the )?office|ooo\b|on (annual |parental |)leave|on vacation|on holiday|away until|back on|"
    r"auto(matic|mated)?[- ]?(reply|response)|autoreply|limited access to (my )?email|currently (out|away|traveling))", re.I)
REFERRAL_WORDS = re.compile(
    r"\b(reach out to|contact|talk to|speak (to|with)|loop(ing)? in|cc'?(ing|ed)?|forward(ed|ing)? (this|you)|"
    r"better person|right person|in charge of|handles? (this|that))\b", re.I)
NOT_NOW_WORDS = re.compile(
    r"\b(not (right )?now|not at (this|the moment)|maybe later|next (quarter|year|month)|circle back|revisit|"
    r"not a (priority|fit right now)|no budget|bad timing|too early|in a few months|later this year)\b", re.I)
INTERESTED_WORDS = re.compile(
    r"\b(interested|sounds (good|great|interesting)|let'?s (chat|talk|meet|do it)|happy to (chat|talk|meet)|"
    r"book a|calendly|cal\.com|schedule|set up a (call|time)|free (on|this|next)|would love to|send (me |over )?more)\b", re.I)
BOUNCE_SENDERS = ("mailer-daemon", "postmaster")


def classify_reply(text: str) -> str:
    """How a reply reads, deterministically (no LLM, no cost): ooo / unsubscribe / complaint / referral / not_now /
    interested / question / other. Order matters: an auto-reply or an opt-out outranks friendly words."""
    t = text or ""
    if OOO_WORDS.search(t):
        return "ooo"
    if COMPLAINT_WORDS.search(t):
        return "complaint"
    if OPT_OUT_WORDS.search(t):
        return "unsubscribe"
    if NOT_NOW_WORDS.search(t):
        return "not_now"
    if REFERRAL_WORDS.search(t) and ("@" in t or re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", t)):
        return "referral"
    if INTERESTED_WORDS.search(t):
        return "interested"
    if "?" in t:
        return "question"
    return "other"


def classify(messages: list[dict]) -> tuple[str | None, str]:
    """(status, reply intent) implied by a thread's messages ({"labelIds", "from", "snippet"}).
    Out-of-office auto-replies are not replies: the thread stays 'sent' (the follow-up timer keeps running)."""
    theirs = [m for m in messages if "SENT" not in m.get("labelIds", [])]
    if any(any(b in m.get("from", "").lower() for b in BOUNCE_SENDERS) for m in theirs):
        return "bounced", "bounce"
    intents = [classify_reply(m.get("snippet", "")) for m in theirs]
    if "complaint" in intents:
        return "complaint", "complaint"
    if "unsubscribe" in intents:
        return "opted_out", "unsubscribe"
    real = [i for i in intents if i != "ooo"]
    if real:
        return "replied", real[-1]  # the latest human reply is the one that counts
    return ("sent", "") if messages else (None, "")


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
    """Status implied by a thread's messages: bounced / complaint / opted_out / replied / sent (see `classify`)."""
    return classify(messages)[0]


def _raw(item: dict) -> dict:
    msg = EmailMessage()
    msg["To"], msg["Subject"] = item["to"], item["subject"]
    msg.set_content(item["body"])
    return {"message": {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}}


def _header(svc, message_id: str, name: str) -> str:
    msg = svc.users().messages().get(userId="me", id=message_id, format="metadata", metadataHeaders=[name]).execute()
    return next((h["value"] for h in msg.get("payload", {}).get("headers", []) if h["name"].lower() == name.lower()), "")


def send_item(svc, item: dict) -> dict:
    """Send one plain-text email from the user's own mailbox. Follow-ups join the first email's thread.

    Deliverability: real mailbox (Google signs SPF/DKIM), no HTML/tracking, List-Unsubscribe, proper threading.
    Returns the Gmail API response ({"id", "threadId", ...}).
    """
    me = svc.users().getProfile(userId="me").execute()["emailAddress"]
    msg = EmailMessage()
    msg["To"], msg["From"], msg["Subject"] = item["to"], me, item["subject"]
    msg["List-Unsubscribe"] = f"<mailto:{me}?subject=unsubscribe>"
    body = {}
    if item["kind"] == "follow_up" and item.get("gmail_thread_id"):
        body["threadId"] = item["gmail_thread_id"]
        if item.get("reply_to_message_id") and (rfc_id := _header(svc, item["reply_to_message_id"], "Message-Id")):
            msg["In-Reply-To"] = msg["References"] = rfc_id
    msg.set_content(item["body"])
    body["raw"] = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return svc.users().messages().send(userId="me", body=body).execute()


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
    """Read threads for drafted / sent / replied items and record sent / replied (+ intent) / bounced / opted_out.
    Replied threads are re-read too: a later "please remove me" must still suppress the address."""
    svc = svc or service()
    changed = 0
    for item in list(outreach.load_outbox(data_dir).values()):
        if item["status"] not in ("drafted", "sent", "replied") or not item.get("gmail_thread_id"):
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
        status, intent = classify(messages)
        if item["status"] == "replied" and status not in ("opted_out", "complaint"):
            # a conversation never moves back to 'sent'; only a later opt-out/complaint (or a new intent) changes it
            if status == "replied" and intent and intent != item.get("reply_intent"):
                outreach.set_status(item["company"], item["kind"], "replied", data_dir, reply_intent=intent)
                changed += 1
            continue
        if status and (status != item["status"] or (intent and intent != item.get("reply_intent"))):
            extra = {"reply_intent": intent} if intent else {}
            outreach.set_status(item["company"], item["kind"], status, data_dir, **extra)
            changed += 1
    return f"updated {changed} item(s)"
