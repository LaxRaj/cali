"""Deterministic first-email drafts from a profile. Never sends; never guesses an address.

The recipient is only ever an address the company published itself (profile["contact"]["emails"]), with its
source URL kept alongside. If there is none, `to` is empty and the human decides where to send it.

Each draft has a collaboration intent chosen from scout signals (override with CALI_OUTREACH_INTENT):
work_for (join them), build_for (ship something that fixes their bottleneck), build_with (partner/co-build).
"""

import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse

DB_DIR = Path(__file__).parent / "data"  # same location as memory.DB_DIR, without importing the embedder

# Published address kinds in order of preference; support/press inboxes are the wrong door for a pitch.
KIND_RANK = {"person": 0, "sales": 1, "general": 2, "other": 3}
LEADER = re.compile(r"founder|ceo|cto|chief|president", re.I)
INTENTS = ("work_for", "build_for", "build_with")
OPT_OUT = 'If this isn\'t relevant, just reply "no" and I won\'t follow up.'


def pick_email(emails: list[dict]) -> dict | None:
    usable = [e for e in emails if e.get("kind", "other") in KIND_RANK]
    return min(usable, key=lambda e: KIND_RANK[e.get("kind", "other")], default=None)


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0] if text.strip() else ""


def load_sender(data_dir: Path = DB_DIR) -> dict:
    """Who is writing: CALI_SENDER_NAME / CALI_SENDER_BIO / CALI_SENDER_LINKS, else data/me.json (name, bio, links)."""
    try:
        me = json.loads((Path(data_dir) / "me.json").read_text())
    except (OSError, ValueError):
        me = {}
    return {
        "name": os.environ.get("CALI_SENDER_NAME") or me.get("name", ""),
        "bio": os.environ.get("CALI_SENDER_BIO") or me.get("bio", ""),
        "links": os.environ.get("CALI_SENDER_LINKS") or me.get("links", ""),
    }


def pick_intent(profile: dict, override: str | None = None) -> tuple[str, str]:
    """(intent, reason). Order: explicit override, hiring/launch signal, concrete bottleneck + stack, else partner."""
    forced = override or os.environ.get("CALI_OUTREACH_INTENT", "")
    if forced in INTENTS:
        return forced, "set by you"
    hn = next((s for s in profile.get("why_now") or [] if s.get("signal") == "hn"), None)
    if hn or urlparse(profile.get("source_url", "")).netloc.endswith("news.ycombinator.com"):
        return "work_for", "found on a Hacker News hiring/launch post"
    if profile.get("likely_bottleneck", "").strip() and profile.get("tech_stack"):
        return "build_for", "a concrete bottleneck on a stack you can work with"
    return "build_with", "no hiring signal or clear bottleneck, so propose a partnership"


def _clean(text: str) -> str:
    return text.strip().rstrip(".")


def _signal(profile: dict) -> str:
    text = (profile.get("why_now") or [{}])[0].get("text", "")
    return f"Saw the recent news ({text[0].lower() + text[1:]})." if text else ""


def _intent_lines(intent: str, profile: dict) -> list[str]:
    bottleneck = _clean(_short(profile.get("likely_bottleneck", ""), 120)).rstrip(".")
    if bottleneck[:2].istitle():  # "Scaling X" reads mid-sentence as "scaling X"; leave acronyms ("GPU ...") alone
        bottleneck = bottleneck[0].lower() + bottleneck[1:]
    stack = ", ".join((profile.get("tech_stack") or [])[:3])
    pitch = _first_sentence(profile.get("value_prop_pitch", ""))  # one sentence: short cold emails read as human
    if intent == "work_for":
        lines = [f"I'm looking to join a team like yours{f' and work with {stack}' if stack else ''}."]
        if bottleneck:
            lines.append(f"One thing I'd want to help with: {bottleneck}.")
        return lines + ["", "Is there a role, or a small project, where I could contribute?"]
    if intent == "build_for":
        lines = [f"One thing I noticed: {bottleneck}." if bottleneck else "I think I can help with a piece of your stack."]
        if pitch:
            lines += ["", pitch]
        return lines + ["", "Would a short trial project to tackle this be useful?"]
    lines = [f"I'd like to build something with you{f' around {stack}' if stack else ''}."]
    if bottleneck:
        lines.append(f"One place we could start: {bottleneck}.")
    return lines + ["", "Open to a quick call to see if there is a fit?"]


# Every angle is built only from facts the scout found (role, bottleneck, stack): no "[fill this in]" placeholders, so a
# draft can pass outreach.lint unattended. Nothing here claims experience the sender did not state in me.json.
ANGLES = {
    "eng": "I'd like to help on the engineering side{focus}.",
    "founding": "I'd like to be one of the first engineers helping {product} ship{focus}.",
    "product": "I'd like to help {product} turn what users say into what ships next{focus}.",
    "customer": "I'd like to help {product} reach more of the teams it is built for.",
    "sales": "I'd like to help {product} reach more of the teams it is built for.",
    "design": "I'd like to help with design and UX on {product}{focus}.",
}


def _focus(profile: dict) -> str:
    bottleneck = _clean(profile.get("likely_bottleneck", ""))
    if bottleneck:
        return f", starting with {bottleneck[0].lower() + bottleneck[1:]}" if len(bottleneck) <= 90 else ""
    stack = ", ".join((profile.get("tech_stack") or [])[:2])
    return f" on {stack}" if stack else ""


def signal_hook(profile: dict) -> tuple[str, str]:
    """(hook sentence, angle sentence) from the strongest published signal; ('', '') when there is none."""
    sigs = sorted(profile.get("signals") or [], key=lambda s: -{"seeking_freelancer": 3, "hiring": 2, "funding": 1}.get(s["type"], 0))
    if not sigs:
        return "", ""
    s = sigs[0]
    product = profile.get("company_name", "your product")
    from signals import clean_roles

    roles = ", ".join(clean_roles(s.get("roles", []))[:2])
    hook = {
        "hiring": f"I saw you're hiring ({roles})" if roles else "I saw you're hiring",
        "seeking_freelancer": "I saw you're looking for outside help",
        "funding": "Congrats on the new funding", "launch": "Congrats on the launch",
    }.get(s["type"], "")
    kinds = s.get("role_kinds") or ["eng"]
    # a role-based angle only makes sense for a hiring / outside-help signal; for funding or a launch the intent lines
    # below already make the ask (two "I'd like to..." lines read as a template)
    angle = ANGLES.get(kinds[0], ANGLES["eng"]).format(product=product, focus=_focus(profile)) if s["type"] in ("hiring", "seeking_freelancer") else ""
    return (hook + (f" ({s['url']})" if s.get("url") else "") + "." if hook else ""), angle


def _short(text: str, limit: int = 140) -> str:
    """Keep cold emails short: cut at a word boundary."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind(", "), head.rfind("; "), head.rfind(" - "), head.rfind(" — "))
    return (head[:cut] if cut >= limit // 2 else head.rsplit(" ", 1)[0]).rstrip(",;:- ")  # end on a clause, not mid-phrase


def build_draft(profile: dict, warm_path: dict | None = None, sender: dict | None = None, data_dir: Path | None = None) -> dict:
    company = profile["company_name"]
    sender = sender if sender is not None else load_sender(data_dir or DB_DIR)
    intent, reason = pick_intent(profile)
    leader = next((p for p in profile.get("people", []) if LEADER.search(p.get("role") or "")), None)
    greeting = f"Hi {leader['name'].split()[0]}," if leader else f"Hi {company} team,"

    lines = [greeting, ""]
    if warm_path:
        lines += [f"{warm_path['summary']}.", ""]
    hook, angle = signal_hook(profile)
    if hook:
        lines += [hook, *([angle] if angle else []), ""]
    product = _short(_first_sentence(re.sub(r"\[([^\]]*)\]\([^)]*\)|https?://\S+", r"\1", profile.get("core_product", ""))).strip())
    lines.append(f"I came across {company}: {product}".rstrip(".") + "." if len(product) > 15 else f"I came across {company}.")
    if not hook and (signal := _signal(profile)):  # the hook already cites the news
        lines.append(signal)
    lines += _intent_lines(intent, profile)
    lines += ["", OPT_OUT]
    if sender["name"]:
        lines += ["", sender["name"], *[x for x in (sender["bio"], sender["links"]) if x]]
    body = "\n".join(lines)

    from decide.policy import sendable_emails

    emails = sendable_emails(profile)  # company-domain, sourced, never a publisher's page
    sig_urls = {sg.get("url") for sg in profile.get("signals") or []}
    # an address published in the very post we are replying to beats a generic or unrelated inbox
    chosen = next((e for e in emails if e.get("source_url") in sig_urls), None) or pick_email(emails)
    to = chosen["value"] if chosen else ""
    subject = f"{company}: a thought on {_first_sentence(profile.get('likely_bottleneck', '')).rstrip('.')[:60] or 'your stack'}"
    specific = bool(profile.get("likely_bottleneck", "").strip() or profile.get("tech_stack") or hook)
    return {
        "intent": intent,
        "intent_reason": reason,
        "to": to,
        "to_source_url": chosen.get("source_url", "") if chosen else "",
        "subject": subject,
        "body": body,
        "mailto": f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}" if to else "",
        # nothing concrete to say: the queue shows it, but it is never sent without a human rewriting it
        "needs_human": not specific,
        "needs_human_reason": "" if specific else "no bottleneck, stack or signal to mention",
    }
