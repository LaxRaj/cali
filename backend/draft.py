"""Deterministic first-email drafts from a profile. Never sends; never guesses an address.

The recipient is only ever an address the company published itself (profile["contact"]["emails"]), with its
source URL kept alongside. If there is none, `to` is empty and the human decides where to send it.
"""

import re
from urllib.parse import quote

# Published address kinds in order of preference; support/press inboxes are the wrong door for a pitch.
KIND_RANK = {"person": 0, "sales": 1, "general": 2, "other": 3}
LEADER = re.compile(r"founder|ceo|cto|chief|president", re.I)


def pick_email(emails: list[dict]) -> dict | None:
    usable = [e for e in emails if e.get("kind", "other") in KIND_RANK]
    return min(usable, key=lambda e: KIND_RANK[e.get("kind", "other")], default=None)


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0] if text.strip() else ""


def build_draft(profile: dict, warm_path: dict | None = None) -> dict:
    company = profile["company_name"]
    leader = next((p for p in profile.get("people", []) if LEADER.search(p.get("role") or "")), None)
    greeting = f"Hi {leader['name'].split()[0]}," if leader else f"Hi {company} team,"

    lines = [greeting, ""]
    if warm_path:
        lines += [f"{warm_path['summary']}.", ""]
    lines.append(f"I came across {company}: {_first_sentence(profile.get('core_product', ''))}".rstrip(".") + ".")
    if profile.get("likely_bottleneck", "").strip():
        lines.append(f"One thing I noticed: {profile['likely_bottleneck'].strip().rstrip('.')}.")
    pitch = profile.get("value_prop_pitch", "").strip()
    if pitch:
        lines += ["", pitch]
    lines += ["", "Open to a quick chat?"]
    body = "\n".join(lines)

    chosen = pick_email(profile.get("contact", {}).get("emails", []))
    to = chosen["value"] if chosen else ""
    subject = f"{company}: a thought on {_first_sentence(profile.get('likely_bottleneck', '')).rstrip('.')[:60] or 'your stack'}"
    return {
        "to": to,
        "to_source_url": chosen.get("source_url", "") if chosen else "",
        "subject": subject,
        "body": body,
        "mailto": f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}" if to else "",
    }
