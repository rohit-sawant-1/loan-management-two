// The stored details of one activity event, laid out as labelled rows rather
// than dumped as a line of JSON. Used by the Activity page and by the activity
// panel on an application.

import { CONFIRMED_ACTION_NAMES, DETAIL_LABELS, parseDetails, TOOL_NAMES } from "../utils/activity";
import { FIELD_LABELS } from "../utils/editRequests";
import { label, rupees, whole } from "../utils/format";

function DetailValue({ name, value }) {
  if (value === null || value === undefined || value === "") return <span className="muted">not recorded</span>;
  if (typeof value === "boolean") return value ? <span className="tick">Yes</span> : <span className="cross">No</span>;
  if (name === "amount" || name === "amount_requested") return rupees(value);
  if (name === "tenure_months") return `${value} months`;
  // A risk score is a float out of 100, and "70.0/100" reads like a
  // measurement precise to a tenth when it is nothing of the sort. It also
  // needs its scale said out loud here: this panel is the one place the
  // number appears with no sentence around it to explain it.
  if (name === "risk_score") return `${whole(value)} out of 100`;
  if (name === "days_waiting") return `${whole(value)} days`;
  if (name === "from" || name === "to") return label(value);
  if (name === "doc_type" || name === "loan_type") return label(value);
  // The assistant's tools are stored under their function names, which mean
  // nothing to whoever is reading an audit trail. "Changed an application's
  // status" is the same fact in words a manager already uses.
  if (name === "tool") return CONFIRMED_ACTION_NAMES[value] || TOOL_NAMES[value] || label(value);
  if ((name === "tools" || name === "agents_run") && Array.isArray(value)) {
    return value.length
      ? value.map((t) => TOOL_NAMES[t] || label(t)).join(", ")
      : <span className="muted">none needed</span>;
  }
  // Piece 25: the fields a customer asked to change, in words.
  if (name === "fields" && Array.isArray(value)) {
    return value.map((f) => FIELD_LABELS[f] || label(f)).join(", ");
  }
  // A whole stored eligibility assessment keeps its line breaks, and so does
  // the chatbot answer excerpt in the audit trail (a review answer is several lines).
  if (name === "previous_eligibility_summary" || name === "answer") {
    return <pre className="eligibility-summary" style={{ margin: 0 }}>{value}</pre>;
  }
  if (Array.isArray(value)) {
    return value.length ? value.join("; ") : <span className="muted">none</span>;
  }
  return String(value);
}

export default function ActivityDetails({ raw }) {
  const parsed = parseDetails(raw);
  if (!parsed) return <p className="muted">Nothing further was recorded for this event.</p>;

  // A nested object — the assistant stores what it passed to a tool this way —
  // used to print as "[object Object]", which is JavaScript admitting it gave
  // up rather than anything a person could read. Flattening it one level turns
  // it into ordinary labelled rows, because the values inside are already the
  // plain things a manager wants: which application, which status, what reason.
  //
  // Piece 25 stores an edit as two groups, `before` and `after`. Flattened
  // plainly those would print "Amount" twice with no way to tell which is
  // which, so rows from those two groups say so: "Amount (before)".
  const rows = [];
  for (const [key, value] of Object.entries(parsed)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const suffix = key === "before" || key === "after" ? ` (${key})` : "";
      for (const [innerKey, innerValue] of Object.entries(value)) {
        rows.push([innerKey, innerValue, suffix]);
      }
    } else {
      rows.push([key, value, ""]);
    }
  }

  return (
    <dl className="kv">
      {rows.map(([key, value, suffix], i) => (
        <div key={`${key}-${i}`} style={{ display: "contents" }}>
          <dt>{DETAIL_LABELS[key] || label(key)}{suffix}</dt>
          <dd><DetailValue name={key} value={value} /></dd>
        </div>
      ))}
    </dl>
  );
}
