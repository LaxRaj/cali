"""Free, local decision provider: sentence embeddings + (optional) a classifier learned from our own outcomes.

Cold start is zero-shot: each option is described by one or more prototype sentences (separate several with
" || "); the state is compared to them by cosine similarity and softmaxed. When `data/decider_model.json`
exists (see train_decider.py) a logistic head per yes/no question is blended in, weighted by how many labelled
examples it has seen. Everything runs in milliseconds, offline, at zero cost.
"""

import json
import math
from pathlib import Path

import numpy as np

from decide.protocol import Answer, Question
from memory import DB_DIR, _encoder

SCALE = 22.0  # similarity -> logit; MiniLM cosine gaps between classes are small (~0.05-0.3)
MODEL_FILE = "decider_model.json"
MAX_HEAD_WEIGHT = 0.85
HEAD_HALF_LIFE = 40  # labelled examples at which the learned head gets half of its max weight


def _softmax(xs: list[float]) -> list[float]:
    m = max(xs)
    es = [math.exp(x - m) for x in xs]
    s = sum(es)
    return [e / s for e in es]


class LocalProvider:
    name = "local"

    def __init__(self, model_path: Path | None = None):
        self._proto: dict[str, np.ndarray] = {}
        self._heads: dict[str, dict] = {}
        path = model_path or (DB_DIR / MODEL_FILE)
        try:
            self._heads = json.loads(Path(path).read_text()).get("heads", {})
        except (OSError, ValueError):
            pass

    # --- embeddings ------------------------------------------------------------------------------
    def _embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(_encoder().encode(texts, normalize_embeddings=True))

    def _proto_embeddings(self, text: str) -> np.ndarray:
        if text not in self._proto:
            self._proto[text] = self._embed([p.strip() for p in text.split("||") if p.strip()])
        return self._proto[text]

    def embedding(self, state: str) -> np.ndarray:
        return self._embed([state])[0]

    def _class_sims(self, e: np.ndarray, descriptions: list[str]) -> list[float]:
        return [float(np.max(self._proto_embeddings(d) @ e)) for d in descriptions]

    # --- learned head ------------------------------------------------------------------------------
    def _head_p_yes(self, qname: str, e: np.ndarray) -> tuple[float, float] | None:
        h = self._heads.get(qname)
        if not h or h.get("n", 0) < 10:
            return None
        z = float(np.dot(h["w"], e) + h["b"])
        weight = MAX_HEAD_WEIGHT * h["n"] / (h["n"] + HEAD_HALF_LIFE)
        return 1 / (1 + math.exp(-z)), weight

    # --- decisions ----------------------------------------------------------------------------------
    def decide(self, state: str, questions: list[Question]) -> dict[str, Answer]:
        e = self.embedding(state)
        return {q.name: self._answer(q, e) for q in questions}

    def _answer(self, q: Question, e: np.ndarray) -> Answer:
        if q.type == "choice":
            assert isinstance(q.criteria, dict)
            names = list(q.criteria)
            probs = _softmax([SCALE * s for s in self._class_sims(e, [q.criteria[n] or n for n in names])])
            top = int(np.argmax(probs))
            return Answer("choice", choice=names[top], confidence=float(probs[top]), probabilities=dict(zip(names, map(float, probs))))
        if q.type == "noul":
            assert isinstance(q.criteria, dict)
            sims = self._class_sims(e, [q.criteria["true"], q.criteria["false"]])
            p_yes = _softmax([SCALE * sims[0], SCALE * sims[1]])[0]
            head = self._head_p_yes(q.name, e)
            if head:
                p_head, w = head
                p_yes = (1 - w) * p_yes + w * p_head
            return Answer("noul", noul=float(p_yes), confidence=float(abs(p_yes - 0.5) * 2), probabilities={"true": float(p_yes), "false": float(1 - p_yes)})
        assert isinstance(q.criteria, list)
        probs = _softmax([SCALE * s for s in self._class_sims(e, q.criteria)])
        return Answer(
            "score",
            score=float(sum(i * p for i, p in enumerate(probs))),
            confidence=float(max(probs)),
            probabilities={str(i): float(p) for i, p in enumerate(probs)},
        )
