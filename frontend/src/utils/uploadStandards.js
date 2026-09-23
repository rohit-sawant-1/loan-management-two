// What each document type accepts, mirroring `rules.UPLOAD_STANDARDS` on the
// server (Piece 31). Used only for a quick, friendly check before the file
// ever leaves the browser — the server runs the real pipeline and is the
// only check that actually matters. Nothing here decides pixels, page
// counts or the rebuilt size; those are the server's job entirely.

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB, every type

const MIME_LABELS = { "application/pdf": "PDF", "image/jpeg": "JPG", "image/png": "PNG" };

export const UPLOAD_ACCEPTED = {
  photograph: ["image/jpeg", "image/png"],
  signature: ["image/jpeg", "image/png"],
  id_proof: ["application/pdf", "image/jpeg", "image/png"],
  income_proof: ["application/pdf", "image/jpeg", "image/png"],
  bank_statement: ["application/pdf"],
  property_docs: ["application/pdf", "image/jpeg", "image/png"],
  employment_letter: ["application/pdf", "image/jpeg", "image/png"],
  vehicle_quotation: ["application/pdf", "image/jpeg", "image/png"],
};

// For the file input's own `accept` attribute — the browser's file picker
// filtering, not a security check.
const EXTENSIONS = { "application/pdf": ".pdf", "image/jpeg": ".jpg,.jpeg", "image/png": ".png" };

export function acceptAttrFor(docType) {
  return (UPLOAD_ACCEPTED[docType] || []).map((t) => EXTENSIONS[t]).join(",");
}

export function acceptedLabelsFor(docType) {
  return (UPLOAD_ACCEPTED[docType] || []).map((t) => MIME_LABELS[t]).join(", ");
}

/** A quick client-side check before sending. The server checks the file's
    real bytes regardless — this only saves a doomed round trip. */
export function checkUpload(docType, file) {
  if (!file) return "Choose a file";
  if (file.size > MAX_UPLOAD_BYTES) return "The file is larger than the 5 MB limit";
  const accepted = UPLOAD_ACCEPTED[docType] || [];
  if (accepted.length && !accepted.includes(file.type)) {
    return `This document type accepts ${acceptedLabelsFor(docType)} only`;
  }
  return "";
}
