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
