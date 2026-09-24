"""
Reading a document's details out of the document itself (Piece 34, lean).

Only a PDF's own text layer is read: the text that's already inside the file,
with each character's position. No OCR, no AI, no new libraries. A photo or a
scan has no text layer, so its fields are left for the person to type.

This runs inside the upload pipeline, before the rebuild (see
`file_service.process_upload`), because the rebuild redraws every page as a
picture and the text is gone after that.

Three jobs:
  1. read     — find each field of the declared kind with plain rules, and
                run it through Piece 33's validators. Nothing is invented: a
                value that isn't there stays missing.
  2. identify — score which kind the text looks like, so a mismatch with
                the declared kind can be shown. It is never switched.
  3. locate   — find every Aadhaar number on each page and the boxes of its
                first 8 digits, so the rebuild can black them out (T-114).

The full Aadhaar number exists only in memory here. It leaves this module
already masked, and only its positions go on to the rebuild.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import pypdfium2 as pdfium
import structlog

from app.domain import document_kinds, validators
from app.services.pdfium_lock import PDFIUM_LOCK

logger = structlog.get_logger()

# A text-layer value that passed its check. The text is exact, but the rule
# that picked it out of the page could still have picked the wrong line.
TEXT_LAYER_CONFIDENCE = 0.95
# Found, but it failed its check: the person must look at it.
UNCERTAIN_CONFIDENCE = 0.6


# ---------------------------------------------------------------------------
# What a reading produces
# ---------------------------------------------------------------------------

@dataclass
class FieldReading:
    value: str | None          # already cleaned, and masked where the registry says
    state: str                 # extracted / uncertain / missing
    confidence: float | None = None
    note: str | None = None


@dataclass
class DocumentReading:
    kind: str
    fields: dict[str, FieldReading]
    read_automatically: bool                 # was there any text to read at all?
    detected_kind: str | None = None
    detection_score: float | None = None
    # Aadhaar only: "redacted", "already_masked" or "not_found".
    aadhaar_status: str | None = None
    # Page index → boxes to black out, in PDF points (left, bottom, right, top).
    redactions: dict[int, list[tuple[float, float, float, float]]] = field(default_factory=dict)


@dataclass
class PageText:
    text: str                  # the page's characters, one per position
    boxes: list[tuple]         # one (left, bottom, right, top) per character


# ---------------------------------------------------------------------------
# Text with positions
# ---------------------------------------------------------------------------

def pages_with_positions(raw: bytes) -> list[PageText]:
    """
    Every page's text, one character at a time, so each character's index
    in `text` is also its index in `boxes`. Reading character by character
    is slower than one call per page, but a document page has a few hundred
    characters and this keeps the positions exactly right. Never raises: an
    unreadable PDF simply has no text.
    """
    pages: list[PageText] = []
    try:
        # PDFium isn't thread-safe: only one call at a time (see pdfium_lock.py).
        with PDFIUM_LOCK:
            pdf = pdfium.PdfDocument(raw)
            try:
                for page in pdf:
                    textpage = page.get_textpage()
                    chars, boxes = [], []
                    for i in range(textpage.count_chars()):
                        chars.append(textpage.get_text_range(index=i, count=1)[:1] or " ")
                        boxes.append(textpage.get_charbox(i))
                    pages.append(PageText(text="".join(chars), boxes=boxes))
                    textpage.close()
                    page.close()
            finally:
                pdf.close()
    except Exception as e:                                             # noqa: BLE001
        logger.warning("text_positions_failed", error=str(e))
        return []
    return pages


# ---------------------------------------------------------------------------
# Small helpers for finding values in text
# ---------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# 12 digits, optionally in groups of 4, never starting with 0 or 1.
AADHAAR_PATTERN = re.compile(r"(?<!\d)[2-9]\d{3}[  ]?\d{4}[  ]?\d{4}(?!\d)")
MASKED_AADHAAR_PATTERN = re.compile(r"[Xx*]{4}[  ]?[Xx*]{4}[  ]?\d{4}")
PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def _lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]


def _labelled(lines: list[str], labels: str) -> str | None:
    """
    The value after a label: "Name: Priya Sharma" on one line, or "Name" on
    one line and the value on the next. `labels` is a regex alternation,
    longest first, so "Employee Name" wins over "Name".
    """
    for i, line in enumerate(lines):
        # (?![A-Za-z]) stops "Name" from matching the start of "Nameplate".
        m = re.match(rf"^(?:{labels})(?![A-Za-z])\s*[:\-]?\s*(.*)$", line, re.IGNORECASE)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest:
            return rest
        if i + 1 < len(lines):
            return lines[i + 1]
    return None


def _to_iso_date(value: str | None) -> str | None:
    """dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd or "12 May 1992" → yyyy-mm-dd. None if it isn't a date."""
    if not value:
        return None
    value = value.strip()
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", value)
    try:
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\s+(\d{4})", value)
        if m and m.group(2).lower() in _MONTHS:
            return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    except ValueError:
        return value            # looked like a date but isn't one: let the check say so
    return value


def _to_month(value: str | None) -> str | None:
    """"August 2026", "Aug-2026", "08/2026" or "2026-08" → "2026-08"."""
    if not value:
        return None
    m = re.search(r"([A-Za-z]{3})[A-Za-z]*[\s\-,]+(\d{4})", value)
    if m and m.group(1).lower() in _MONTHS:
        return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"(\d{1,2})[/\-](\d{4})", value)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{4})-(\d{2})", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return value


def _money(value: str | None) -> str | None:
    """"₹ 52,000.00" or "Rs. 52,000" → "52,000.00" (the check strips the commas)."""
    if not value:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d{1,2})?", value)
    return m.group(0) if m else value


# ---------------------------------------------------------------------------
# One reader per kind: text in, raw values out (not yet checked)
# ---------------------------------------------------------------------------

def _read_aadhaar(text: str, lines: list[str]) -> dict[str, str | None]:
    dob_line = _labelled(lines, r"DOB|Date of Birth|Year of Birth")
    name = _labelled(lines, r"Name")
    if name is None:
        # A real card has no "Name" label: the name is the line above the DOB.
        for i, line in enumerate(lines):
            if re.search(r"\b(DOB|Date of Birth)\b", line, re.IGNORECASE) and i > 0:
                name = lines[i - 1]
                break
    gender = re.search(r"\b(FEMALE|MALE|TRANSGENDER)\b", text, re.IGNORECASE)
    number = AADHAAR_PATTERN.search(text)
    return {
        "name": name,
        "date_of_birth": _to_iso_date(dob_line),
        "gender": gender.group(1) if gender else None,
        "aadhaar_number": number.group(0) if number else None,
        "address": _labelled(lines, r"Address"),
    }


def _read_pan(text: str, lines: list[str]) -> dict[str, str | None]:
    pan = PAN_PATTERN.search(text)
    return {
        "name": _labelled(lines, r"Name"),
        # PDFs often turn a typed ' into a curly ’, so both are accepted.
        "fathers_name": _labelled(lines, r"Father['’]?s Name|Father Name"),
        "date_of_birth": _to_iso_date(_labelled(lines, r"Date of Birth|DOB")),
        "pan_number": pan.group(0) if pan else None,
    }


def _read_salary_slip(text: str, lines: list[str]) -> dict[str, str | None]:
    return {
        "employer": _labelled(lines, r"Employer|Company Name|Company"),
        "employee_name": _labelled(lines, r"Employee Name|Name of Employee|Name"),
        "pay_month": _to_month(_labelled(lines, r"Pay Period|Pay Month|Salary Month|Month")),
        "gross_pay": _money(_labelled(lines, r"Gross Pay|Gross Earnings|Gross Salary|Gross")),
        "net_pay": _money(_labelled(lines, r"Net Pay|Net Salary|Take Home|Net Amount")),
    }


def _read_bank_statement(text: str, lines: list[str]) -> dict[str, str | None]:
    period = _labelled(lines, r"Statement Period|Period")
    start = end = None
    if period:
        dates = re.findall(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}", period)
        if len(dates) >= 2:
            start, end = _to_iso_date(dates[0]), _to_iso_date(dates[1])
    bank = _labelled(lines, r"Bank Name|Bank")
    if bank is None:
        bank = next((line for line in lines if re.search(r"\bBank\b", line) and len(line) <= 60), None)
    account = _labelled(lines, r"Account Number|Account No\.?|A/c No\.?")
    return {
        "account_holder": _labelled(lines, r"Account Holder|Account Name|Customer Name|Name"),
        "bank_name": bank,
        "account_number": re.sub(r"[^\d]", "", account) if account else None,
        "period_from": start or _to_iso_date(_labelled(lines, r"From")),
        "period_to": end or _to_iso_date(_labelled(lines, r"To")),
    }


_READERS = {
    "aadhaar": _read_aadhaar,
    "pan": _read_pan,
    "salary_slip": _read_salary_slip,
    "bank_statement": _read_bank_statement,
}


# ---------------------------------------------------------------------------
# Identification: which kind does the text look like?
# ---------------------------------------------------------------------------

_KEYWORDS = {
    "aadhaar": ("unique identification authority", "aadhaar", "enrolment", "vid"),
    "pan": ("income tax department", "permanent account number", "pan"),
    "salary_slip": ("salary slip", "payslip", "pay slip", "net pay", "earnings", "deductions"),
    "bank_statement": ("statement of account", "account statement", "opening balance",
                       "closing balance", "ifsc"),
}


def identify(text: str) -> tuple[str | None, float | None]:
    """The kind the text most looks like, and how strongly (0 to 1). Identification, never authenticity."""
    lowered = text.lower()
    scores = {}
    for kind, words in _KEYWORDS.items():
        hits = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", lowered))
        # A number in the right shape is strong evidence on its own.
        if kind == "aadhaar" and (AADHAAR_PATTERN.search(text) or MASKED_AADHAAR_PATTERN.search(text)):
            hits += 1
        if kind == "pan" and PAN_PATTERN.search(text):
            hits += 1
        scores[kind] = hits / (len(words) + (1 if kind in ("aadhaar", "pan") else 0))
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return None, None
    return best, round(scores[best], 2)


# ---------------------------------------------------------------------------
# Locating Aadhaar numbers, for blacking out
# ---------------------------------------------------------------------------

def aadhaar_redactions(pages: list[PageText], checksum_only: bool = False) -> dict[int, list[tuple]]:
    """
    Every Aadhaar-shaped number on every page, and the boxes of its first 8
    digits. For a declared Aadhaar, all of them, not just the one that passed
    the checksum: a card can show the number twice, and a wrong-checksum
    number is still someone's number as far as blacking out goes.

    `checksum_only` (D-33) is for any other ID proof, where the person may
    have picked "Something else": only numbers that pass the Aadhaar check
    are blacked out, so a random 12-digit number on some other document
    isn't.
    """
    found: dict[int, list[tuple]] = {}
    for index, page in enumerate(pages):
        for match in AADHAAR_PATTERN.finditer(page.text):
            digit_positions = [i for i in range(match.start(), match.end()) if page.text[i].isdigit()]
            digits = "".join(page.text[i] for i in digit_positions)
            if checksum_only and not validators.verhoeff_valid(digits):
                continue
            found.setdefault(index, []).extend(page.boxes[i] for i in digit_positions[:8])
    return found


# ---------------------------------------------------------------------------
# The whole reading
# ---------------------------------------------------------------------------

def _check(kind: document_kinds.DocumentKind, raw: dict[str, str | None]) -> dict[str, FieldReading]:
    """Run every raw value through its field's check. Pass → extracted, fail → uncertain."""
    results: dict[str, FieldReading] = {}
    for f in kind.fields:
        value = raw.get(f.key)
        if not value or not value.strip():
            results[f.key] = FieldReading(value=None, state="missing")
            continue
        try:
            cleaned = validators.CHECKS[f.check](value)
            results[f.key] = FieldReading(value=cleaned, state="extracted",
                                          confidence=TEXT_LAYER_CONFIDENCE)
        except ValueError as e:
            if f.masked:
                # A masked field's raw value may never be stored, even as "uncertain".
                results[f.key] = FieldReading(value=None, state="missing",
                                              note=f"Something was found, but: {e}")
            else:
                results[f.key] = FieldReading(value=value.strip()[:300], state="uncertain",
                                              confidence=UNCERTAIN_CONFIDENCE, note=str(e))
    return results


def read_upload(kind_key: str, raw: bytes, content_type: str) -> DocumentReading:
    """
    Read an upload's details for its declared kind. A photo, or a PDF with no
    text layer, comes back with every field missing and `read_automatically`
    false: nothing is guessed.
    """
    kind = document_kinds.get_kind(kind_key)
    pages = pages_with_positions(raw) if content_type == "application/pdf" else []
    text = "\n".join(p.text for p in pages)
    has_text = bool(text.strip())

    raw_values = _READERS[kind.key](text, _lines(text)) if has_text else {}
    reading = DocumentReading(
        kind=kind.key,
        fields=_check(kind, raw_values),
        read_automatically=has_text,
    )
    if has_text:
        reading.detected_kind, reading.detection_score = identify(text)

    if kind.key == "aadhaar":
        reading.redactions = aadhaar_redactions(pages)
        if reading.redactions:
            reading.aadhaar_status = "redacted"
        elif MASKED_AADHAAR_PATTERN.search(text):
            reading.aadhaar_status = "already_masked"
        else:
            reading.aadhaar_status = "not_found"
    return reading
