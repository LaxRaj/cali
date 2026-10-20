import json

from decide.decisions import STARTUP
from decide.local import LocalProvider
from decide.training import append_decisions, labelled, load_decisions
from train_decider import MIN_LABELS, evaluate, train

POS = ["Tako raises $5.75M seed round", "Chariot raises seed to stop hidden fees", "Launch HN: Laminar – agent observability",
       "Fini: an AI teammate for your support team", "Vesta raises $30M as lenders adopt AI agents", "machine0: cloud computers for AI agents",
       "Kairos Health: AI front desk for dental practices", "Respan: observability for LLM apps"]
NEG = ["Show HN: The Lion King SNES port", "10 best vector databases", "Show HN: My weather station", "How to launch on Hacker News",
       "Show HN: zombie car game", "Zelda timeline explained", "Show HN: 500 clocks in one html file"]


def rows(source="rss"):
    return ([{"title": t, "snippet": "", "source": source, "outcome": "accepted", "triage": 7} for t in POS]
            + [{"title": t, "snippet": "", "source": "hn", "outcome": "rejected", "triage": 4} for t in NEG]
            + [{"title": "gated one", "snippet": "", "source": "web", "outcome": "gated"}, {"title": "err", "source": "web", "outcome": "error"}])


def test_only_accepted_and_rejected_rows_become_labels(tmp_path):
    append_decisions(tmp_path, "r1", rows())
    pairs = labelled(load_decisions(tmp_path))
    assert len(pairs) == len(POS) + len(NEG) and sum(l for _, l in pairs) == len(POS)  # gated/error ignored


def test_log_is_appended_across_runs_and_capped(tmp_path, monkeypatch):
    import decide.training as t

    monkeypatch.setattr(t, "MAX_ROWS", 20)
    for i in range(3):
        append_decisions(tmp_path, f"r{i}", rows())
    got = load_decisions(tmp_path)
    assert len(got) == 20 and got[-1]["run_id"] == "r2"


def test_not_enough_labels_means_no_model(tmp_path):
    append_decisions(tmp_path, "r", rows()[:3])
    assert train(tmp_path) is None and not (tmp_path / "decider_model.json").exists()
    assert evaluate(tmp_path)["n"] == 3


def test_training_saves_a_head_the_local_provider_uses(tmp_path):
    append_decisions(tmp_path, "r", rows())
    model = train(tmp_path)
    assert model and model["heads"]["startup"]["n"] == len(POS) + len(NEG) >= MIN_LABELS
    saved = json.loads((tmp_path / "decider_model.json").read_text())
    assert len(saved["heads"]["startup"]["w"]) == 384

    learned = LocalProvider(model_path=tmp_path / "decider_model.json")
    zero = LocalProvider(model_path="/nonexistent")
    startup, hobby = "Acme raises a $4M seed round for its search product", "Show HN: A zombie racing game I made"
    ln = {t: learned.decide(t, [STARTUP])["startup"].noul for t in (startup, hobby)}
    zn = {t: zero.decide(t, [STARTUP])["startup"].noul for t in (startup, hobby)}
    assert ln[hobby] != zn[hobby]  # the learned head is actually in the blend
    assert ln[startup] > ln[hobby] + 0.4  # ...and still ranks startups above hobby projects


def test_eval_reports_zero_shot_and_cross_validated_head(tmp_path):
    append_decisions(tmp_path, "r", rows())
    out = evaluate(tmp_path)
    assert out["n"] == len(POS) + len(NEG) and out["zero_shot"]["auc"] >= 0.9
    assert out["learned_cv"]["auc"] >= 0.8 and 0 <= out["learned_cv"]["precision"] <= 1
