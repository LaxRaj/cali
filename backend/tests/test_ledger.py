import pytest

import ledger
from models import Contact, ContactItem, Edge, Person, StartupProfile

S = StartupProfile(company_name="Acme, Inc.", core_product="Search", likely_bottleneck="Slow", value_prop_pitch="x",
                   is_relevant=True, funding_stage="seed", hq="Berlin", website="https://acme.io")
PEOPLE = [Person(name="Ada L", role="CEO", org="Acme", evidence="Ada is CEO", linkedin="https://linkedin.com/in/ada", link_source="search")]
EDGES = [Edge(src="Ada L", rel="founded", dst="Acme Inc", evidence="Ada founded Acme")]
CONTACT = Contact(website="https://acme.io", emails=[ContactItem(value="hi@acme.io", kind="general", source_url="https://acme.io/contact")])


@pytest.fixture
def db(tmp_path):
    return tmp_path


def rows(url="https://news.example/a"):
    return ledger.observations_for(S, PEOPLE, EDGES, CONTACT, url)


def test_rows_cover_facts_with_trust_levels():
    by = {(r["entity_type"], r["field"]): r for r in rows()}
    assert by[("startup", "funding_stage")]["confidence"] == ledger.INFERRED
    assert by[("person", "role")]["confidence"] == ledger.GROUNDED
    assert by[("person", "linkedin")]["confidence"] == ledger.MATCHED  # found by search, not read off a page
    assert by[("contact", "email")]["source_url"] == "https://acme.io/contact"
    assert by[("edge", "founded")]["entity_key"] == "ada l|founded|acme"
    assert {r["company"] for r in rows()} == {"acme"}
    assert by[("person", "role")]["label"] == "Ada L · CEO" and by[("edge", "founded")]["label"] == "Ada L founded Acme Inc"
    assert by[("startup", "hq")]["label"] == "hq: Berlin"


def test_first_record_stamps_run_and_dates(db):
    new = ledger.record(rows(), "r1", "2026-10-01T00:00:00", db)
    assert new == len(rows()) == len(ledger.load(db))
    assert {r["first_seen"] for r in ledger.load(db)} == {"2026-10-01T00:00:00"}


def test_refinding_a_fact_keeps_first_seen_and_counts_runs(db):
    ledger.record(rows(), "r1", "2026-10-01T00:00:00", db)
    assert ledger.record(rows(), "r2", "2026-10-05T00:00:00", db) == 0
    again = ledger.record(rows(), "r2", "2026-10-06T00:00:00", db)  # same run twice must not double count
    assert again == 0
    got = {r["field"]: r for r in ledger.load(db) if r["entity_type"] == "startup"}["hq"]
    assert (got["first_seen"], got["last_seen"], got["run_id"], got["seen_count"]) == ("2026-10-01T00:00:00", "2026-10-06T00:00:00", "r2", 2)


def test_same_fact_from_a_new_source_is_a_new_row(db):
    ledger.record(rows(), "r1", "2026-10-01T00:00:00", db)
    new = ledger.record(rows("https://other.example/b"), "r2", "2026-10-02T00:00:00", db)
    assert new > 0 and len({r["source_url"] for r in ledger.load(db) if r["field"] == "hq"}) == 2


def test_empty_is_a_noop(db):
    assert ledger.record([], "r1", "t", db) == 0 and ledger.load(db) == []
