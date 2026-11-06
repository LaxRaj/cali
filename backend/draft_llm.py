"""Optional Groq help for outreach drafts: a better first sentence + subject, and rewrites from your feedback.

Free tier only (llm.py); ~300 tokens per call. Every function returns None / raises ValueError instead of
guessing: without a key, over quota, or when the model breaks a rule, the deterministic draft is used as is.
The human still reviews every email, so this only saves typing; it is never trusted to send.
"""

import json
import re

import llm
from draft import OPT_OUT

RULES = (
    "Plain, direct, founder-to-founder: one builder writing to another. No flattery, no hype, no buzzwords, "
    "no exclamation marks, no emoji. Use ONLY facts given to you; never invent products, metrics, customers, "
    "or claim you have used their product."
)


def _ask(system: str, user: dict, client=None, purpose: str = "outreach") -> dict:
    client = client or llm.get_client()
    out = llm.complete(client, [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user)}], purpose=purpose)
    return json.loads(out.choices[0].message.content)


def available() -> bool:
    return bool(llm.api_keys())


def polish(profile: dict, client=None) -> dict | None:
    """{"observation", "subject"} written from the profile's facts, or None to keep the deterministic text."""
    if client is None and not available():
        return None
    facts = {k: profile.get(k) for k in ("company_name", "core_product", "likely_bottleneck", "tech_stack", "funding_stage", "hq")}
    system = (
        f"{RULES} Write (1) `observation`: one or two sentences, at most 35 words in total, saying what the company "
        "builds and the specific hard part of it, in plain words; (2) `subject`: at most 7 words, specific, no clickbait, "
        'not just the company name. Reply as JSON: {"observation": "...", "subject": "..."}.'
    )
    try:
        got = _ask(system, facts, client, "outreach_polish")
    except Exception:  # no network, quota, bad JSON: the deterministic draft is fine
        return None
    obs, subj = str(got.get("observation", "")).strip(), str(got.get("subject", "")).strip()
    if not obs or len(obs.split()) > 40 or re.search(r"[\[\]!<>]|https?://", obs + subj) or len(subj.split()) > 8:
        return None
    return {"observation": obs, "subject": subj}


def revise(item: dict, feedback: str, client=None) -> dict:
    """Rewrite the email per the human's feedback. Returns {"subject", "body"} or raises ValueError(why not)."""
    if client is None and not available():
        raise ValueError("Groq is not configured (set GROQ_API_KEY); edit the text by hand instead")
    import outreach  # late: outreach does not import this module, but keep the dependency one-way at import time

    system = (
        f"{RULES} You revise a cold email. Apply the user's feedback. Keep it plain text, at most 110 words, keep the "
        f'exact line "{OPT_OUT}" and the signature lines, keep the call-to-action a short call, add no links. '
        'Reply as JSON: {"subject": "...", "body": "..."}.'
    )
    try:
        got = _ask(system, {"subject": item["subject"], "body": item["body"], "feedback": feedback}, client, "outreach_revise")
    except Exception as e:
        raise ValueError(f"the rewrite failed ({type(e).__name__}); try again or edit by hand") from e
    new = {"subject": str(got.get("subject", "")).strip(), "body": str(got.get("body", "")).strip()}
    if not new["subject"] or not new["body"]:
        raise ValueError("the model returned an empty draft")
    if item["kind"] == "first" and OPT_OUT not in new["body"]:
        raise ValueError("the rewrite dropped the opt-out line, so it was discarded")
    problems = outreach.lint({**item, **new})
    if problems:
        raise ValueError("the rewrite breaks a rule (" + "; ".join(problems) + "), so it was discarded")
    return new
