import pytest


@pytest.fixture(autouse=True)
def _no_real_sender_or_outbox(tmp_path_factory, monkeypatch):
    """Tests must never read the developer's real data/me.json or env sender, nor write the real outbox."""
    import draft
    import outreach

    empty = tmp_path_factory.mktemp("empty_data")
    monkeypatch.setattr(draft, "DB_DIR", empty)
    monkeypatch.setattr(outreach, "DB_DIR", empty)
    for k in ("NAME", "BIO", "LINKS", "OFFER", "PROOF", "PROOF_URL"):
        monkeypatch.delenv(f"CALI_SENDER_{k}", raising=False)
