// Display helpers.

// Indian grouping: ₹25,00,000 not ₹2,500,000. The browser's built-in
// formatter knows the en-IN rules, so this is one line.
const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
export function rupees(amount) {
  if (amount === null || amount === undefined || amount === "") return "";
  return inr.format(Number(amount));
}

export function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// A whole number for things counted in whole units. The server sends
// `days_waiting` and `years_with_employer` as floats, so the browser was
// printing "3.0 days" and "3.0 years" on the Morning Briefing and on My
// Profile. Nobody says "three point zero days", and the tenth of a day the
// decimal carries is not something anyone acts on.
export function whole(value) {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  return Number.isFinite(n) ? String(Math.round(n)) : String(value);
}

// "3 minutes ago", for the notification panel (Piece 30). A bell is read at a
// glance, and "22 Sep 2026, 11:58 pm" makes you work out how long ago that was.
// The browser's own formatter knows the wording for every language it supports.
const relative = new Intl.RelativeTimeFormat("en-IN", { numeric: "auto" });
const STEPS = [
  ["second", 60],
  ["minute", 60],
  ["hour", 24],
  ["day", 7],
  ["week", 4.35],
  ["month", 12],
  ["year", Infinity],
];

export function timeAgo(value) {
  if (!value) return "";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "";

  let amount = (then - Date.now()) / 1000;   // negative for the past
  for (const [unit, size] of STEPS) {
    if (Math.abs(amount) < size) return relative.format(Math.round(amount), unit);
    amount /= size;
  }
  return "";
}

// Words that are not simply capitalised when an underscore is removed.
// "id_proof" became "Id proof", which reads as a name rather than as the
// initials it actually is. Keyed by the lower-case word so the lookup does
// not depend on where in the string it appears.
const WORD_FIXES = {
  id: "ID",
  kyc: "KYC",
  emi: "EMI",
  cibil: "CIBIL",
  pan: "PAN",
  ai: "AI",
  nri: "NRI",
};

// "under_review" -> "Under review", "id_proof" -> "ID proof"
export function label(value) {
  if (!value) return "";
  const words = String(value).replace(/_/g, " ").split(" ");
  const fixed = words.map((word, i) => {
    const known = WORD_FIXES[word.toLowerCase()];
    if (known) return known;
    // Only the first word is capitalised: this is a sentence-style label,
    // not a title, so "Under review" rather than "Under Review".
    return i === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word;
  });
  return fixed.join(" ");
}
