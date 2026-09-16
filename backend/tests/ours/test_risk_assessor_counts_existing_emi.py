"""
D-27: the Risk Assessor must charge an applicant for the EMIs they already pay.

Phase 1's eligibility check always did this. It takes the 50% share of monthly
income, subtracts what the applicant already pays to other lenders, and the new
loan's EMI has to fit in whatever room is left — the FOIR rule real banks use.

Phase 5's Risk Assessor did not. It folded the existing EMIs into the
`debt_to_income_ratio` it reported, then ignored them when setting
`emi_affordability`, which is the flag that costs 20 points and moves the final
recommendation. So the same applicant could fail the form and pass the
underwriting review, on identical numbers.

The trainer's acceptance criterion is one-way — "given EMI > 50% of monthly
income, then emi_affordability = no" — and says nothing about the case where
the EMI alone fits but the total does not. Netting existing EMIs only adds
"no" verdicts, so that criterion still holds; the last test here pins it.

Nothing here touches a real AI. The summary writer is stubbed out, so this
file costs no quota and needs no network.
"""

import pytest

from app.utils.finance import calculate_emi, max_affordable_emi
from multi_agent.agents import risk_assessor as risk_module
from multi_agent.agents.risk_assessor import risk_assessor

RATE = 12.0


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """The score is deterministic; only the prose needs a model. Stub it."""
    monkeypatch.setattr(risk_module, "_llm_summary", lambda risk_data: "Stubbed summary.")


def _state(*, annual_income, amount, tenure, existing=None, credit=760, years=6.0):
    applicant = {
        "name": "Test", "annual_income": annual_income,
        "credit_score": credit, "employment_status": "salaried",
        "years_with_employer": years,
    }
    if existing is not None:
        applicant["existing_monthly_emi"] = existing
    return {
        "application_id": "1",
        "applicant_data": applicant,
        "application_data": {
            "loan_type": "personal", "amount_requested": amount, "tenure_months": tenure,
        },
        "documents": [], "risk_assessment": {}, "compliance_check": {},
        "final_decision": "", "reasoning": "", "messages": [],
        "current_agent": "", "errors": [],
    }


# A borrower on 1,00,000 a month. The 50% ceiling is 50,000. They already pay
# 20,000 elsewhere, so only 30,000 of room is left. The new loan's EMI is
# 44,489 — comfortably under the ceiling, comfortably over the room.
HEAVY = dict(annual_income=1_200_000, amount=2_000_000, tenure=60)


def test_existing_emis_make_an_otherwise_affordable_loan_unaffordable():
    result = risk_assessor(_state(**HEAVY, existing=20_000))["risk_assessment"]

    emi = calculate_emi(HEAVY["amount"], RATE, HEAVY["tenure"])
    assert emi < 50_000, "this fixture only means something if the EMI fits the bare ceiling"
    assert result["emi_affordability"] == "no"


def test_the_same_loan_is_affordable_when_nothing_is_owed_elsewhere():
    result = risk_assessor(_state(**HEAVY, existing=0))["risk_assessment"]

    assert result["emi_affordability"] == "yes"
    assert result["overall_risk_score"] == 100.0


def test_the_unaffordable_verdict_costs_the_twenty_points():
    owing = risk_assessor(_state(**HEAVY, existing=20_000))["risk_assessment"]
    clear = risk_assessor(_state(**HEAVY, existing=0))["risk_assessment"]

    assert clear["overall_risk_score"] - owing["overall_risk_score"] == 20.0


def test_no_figure_on_file_still_assumes_the_trainers_ten_percent():
    """The spec says "assume existing obligations = 10% of income unless
    specified". On 1,00,000 a month that is 10,000, leaving 40,000 of room —
    still short of the 44,489 EMI."""
    result = risk_assessor(_state(**HEAVY))["risk_assessment"]

    assert result["emi_affordability"] == "no"


@pytest.mark.parametrize("annual_income,existing", [
    (1_200_000, 0),
    (1_200_000, 12_000),
    (1_200_000, 20_000),
    (900_000, 15_000),
    (480_000, 4_000),
])
def test_phase_five_agrees_with_phase_ones_affordability_maths(annual_income, existing):
    """The whole point of D-27: one helper, one answer, both engines."""
    state = _state(annual_income=annual_income, amount=2_000_000, tenure=60, existing=existing)
    result = risk_assessor(state)["risk_assessment"]

    emi = calculate_emi(2_000_000, RATE, 60)
    expected = "yes" if emi <= max_affordable_emi(annual_income, existing) else "no"
    assert result["emi_affordability"] == expected


def test_the_trainers_one_way_criterion_still_holds():
    """An EMI over 50% of income on its own is "no" whatever is owed elsewhere."""
    state = _state(annual_income=240_000, amount=500_000, tenure=12, existing=0)
    result = risk_assessor(state)["risk_assessment"]

    emi = calculate_emi(500_000, RATE, 12)
    assert emi > 240_000 / 12 * 0.50
    assert result["emi_affordability"] == "no"
