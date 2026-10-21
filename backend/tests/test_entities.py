from entities import canonical_key


def test_legal_suffixes_are_ignored():
    assert canonical_key("Acme, Inc.") == canonical_key("ACME inc") == canonical_key(" acme ") == "acme"
    assert canonical_key("Acme Labs GmbH") == "acme labs"


def test_real_name_words_and_suffix_only_names_survive():
    assert canonical_key("Stripe Technologies") == "stripe technologies"
    assert canonical_key("Inc") == "inc"
    assert canonical_key("") == ""
