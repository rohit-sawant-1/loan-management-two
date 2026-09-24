"""
Pieces 37 + 38: documents attached from the Assistant.

The files go up through the normal upload address (the same pipeline as the
Documents card); `/chat/attachments` only records, in the customer's own chat,
which of their documents they attached. No AI is involved anywhere here.
"""

from __future__ import annotations

import json
import uuid

from app.models.activity_log import ActivityLog
from tests.conftest import TestingSessionLocal
# Fixtures are picked up by pytest just by being imported into this module.
from tests.ours.test_uploads import (  # noqa: F401
    _apply, _headers, _jpeg_bytes, _upload, app_id, isolated_storage, people,
)


def _attach(client, token, application_id, document_ids, key=None, session_id=None):
    return client.post("/api/v1/chat/attachments", json={
        "session_id": session_id, "application_id": application_id,
        "document_ids": document_ids, "attach_key": key or str(uuid.uuid4()),
    }, headers=_headers(token))


def _uploaded(client, token, app_id, doc_type="id_proof", seed=1):
    response = _upload(client, token, app_id, doc_type, _jpeg_bytes(seed=seed))
    assert response.status_code == 201, response.text
    return response.json()


def test_attaching_saves_the_message_audits_it_and_a_retry_is_not_a_duplicate(client, people, app_id):
    customer = people["customer"]
    first = _uploaded(client, customer, app_id, seed=1)                  # "Something else" (no kind)
    second = _uploaded(client, customer, app_id, "income_proof", seed=2)
    key = str(uuid.uuid4())

    response = _attach(client, customer, app_id, [first["id"], second["id"]], key)
    assert response.status_code == 200, response.text
    body = response.json()
    session_id = body["session_id"]
    assert body["message"]["application_id"] == app_id
    assert body["message"]["document_ids"] == [first["id"], second["id"]]
    assert body["message"]["role"] == "user"

    # A retry of the same event (same key) returns the same message.
    retry = _attach(client, customer, app_id, [first["id"], second["id"]], key, str(session_id))
    assert retry.status_code == 200
    assert retry.json()["message"]["id"] == body["message"]["id"]

    # Reopening the chat brings the attachment back, once.
    page = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=_headers(customer)).json()
    attached = [m for m in page["items"] if m["document_ids"]]
    assert len(attached) == 1
    assert attached[0]["document_ids"] == [first["id"], second["id"]]

    # Attaching the same documents again later is a new event, and is allowed.
    again = _attach(client, customer, app_id, [first["id"]], session_id=str(session_id))
    assert again.status_code == 200 and again.json()["message"]["id"] != body["message"]["id"]

    # Audited, with ids and file names only: never a document's contents.
    db = TestingSessionLocal()
    rows = db.query(ActivityLog).filter(ActivityLog.action == "chat_documents_attached").all()
    db.close()
    assert len(rows) == 2                                               # the retry added none
    details = json.loads(rows[0].details)
    assert set(details) == {"document_ids", "file_names", "chat"}
    assert rows[0].entity_type == "application" and rows[0].entity_id == app_id


def test_attaching_follows_the_ownership_and_current_document_rules(client, people, app_id):
    customer = people["customer"]
    doc = _uploaded(client, customer, app_id)

    # Another customer: the document system's own rule for someone else's application (403).
    assert _attach(client, people["other_customer"], app_id, [doc["id"]]).status_code == 403

    # A document from a different application of the same customer: refused.
    other_app = _apply(client, customer)
    elsewhere = _uploaded(client, customer, other_app, seed=5)
    assert _attach(client, customer, app_id, [elsewhere["id"]]).status_code == 422

    # A replaced (no longer current) document: refused.
    old = client.post(f"/api/v1/applications/{app_id}/documents",
                      json={"doc_type": "income_proof", "file_name": "old.pdf"}, headers=_headers(customer)).json()
    client.post(f"/api/v1/applications/{app_id}/documents/{old['id']}/replace",
                json={"file_name": "new.pdf"}, headers=_headers(customer))
    assert _attach(client, customer, app_id, [old["id"]]).status_code == 422

    # Staff and the admin have no Assistant attachment capability.
    for role in ("officer", "manager", "admin"):
        assert _attach(client, people[role], app_id, [doc["id"]]).status_code == 403
