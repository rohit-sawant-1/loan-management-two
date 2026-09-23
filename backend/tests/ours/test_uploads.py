"""
Piece 31: real document uploads, the safety pipeline, and the two storage
folders.

Everything here runs through the real HTTP addresses, files built in
memory — nothing on the real filesystem outside pytest's own tmp path
(the fixture below points UPLOAD_DIR_SAFE and UPLOAD_DIR_SENSITIVE at a
throwaway folder for the whole test session). The Gemini confirmation step
is monkeypatched wherever a test needs it to go one way or the other, so
nothing here spends real quota.

The refusals come first, because — as with Piece 25 — they are the ones
whose failure matters most: a customer must never end up with a file that
should have been rejected, and nothing may reach the git-tracked folder
except a file the classifier is genuinely confident about.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from sqlalchemy.exc import DatabaseError

from app.models.stored_file import StoredFile
from app.models.user import User, UserRole
from app.services import file_service
from tests.conftest import TestingSessionLocal

PASSWORD = "Test@1234"


# ---------------------------------------------------------------------------
# Isolate every test's files from the real project (and from each other)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir_safe", str(tmp_path / "safe"))
    monkeypatch.setattr(settings, "upload_dir_sensitive", str(tmp_path / "sensitive"))
    monkeypatch.setattr(settings, "upload_encryption_key",
                        "SRgn_cvcX0bCaFDb2Vxp-Mybkh_2e473C80ybZm7eUE=")
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _staff_with_role(client, email, role):
    client.post("/api/v1/auth/register", json={"name": "Staff Test", "email": email, "password": PASSWORD})
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    user.role = role
    db.commit()
    db.close()
    return _login(client, email)


def _customer(client, email="priya.upload@test.com", phone="9876500071"):
    response = client.post("/api/v1/auth/register-applicant", json={
        "name": "Priya Upload", "email": email, "password": PASSWORD, "phone": phone,
        "annual_income": 600000.0, "employment_status": "salaried",
        "credit_score": 760, "date_of_birth": "1994-03-15", "years_with_employer": 3.0,
    })
    assert response.status_code in (200, 201), response.text
    return _login(client, email)


def _apply(client, token):
    me = client.get("/api/v1/applicants/me", headers=_headers(token)).json()
    response = client.post("/api/v1/applications", json={
        "applicant_id": me["id"], "loan_type": "personal",
        "amount_requested": 200000.0, "tenure_months": 24, "purpose": "Home renovation",
    }, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _switch_uploads(client, admin_token, enabled):
    response = client.put("/api/v1/admin/settings/real-uploads",
                          json={"enabled": enabled}, headers=_headers(admin_token))
    assert response.status_code == 200, response.text


def _upload(client, token, app_id, doc_type, data, filename="photo.jpg",
           content_type="image/jpeg", consent=True):
    return client.post(
        f"/api/v1/applications/{app_id}/documents/upload",
        data={"doc_type": doc_type, "consent": str(consent).lower()},
        files={"file": (filename, data, content_type)},
        headers=_headers(token),
    )


# ---------------------------------------------------------------------------
# Building test files
# ---------------------------------------------------------------------------

def _photo_like(w, h, seed=1):
    """A synthetic but genuinely detailed photo — flat colours refuse at the
    blank-page check, so this needs real variation, not just any bytes."""
    img = Image.new("RGB", (w, h), (180, 170, 160))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        shade = int(110 + 110 * y / h)
        draw.line([(0, y), (w, y)], fill=(shade, shade - 20, shade - 40))
    draw.ellipse([w * 0.3, h * 0.15, w * 0.7, h * 0.85], fill=(215, 190, 170))
    for i in range(0, w, 11 + seed):
        draw.line([(i, 0), (i, h)], fill=(200, 60, 60), width=1)
    return img


def _jpeg_bytes(w=2400, h=1800, quality=95, seed=1):
    buf = io.BytesIO()
    _photo_like(w, h, seed).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _blank_jpeg_bytes(w=800, h=600):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="JPEG")
    return buf.getvalue()


def _minimal_pdf_with_text(text: str) -> bytes:
    """A hand-built, minimal but valid PDF with a real, extractable text
    layer — the only reliable way to test the watermark check without a
    PDF-authoring library in requirements.txt."""
    content = f"BT /F1 24 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 400 400] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return pdf


def _scanned_pdf_bytes(w=1600, h=1200):
    """An image-only PDF, the way a real scanned document looks: no text layer at all."""
    buf = io.BytesIO()
    _photo_like(w, h, seed=2).save(buf, format="PDF")
    return buf.getvalue()


def _encrypted_pdf_bytes():
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _pdf_with_js_bytes():
    plain = _scanned_pdf_bytes(200, 200)
    return plain + b"\n/JavaScript (app.alert('hi'));"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def people(client, auth_token):
    return {
        "admin": _staff_with_role(client, "admin.upload@test.com", UserRole.admin),
        "manager": _staff_with_role(client, "manager.upload@test.com", UserRole.branch_manager),
        "officer": auth_token,
        "customer": _customer(client),
        "other_customer": _customer(client, "rahul.upload@test.com", "9876500072"),
    }


@pytest.fixture
def app_id(client, people):
    _switch_uploads(client, people["admin"], True)
    return _apply(client, people["customer"])


# ---------------------------------------------------------------------------
# The switch
# ---------------------------------------------------------------------------

def test_the_switch_off_refuses_uploads_and_the_name_route_still_works(client, people):
    _switch_uploads(client, people["admin"], False)
    app_id = _apply(client, people["customer"])

    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    assert response.status_code == 409, response.text

    named = client.post(f"/api/v1/applications/{app_id}/documents",
                        json={"doc_type": "id_proof", "file_name": "aadhaar.pdf"},
                        headers=_headers(people["customer"]))
    assert named.status_code == 201, named.text


# ---------------------------------------------------------------------------
# Accepted uploads
# ---------------------------------------------------------------------------

def test_a_phone_photo_is_accepted_and_shrunk(client, people, app_id):
    raw = _jpeg_bytes()
    response = _upload(client, people["customer"], app_id, "id_proof", raw)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["original_size_bytes"] == len(raw)
    assert 0 < body["size_bytes"] <= 300_000
    assert body["content_type"] == "image/jpeg"
    # No question was asked, so nothing local could have confirmed test material.
    assert body["nature"] == "undeclared"


def test_a_scanned_pdf_is_rebuilt(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "bank_statement",
                       _scanned_pdf_bytes(), filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] <= 3_000_000
    assert body["nature"] == "undeclared"   # no text layer to check


def test_encryption_round_trip(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    file_id = response.json()["file_id"]

    db = TestingSessionLocal()
    stored = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    from app.services import storage
    on_disk = storage._dir_for(stored.storage_zone.value) / stored.stored_name
    on_disk_bytes = on_disk.read_bytes()
    db.close()

    # What is actually on disk is never the plain rebuilt file.
    assert on_disk_bytes != response.content
    assert b"JFIF" not in on_disk_bytes[:64]   # not a readable JPEG header

    viewed = client.get(f"/api/v1/files/{file_id}", headers=_headers(people["customer"]))
    assert viewed.status_code == 200
    assert viewed.headers["content-type"].startswith("image/jpeg")
    assert viewed.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------------------
# Refusals — attacks and malformed input
# ---------------------------------------------------------------------------

def test_a_renamed_text_file_is_refused(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "id_proof",
                       b"just plain text pretending to be a pdf" * 20,
                       filename="aadhaar.pdf", content_type="application/pdf")
    assert response.status_code == 422, response.text


def test_an_svg_is_refused(client, people, app_id):
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
    response = _upload(client, people["customer"], app_id, "id_proof", svg,
                       filename="image.jpg", content_type="image/jpeg")
    assert response.status_code == 422, response.text


def test_a_jpeg_with_a_zip_appended_is_rebuilt_clean(client, people, app_id):
    raw = _jpeg_bytes() + b"PK\x03\x04" + b"hidden zip data" * 50
    response = _upload(client, people["customer"], app_id, "id_proof", raw)
    assert response.status_code == 201, response.text
    file_id = response.json()["file_id"]
    viewed = client.get(f"/api/v1/files/{file_id}", headers=_headers(people["customer"]))
    assert b"PK\x03\x04" not in viewed.content


def test_a_pdf_with_javascript_is_refused(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "bank_statement", _pdf_with_js_bytes(),
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 422, response.text


def test_a_password_protected_pdf_is_refused(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "bank_statement", _encrypted_pdf_bytes(),
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 422, response.text


def test_too_many_pages_is_refused(client, people, app_id):
    pages = [_photo_like(400, 400, seed=i) for i in range(6)]
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
    # employment_letter's cap is 5 pages
    response = _upload(client, people["customer"], app_id, "employment_letter", buf.getvalue(),
                       filename="letter.pdf", content_type="application/pdf")
    assert response.status_code == 422, response.text


def test_over_5mb_is_refused(client, people, app_id):
    big = b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024)
    response = _upload(client, people["customer"], app_id, "id_proof", big)
    assert response.status_code == 422, response.text


def test_an_empty_file_is_refused(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "id_proof", b"")
    assert response.status_code == 422, response.text


def test_a_blank_photo_is_refused(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "id_proof", _blank_jpeg_bytes())
    assert response.status_code == 422, response.text


def test_a_photograph_smaller_than_the_standard_is_refused(client, people, app_id):
    buf = io.BytesIO()
    _photo_like(50, 50).save(buf, format="JPEG", quality=95)
    response = _upload(client, people["customer"], app_id, "photograph", buf.getvalue())
    assert response.status_code == 422, response.text


def test_a_path_trick_display_name_is_refused(client, people, app_id):
    """Same rule as the trainer's own name-only route: a folder separator in
    the name is refused outright, not silently stripped."""
    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes(),
                       filename="../../etc/passwd.jpg")
    assert response.status_code == 422, response.text


def test_a_line_break_display_name_is_refused(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes(),
                       filename="aadhaar\n.jpg")
    assert response.status_code == 422, response.text


def test_consent_is_required(client, people, app_id):
    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes(), consent=False)
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Classification: local watermark check, gated Gemini confirmation
# ---------------------------------------------------------------------------

def test_a_specimen_pdf_confirmed_by_gemini_lands_in_the_safe_folder(client, people, app_id, monkeypatch):
    monkeypatch.setattr("app.services.file_service._gemini_confirms_specimen", lambda text, phrase: True)
    specimen = _minimal_pdf_with_text("SPECIMEN DOCUMENT FOR TESTING ONLY")

    response = _upload(client, people["customer"], app_id, "bank_statement", specimen,
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["nature"] == "test"

    db = TestingSessionLocal()
    stored = db.query(StoredFile).filter(StoredFile.id == body["file_id"]).first()
    assert stored.storage_zone.value == "safe"
    db.close()

    from app.config import settings
    safe_files = list(Path(settings.upload_dir_safe).glob("*"))
    assert len(safe_files) == 1


def test_a_specimen_pdf_gemini_does_not_confirm_stays_undeclared(client, people, app_id, monkeypatch):
    monkeypatch.setattr("app.services.file_service._gemini_confirms_specimen", lambda text, phrase: False)
    specimen = _minimal_pdf_with_text("SPECIMEN DOCUMENT FOR TESTING ONLY")

    response = _upload(client, people["customer"], app_id, "bank_statement", specimen,
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 201, response.text
    assert response.json()["nature"] == "undeclared"


def test_a_gemini_failure_fails_safe(client, people, app_id, monkeypatch):
    """
    A real Gemini failure (a timeout, a rate limit, the API itself being
    down) happens inside the call `_gemini_confirms_specimen` makes, not by
    that function vanishing — so the patch has to sit one level lower than
    the function itself, or it only proves the wrapper's own try/except was
    skipped, not that it works.
    """
    import llm_provider
    monkeypatch.setattr(llm_provider, "get_llm", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("quota exhausted")))
    specimen = _minimal_pdf_with_text("SPECIMEN DOCUMENT FOR TESTING ONLY")

    response = _upload(client, people["customer"], app_id, "bank_statement", specimen,
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 201, response.text   # the upload itself still succeeds
    assert response.json()["nature"] == "undeclared"


def test_an_unexpected_break_in_classification_still_fails_safe(client, people, app_id, monkeypatch):
    """
    The second, outer safety net in classify_nature itself — for a failure
    `_gemini_confirms_specimen`'s own handling didn't anticipate. An upload
    must never 500 just because classification broke.
    """
    def _boom(text, phrase):
        raise RuntimeError("something classify_nature's own try/except has to catch")
    monkeypatch.setattr("app.services.file_service._gemini_confirms_specimen", _boom)
    specimen = _minimal_pdf_with_text("SPECIMEN DOCUMENT FOR TESTING ONLY")

    response = _upload(client, people["customer"], app_id, "bank_statement", specimen,
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 201, response.text
    assert response.json()["nature"] == "undeclared"


def test_ordinary_text_never_calls_gemini(client, people, app_id, monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.file_service._gemini_confirms_specimen",
                        lambda text, phrase: calls.append(1) or True)
    ordinary = _minimal_pdf_with_text("Statement of Account for the month")

    response = _upload(client, people["customer"], app_id, "bank_statement", ordinary,
                       filename="statement.pdf", content_type="application/pdf")
    assert response.status_code == 201, response.text
    assert response.json()["nature"] == "undeclared"
    assert calls == []


def test_an_image_can_never_be_classified_test_in_this_piece(client, people, app_id):
    """No OCR yet — Piece 34's job. An image always falls to undeclared/sensitive."""
    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    assert response.status_code == 201, response.text
    assert response.json()["nature"] == "undeclared"


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def test_another_customer_cannot_view(client, people, app_id):
    uploaded = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    file_id = uploaded.json()["file_id"]

    refused = client.get(f"/api/v1/files/{file_id}", headers=_headers(people["other_customer"]))
    assert refused.status_code == 403


def test_another_customer_cannot_upload_to_someone_elses_application(client, people, app_id):
    response = _upload(client, people["other_customer"], app_id, "id_proof", _jpeg_bytes())
    assert response.status_code == 403


def test_staff_and_admin_can_view_but_admin_cannot_upload(client, people, app_id):
    uploaded = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    file_id = uploaded.json()["file_id"]

    assert client.get(f"/api/v1/files/{file_id}", headers=_headers(people["officer"])).status_code == 200
    assert client.get(f"/api/v1/files/{file_id}", headers=_headers(people["admin"])).status_code == 200
    assert _upload(client, people["admin"], app_id, "id_proof", _jpeg_bytes()).status_code == 403


def test_staff_view_is_logged_the_owners_own_view_is_not(client, people, app_id):
    from app.models.activity_log import ActivityLog

    uploaded = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    file_id = uploaded.json()["file_id"]

    client.get(f"/api/v1/files/{file_id}", headers=_headers(people["customer"]))
    client.get(f"/api/v1/files/{file_id}", headers=_headers(people["officer"]))

    db = TestingSessionLocal()
    views = db.query(ActivityLog).filter(ActivityLog.action == "document_viewed").all()
    db.close()
    assert len(views) == 1
    assert views[0].actor_id == "officer@test.com"


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------

def _plant_stored_files(db, applicant_id, uploaded_by, count, size_bytes=1000):
    """Insert rows directly rather than run the real pipeline `count` times —
    this is testing the rate-limit query, not the pipeline again."""
    import uuid
    from datetime import datetime, timezone
    for _ in range(count):
        db.add(StoredFile(
            applicant_id=applicant_id, stored_name=f"{uuid.uuid4()}.jpg",
            display_name="x.jpg", content_type="image/jpeg",
            size_bytes=size_bytes, original_size_bytes=size_bytes,
            sha256="0" * 64, nature="undeclared", storage_zone="sensitive",
            consent_at=datetime.now(timezone.utc), uploaded_by=uploaded_by,
        ))
    db.commit()


def test_too_many_uploads_in_an_hour_is_refused(client, people, app_id, db_session):
    me = client.get("/api/v1/applicants/me", headers=_headers(people["customer"])).json()
    _plant_stored_files(db_session, me["id"], "priya.upload@test.com", 30)

    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    assert response.status_code == 422, response.text
    assert "last hour" in response.json()["detail"]


def test_the_total_storage_cap_is_refused(client, people, app_id, db_session):
    me = client.get("/api/v1/applicants/me", headers=_headers(people["customer"])).json()
    _plant_stored_files(db_session, me["id"], "priya.upload@test.com", 1, size_bytes=101 * 1024 * 1024)

    response = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    assert response.status_code == 422, response.text
    assert "total limit" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Documents to check
# ---------------------------------------------------------------------------

def test_documents_to_check_lists_unverified_across_applications(client, people, app_id):
    _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())

    response = client.get("/api/v1/documents/unverified", headers=_headers(people["officer"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] >= 1

    doc_id = body["items"][0]["id"]
    application_id = body["items"][0]["application_id"]
    verified = client.patch(f"/api/v1/applications/{application_id}/documents/{doc_id}/verify",
                            headers=_headers(people["officer"]))
    assert verified.status_code == 200, verified.text

    after = client.get("/api/v1/documents/unverified", headers=_headers(people["officer"])).json()
    assert doc_id not in [i["id"] for i in after["items"]]


def test_admin_can_view_the_queue_but_it_is_view_only(client, people, app_id):
    assert client.get("/api/v1/documents/unverified",
                      headers=_headers(people["admin"])).status_code == 200
    assert client.get("/api/v1/documents/unverified",
                      headers=_headers(people["customer"])).status_code == 403


# ---------------------------------------------------------------------------
# The database keeps nature and storage_zone fixed
# ---------------------------------------------------------------------------

def test_nature_cannot_be_changed_through_sql(client, people, app_id, db_session):
    uploaded = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    file_id = uploaded.json()["file_id"]

    stored = db_session.query(StoredFile).filter(StoredFile.id == file_id).first()
    stored.nature = "test"
    with pytest.raises(DatabaseError):
        db_session.commit()
    db_session.rollback()


def test_storage_zone_cannot_be_changed_through_sql(client, people, app_id, db_session):
    uploaded = _upload(client, people["customer"], app_id, "id_proof", _jpeg_bytes())
    file_id = uploaded.json()["file_id"]

    stored = db_session.query(StoredFile).filter(StoredFile.id == file_id).first()
    stored.storage_zone = "safe"
    with pytest.raises(DatabaseError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# The pipeline stages, unit-level (no HTTP, fast)
# ---------------------------------------------------------------------------

def test_read_capped_refuses_oversize():
    from app.services.errors import RuleViolation
    with pytest.raises(RuleViolation):
        file_service.read_capped(b"0" * (6 * 1024 * 1024))


def test_detect_type_refuses_unrecognised_bytes():
    from app.services.errors import RuleViolation
    with pytest.raises(RuleViolation):
        file_service.detect_type(b"not a real file at all, just some text")


def test_check_allowed_for_refuses_wrong_type_for_document():
    from app.services.errors import RuleViolation
    with pytest.raises(RuleViolation):
        file_service.check_allowed_for("bank_statement", "image/jpeg")   # PDF only
