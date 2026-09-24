"""
Piece 33: a document's details, typed in by hand.

Deliberately short (Rohit, 2026-09-24: speed over coverage). Only the two
things that must never break are here: the full Aadhaar number is never
stored (a legal rule, T-114), and the counting rule leaves name-only
documents alone (the seed data and the trainer's tests depend on it). The
admin's refusals are in test_admin_role.py. Everything else is covered by
the browser check.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.validators import verhoeff_check_digit
from app.models.extraction import ExtractedField
from tests.conftest import TestingSessionLocal
# Fixtures are picked up by pytest just by being imported into this module.
from tests.ours.test_uploads import (  # noqa: F401
    _headers, _jpeg_bytes, app_id, isolated_storage, people,
)

# A well-formed Aadhaar number: 11 digits plus its Verhoeff check digit.
GOOD_AADHAAR = "23412341234" + verhoeff_check_digit("23412341234")


def _upload_with_kind(client, token, app_id, doc_type, kind):
    response = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": doc_type, "consent": "true", "kind": kind},
        files={"file": ("doc.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["extraction_id"] is not None and body["needs_details"] is True
    return body


def _missing(client, token, app_id):
    response = client.get(f"/api/v1/applications/{app_id}/documents", headers=_headers(token))
    assert response.status_code == 200, response.text
    return response.json()["missing"]


def test_the_full_aadhaar_number_is_never_stored(client, people, app_id):
    doc = _upload_with_kind(client, people["customer"], app_id, "id_proof", "aadhaar")
    response = client.patch(f"/api/v1/extractions/{doc['extraction_id']}/fields",
                            json={"values": {"aadhaar_number": GOOD_AADHAAR}},
                            headers=_headers(people["customer"]))
    assert response.status_code == 200, response.text

    db = TestingSessionLocal()
    stored = [f.value for f in db.query(ExtractedField).all() if f.value]
    assert stored == [f"XXXX XXXX {GOOD_AADHAAR[-4:]}"]
    assert not any(GOOD_AADHAAR in v for v in stored)

    # And the database itself refuses a full number, whatever the code does.
    row = db.query(ExtractedField).filter(ExtractedField.field_key == "aadhaar_number").one()
    row.value = GOOD_AADHAAR
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_only_confirmed_details_count_and_name_only_documents_still_do(client, people, app_id):
    customer = people["customer"]
    # A name-only document counts straight away, exactly as before Piece 33.
    client.post(f"/api/v1/applications/{app_id}/documents",
                json={"doc_type": "id_proof", "file_name": "aadhaar.pdf"}, headers=_headers(customer))
    assert "id_proof" not in _missing(client, customer, app_id)

    # A real salary slip doesn't count until its details are confirmed.
    doc = _upload_with_kind(client, customer, app_id, "income_proof", "salary_slip")
    assert "income_proof" in _missing(client, customer, app_id)

    extraction = f"/api/v1/extractions/{doc['extraction_id']}"
    early = client.post(f"{extraction}/confirm", headers=_headers(customer))
    assert early.status_code == 422                      # required fields still empty
    assert "net_pay" in early.json()["detail"]["fields"]

    saved = client.patch(f"{extraction}/fields", json={"values": {
        "employer": "Demo Industries", "employee_name": "Priya Upload",
        "pay_month": "2026-08", "gross_pay": "65,000", "net_pay": "52000",
    }}, headers=_headers(customer))
    assert saved.status_code == 200, saved.text
    confirmed = client.post(f"{extraction}/confirm", headers=_headers(customer))
    assert confirmed.status_code == 200, confirmed.text

    assert "income_proof" not in _missing(client, customer, app_id)
