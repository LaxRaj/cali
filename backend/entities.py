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
