"""
Piece 33: a document's details, typed in by hand, and Piece 34: read
automatically from a PDF's own text, with the Aadhaar digits blacked out.

Deliberately short (Rohit, 2026-09-24: speed over coverage). Only the
things that must never break are here: the full Aadhaar number is never
stored (a legal rule, T-114), and the counting rule leaves name-only
documents alone (the seed data and the trainer's tests depend on it). The
admin's refusals are in test_admin_role.py. Everything else is covered by
the browser check.
"""

from __future__ import annotations

import pypdfium2 as pdfium
import pytest
from PIL import ImageStat
from sqlalchemy.exc import IntegrityError

from app.domain.validators import verhoeff_check_digit
from app.models.extraction import ExtractedField
from app.models.stored_file import StoredFile
from app.services import document_reader, storage
from scripts.make_specimen_docs import build_pdf
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


def _aadhaar_pdf(number_line=f"Aadhaar No: {GOOD_AADHAAR[:4]} {GOOD_AADHAAR[4:8]} {GOOD_AADHAAR[8:]}",
                 banner="Unique Identification Authority of India"):
    """An Aadhaar-style PDF with a real text layer, built the same way as the demo kit."""
    return build_pdf([(14, banner), (13, "Name: Priya Upload"), (13, "DOB: 15/03/1994"),
                      (13, "FEMALE"), (13, number_line)])


def test_an_aadhaar_pdf_is_read_masked_and_blacked_out(client, people, app_id):
    """Piece 33 + 34, and T-114: the number is read, stored masked, and blacked out on the stored copy."""
    raw = _aadhaar_pdf()
    response = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": "id_proof", "consent": "true", "kind": "aadhaar"},
        files={"file": ("aadhaar.pdf", raw, "application/pdf")},
        headers=_headers(people["customer"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # Read from the text layer, and only the last 4 digits kept.
    details = client.get(f"/api/v1/extractions/{body['extraction_id']}",
                         headers=_headers(people["customer"])).json()
    number = next(f for f in details["fields"] if f["key"] == "aadhaar_number")
    assert number["value"] == f"XXXX XXXX {GOOD_AADHAAR[-4:]}"
    assert number["state"] == "extracted"
    assert details["read_automatically"] is True

    db = TestingSessionLocal()
    stored_values = [v for f in db.query(ExtractedField).all() for v in (f.value, f.machine_value) if v]
    assert not any(GOOD_AADHAAR in v.replace(" ", "") for v in stored_values)

    db.close()
    _assert_first_8_digits_blacked_out(raw, body["file_id"])


def _assert_first_8_digits_blacked_out(raw, file_id):
    """The stored copy is black where the first 8 digits were. The rebuilt PDF
    was drawn at 150 DPI, so it renders back at the same pixel size."""
    db = TestingSessionLocal()
    stored = db.query(StoredFile).filter(StoredFile.id == file_id).one()
    rebuilt = storage.open_file(stored.storage_zone.value, stored.stored_name)
    db.close()
    page = pdfium.PdfDocument(rebuilt)[0].render(scale=1).to_pil().convert("L")

    original = pdfium.PdfDocument(raw)[0]
    height, scale = original.get_height(), 150 / 72
    boxes = document_reader.aadhaar_redactions(document_reader.pages_with_positions(raw))[0]
    assert len(boxes) == 8
    for left, bottom, right, top in boxes:
        region = page.crop((int(left * scale), int((height - top) * scale),
                            int(right * scale) + 1, int((height - bottom) * scale) + 1))
        assert ImageStat.Stat(region).mean[0] < 40, "a digit's box isn't blacked out"


def test_an_aadhaar_in_any_id_proof_pdf_is_blacked_out(client, people, app_id):
    """D-33 privacy guard: uploaded as "Something else" (no kind), still blacked out."""
    raw = _aadhaar_pdf()
    response = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": "id_proof", "consent": "true"},           # no kind
        files={"file": ("id.pdf", raw, "application/pdf")},
        headers=_headers(people["customer"]),
    )
    assert response.status_code == 201, response.text
    _assert_first_8_digits_blacked_out(raw, response.json()["file_id"])


def test_something_else_counts_on_upload(client, people, app_id):
    """D-33: a document with no form (a passport, say) counts at once; staff check it."""
    response = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": "id_proof", "consent": "true"},           # "Something else"
        files={"file": ("passport.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=_headers(people["customer"]),
    )
    assert response.status_code == 201, response.text
    assert response.json()["needs_details"] is False
    assert "id_proof" not in _missing(client, people["customer"], app_id)


def test_an_aadhaar_that_cant_be_blacked_out_is_refused_unless_test(client, people, app_id, monkeypatch):
    """Rohit, 2026-09-24: a real or undeclared Aadhaar with no findable number is refused; TEST is stored."""
    photo = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": "id_proof", "consent": "true", "kind": "aadhaar"},
        files={"file": ("aadhaar.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=_headers(people["customer"]),
    )
    assert photo.status_code == 422
    assert "masked Aadhaar" in photo.json()["detail"]

    monkeypatch.setattr("app.services.file_service._gemini_confirms_specimen", lambda text, phrase: True)
    specimen = _aadhaar_pdf(number_line="Aadhaar No: (printed on the back)", banner="SPECIMEN AADHAAR")
    test_doc = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": "id_proof", "consent": "true", "kind": "aadhaar"},
        files={"file": ("specimen.pdf", specimen, "application/pdf")},
        headers=_headers(people["customer"]),
    )
    assert test_doc.status_code == 201, test_doc.text
    assert test_doc.json()["nature"] == "test"


def test_the_database_refuses_a_full_aadhaar_number(client, people, app_id):
    response = client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": "id_proof", "consent": "true", "kind": "aadhaar"},
        files={"file": ("aadhaar.pdf", _aadhaar_pdf(), "application/pdf")},
        headers=_headers(people["customer"]),
    )
    assert response.status_code == 201, response.text
    db = TestingSessionLocal()

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
