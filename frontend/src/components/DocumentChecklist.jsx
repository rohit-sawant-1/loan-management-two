// What this loan type needs, what has been uploaded, and what is still missing.
// Staff can mark a document as verified; anyone who may see the application can
// add one, except the administrator, who can only look (Piece 27).

import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useSettings } from "../settings/useSettings";
import ErrorBanner from "./ErrorBanner";
import ViewOnly from "./ViewOnly";
import Button from "./ui/Button";
import Icon from "./ui/Icon";
import { DOCUMENT_TYPES, checkFileName } from "../utils/validation";
import { acceptAttrFor, checkUpload } from "../utils/uploadStandards";
import { fileSize, formatDate, label } from "../utils/format";

// Fetches a stored file as the signed-in user and opens it in a new tab —
// in memory only, never written to browser storage (Rule 13).
async function viewFile(fileId, setError) {
  try {
    const res = await api.get(`/files/${fileId}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank");
    // Give the new tab a moment to load the blob before it is released.
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (err) {
    setError(errorMessage(err));
  }
}

// The name-only form: exactly what Phase 1 has always done. Used when the
// admin's switch (Piece 28) is off.
function NameOnlyForm({ applicationId, onChange, setError }) {
  const [docType, setDocType] = useState("id_proof");
  const [fileName, setFileName] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [busy, setBusy] = useState(false);

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

  return (
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
  );
}

// The real upload form (Piece 31). Nobody is asked whether a document is
// real or a test one — the server decides that for itself, after the file
// is read (see file_service.classify_nature on the backend). The only
// question here is consent.
function RealUploadForm({ applicationId, onChange, setError }) {
  const [docType, setDocType] = useState("id_proof");
  const [file, setFile] = useState(null);
  const [consent, setConsent] = useState(false);
  const [fieldError, setFieldError] = useState("");
  const [busy, setBusy] = useState(false);

  async function upload(e) {
    e.preventDefault();
    const problem = checkUpload(docType, file);
    if (problem) { setFieldError(problem); return; }
    if (!consent) { setFieldError("You must agree before a document can be stored"); return; }
    setFieldError("");
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("doc_type", docType);
      body.append("consent", "true");
      body.append("file", file);
      // No explicit Content-Type here: axios sets multipart/form-data with
      // the correct boundary itself when it sees a FormData body. Setting
      // it by hand would strip the boundary and break the upload.
      await api.post(`/applications/${applicationId}/documents/upload`, body);
      setFile(null);
      setConsent(false);
      onChange?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={upload} noValidate>
      <div className="toolbar" style={{ marginBottom: "0.35rem" }}>
        <label>
          Document type
          <select value={docType} onChange={(e) => { setDocType(e.target.value); setFile(null); }}>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t} value={t}>{label(t)}</option>
            ))}
          </select>
        </label>
        <label className="grow">
          File
          <input
            type="file"
            accept={acceptAttrFor(docType)}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <Button type="submit" variant="primary" icon="plus" loading={busy}>Upload</Button>
      </div>
      <label className="check" style={{ marginBottom: "0.35rem" }}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>I agree this document is stored by the bank and checked by staff</span>
      </label>
      {fieldError && <span className="field-error">{fieldError}</span>}
      <span className="hint">
        PDF, JPG or PNG, up to 5 MB. This is a demonstration system — never upload a
        genuine identity document.
      </span>
    </form>
  );
}

export default function DocumentChecklist({ applicationId, data, onChange }) {
  const { isStaff, isAdmin } = useAuth();
  // Piece 28: the admin's switch. OFF is exactly the form Phase 1 has
  // always had; ON is the real upload form Piece 31 builds.
  const { realUploads } = useSettings();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { items = [], required = [], missing = [] } = data || {};

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
                <th>Type</th><th>File</th><th>Size</th><th>Uploaded</th><th>Verified</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>{label(d.doc_type)}</td>
                  <td>{d.file_name}</td>
                  <td className="mono">
                    {d.file_id
                      ? `${fileSize(d.original_size_bytes)} → ${fileSize(d.size_bytes)}`
                      : <span className="muted">—</span>}
                  </td>
                  <td>{formatDate(d.uploaded_at)}</td>
                  <td>
                    {d.verified
                      ? <span className="pill pill-ok">Verified</span>
                      : <span className="muted">not yet</span>}
                  </td>
                  <td>
                    <div className="row" style={{ gap: "0.4rem" }}>
                      {d.file_id && (
                        <Button size="sm" icon="file" onClick={() => viewFile(d.file_id, setError)}>
                          View
                        </Button>
                      )}
                      {isStaff && !d.verified && (
                        <Button size="sm" variant="ok" icon="check" disabled={busy} onClick={() => verify(d.id)}>
                          Mark verified
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <hr className="divider" />

      {isAdmin ? (
        <ViewOnly>View only. The administrator can't add documents.</ViewOnly>
      ) : realUploads ? (
        <RealUploadForm applicationId={applicationId} onChange={onChange} setError={setError} />
      ) : (
        <NameOnlyForm applicationId={applicationId} onChange={onChange} setError={setError} />
      )}
    </div>
  );
}
