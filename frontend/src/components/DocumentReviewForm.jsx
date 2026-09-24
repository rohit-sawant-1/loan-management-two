// A document's details (Piece 33): the pop-up where the uploader types in
// what the document says, field by field, then confirms. Only then does the
// document tick its box in the checklist.
//
// The fields, their labels and which are required all come from the server
// (backend/app/domain/document_kinds.py), so this form never has its own
// copy of them. Every check is done by the server too; its message for each
// field is shown right under that field's box.
//
// A masked field (the Aadhaar number) comes back as "XXXX XXXX 1234" and is
// never sent back unless it's typed again: the full number only exists in
// the box while it's being typed.
//
// Piece 38 reuses this inside the chat, so it only needs a document row and
// a couple of callbacks.

import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import ErrorBanner from "./ErrorBanner";
import TestBadge from "./TestBadge";
import Button from "./ui/Button";
import Modal from "./ui/Modal";
import { kindsForType } from "../utils/documentKinds";
import { label } from "../utils/format";

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

export default function DocumentReviewForm({ applicationId, doc, canEdit, onClose, onChanged }) {
  const [data, setData] = useState(null);             // the server's view of the details
  const [edits, setEdits] = useState({});             // only what was typed since the last save
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const kinds = kindsForType(doc.doc_type);
  const [kind, setKind] = useState(kinds[0]?.key || "");

  useEffect(() => {
    if (!doc.extraction_id) return;
    api.get(`/extractions/${doc.extraction_id}`)
      .then((res) => setData(res.data))
      .catch((err) => setError(errorMessage(err)));
  }, [doc.extraction_id]);

  const editable = canEdit && data?.status === "needs_input";

  function showError(err) {
    setError(errorMessage(err));
    setFieldErrors(err?.response?.data?.detail?.fields || {});
  }

  async function start() {
    setBusy(true);
    setError("");
    try {
      const res = await api.post(`/applications/${applicationId}/documents/${doc.id}/extraction`, { kind });
      setData(res.data);
      onChanged?.();
    } catch (err) {
      showError(err);
    } finally {
      setBusy(false);
    }
  }

  // Sends only what changed, plus any `extra` values. Returns false if the
  // server refused something.
  async function save(extra = {}) {
    const values = { ...extra, ...edits };
    if (Object.keys(values).length === 0) return true;
    try {
      const res = await api.patch(`/extractions/${data.id}/fields`, { values });
      setData(res.data);
      setEdits({});
      setFieldErrors({});
      setError("");
      return true;
    } catch (err) {
      showError(err);
      return false;
    }
  }

  async function saveOnly() {
    setBusy(true);
    await save();
    setBusy(false);
  }

  async function confirm() {
    setBusy(true);
    try {
      // Piece 34: a value read from the file that failed its check ("Please
      // check") is sent again as it now stands in its box, so the server
      // checks it once more. Fixed or confirmed as right, it stops blocking.
      const recheck = {};
      for (const f of data.fields) {
        if (f.state === "uncertain" && f.value) recheck[f.key] = f.value;
      }
      if (!(await save(recheck))) return;
      await api.post(`/extractions/${data.id}/confirm`);
      onChanged?.();
      onClose();
    } catch (err) {
      showError(err);
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    try {
      await api.post(`/extractions/${data.id}/discard`);
      onChanged?.();
      onClose();
    } catch (err) {
      showError(err);
    } finally {
      setBusy(false);
    }
  }

  function valueFor(field) {
    if (field.key in edits) return edits[field.key];
    return field.masked ? "" : (field.value || "");
  }

  // --- No details yet: first say which document this is ----------------------
  if (!doc.extraction_id && !data) {
    return (
      <Modal open onClose={onClose} title={`${label(doc.doc_type)} details`} subtitle={doc.file_name}
        footer={
          <>
            <Button type="button" onClick={onClose} disabled={busy}>Go back</Button>
            <Button type="button" variant="primary" loading={busy} onClick={start}
              disabled={!canEdit || !kind}>Continue</Button>
          </>
        }
      >
        <ErrorBanner message={error} onClose={() => setError("")} />
        <label>
          Which document is this?
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            {kinds.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
          </select>
        </label>
      </Modal>
    );
  }

  return (
    <Modal
      open
      size="lg"
      onClose={() => { if (!busy) onClose(); }}
      title={data ? `${data.kind_label} details` : "Details"}
      subtitle={doc.file_name}
      footer={
        editable ? (
          <>
            <Button type="button" variant="ghost" onClick={discard} disabled={busy}>
              Wrong document? Start again
            </Button>
            <Button type="button" onClick={saveOnly} disabled={busy}>Save for later</Button>
            <Button type="button" variant="primary" icon="check" loading={busy} onClick={confirm}>
              Confirm details
            </Button>
          </>
        ) : (
          <Button type="button" onClick={onClose}>Close</Button>
        )
      }
    >
      <ErrorBanner message={error} onClose={() => setError("")} />
      {!data ? (
        <p className="muted">Loading…</p>
      ) : (
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
                This looks like a <strong>{data.detected_label}</strong>, not a {data.kind_label}. If the
                wrong kind was picked, use "Wrong document? Start again".
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
                          onChange={(v) => setEdits((prev) => ({ ...prev, [f.key]: v }))} />
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
      )}
    </Modal>
  );
}
