// The body of a document's details form: one line saying where the values
// came from, a warning if the text looks like a different kind, and the
// table of fields.
//
// Shared by the single pop-up (DocumentReviewForm, Pieces 33–34) and the
// several-at-once cards (BatchReview, Piece 35). Piece 38 reuses it in the
// chat. Moved here unchanged from DocumentReviewForm, so both look and behave
// exactly the same.
//
// A masked field (the Aadhaar number) comes back as "XXXX XXXX 1234" and is
// never sent back unless it's typed again: the full number only exists in the
// box while it's being typed.

import TestBadge from "./TestBadge";

const STATE_TEXT = {
  missing: "Missing",
  user_entered: "You entered",
  user_corrected: "You corrected",
  extracted: "Read from document",   // Piece 34
  uncertain: "Please check",         // Piece 34
};

function FieldInput({ field, value, onChange, disabled }) {
  const common = { value, disabled, onChange: (e) => onChange(e.target.value) };
  switch (field.check) {
    case "date_of_birth":
    case "past_date":
      return <input type="date" {...common} />;
    case "month":
      return <input type="month" {...common} />;
    case "money":
      return <input inputMode="decimal" placeholder="52000" {...common} />;
    case "gender":
      return (
        <select {...common}>
          <option value="">Choose…</option>
          <option>Female</option><option>Male</option><option>Transgender</option>
        </select>
      );
    case "address":
      return <textarea rows={2} maxLength={300} {...common} />;
    case "aadhaar":
      return (
        <input inputMode="numeric" maxLength={14} autoComplete="off"
          placeholder={field.value ? `${field.value}. Type again to change` : "12 digits"} {...common} />
      );
    case "pan":
      return (
        <input maxLength={10} placeholder="ABCPE1234F" style={{ textTransform: "uppercase" }} {...common} />
      );
    case "account":
      return (
        <input inputMode="numeric" maxLength={18} autoComplete="off"
          placeholder={field.value ? `${field.value}. Type again to change` : "9 to 18 digits"} {...common} />
      );
    default:
      return <input maxLength={150} {...common} />;
  }
}

// `restartHint` is what to tell someone who picked the wrong kind, since the
// pop-up and the cards offer different ways back.
export default function DetailsTable({ data, doc, editable, edits, onEdit, fieldErrors, busy, restartHint }) {
  function valueFor(field) {
    if (field.key in edits) return edits[field.key];
    return field.masked ? "" : (field.value || "");
  }

  return (
    <>
      <p className="muted" style={{ marginTop: 0 }}>
        {doc.nature === "test" && <><TestBadge />{" "}</>}
        {data.status === "confirmed"
          ? `Confirmed by ${data.confirmed_by}. The format checks passed; that doesn't prove the document is genuine.`
          : data.read_automatically
            ? "Filled in from the document's own text. Check every value against the document before confirming. Fields marked * are required."
            : "This file couldn't be read automatically (a photo or a scan). Type what the document says. Fields marked * are required."}
      </p>
      {/* Piece 34: what the text looked like, only when it disagrees. Never switched for them. */}
      {data.detected_kind && data.detected_kind !== data.kind && (
        <div className="banner banner-warn">
          <span>
            This looks like a <strong>{data.detected_label}</strong>, not a {data.kind_label}.
            {restartHint && ` If the wrong kind was picked, ${restartHint}.`}
          </span>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Field</th><th>Value</th><th>State</th></tr></thead>
          <tbody>
            {data.fields.map((f) => (
              <tr key={f.key}>
                <td>{f.label}{f.required && " *"}</td>
                <td>
                  {editable ? (
                    <FieldInput field={f} value={valueFor(f)} disabled={busy}
                      onChange={(v) => onEdit(f.key, v)} />
                  ) : (
                    <span className="mono">{f.value || "—"}</span>
                  )}
                  {fieldErrors[f.key] && <span className="field-error">{fieldErrors[f.key]}</span>}
                  {f.check_note && <span className="hint" style={{ color: "var(--warn-ink)" }}>{f.check_note}</span>}
                </td>
                <td>
                  <span className={`pill ${f.state === "missing" && f.required ? "pill-warn" : ""}`}>
                    {STATE_TEXT[f.state] || f.state}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
