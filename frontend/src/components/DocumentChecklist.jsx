// What this loan type needs, what has been uploaded, and what is still missing.
// Staff can mark a document as verified; anyone who may see the application can
// add one, except the administrator, who can only look (Piece 27).

import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ErrorBanner from "./ErrorBanner";
import ViewOnly from "./ViewOnly";
import Button from "./ui/Button";
import Icon from "./ui/Icon";
import { DOCUMENT_TYPES, checkFileName } from "../utils/validation";
import { formatDate, label } from "../utils/format";

export default function DocumentChecklist({ applicationId, data, onChange }) {
  const { isStaff, isAdmin } = useAuth();
  const [docType, setDocType] = useState("id_proof");
  const [fileName, setFileName] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { items = [], required = [], missing = [] } = data || {};

  async function addDocument(e) {
    e.preventDefault();
    const problem = checkFileName(fileName);
    setFieldError(problem);
    if (problem) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/applications/${applicationId}/documents`, { doc_type: docType, file_name: fileName.trim() });
      setFileName("");
      onChange?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function verify(docId) {
    setBusy(true);
    setError("");
    try {
      await api.patch(`/applications/${applicationId}/documents/${docId}/verify`);
      onChange?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <ErrorBanner message={error} onClose={() => setError("")} />

      <h3 style={{ margin: "0 0 0.5rem" }}>Required for this loan</h3>
      <ul className="checklist">
        {required.map((t) => {
          // The server works out what is still missing; trust its answer rather
          // than recomputing the same thing from the uploaded list.
          const have = !missing.includes(t);
          return (
            <li key={t}>
              <Icon name={have ? "check" : "close"} size={15} className={have ? "tick" : "cross"} />
              <span>{label(t)}</span>
              {!have && <span className="pill pill-warn">still needed</span>}
            </li>
          );
        })}
      </ul>

      <h3 style={{ margin: "1rem 0 0.5rem" }}>Uploaded</h3>
      {items.length === 0 ? (
        <p className="muted">Nothing uploaded yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Type</th><th>File</th><th>Uploaded</th><th>Verified</th>{isStaff && <th />}
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>{label(d.doc_type)}</td>
                  <td>{d.file_name}</td>
                  <td>{formatDate(d.uploaded_at)}</td>
                  <td>
                    {d.verified
                      ? <span className="pill pill-ok">Verified</span>
                      : <span className="muted">not yet</span>}
                  </td>
                  {isStaff && (
                    <td>
                      {!d.verified && (
                        <Button size="sm" variant="ok" icon="check" disabled={busy} onClick={() => verify(d.id)}>
                          Mark verified
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <hr className="divider" />

      {isAdmin ? (
        <ViewOnly>View only. The administrator can't add documents.</ViewOnly>
      ) : (
        <form onSubmit={addDocument} noValidate>
          <div className="toolbar" style={{ marginBottom: "0.35rem" }}>
            <label>
              Document type
              <select value={docType} onChange={(e) => setDocType(e.target.value)}>
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t} value={t}>{label(t)}</option>
                ))}
              </select>
            </label>
            <label className="grow">
              File name
              <input value={fileName} onChange={(e) => setFileName(e.target.value)} placeholder="aadhaar.pdf" />
            </label>
            <Button type="submit" variant="primary" icon="plus" loading={busy}>Add</Button>
          </div>
          {fieldError && <span className="field-error">{fieldError}</span>}
          <span className="hint">Phase 1 records the file name only. PDF, JPG or PNG.</span>
        </form>
      )}
    </div>
  );
}
