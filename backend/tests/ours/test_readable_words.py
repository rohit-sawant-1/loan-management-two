"""
The audit, phase 2: stored values must read as words, everywhere they are read.

A value like `id_proof` is the right thing to store and the wrong thing to show.
It reaches people through two doors — the screen, and the AI, which repeats
whatever it is handed — so both doors need the same translation, or the chatbot
and the app say different things about the same document (Rule 12).

Removing the underscore is not enough on its own. "id_proof" became "Id proof",
which reads as somebody's name rather than as the initials it actually is.
"""

from app.utils.text import readable, readable_list


def test_an_acronym_stays_an_acronym():
    assert readable("id_proof") == "ID proof"
    assert readable("kyc_verified") == "KYC verified"


def test_ordinary_words_are_left_in_lower_case():
    """Most call sites drop this into the middle of a sentence."""
    assert readable("under_review") == "under review"
    assert readable("bank_statement") == "bank statement"
    assert readable("self_employed") == "self employed"


def test_capitalise_is_available_for_the_start_of_a_sentence():
    assert readable("under_review", capitalise=True) == "Under review"
    # An acronym is already correct and must not be re-capitalised into "Id".
    assert readable("id_proof", capitalise=True) == "ID proof"


def test_nothing_in_means_nothing_out():
    assert readable(None) == ""
    assert readable("") == ""
    assert readable_list(None) == ""
    assert readable_list([]) == ""


def test_a_list_reads_as_a_phrase():
    assert readable_list(["id_proof", "bank_statement"]) == "ID proof, bank statement"


def test_no_underscore_survives_any_document_type():
    """Every value the app can actually store, checked in one go."""
    from app.domain import rules

    for value in rules.DOCUMENT_TYPES + rules.STATUSES + rules.EMPLOYMENT_STATUSES:
        assert "_" not in readable(value), value
