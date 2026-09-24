"""
Every uploaded file passes through this pipeline, in this order, before it is
ever stored (Piece 31). Each stage raises `RuleViolation` with a plain
sentence the moment something is wrong; nothing later runs.

    1. read_capped        — 5 MB cap, enforced while reading
    2. detect_type         — the real type, read from the bytes, not the name
    3. check_allowed_for   — is this type accepted for this kind of document?
    4. scan_pdf_markers    — refuse anything a PDF can use to run code or reach out
    5. classify_nature     — is this confidently demo material, on the ORIGINAL bytes
    5b. read (Piece 34)    — only when the uploader said which kind it is: read its
                             details from the PDF's own text, and find the Aadhaar
                             digits to black out. Also on the ORIGINAL bytes.
    6. rebuild_image/_pdf  — re-encode from scratch (CDR): nothing hidden survives,
                             and the Aadhaar digits found in 5b are drawn over in black
    7. apply_standard      — resize, page count, blank-page check, target size
    8. encrypt_and_store   — write the final bytes, encrypted, to the right folder
    9. sha256              — a fingerprint of the original, for duplicate detection later

Stage 5 runs on the ORIGINAL bytes, before stage 6, on purpose. Stage 6
redraws every PDF page as a picture so nothing hidden can survive inside
it — which also destroys any text layer the PDF had. If classification ran
after rebuild, there would be nothing left in a specimen PDF to recognise.

Why classification doesn't simply ask Gemini: a document's realness isn't
known until this pipeline decides it, so showing an unknown document to
Gemini first is exactly what T-108 exists to prevent. See
TRAPS-AND-DECISIONS.md, "Piece 31 — two upload folders", for the full
reasoning. What actually happens: a local, non-AI check of a PDF's own text
layer for specimen wording; only when that already finds a strong match is
Gemini asked to confirm, and only the matched text is sent, never the file.
Anything short of both agreeing is `undeclared`, treated the same as `real`.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass

import filetype
import pypdf
import pypdfium2 as pdfium
import structlog
from PIL import Image, ImageDraw, ImageStat

from app.domain import rules
from app.services import document_reader, storage
from app.services.pdfium_lock import PDFIUM_LOCK
from app.services.errors import RuleViolation

logger = structlog.get_logger()

# Pillow's own decompression-bomb guard, set from the one number in rules.py.
Image.MAX_IMAGE_PIXELS = rules.MAX_IMAGE_PIXELS

# Attempted JPEG qualities, highest first, when a rebuilt image has to be
# squeezed into a target byte range. A plain search, not a formula — good
# enough for a handful of document photos, and easy to read. The high end
# matters more than it looks: a fixed target like photograph's 200×230
# pixels is small enough that only quality 95+ can produce even 20 KB, so
# stopping at 90 would refuse a perfectly good photo as "too simple."
_JPEG_QUALITIES = (100, 98, 95, 90, 80, 70, 60, 50, 40, 30, 20)


@dataclass
class ProcessedUpload:
    """Everything `document_service.add_uploaded_document` needs to store."""
    rebuilt_bytes: bytes
    content_type: str          # what the REBUILT file is: application/pdf or image/jpeg
    original_size_bytes: int
    size_bytes: int            # the rebuilt file's size
    pages: int | None          # PDFs only
    width: int | None          # images only
    height: int | None
    sha256: str                # of the ORIGINAL bytes — see classify below
    nature: str                # test / real / undeclared
    storage_zone: str          # safe / sensitive
    # Piece 34: the details read from the file, when a kind was given.
    reading: document_reader.DocumentReading | None = None


# ---------------------------------------------------------------------------
# 1. Read, capped
# ---------------------------------------------------------------------------

def read_capped(source) -> bytes:
    """
    `source` is anything with a `.read()`, or plain bytes. Reads one byte
    more than the cap, so an over-size file is caught without ever loading
    an arbitrarily large upload fully into memory first.
    """
    limit = rules.MAX_UPLOAD_BYTES
    if hasattr(source, "read"):
        data = source.read(limit + 1)
    else:
        data = bytes(source)
    if not data:
        raise RuleViolation("The file is empty")
    if len(data) > limit:
        raise RuleViolation(f"The file is larger than the {limit // (1024 * 1024)} MB limit")
    return data


# ---------------------------------------------------------------------------
# 2 & 3. What it really is, and whether that's allowed here
# ---------------------------------------------------------------------------

_RECOGNISED_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png"})


def detect_type(raw: bytes) -> str:
    """The type read from the file's own bytes. A renamed extension changes nothing."""
    kind = filetype.guess(raw)
    if kind is None or kind.mime not in _RECOGNISED_TYPES:
        raise RuleViolation(
            "This doesn't look like a real PDF, JPG or PNG file. "
            "Renaming a different kind of file doesn't change what it actually is."
        )
    return kind.mime


def check_allowed_for(doc_type: str, content_type: str) -> None:
    """Is this content type accepted for this document type specifically?"""
    standard = rules.upload_standard(doc_type)
    if content_type not in standard["accepted"]:
        allowed = ", ".join(sorted(t.split("/")[-1].upper() for t in standard["accepted"]))
        raise RuleViolation(f"This document type accepts {allowed} only")


# ---------------------------------------------------------------------------
# 4. PDF danger markers and password protection
# ---------------------------------------------------------------------------

def scan_pdf_markers(raw: bytes, content_type: str) -> None:
    """
    Refuse a PDF carrying anything that can run code, reach outside the
    file, or embed a payload of its own — checked as a plain byte search
    across the whole file, which catches these markers wherever a PDF
    generator chose to put them. Also refuses a password-protected PDF,
    which the rebuild step could not safely open anyway.
    """
    if content_type != "application/pdf":
        return
    for marker in rules.PDF_DANGER_MARKERS:
        if marker in raw:
            raise RuleViolation(
                "This PDF contains something (such as a script or an embedded file) "
                "that isn't allowed in an uploaded document"
            )
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        encrypted = reader.is_encrypted
    except Exception as e:
        raise RuleViolation("This PDF could not be opened — it may be damaged") from e
    if encrypted:
        raise RuleViolation("A password-protected PDF cannot be uploaded")


# ---------------------------------------------------------------------------
# 5. Classification: is this confidently demo material?
# ---------------------------------------------------------------------------

def _pdf_text_layer(raw: bytes) -> str:
    """
    The PDF's own, original text — empty for a scanned or image-only PDF,
    which is most real documents. Never raises: a PDF this can't read is
    just treated as having no text layer, which already means "undeclared".
    """
    try:
        # PDFium isn't thread-safe: only one call at a time (see pdfium_lock.py).
        with PDFIUM_LOCK:
            pdf = pdfium.PdfDocument(raw)
            try:
                parts = []
                for page in pdf:
                    textpage = page.get_textpage()
                    parts.append(textpage.get_text_range(0, -1))
                    textpage.close()
                    page.close()
            finally:
                pdf.close()
        return "\n".join(parts)
    except Exception as e:                                             # noqa: BLE001
        logger.warning("pdf_text_layer_failed", error=str(e))
        return ""


def _local_specimen_match(text: str) -> str | None:
    """The first watermark phrase found, or None. Case-insensitive."""
    lowered = text.lower()
    for phrase in rules.SPECIMEN_WATERMARK_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def _gemini_confirms_specimen(text: str, matched_phrase: str) -> bool:
    """
    Sent only the matched text, never the file, and only ever called after
    a local match already found one — see the module docstring for why.
    Any failure at all is a "no": this only ever narrows `test` down from
    a local match, it never widens it.
    """
    try:
        from llm_provider import get_llm
        from multi_agent.llm_text import text_of

        snippet = text.strip()[:500]
        llm = get_llm(temperature=0)
        prompt = (
            "The following text was extracted from a document that a customer "
            f"uploaded to a bank. It contains the word or phrase '{matched_phrase}'.\n\n"
            f"---\n{snippet}\n---\n\n"
            "Does this read like specimen, sample or demonstration material — the "
            "kind used for training or testing a system — rather than a genuine "
            "person's real document? Answer with exactly one word: YES or NO."
        )
        answer = text_of(llm.invoke(prompt).content).strip().upper()
        return answer.startswith("YES")
    except Exception as e:                                             # noqa: BLE001
        logger.warning("specimen_confirmation_failed", error=str(e))
        return False


def classify_nature(raw: bytes, content_type: str) -> str:
    """
    `test` only when a local match AND Gemini's confirmation both agree.
    Everything else — no local signal at all, or a local match Gemini did
    not confirm — is `undeclared`, which is treated the same as `real`
    everywhere else in the app. Nobody self-declares this; there is
    nothing in the upload request for a client to set it with.

    A whole-function safety net, separate from `_gemini_confirms_specimen`'s
    own one: classification deciding "safe" or "sensitive" must never be
    the reason an upload fails outright. If anything here breaks in a way
    its own handling didn't anticipate, the file still gets stored — just
    to the cautious folder, the same outcome as any other undecided case.
    """
    try:
        if content_type != "application/pdf":
            # Photographs, signatures, and every JPEG/PNG: no text layer
            # exists to check yet. Piece 34's OCR widens this to images.
            return "undeclared"

        text = _pdf_text_layer(raw)
        matched = _local_specimen_match(text)
        if matched is None:
            return "undeclared"
        if _gemini_confirms_specimen(text, matched):
            return "test"
        return "undeclared"
    except Exception as e:                                             # noqa: BLE001
        logger.warning("classify_nature_failed", error=str(e))
        return "undeclared"


def storage_zone_for(nature: str) -> str:
    """The one-line rule the whole design rests on: confidently-test goes
    into the git-tracked folder, everything else does not."""
    return "safe" if nature == "test" else "sensitive"


# ---------------------------------------------------------------------------
# 6. Rebuild (CDR) — re-encoded from scratch, nothing carried over
# ---------------------------------------------------------------------------

def _blank_check(img: Image.Image, what: str) -> None:
    """A rebuilt page or photo whose pixels barely vary is almost certainly blank."""
    stat = ImageStat.Stat(img.convert("L"))
    if stat.stddev[0] < rules.BLANK_PAGE_STD_DEV_THRESHOLD:
        raise RuleViolation(f"{what} looks blank")


def _encode_jpeg_within(img: Image.Image, min_bytes: int | None, max_bytes: int | None) -> bytes:
    """
    Re-encode `img` as JPEG, searching qualities (highest first) until the
    result fits the given range. `save()` here is also what strips hidden
    metadata such as GPS coordinates — Pillow does not carry EXIF over
    unless told to.

    A lower quality only ever makes the file *smaller*, never larger. So if
    the very first (highest) quality tried is already below `min_bytes`,
    no quality setting can fix that — the image itself is too simple or
    too low in detail for this document type, and that is refused rather
    than silently accepting an undersized file.
    """
    for i, quality in enumerate(_JPEG_QUALITIES):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        if max_bytes is not None and len(data) > max_bytes:
            continue
        if min_bytes is not None and len(data) < min_bytes:
            if i == 0:
                raise RuleViolation("This image doesn't have enough visual detail for this document type")
            break
        return data
    raise RuleViolation("The document could not be brought within the size this document type needs")


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale to cover the target box, then crop the centre to it exactly."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((max(1, round(src_w * scale)), max(1, round(src_h * scale))), Image.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def rebuild_image(raw: bytes, doc_type: str) -> tuple[bytes, int, int]:
    """Decode and re-encode as JPEG — a fixed size for photo/signature, a
    resized long/short side for everything else. Returns (bytes, w, h)."""
    standard = rules.upload_standard(doc_type)
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as e:
        raise RuleViolation("This image could not be opened — it may be damaged") from e
    img = img.convert("RGB")

    if standard.get("exact_pixels"):
        target_w, target_h = standard["exact_pixels"]
        if img.width < target_w or img.height < target_h:
            raise RuleViolation(
                f"This image is too small. It must be at least {target_w}×{target_h} pixels."
            )
        img = _cover_crop(img, target_w, target_h)
    else:
        long_side = standard.get("image_long_side")
        short_side = standard.get("image_short_side")
        if short_side and min(img.size) < short_side:
            raise RuleViolation(f"This image's resolution is too low (below {short_side}px on the short side)")
        if long_side and max(img.size) > long_side:
            scale = long_side / max(img.size)
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)

    _blank_check(img, "This image")
    data = _encode_jpeg_within(img, standard.get("min_bytes"), standard.get("max_bytes"))
    final = Image.open(io.BytesIO(data))
    return data, final.width, final.height


def rebuild_pdf(raw: bytes, doc_type: str, redact: dict[int, list[tuple]] | None = None) -> tuple[bytes, int]:
    """
    Redraw every page as a picture at 150 DPI and rebuild the PDF from
    those pictures — this is the step that destroys a PDF's original text
    layer, which is exactly why classification runs before it. Returns
    (bytes, page_count).

    `redact` (Piece 34): page index → character boxes in PDF points, drawn
    over in solid black on the redrawn page, before it is encoded. The
    stored copy never contains what was under them.
    """
    standard = rules.upload_standard(doc_type)
    min_pages, max_pages = standard["min_pages"], standard["max_pages"]
    per_page_cap = standard.get("max_bytes_per_pdf_page")

    scale = standard["pdf_dpi"] / 72

    # Step 1, with PDFium: draw every page as a picture. PDFium isn't
    # thread-safe, so this runs under the lock (see pdfium_lock.py), and every
    # PDFium object is closed here, inside it, rather than left for Python to
    # free later from outside the lock.
    rendered: list[tuple[Image.Image, float]] = []     # (picture, page height in points)
    with PDFIUM_LOCK:
        try:
            pdf = pdfium.PdfDocument(raw)
        except Exception as e:
            raise RuleViolation("This PDF could not be opened — it may be damaged") from e
        try:
            page_count = len(pdf)
            if page_count < min_pages:
                raise RuleViolation(f"This document needs at least {min_pages} page(s)")
            if page_count > max_pages:
                raise RuleViolation(f"This document has too many pages (the limit is {max_pages})")
            for i in range(page_count):
                page = pdf[i]
                bitmap = page.render(scale=scale)
                # convert() makes a copy, so the picture no longer needs PDFium.
                rendered.append((bitmap.to_pil().convert("RGB"), page.get_height()))
                bitmap.close()
                page.close()
        finally:
            pdf.close()

    # Step 2, plain pictures, no PDFium: black out, check, and compress.
    pages_as_images: list[Image.Image] = []
    for i, (img, page_height) in enumerate(rendered):
        _black_out(img, (redact or {}).get(i, []), scale, page_height)
        _blank_check(img, f"Page {i + 1}")
        # Compress this one page to its own cap before it goes into the PDF,
        # so a single busy page can't blow the whole file past the limit.
        data = _encode_jpeg_within(img, None, per_page_cap)
        pages_as_images.append(Image.open(io.BytesIO(data)))

    buf = io.BytesIO()
    pages_as_images[0].save(
        buf, format="PDF", save_all=True, append_images=pages_as_images[1:]
    )
    return buf.getvalue(), page_count


def _black_out(img: Image.Image, boxes: list[tuple], scale: float, page_height: float) -> None:
    """
    Draw a solid black rectangle over each character box. A PDF measures
    from the bottom-left corner in points; an image from the top-left in
    pixels, so each box is flipped and scaled. Two pixels of padding make
    sure no edge of a digit peeks out.
    """
    draw = ImageDraw.Draw(img)
    for left, bottom, right, top in boxes:
        draw.rectangle(
            [left * scale - 2, (page_height - top) * scale - 2,
             right * scale + 2, (page_height - bottom) * scale + 2],
            fill="black",
        )


# ---------------------------------------------------------------------------
# 7. Apply the standard (whole-file size, after rebuild)
# ---------------------------------------------------------------------------

def apply_standard(doc_type: str, content_type: str, rebuilt_bytes: bytes) -> bytes:
    """
    The per-image and per-page caps are already enforced by the rebuild
    step. This is the one check that only makes sense on the finished
    file: the PDF's total size, for every type except id_proof, which is
    judged per page instead (see rebuild_pdf).
    """
    if content_type != "application/pdf":
        return rebuilt_bytes
    standard = rules.upload_standard(doc_type)
    if standard.get("max_bytes_per_pdf_page"):
        return rebuilt_bytes   # already capped page by page
    max_bytes = standard.get("max_bytes")
    if max_bytes and len(rebuilt_bytes) > max_bytes:
        raise RuleViolation(
            f"This document is larger than the {max_bytes // (1024 * 1024)} MB limit even after compressing"
        )
    return rebuilt_bytes


# ---------------------------------------------------------------------------
# 8 & 9. Store, and fingerprint
# ---------------------------------------------------------------------------

def encrypt_and_store(zone: str, rebuilt_bytes: bytes, content_type: str) -> str:
    """Writes the encrypted bytes and returns the random stored name (a UUID)."""
    extension = ".pdf" if content_type == "application/pdf" else ".jpg"
    stored_name = f"{uuid.uuid4()}{extension}"
    storage.save(zone, stored_name, rebuilt_bytes)
    return stored_name


def sha256_of(raw: bytes) -> str:
    """
    Of the ORIGINAL bytes, not the rebuilt ones — this is meant to answer
    "was this exact source file uploaded before", which the rebuild step's
    re-encoding would otherwise obscure.
    """
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# The whole pipeline, in order
# ---------------------------------------------------------------------------

def read_details(kind: str, raw: bytes, content_type: str, nature: str) -> document_reader.DocumentReading:
    """
    Stage 5b (Piece 34). Reads the declared kind's details and enforces the
    Aadhaar rule: a stored Aadhaar must have its first 8 digits blacked out
    (UIDAI, T-114). If they can't be found to black out, a TEST document is
    stored with a note, and anything else is refused (Rohit, 2026-09-24).
    """
    try:
        reading = document_reader.read_upload(kind, raw, content_type)
    except Exception as e:                                             # noqa: BLE001
        # Reading must never be why an ordinary upload fails. An empty reading
        # is the cautious outcome: nothing filled in, and for an Aadhaar,
        # "not found", which the rule below then treats as it should.
        logger.warning("read_details_failed", error=str(e))
        reading = document_reader.read_upload(kind, b"", "image/jpeg")

    if kind == "aadhaar" and reading.aadhaar_status == "not_found":
        if nature != "test":
            raise RuleViolation(
                "We couldn't find the Aadhaar number on this file to black it out, and an "
                "Aadhaar can't be stored with its full number showing. Please download your "
                "masked Aadhaar from myAadhaar (UIDAI) and upload that instead."
            )
        number = reading.fields.get("aadhaar_number")
        if number is not None:
            number.note = "Not blacked out on the stored copy (TEST document)"
    return reading


def process_upload(doc_type: str, source, kind: str | None = None) -> tuple[ProcessedUpload, str]:
    """
    Runs every stage above in order and returns `(result, stored_name)`,
    ready for `document_service.add_uploaded_document` to record. Raises
    `RuleViolation` the moment any stage refuses the file; nothing after
    that stage runs, and nothing is written to disk.

    `kind` (Piece 33/34): which document this is. When given, its details
    are read (stage 5b) and returned on the result.
    """
    raw = read_capped(source)
    content_type = detect_type(raw)
    check_allowed_for(doc_type, content_type)
    scan_pdf_markers(raw, content_type)

    nature = classify_nature(raw, content_type)
    zone = storage_zone_for(nature)

    reading = read_details(kind, raw, content_type, nature) if kind else None

    if content_type == "application/pdf":
        rebuilt, pages = rebuild_pdf(raw, doc_type, redact=reading.redactions if reading else None)
        width = height = None
    else:
        rebuilt, width, height = rebuild_image(raw, doc_type)
        pages = None

    final_content_type = "application/pdf" if content_type == "application/pdf" else "image/jpeg"
    rebuilt = apply_standard(doc_type, final_content_type, rebuilt)
    stored_name = encrypt_and_store(zone, rebuilt, final_content_type)

    result = ProcessedUpload(
        rebuilt_bytes=rebuilt,
        content_type=final_content_type,
        original_size_bytes=len(raw),
        size_bytes=len(rebuilt),
        pages=pages,
        width=width,
        height=height,
        sha256=sha256_of(raw),
        nature=nature,
        storage_zone=zone,
        reading=reading,
    )
    return result, stored_name
