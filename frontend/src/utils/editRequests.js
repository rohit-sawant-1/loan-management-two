// Piece 25: everything the screens need to know about edit requests.
//
// Mirrors the "Editing an application" section at the bottom of
// backend/app/domain/rules.py, the same way utils/validation.js mirrors the
// loan limits. The server still decides; these only let the screen explain
// things before a round trip.

// Only while nobody has decided on the loan yet.
export const EDITABLE_STATUSES = ["submitted", "under_review"];

// What a customer may ask to change, in the order the form shows them.
export const EDITABLE_FIELDS = ["amount_requested", "tenure_months", "purpose"];

export const FIELD_LABELS = {
  amount_requested: "Amount",
  tenure_months: "Tenure",
  purpose: "Purpose",
};

export const REASON_MIN = 10;
export const REASON_MAX = 1000;
export const NOTE_MIN = 10;
export const NOTE_MAX = 1000;

// A placeholder until the bank has a real address. The user manual quotes the
// same address so the chatbot gives it too; change both together (T-104).
export const SUPPORT_EMAIL = "support@bank.com";

// How each request status reads on screen, and the pill colour it gets.
export const REQUEST_STATUS = {
  pending: { text: "Waiting for bank staff", pill: "pill pill-warn" },
  approved: { text: "Approved, ready to edit", pill: "pill pill-ok" },
  refused: { text: "Refused", pill: "pill" },
  completed: { text: "Edit saved", pill: "pill pill-ok" },
  closed: { text: "Closed", pill: "pill" },
};

export function isEditable(status) {
  return EDITABLE_STATUSES.includes(status);
}

// ["amount_requested", "purpose"] -> "amount and purpose"
export function fieldList(fields) {
  const words = (fields || []).map((f) => (FIELD_LABELS[f] || f).toLowerCase());
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

// The same trim-then-count rule the server applies (clean_free_text).
export function checkText(value, min, max) {
  const t = (value || "").trim();
  if (t.length < min || t.length > max) return `${min} to ${max} characters`;
  return "";
}
