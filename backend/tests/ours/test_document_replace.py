"""
Piece 32d: replacing a document with a newer copy.

The helpers and fixtures come from Piece 31's upload tests, so a replace is
set up exactly the way a normal upload is. Everything runs offline: the one
Gemini step (confirming a SPECIMEN file) is monkeypatched.

The refusals come first, for the same reason as in the other suites: a
verified document being quietly swapped out is the failure that matters.
"""

from __future__ import annotations

import json

from app.models.activity_log import ActivityLog
from app.models.document import Document
from tests.conftest import TestingSessionLocal
# Fixtures are picked up by pytest just by being imported into this module.
from tests.ours.test_uploads import (  # noqa: F401
    _headers, _jpeg_bytes, _minimal_pdf_with_text, _switch_uploads, _upload,
    app_id, isolated_storage, people,
)


def _add_by_name(client, token, app_id, doc_type="id_proof", file_name="aadhaar_old.pdf"):
    response = client.post(f"/api/v1/applications/{app_id}/documents",
                           json={"doc_type": doc_type, "file_name": file_name},
                           headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _replace_by_name(client, token, app_id, doc_id, file_name="aadhaar_new.pdf"):
    return client.post(f"/api/v1/applications/{app_id}/documents/{doc_id}/replace",
                       json={"file_name": file_name}, headers=_headers(token))


def _replace_by_upload(client, token, app_id, doc_id, data, filename="new.jpg",
                       content_type="image/jpeg", consent=True):
    return client.post(
        f"/api/v1/applications/{app_id}/documents/{doc_id}/replace/upload",
        data={"consent": str(consent).lower()},
        files={"file": (filename, data, content_type)},
        headers=_headers(token),
    )


def _list(client, token, app_id):
    response = client.get(f"/api/v1/applications/{app_id}/documents", headers=_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def test_a_verified_document_cannot_be_replaced(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    verified = client.patch(f"/api/v1/applications/{app_id}/documents/{old['id']}/verify",
                            headers=_headers(people["officer"]))
    assert verified.status_code == 200, verified.text

    response = _replace_by_name(client, people["customer"], app_id, old["id"])
    assert response.status_code == 422
    assert "verified" in response.json()["detail"].lower()


def test_a_document_cannot_be_replaced_twice(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    assert _replace_by_name(client, people["customer"], app_id, old["id"]).status_code == 201

    again = _replace_by_name(client, people["customer"], app_id, old["id"], "third.pdf")
    assert again.status_code == 422


def test_another_customer_cannot_replace_it(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    response = _replace_by_name(client, people["other_customer"], app_id, old["id"])
    assert response.status_code == 403


def test_the_admin_cannot_replace_it(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    response = _replace_by_name(client, people["admin"], app_id, old["id"])
    assert response.status_code == 403


def test_a_document_on_another_application_is_not_found(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    response = _replace_by_name(client, people["customer"], 999999, old["id"])
    assert response.status_code == 404


def test_upload_replace_is_refused_when_real_uploads_are_off(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    _switch_uploads(client, people["admin"], False)
    response = _replace_by_upload(client, people["customer"], app_id, old["id"], _jpeg_bytes())
    assert response.status_code == 409


def test_a_replaced_copy_cannot_be_verified(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    _replace_by_name(client, people["customer"], app_id, old["id"])
    response = client.patch(f"/api/v1/applications/{app_id}/documents/{old['id']}/verify",
                            headers=_headers(people["officer"]))
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# What a replace does
# ---------------------------------------------------------------------------

def test_replace_by_name_keeps_the_type_and_marks_the_old_copy(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id, "income_proof", "payslip_march.pdf")
    response = _replace_by_name(client, people["customer"], app_id, old["id"], "payslip_april.pdf")
    assert response.status_code == 201, response.text
    new = response.json()
    assert new["doc_type"] == "income_proof"
    assert new["replaced_by_id"] is None

    db = TestingSessionLocal()
    stored_old = db.query(Document).filter(Document.id == old["id"]).first()
    assert stored_old is not None                  # never deleted
    assert stored_old.replaced_by_id == new["id"]
    assert stored_old.replaced_at is not None
    db.close()


def test_replace_by_upload_runs_the_whole_pipeline(client, people, app_id):
    old = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes(seed=1)).json()
    response = _replace_by_upload(client, people["customer"], app_id, old["id"], _jpeg_bytes(seed=3))
    assert response.status_code == 201, response.text
    new = response.json()
    assert new["doc_type"] == "id_proof"
    assert new["file_id"] is not None and new["file_id"] != old["file_id"]

    # The old copy's file is kept, and staff can still open it.
    still_there = client.get(f"/api/v1/files/{old['file_id']}", headers=_headers(people["officer"]))
    assert still_there.status_code == 200


def test_upload_replace_still_needs_consent(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    response = _replace_by_upload(client, people["customer"], app_id, old["id"], _jpeg_bytes(),
                                  consent=False)
    assert response.status_code == 422

    db = TestingSessionLocal()
    assert db.query(Document).filter(Document.id == old["id"]).first().replaced_by_id is None
    db.close()


def test_staff_can_replace_on_a_customers_behalf(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    assert _replace_by_name(client, people["officer"], app_id, old["id"]).status_code == 201


def test_the_replaced_copy_stops_counting_everywhere(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    new = _replace_by_name(client, people["customer"], app_id, old["id"]).json()

    listing = _list(client, people["officer"], app_id)
    assert [d["id"] for d in listing["items"]] == [new["id"]]
    assert "id_proof" not in listing["missing"]    # still covered, by the new copy

    detail = client.get(f"/api/v1/applications/{app_id}", headers=_headers(people["officer"])).json()
    assert [d["id"] for d in detail["documents"]] == [new["id"]]

    queue = client.get("/api/v1/documents/unverified?limit=100", headers=_headers(people["officer"])).json()
    queue_ids = [d["id"] for d in queue["items"]]
    assert new["id"] in queue_ids and old["id"] not in queue_ids


def test_replaced_copies_are_shown_to_staff_but_not_the_customer(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    _replace_by_name(client, people["customer"], app_id, old["id"])

    assert _list(client, people["customer"], app_id)["replaced"] == []
    staff_view = _list(client, people["officer"], app_id)["replaced"]
    assert [d["id"] for d in staff_view] == [old["id"]]
    assert _list(client, people["admin"], app_id)["replaced"][0]["id"] == old["id"]


def test_the_replace_is_in_the_activity_log(client, people, app_id):
    old = _add_by_name(client, people["customer"], app_id)
    new = _replace_by_name(client, people["customer"], app_id, old["id"]).json()

    db = TestingSessionLocal()
    row = db.query(ActivityLog).filter(ActivityLog.action == "document_replaced").one()
    assert row.entity_id == new["id"]
    assert json.loads(row.details)["replaced_document_id"] == old["id"]   # stored as JSON text
    db.close()


# ---------------------------------------------------------------------------
# The purge puts back what a TEST copy replaced
# ---------------------------------------------------------------------------

def test_purging_a_test_replacement_brings_the_old_copy_back(client, people, app_id, monkeypatch):
    monkeypatch.setattr("app.services.file_service._gemini_confirms_specimen", lambda text, phrase: True)
    old = _add_by_name(client, people["customer"], app_id, "bank_statement", "statement.pdf")
    specimen = _minimal_pdf_with_text("SPECIMEN DOCUMENT FOR TESTING ONLY")
    test_copy = _replace_by_upload(client, people["customer"], app_id, old["id"], specimen,
                                   filename="specimen.pdf", content_type="application/pdf")
    assert test_copy.status_code == 201, test_copy.text
    assert test_copy.json()["nature"] == "test"

    purged = client.post("/api/v1/admin/test-documents/purge",
                         json={"confirm": "DELETE TEST DOCUMENTS"}, headers=_headers(people["admin"]))
    assert purged.status_code == 200, purged.text

    listing = _list(client, people["officer"], app_id)
    assert [d["id"] for d in listing["items"]] == [old["id"]]
    assert listing["replaced"] == []
