"""
The demo kit (Piece 34): four SPECIMEN documents for the ADH demo, so the
demo never needs anyone's real document.

    venv\\Scripts\\python.exe scripts\\make_specimen_docs.py

Writes four PDFs to backend/demo_documents/:
    specimen_aadhaar.pdf        upload as ID proof → Aadhaar card
    specimen_pan.pdf            upload as ID proof → PAN card
    specimen_salary_slip.pdf    upload as Income proof
    specimen_bank_statement.pdf upload as Bank statement

Every detail matches Priya Sharma from seed.py (the same name, date of birth
and income), so the details form fills in without any "doesn't match the
profile" notes. Each page says SPECIMEN across the top, so the upload
pipeline classifies it as a TEST document.

Each PDF has a real text layer, which is what Piece 34 reads. The Aadhaar
number is fake but has a valid Verhoeff check digit, so it passes the check;
and because it's in the text layer, the upload can find it and black out its
first 8 digits on the stored copy. There is no QR code: a real Aadhaar's
signed QR can't be faked, and pretending otherwise would be dishonest.

The PDFs are built by hand (a PDF is just text in a fixed structure), the
same way the upload tests build theirs, so no PDF library is needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `app` imports

from app.domain.validators import verhoeff_check_digit  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "demo_documents"
BANNER = "SPECIMEN - NOT A REAL DOCUMENT"

AADHAAR_BASE = "57934610872"                     # made up
AADHAAR = AADHAAR_BASE + verhoeff_check_digit(AADHAAR_BASE)
AADHAAR_SPACED = f"{AADHAAR[:4]} {AADHAAR[4:8]} {AADHAAR[8:]}"

DOCUMENTS = {
    "specimen_aadhaar.pdf": [
        (22, BANNER),
        (14, "Government of India"),
        (14, "Unique Identification Authority of India"),
        (13, "Name: Priya Sharma"),
        (13, "DOB: 15/03/1994"),
        (13, "FEMALE"),
        (13, f"Aadhaar No: {AADHAAR_SPACED}"),
        (12, "Address: 12 Demo Street, Andheri East, Mumbai 400069"),
        (10, "This specimen was made for testing a loan system. It is not an Aadhaar card."),
    ],
    "specimen_pan.pdf": [
        (22, BANNER),
        (14, "INCOME TAX DEPARTMENT - GOVT. OF INDIA"),
        (14, "Permanent Account Number Card"),
        (13, "Name: PRIYA SHARMA"),
        (13, "Father's Name: RAJESH SHARMA"),
        (13, "Date of Birth: 15/03/1994"),
        (13, "PAN: ABCPS1234K"),
        (10, "This specimen was made for testing a loan system. It is not a PAN card."),
    ],
    "specimen_salary_slip.pdf": [
        (22, BANNER),
        (16, "Salary Slip"),
        (13, "Employer: Demo Technologies Pvt Ltd"),
        (13, "Employee Name: Priya Sharma"),
        (13, "Pay Period: August 2026"),
        (13, "Earnings: Basic 30,000.00  HRA 12,000.00  Allowances 8,000.00"),
        (13, "Gross Pay: Rs. 50,000.00"),
        (13, "Deductions: PF 3,600.00  Tax 2,900.00"),
        (13, "Net Pay: Rs. 43,500.00"),
        (10, "This specimen was made for testing a loan system. It is not a real payslip."),
    ],
    "specimen_bank_statement.pdf": [
        (22, BANNER),
        (16, "Statement of Account"),
        (13, "Bank Name: Demo Bank of India"),
        (13, "Account Holder: Priya Sharma"),
        (13, "Account Number: 50100234567890"),
        (13, "IFSC: DEMO0001234"),
        (13, "Statement Period: 01/03/2026 to 31/08/2026"),
        (13, "Opening Balance: Rs. 1,12,400.00"),
        (13, "Closing Balance: Rs. 1,58,900.00"),
        (10, "This specimen was made for testing a loan system. It is not a real statement."),
    ],
}


def _escape(text: str) -> str:
    """Brackets and backslashes have a meaning inside a PDF string, so they're escaped."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(lines: list[tuple[int, str]]) -> bytes:
    """One A4 page: each line in Helvetica, top to bottom, inside a border."""
    ops, y = [], 790
    for size, text in lines:
        ops.append(f"BT /F1 {size} Tf 40 {y} Td ({_escape(text)}) Tj ET")
        y -= int(size * 2.2)
    ops.append("3 w 20 20 555 802 re S")          # a border, so no page looks blank
    content = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 595 842] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return pdf


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, lines in DOCUMENTS.items():
        (OUT / name).write_bytes(build_pdf(lines))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
