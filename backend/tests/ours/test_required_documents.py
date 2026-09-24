"""
D-32: a home loan asks for an employment letter from salaried applicants only,
as the manual (the trainer's spec) says. An unknown status keeps the letter
required, which is what the trainer's AGENT-06 and E2E-06 rely on.
"""

from app.domain import rules


def test_the_employment_letter_is_for_salaried_home_loan_applicants_only():
    assert "employment_letter" in rules.required_documents("home", "salaried")
    assert "employment_letter" not in rules.required_documents("home", "self_employed")
    assert "employment_letter" in rules.required_documents("home")          # unknown: as before
    assert "employment_letter" not in rules.missing_documents(
        "home", ["id_proof", "income_proof", "bank_statement", "property_docs"], "self_employed"
    )
