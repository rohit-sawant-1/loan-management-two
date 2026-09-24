// Several documents at once (Piece 35), at most MAX_FILES_AT_ONCE, through the
// normal upload address: the same checks, reading and masking as a single
// upload. Used by the Documents card and, since Piece 37, by the Assistant's
// 📎 panel. Moved here unchanged from DocumentChecklist.jsx; the only additions
// are the two wording props and reporting every uploaded document.

import { useState } from "react";
import { api, errorMessage, MAX_FILES_AT_ONCE, UPLOAD_TIMEOUT_MS } from "../api/client";
import Button from "./ui/Button";
import { DOCUMENT_TYPES } from "../utils/validation";
import { checkUpload } from "../utils/uploadStandards";
import { firstKind, guessFromFileName, kindChoices } from "../utils/documentKinds";
import { label } from "../utils/format";

// Piece 35: several files at once, at most MAX_FILES_AT_ONCE. Each file is its
// own row with a guessed type and kind the person can change, and each goes up
// on its own request with the 2-minute upload limit. Two small "workers" take
// files off one queue, so at most 2 upload at the same time; JavaScript runs
// one thing at a time, so two workers can safely share the queue. One refusal
// never stops the others: each row shows its own result.
export default function BatchUploadForm({
  applicationId, onChange, onUploaded, onClose,
  // Piece 37: the wording is the only thing the Assistant needs different.
  heading = "Upload several at once", closeLabel = "Back to one at a time",
}) {
  const [rows, setRows] = useState([]);   // { id, file, docType, kind, status, message }
  const [consent, setConsent] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [finished, setFinished] = useState(false);

  function pick(e) {
    const files = Array.from(e.target.files || []);
    setNote(files.length > MAX_FILES_AT_ONCE
      ? `At most ${MAX_FILES_AT_ONCE} files at once, so only the first ${MAX_FILES_AT_ONCE} were kept.`
      : "");
    setFinished(false);
    setRows(files.slice(0, MAX_FILES_AT_ONCE).map((file, i) => ({
      id: i, file, ...guessFromFileName(file.name), status: "ready", message: "",
    })));
  }

  function update(id, patch) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  async function uploadAll() {
    if (!consent) { setNote("You must agree before documents can be stored"); return; }
    setNote("");

    // The screen's own checks first, per file (type and size for its document type).
    const queue = [];
    for (const row of rows) {
      const problem = checkUpload(row.docType, row.file);
      if (problem) update(row.id, { status: "refused", message: problem });
      else queue.push(row);
    }

    setBusy(true);
    const uploaded = [];
    async function worker() {
      while (queue.length > 0) {
        const row = queue.shift();
        update(row.id, { status: "uploading", message: "" });
        try {
          const body = new FormData();
          body.append("doc_type", row.docType);
          body.append("consent", "true");
          body.append("file", row.file);
          if (row.kind) body.append("kind", row.kind);
          const res = await api.post(`/applications/${applicationId}/documents/upload`, body,
            { timeout: UPLOAD_TIMEOUT_MS });
          update(row.id, { status: "done" });
          uploaded.push(res.data);
        } catch (err) {
          update(row.id, { status: "refused", message: errorMessage(err) });
        }
      }
    }
    await Promise.all([worker(), worker()]);
    setBusy(false);
    setFinished(true);
    onChange?.();
    // Every document that went up, "Something else" ones included (Piece 37
    // needs them all). The Documents card picks out the ones with details.
    if (uploaded.length > 0) onUploaded(uploaded);
  }

  const STATUS = {
    ready: ["", "Ready"], uploading: ["", "Uploading…"],
    done: ["pill-ok", "Uploaded"], refused: ["pill-warn", "Refused"],
  };

  return (
    <div>
      <h3 style={{ margin: "0 0 0.5rem" }}>{heading}</h3>
      <label>
        Files (up to {MAX_FILES_AT_ONCE})
        <input type="file" multiple disabled={busy} onChange={pick} accept=".pdf,.jpg,.jpeg,.png" />
      </label>
      {rows.length > 0 && (
        <div className="table-wrap" style={{ marginTop: "0.5rem" }}>
          <table>
            <thead><tr><th>File</th><th>Document type</th><th>Which one?</th><th>Status</th><th /></tr></thead>
            <tbody>
              {rows.map((row) => {
                const locked = busy || row.status !== "ready";
                const choices = kindChoices(row.docType);
                const [pill, text] = STATUS[row.status];
                return (
                  <tr key={row.id}>
                    <td>{row.file.name}</td>
                    <td>
                      <select value={row.docType} disabled={locked}
                        onChange={(e) => update(row.id, { docType: e.target.value, kind: firstKind(e.target.value) })}>
                        {DOCUMENT_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
                      </select>
                    </td>
                    <td>
                      {choices.length > 1 ? (
                        <select value={row.kind} disabled={locked} onChange={(e) => update(row.id, { kind: e.target.value })}>
                          {choices.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
                        </select>
                      ) : (
                        <span className="muted">{choices[0]?.label || "—"}</span>
                      )}
                    </td>
                    <td>
                      <span className={`pill ${pill}`}>{text}</span>
                      {row.message && <span className="field-error">{row.message}</span>}
                    </td>
                    <td>
                      {!locked && (
                        <Button size="sm" variant="ghost" icon="close"
                          onClick={() => setRows((prev) => prev.filter((r) => r.id !== row.id))}>
                          Remove
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <label className="check" style={{ margin: "0.5rem 0 0.35rem" }}>
        <input type="checkbox" checked={consent} disabled={busy} onChange={(e) => setConsent(e.target.checked)} />
        <span>I agree these documents are stored by the bank and checked by staff</span>
      </label>
      {note && <span className="field-error">{note}</span>}
      <div className="row" style={{ gap: "0.5rem" }}>
        {!finished && (
          <Button type="button" variant="primary" icon="plus" loading={busy} onClick={uploadAll}
            disabled={rows.length === 0}>
            Upload all
          </Button>
        )}
        <Button type="button" onClick={onClose} disabled={busy}>{finished ? "Close" : closeLabel}</Button>
      </div>
      <span className="hint">
        PDF, JPG or PNG, up to 5 MB each. This is a demonstration system — never upload a
        genuine identity document.
      </span>
    </div>
  );
}
