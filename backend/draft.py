"""First-email drafts from a profile: founder to founder, short, one ask (a 15-minute call). Never sends and
never guesses an address.

The recipient is only ever an address the company published itself (profile["contact"]["emails"]), with its
source URL kept alongside. If there is none, `to` is empty and the human decides where to send it.

Drafts are deterministic. `polish` ({"observation", "subject"} from draft_llm) may replace the observation and
subject; the review screen lets the human edit anything before it goes out. Anything only a human can truthfully
say (your proof, what you noticed after trying the product) is left as a [bracketed placeholder]: outreach.lint
refuses to send a draft that still has one.

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
ASK = "Worth a 15-minute call this week?"
INTENT_CLAUSE = {
    "work_for": "I'd love to help build it, as a hire or a project.",
    "build_for": "I think I could help on that side.",
    "build_with": "I think there is something we could build on that together.",
}
DANGLING = {"of", "and", "to", "the", "a", "an", "in", "for", "with", "on", "at", "by", "or", "that", "from"}


def pick_email(emails: list[dict]) -> dict | None:
    usable = [e for e in emails if e.get("kind", "other") in KIND_RANK]
    return min(usable, key=lambda e: KIND_RANK[e.get("kind", "other")], default=None)


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0] if text.strip() else ""


def _plain(text: str) -> str:
    """Typographic characters the scout's LLM likes (non-breaking hyphens, curly quotes) read as machine text."""
    table = {"‑": "-", "‐": "-", "–": "-", "—": " - ", "‘": "'", "’": "'", "“": '"', "”": '"'}
    return re.sub(r"\s+", " ", text.translate(str.maketrans(table))).strip()


def _cap_words(text: str, n: int) -> str:
    """At most n words, cut at a word boundary, never ending on a dangling word, no trailing punctuation."""
    words = _plain(text).split()
    cut = len(words) > n
    words = words[:n]
    while cut and words and words[-1].lower().strip(",.;:") in DANGLING:
        words.pop()
    return " ".join(words).rstrip(" ,.;:")


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text[1:2].islower() or len(text) == 1 else text  # keep "AI", "SQL"


def load_sender(data_dir: Path | None = None) -> dict:
    """Who is writing, from CALI_SENDER_* env vars or data/me.json: name, bio, links, and the two things only you
    can say truthfully: offer (what you do for startups, one or two sentences) and proof (one thing you built) with
    proof_url."""
    try:
        me = json.loads((Path(data_dir or DB_DIR) / "me.json").read_text())
    except (OSError, ValueError):
        me = {}
    return {k: os.environ.get(f"CALI_SENDER_{k.upper()}") or me.get(k, "") for k in ("name", "bio", "links", "offer", "proof", "proof_url")}


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


def _observation(profile: dict) -> str:
    """What they build and the hard part, in plain words, from the scout's facts (no flattery, nothing invented)."""
    company = profile["company_name"]
    product = _cap_words(_first_sentence(profile.get("core_product", "")), 24)
    bottleneck = _cap_words(_first_sentence(profile.get("likely_bottleneck", "")), 22)
    if product.lower().startswith(company.lower() + " "):
        out = f"I've been reading about {company}, which {_lower_first(product[len(company):].strip())}."
    elif product:
        out = f"I've been looking at what {company} is building: {_lower_first(product)}."
    else:
        out = f"I've been reading about {company}."
    return out + (f" The hard part looks like {_lower_first(bottleneck)}." if bottleneck else "")


def _subject(company: str, polish: dict | None) -> str:
    subject = _plain((polish or {}).get("subject", ""))
    if subject and len(subject.split()) <= 8 and "!" not in subject and not subject.isupper():
        return subject
    return f"Quick call about {company}?"


def build_draft(profile: dict, warm_path: dict | None = None, sender: dict | None = None, polish: dict | None = None) -> dict:
    company = profile["company_name"]
    sender = sender if sender is not None else load_sender()
    intent, reason = pick_intent(profile)
    leader = next((p for p in profile.get("people", []) if LEADER.search(p.get("role") or "")), None)
    greeting = f"Hi {leader['name'].split()[0]}," if leader else f"Hi {company} team,"
    name = sender.get("name", "")
    who = f"I'm {name}. " if name else ""
    intro = who + (sender.get("offer") or sender.get("bio") or "[offer: one line on what you build for startups]").strip()
    proof_url = f" ({sender['proof_url']})" if sender.get("proof_url") else ""
    proof = f"I built {sender['proof'].strip().rstrip('.')}{proof_url}." if sender.get("proof") else f"I built [proof: one thing you built that fits {company}]."
    observation = ((polish or {}).get("observation") or "").strip() or _observation(profile)

    lines = [greeting, ""]
    if warm_path:
        lines += [f"{warm_path['summary']}.", ""]
    lines += [intro, ""]
    hook, angle = signal_hook(profile)
    if hook:  # a real published signal; the link is kept in `signals`, not in the email (one link per email)
        lines += [re.sub(r" \(https?://[^)]*\)", "", hook), angle, ""]
    lines += [observation, "", f"{proof} {INTENT_CLAUSE[intent]}", "", ASK, "", OPT_OUT]
    if name:
        lines += ["", name, *[x for x in (sender.get("links"),) if x]]
    body = "\n".join(lines)

    emails = profile.get("contact", {}).get("emails", [])
    sig_urls = {sg.get("url") for sg in profile.get("signals") or []}
    # an address published in the very post we are replying to beats a generic or unrelated inbox
    chosen = next((e for e in emails if e.get("source_url") in sig_urls), None) or pick_email(emails)
    to = chosen["value"] if chosen else ""
    subject = _subject(company, polish)
    return {
        "intent": intent,
        "intent_reason": reason,
        "to": to,
        "to_source_url": chosen.get("source_url", "") if chosen else "",
        "subject": subject,
        "body": body,
        "mailto": f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}" if to else "",
    }
