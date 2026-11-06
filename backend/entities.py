"""Entity name normalisation for matching the same company across runs ("Acme", "Acme, Inc.", "ACME Inc")."""

import re

# Legal-form suffixes only. Words like "labs" or "technologies" are part of real names, so they stay.
LEGAL_SUFFIX = re.compile(r"[\s,]+(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|gmbh|co)\.?$", re.I)


def canonical_key(name: str) -> str:
    """Lowercase, collapse whitespace and drop trailing legal suffixes. Never returns a suffix-only name."""
    s = re.sub(r"\s+", " ", (name or "").strip().lower())
    while True:
        t = LEGAL_SUFFIX.sub("", s).strip(" ,")
        if t == s or not t:
            break
        s = t
    return s


# One spelling per funding stage, so the dashboard shows one chip per stage and rating's regexes still match.
STAGES = ("pre-seed", "seed", "Series A", "Series B", "Series C+", "YC", "angel", "bridge")
_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", " ": " "})


def normalize_stage(raw: str) -> str:
    """'pre‑Seed' / 'Pre-seed' / 'preseed' -> 'pre-seed'; 'Series A2' -> 'Series A'; 'seed-plus' -> 'seed'; unknown text is
    kept (trimmed) rather than guessed; '' stays ''."""
    s = re.sub(r"\s+", " ", (raw or "").translate(_DASHES)).strip()
    low = s.lower()
    if not low:
        return ""
    if re.search(r"pre[- ]?seed", low):
        return "pre-seed"
    if re.search(r"\bseries [c-z]\b|\bseries [c-z]\d|growth|late[- ]stage|\bipo\b|public", low):
        return "Series C+"
    if re.search(r"\bseries b", low):
        return "Series B"
    if re.search(r"\bseries a", low):
        return "Series A"
    if "seed" in low:
        return "seed"
    if re.search(r"\byc\b|y ?combinator", low):
        return "YC"
    if "angel" in low:
        return "angel"
    if "bridge" in low:
        return "bridge"
    return s
