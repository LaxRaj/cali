"""Optional TypeSafe Jev provider (hosted, paid, opt-in). Off unless TYPESAFE_API_KEY is set.

Docs: https://docs.typesafe.ai/api/system-one.md  ->  POST {base}/v1/systemone
Request: {"model", "state", "questions": {name: {"type": choice|score|noul, "instructions", "criteria"}}}
Response: {"answers": {name: {"type", "choice"|"score"|"noul", "confidence", "probabilities"}}, "usage": {...}}
Input tokens are billable (~$0.04 / 1M); output is free. See CLAUDE.md: never enabled by default.
"""

import os

import httpx

from decide.protocol import Answer, Question

DEFAULT_BASE = "https://api.typesafe.ai"


class ProviderError(RuntimeError):
    pass


def _plain(text: str) -> str:
    """Our local prototypes may hold several examples separated by ' || '; Jev takes one description."""
    return "; ".join(p.strip() for p in text.split("||") if p.strip())


def build_request(model: str, state: str, questions: list[Question]) -> dict:
    qs = {}
    for q in questions:
        if q.type == "choice":
            criteria = {k: _plain(v) for k, v in (q.criteria or {}).items()}
        elif q.type == "noul":
            criteria = {k: _plain(v) for k, v in (q.criteria or {}).items()}
        else:
            criteria = [_plain(x) for x in (q.criteria or [])]
        qs[q.name] = {"type": q.type, "instructions": q.instructions, "criteria": criteria}
    return {"model": model, "state": state, "questions": qs}


def parse_answers(payload: dict) -> dict[str, Answer]:
    out = {}
    for name, a in (payload.get("answers") or {}).items():
        t = a.get("type")
        if t == "noul":
            p = float(a["noul"])
            out[name] = Answer("noul", noul=p, confidence=abs(p - 0.5) * 2, probabilities={"true": p, "false": 1 - p})
        elif t == "choice":
            out[name] = Answer("choice", choice=a["choice"], confidence=float(a.get("confidence", 0)),
                               probabilities={k: float(v) for k, v in (a.get("probabilities") or {}).items()})
        elif t == "score":
            out[name] = Answer("score", score=float(a["score"]), confidence=float(a.get("confidence", 0)),
                               probabilities={k: float(v) for k, v in (a.get("probabilities") or {}).items()})
    return out


class JevProvider:
    name = "jev"

    def __init__(self, api_key: str | None = None, base: str | None = None, model: str = "jev-latest",
                 timeout: float = 3.0, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.base = (base or os.environ.get("TYPESAFE_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.model, self.timeout = model, timeout
        self._client = client or httpx.Client(timeout=timeout)
        self.input_tokens = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def decide(self, state: str, questions: list[Question]) -> dict[str, Answer]:
        if not self.available:
            raise ProviderError("TYPESAFE_API_KEY not set")
        try:
            r = self._client.post(
                f"{self.base}/v1/systemone",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=build_request(self.model, state, questions),
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ProviderError(f"jev request failed: {e}") from e
        self.input_tokens += int((data.get("usage") or {}).get("input_tokens", 0))
        answers = parse_answers(data)
        missing = {q.name for q in questions} - set(answers)
        if missing:
            raise ProviderError(f"jev response missing answers: {sorted(missing)}")
        return answers
