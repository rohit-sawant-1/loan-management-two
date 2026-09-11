// The stored details of one activity event, laid out as labelled rows rather
// than dumped as a line of JSON. Used by the Activity page and by the activity
// panel on an application.

import { DETAIL_LABELS, parseDetails, TOOL_NAMES } from "../utils/activity";
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
  if (name === "tool") return TOOL_NAMES[value] || label(value);
  if ((name === "tools" || name === "agents_run") && Array.isArray(value)) {
    return value.length
      ? value.map((t) => TOOL_NAMES[t] || label(t)).join(", ")
      : <span className="muted">none needed</span>;
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
  const rows = [];
  for (const [key, value] of Object.entries(parsed)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [innerKey, innerValue] of Object.entries(value)) {
        rows.push([innerKey, innerValue]);
      }
    } else {
      rows.push([key, value]);
    }
  }

  return (
    <dl className="kv">
      {rows.map(([key, value], i) => (
        <div key={`${key}-${i}`} style={{ display: "contents" }}>
          <dt>{DETAIL_LABELS[key] || label(key)}</dt>
          <dd><DetailValue name={key} value={value} /></dd>
        </div>
      ))}
    </dl>
  );
}
