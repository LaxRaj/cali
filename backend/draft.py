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


ANGLES = {
    "eng": "I'd like to use {product} and send you one concrete thing I'd build or fix: [after trying it: one specific observation].",
    "founding": "I'd like to use {product} and send you one concrete thing I'd build or fix: [after trying it: one specific observation].",
    "product": "I talk to users for a living: [after trying it: what customers seem to need that {product} could say or do better].",
    "customer": "I can bring you customer conversations: [one insight about who is struggling with the problem {product} solves].",
    "sales": "I can bring you customer conversations: [one insight about who is struggling with the problem {product} solves].",
    "design": "I'd like to use {product} and share one specific UX improvement: [after trying it: what stood out].",
}


def signal_hook(profile: dict) -> tuple[str, str]:
    """(hook sentence, angle sentence) from the strongest published signal; ('', '') when there is none."""
    sigs = sorted(profile.get("signals") or [], key=lambda s: -{"seeking_freelancer": 3, "hiring": 2, "funding": 1}.get(s["type"], 0))
    if not sigs:
        return "", ""
    s = sigs[0]
    product = profile.get("company_name", "your product")
    roles = ", ".join(s.get("roles", [])[:2])
    hook = {
        "hiring": f"I saw you're hiring ({roles})" if roles else "I saw you're hiring",
        "seeking_freelancer": "I saw you're looking for outside help",
        "funding": "Congrats on the new funding", "launch": "Congrats on the launch",
    }.get(s["type"], "")
    kinds = s.get("role_kinds") or ["eng"]
    angle = ANGLES.get(kinds[0], ANGLES["eng"]).format(product=product)
    return (hook + (f" ({s['url']})" if s.get("url") else "") + "." if hook else ""), angle


def build_draft(profile: dict, warm_path: dict | None = None) -> dict:
    company = profile["company_name"]
    leader = next((p for p in profile.get("people", []) if LEADER.search(p.get("role") or "")), None)
    greeting = f"Hi {leader['name'].split()[0]}," if leader else f"Hi {company} team,"

    lines = [greeting, ""]
    if warm_path:
        lines += [f"{warm_path['summary']}.", ""]
    hook, angle = signal_hook(profile)
    if hook:
        lines += [hook, angle, ""]
    lines.append(f"I came across {company}: {_first_sentence(profile.get('core_product', ''))}".rstrip(".") + ".")
    if profile.get("likely_bottleneck", "").strip():
        lines.append(f"One thing I noticed: {profile['likely_bottleneck'].strip().rstrip('.')}.")
    pitch = profile.get("value_prop_pitch", "").strip()
    if pitch:
        lines += ["", pitch]
    lines += ["", "Open to a quick chat?"]
    body = "\n".join(lines)

    emails = profile.get("contact", {}).get("emails", [])
    sig_urls = {sg.get("url") for sg in profile.get("signals") or []}
    # an address published in the very post we are replying to beats a generic or unrelated inbox
    chosen = next((e for e in emails if e.get("source_url") in sig_urls), None) or pick_email(emails)
    to = chosen["value"] if chosen else ""
    subject = f"{company}: a thought on {_first_sentence(profile.get('likely_bottleneck', '')).rstrip('.')[:60] or 'your stack'}"
    return {
        "to": to,
        "to_source_url": chosen.get("source_url", "") if chosen else "",
        "subject": subject,
        "body": body,
        "mailto": f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}" if to else "",
    }
