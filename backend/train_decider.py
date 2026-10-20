"""Train / evaluate the local decider from logged outcomes (data/decisions.jsonl).

    uv run python train_decider.py            # fit + save data/decider_model.json (needs >= MIN_LABELS labelled rows)
    uv run python train_decider.py --eval     # compare zero-shot vs learned vs the labels, no saving

Labels: accepted startup = 1, crawled-but-not-a-startup = 0. Gated pages and extraction errors are ignored.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict

from decide.decisions import STARTUP
from decide.local import MODEL_FILE, LocalProvider
from decide.training import labelled, load_decisions
from memory import DB_DIR

MIN_LABELS = 10


def _metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    pred = p >= threshold
    tp = int(np.sum(pred & (y == 1)))
    return {
        "auc": round(float(roc_auc_score(y, p)), 3) if len(set(y)) == 2 else None,
        "precision": round(tp / max(int(pred.sum()), 1), 3),
        "recall": round(tp / max(int((y == 1).sum()), 1), 3),
    }


def evaluate(data_dir: Path) -> dict:
    pairs = labelled(load_decisions(data_dir))
    if len(pairs) < 2:
        return {"n": len(pairs), "note": "not enough labelled rows yet"}
    local = LocalProvider(model_path="/nonexistent")
    y = np.array([label for _, label in pairs])
    zero = np.array([local.decide(s, [STARTUP])["startup"].noul for s, _ in pairs])
    out = {"n": len(pairs), "positives": int(y.sum()), "zero_shot": _metrics(y, zero)}
    X = np.array([local.embedding(s) for s, _ in pairs])
    folds = min(5, int(y.sum()), int((1 - y).sum()))
    if folds >= 2:
        cv = cross_val_predict(LogisticRegression(C=2.0, class_weight="balanced", max_iter=1000), X, y, cv=folds, method="predict_proba")[:, 1]
        out["learned_cv"] = _metrics(y, cv)
    return out


def train(data_dir: Path) -> dict | None:
    """Fit the logistic head for the 'startup' question and save it next to the data."""
    pairs = labelled(load_decisions(data_dir))
    y = np.array([label for _, label in pairs])
    if len(pairs) < MIN_LABELS or len(set(y)) < 2:
        return None
    local = LocalProvider(model_path="/nonexistent")
    X = np.array([local.embedding(s) for s, _ in pairs])
    clf = LogisticRegression(C=2.0, class_weight="balanced", max_iter=1000).fit(X, y)
    model = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "heads": {"startup": {"w": clf.coef_[0].tolist(), "b": float(clf.intercept_[0]), "n": len(pairs), "positives": int(y.sum())}},
    }
    (Path(data_dir) / MODEL_FILE).write_text(json.dumps(model))
    return model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    ap.add_argument("--eval", action="store_true")
    a = ap.parse_args()
    if a.eval:
        print(json.dumps(evaluate(a.data_dir), indent=2))
    else:
        m = train(a.data_dir)
        print("trained:", json.dumps({k: v for k, v in m["heads"]["startup"].items() if k != "w"}) if m else f"need >= {MIN_LABELS} labelled rows of both classes")
