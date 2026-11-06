import json

from enrich import team_markdown
from memory import TABLE, _rows, upsert_people, upsert_profile
from models import Contact, ContactItem, Person, StartupProfile
from rescore import rescore


def prof(name, **kw):
    return StartupProfile(company_name=name, core_product="Semantic search for legal contracts and filings",
                          tech_stack=["Go"], likely_bottleneck="Keyword search misses clauses at scale",
                          value_prop_pitch="One. Two.", is_relevant=True, source_url="https://x.com/y",
                          discovered_at="2026-10-19", funding_stage="Seed", **kw)


def test_rescore_rerates_stored_rows_without_dropping_other_columns(tmp_path):
    d = tmp_path / "db"
    contact = Contact(emails=[ContactItem(value="jane@acme.io", kind="person", source_url="https://acme.io/")], contact_page="https://acme.io/contact")
    upsert_profile(prof("Acme"), db_dir=d, extras={"score": 10, "score_json": "{}", "contact_json": contact.model_dump_json(), "outcome": "kept"})
    upsert_people([Person(name="Jane Roe", role="CEO", org="Acme", evidence="Jane Roe is CEO of Acme")], db_dir=d)

    res = rescore(d)
    row = _rows(TABLE, d)[0]
    sj = json.loads(row["score_json"])
    assert res["rows"] == 1 and res["changed"] == 1 and res["qualified"] == 1
    assert row["score"] > 10 and sj["qualified"] is True and set(sj["axes"]) == {"fit", "reach", "evidence"}
    assert row["outcome"] == "kept" and row["contact_json"] == contact.model_dump_json()
    assert rescore(d)["changed"] == 0  # idempotent


def test_team_markdown_puts_team_pages_first_and_drops_contact_nav_noise():
    nav = "\n".join(f"  * [Item {i}](https://acme.io/p{i}/)" for i in range(400))
    about = nav + "\n## Leadership Team\n##### Ada Lovelace\nChief Executive Officer\n"
    contact = "# Get in touch\nGeneral inquiries: hi@acme.io\n" * 50
    out = team_markdown([("https://acme.io/contact/", contact), ("https://acme.io/about/", about)], limit=3000)
    assert "Ada Lovelace" in out and "Get in touch" not in out and "https://acme.io/p1/" not in out
