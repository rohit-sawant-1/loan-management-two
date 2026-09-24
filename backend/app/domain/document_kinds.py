"""
Document kinds (Piece 33): which document a file actually is, and the
fields that document carries.

A *type* is what the trainer's tests and the checklist know about
("id_proof"). A *kind* sits inside a type ("aadhaar" and "pan" are both
id_proof), so nothing about types, the checklist or the trainer's tests has
to change for kinds to exist.

Only the demo set of four is here for now (Rohit, 2026-09-24). Adding a
kind later means adding one entry to KINDS and the same entry to
`frontend/src/utils/documentKinds.js`; `tests/ours/test_extractions.py`
checks the two lists still match.

Each field's `check` names a rule in `app/domain/validators.py`. `masked`
means the value is cut down before it is ever stored: an Aadhaar number to
its last 4 digits (UIDAI's rule, T-114), an account number likewise.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class KindField:
    key: str
    label: str
    required: bool
    check: str             # a rule name in validators.CHECKS
    masked: bool = False


@dataclass(frozen=True)
class DocumentKind:
    key: str
    doc_type: str          # one of rules.DOCUMENT_TYPES
    label: str
    fields: tuple[KindField, ...]


KINDS: dict[str, DocumentKind] = {
    "aadhaar": DocumentKind(
        key="aadhaar", doc_type="id_proof", label="Aadhaar card",
        fields=(
            KindField("name", "Name", True, "name"),
            KindField("date_of_birth", "Date of birth", True, "date_of_birth"),
            KindField("gender", "Gender", False, "gender"),
            KindField("aadhaar_number", "Aadhaar number", True, "aadhaar", masked=True),
            KindField("address", "Address", False, "address"),
        ),
    ),
    "pan": DocumentKind(
        key="pan", doc_type="id_proof", label="PAN card",
        fields=(
            KindField("name", "Name", True, "name"),
            KindField("fathers_name", "Father's name", False, "name"),
            KindField("date_of_birth", "Date of birth", True, "date_of_birth"),
            KindField("pan_number", "PAN", True, "pan"),
        ),
    ),
    "salary_slip": DocumentKind(
        key="salary_slip", doc_type="income_proof", label="Salary slip",
        fields=(
            KindField("employer", "Employer", True, "text"),
            KindField("employee_name", "Employee name", True, "name"),
            KindField("pay_month", "Pay month", True, "month"),
            KindField("gross_pay", "Gross pay (₹)", False, "money"),
            KindField("net_pay", "Net pay (₹)", True, "money"),
        ),
    ),
    "bank_statement": DocumentKind(
        key="bank_statement", doc_type="bank_statement", label="Bank statement",
        fields=(
            KindField("account_holder", "Account holder", True, "name"),
            KindField("bank_name", "Bank", False, "text"),
            KindField("account_number", "Account number", False, "account", masked=True),
            KindField("period_from", "Statement from", True, "past_date"),
            KindField("period_to", "Statement to", True, "past_date"),
        ),
    ),
}

# The one field shown next to a confirmed document in the list, so a row
# reads "Aadhaar card · XXXX XXXX 1234" rather than just "ID proof".
SUMMARY_FIELD: dict[str, str] = {
    "aadhaar": "aadhaar_number",
    "pan": "pan_number",
    "salary_slip": "pay_month",
    "bank_statement": "period_to",
}

# Field names that hold a person's name, compared with the profile's name
# (a warning only, never a block).
NAME_FIELDS: frozenset[str] = frozenset({"name", "employee_name", "account_holder"})


def kinds_for_type(doc_type: str) -> list[DocumentKind]:
    """The kinds that sit inside one document type, in the order above."""
    return [k for k in KINDS.values() if k.doc_type == doc_type]


def get_kind(key: str) -> DocumentKind | None:
    return KINDS.get(key)


def field_of(kind: DocumentKind, key: str) -> KindField | None:
    return next((f for f in kind.fields if f.key == key), None)
