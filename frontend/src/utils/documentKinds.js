// Document kinds (Piece 33): which document a file is, inside its type.
// A copy of backend/app/domain/document_kinds.py, used only to build the
// "Which one?" dropdown. The fields themselves always come from the server,
// so this list only needs each kind's key, type and label.

export const DOCUMENT_KINDS = [
  { key: "aadhaar", docType: "id_proof", label: "Aadhaar card" },
  { key: "pan", docType: "id_proof", label: "PAN card" },
  { key: "salary_slip", docType: "income_proof", label: "Salary slip" },
  { key: "bank_statement", docType: "bank_statement", label: "Bank statement" },
];

// The kinds inside one document type, in the order above. Empty for a type
// that has none yet (property documents, say), which then works as before.
export function kindsForType(docType) {
  return DOCUMENT_KINDS.filter((k) => k.docType === docType);
}

// Piece 35: a first guess at a file's type and kind from its name, for the
// several-at-once form. Only a guess: every row's dropdowns can be changed.
// Whole words only, so "pan" matches "pan_card.pdf" but not "company.pdf".
const NAME_HINTS = [
  { words: ["aadhaar", "aadhar", "uid", "uidai"], docType: "id_proof", kind: "aadhaar" },
  { words: ["pan"], docType: "id_proof", kind: "pan" },
  { words: ["payslip", "salary", "slip", "payroll"], docType: "income_proof", kind: "salary_slip" },
  { words: ["statement", "bank", "passbook"], docType: "bank_statement", kind: "bank_statement" },
  { words: ["property", "deed", "noc"], docType: "property_docs" },
  { words: ["employment", "appointment", "offer", "experience"], docType: "employment_letter" },
  { words: ["quotation", "quote", "proforma"], docType: "vehicle_quotation" },
];

export function guessFromFileName(name) {
  const words = name.toLowerCase().replace(/\.[a-z0-9]+$/, "").split(/[^a-z0-9]+/);
  const hit = NAME_HINTS.find((h) => h.words.some((w) => words.includes(w)));
  const docType = hit ? hit.docType : "id_proof";
  return { docType, kind: hit?.kind || kindsForType(docType)[0]?.key || "" };
}

// Piece 34: a value read from the file that failed its check ("Please check")
// is sent again, as it now stands, when confirming, so the server checks it
// once more. Fixed or confirmed as right, it stops blocking.
export function recheckValues(details) {
  const values = {};
  for (const f of details.fields) {
    if (f.state === "uncertain" && f.value) values[f.key] = f.value;
  }
  return values;
}
