// What this loan type needs, what has been uploaded, and what is still missing.
// Staff can mark a document as verified; anyone who may see the application can
// add one, except the administrator, who can only look (Piece 27).
// Piece 32d: an unverified document can be replaced by a newer copy. Staff and
// the admin also see the earlier copies that were replaced; a customer doesn't.
// Piece 33: a real file of a type with kinds (ID proof, income proof, bank
// statement) says which document it is, and its details are typed in. It only
// ticks its box once they're confirmed.

import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useSettings } from "../settings/useSettings";
import DocumentReviewForm from "./DocumentReviewForm";
import ErrorBanner from "./ErrorBanner";
import TestBadge from "./TestBadge";
import ViewOnly from "./ViewOnly";
import Button from "./ui/Button";
import Icon from "./ui/Icon";
import Modal from "./ui/Modal";
import { DOCUMENT_TYPES, checkFileName } from "../utils/validation";
import { acceptAttrFor, checkUpload } from "../utils/uploadStandards";
import { kindsForType } from "../utils/documentKinds";
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

// Piece 33: "Which one?" under a type that has more than one kind (ID proof:
// Aadhaar or PAN). A type with exactly one kind picks it without asking, and a
// type with none shows nothing.
function KindPicker({ docType, kind, setKind }) {
  const kinds = kindsForType(docType);
  if (kinds.length < 2) return null;
  return (
    <label>
      Which one?
      <select value={kind} onChange={(e) => setKind(e.target.value)}>
        {kinds.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
      </select>
    </label>
  );
}

function firstKind(docType) {
  return kindsForType(docType)[0]?.key || "";
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
function RealUploadForm({ applicationId, onChange, onUploaded, setError }) {
  const [docType, setDocType] = useState("id_proof");
  const [kind, setKind] = useState(firstKind("id_proof"));
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
      if (kind) body.append("kind", kind);
      // No explicit Content-Type here: axios sets multipart/form-data with
      // the correct boundary itself when it sees a FormData body. Setting
      // it by hand would strip the boundary and break the upload.
      const res = await api.post(`/applications/${applicationId}/documents/upload`, body);
      setFile(null);
      setConsent(false);
      onChange?.();
      // Straight on to its details, while the document is in front of them.
      if (res.data.extraction_id) onUploaded?.(res.data);
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
          <select value={docType} onChange={(e) => {
            setDocType(e.target.value); setKind(firstKind(e.target.value)); setFile(null);
          }}>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t} value={t}>{label(t)}</option>
            ))}
          </select>
        </label>
        <KindPicker docType={docType} kind={kind} setKind={setKind} />
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

// Piece 32d: the pop-up behind a row's Replace button. Same controls as the
// add form for whichever mode the switch is in, minus the type: a replacement
// always keeps the type of the document it replaces.
function ReplaceModal({ applicationId, doc, realUploads, onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState("");
  const [consent, setConsent] = useState(false);
  const [kind, setKind] = useState(firstKind(doc.doc_type));
  const [fieldError, setFieldError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function replace() {
    const problem = realUploads ? checkUpload(doc.doc_type, file) : checkFileName(fileName);
    if (problem) { setFieldError(problem); return; }
    if (realUploads && !consent) { setFieldError("You must agree before a document can be stored"); return; }
    setFieldError("");
    setBusy(true);
    setError("");
    try {
      const base = `/applications/${applicationId}/documents/${doc.id}/replace`;
      if (realUploads) {
        const body = new FormData();
        body.append("consent", "true");
        body.append("file", file);
        if (kind) body.append("kind", kind);
        const res = await api.post(`${base}/upload`, body);
        onDone(res.data);
      } else {
        await api.post(base, { file_name: fileName.trim() });
        onDone(null);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={() => { if (!busy) onClose(); }}
      title={`Replace ${label(doc.doc_type)}`}
      subtitle={doc.file_name}
      footer={
        <>
          <Button type="button" onClick={onClose} disabled={busy}>Go back</Button>
          <Button type="button" variant="primary" icon="refresh" loading={busy} onClick={replace}>
            Replace
          </Button>
        </>
      }
    >
      <ErrorBanner message={error} onClose={() => setError("")} />
      <p>The new copy takes this one's place and is checked again by staff.</p>
      {realUploads ? (
        <>
          <KindPicker docType={doc.doc_type} kind={kind} setKind={setKind} />
          <label>
            New file
            <input
              type="file"
              accept={acceptAttrFor(doc.doc_type)}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
          <label className="check" style={{ marginTop: "0.5rem" }}>
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>I agree this document is stored by the bank and checked by staff</span>
          </label>
        </>
      ) : (
        <label>
          New file name
          <input value={fileName} onChange={(e) => setFileName(e.target.value)} placeholder="aadhaar.pdf" />
        </label>
      )}
      {fieldError && <span className="field-error">{fieldError}</span>}
    </Modal>
  );
}

export default function DocumentChecklist({ applicationId, data, onChange }) {
  const { isStaff, isAdmin } = useAuth();
  // Piece 28: the admin's switch. OFF is exactly the form Phase 1 has
  // always had; ON is the real upload form Piece 31 builds.
  const { realUploads } = useSettings();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [replacing, setReplacing] = useState(null);   // the document being replaced, or null
  const [reviewing, setReviewing] = useState(null);   // the document whose details are open, or null

  const {
    items = [], required = [], missing = [], test_count: testCount = 0, replaced = [],
  } = data || {};

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

      <h3 style={{ margin: "1rem 0 0.5rem" }}>
        Uploaded
        {items.length > 0 && (
          <span className="muted" style={{ fontWeight: 400, fontSize: "0.85rem", marginLeft: "0.5rem" }}>
            {/* Count required types covered, not files: two ID proofs are still one type. */}
            {required.length - missing.length}/{required.length} submitted
            {testCount > 0 && `, including ${testCount} TEST document${testCount === 1 ? "" : "s"}`}
          </span>
        )}
      </h3>
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
                  <td>
                    {label(d.doc_type)}{" "}
                    {d.nature === "test" && <TestBadge />}{" "}
                    {d.needs_details && <span className="pill pill-warn">needs details</span>}
                    {d.detail_summary && (
                      <div className="muted mono" style={{ fontSize: "0.8rem" }}>{d.detail_summary}</div>
                    )}
                  </td>
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
                        <Button
                          size="sm" variant="ok" icon="check" disabled={busy}
                          onClick={() => verify(d.id)}
                          title={d.nature === "test"
                            ? "Checked for the demo, not for authenticity"
                            : undefined}
                        >
                          {d.nature === "test" ? "Verify (test document)" : "Mark verified"}
                        </Button>
                      )}
                      {d.needs_details && !isAdmin && (
                        <Button size="sm" variant="primary" icon="file" onClick={() => setReviewing(d)}>
                          Fill in details
                        </Button>
                      )}
                      {d.extraction_id && (!d.needs_details || isAdmin) && (
                        <Button size="sm" icon="file" onClick={() => setReviewing(d)}>
                          View details
                        </Button>
                      )}
                      {!isAdmin && !d.verified && (
                        <Button size="sm" icon="refresh" disabled={busy} onClick={() => setReplacing(d)}>
                          Replace
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

      {/* The server only sends these to staff and the admin. */}
      {replaced.length > 0 && (
        <details style={{ marginTop: "0.75rem" }}>
          <summary className="muted" style={{ cursor: "pointer" }}>
            Replaced copies ({replaced.length})
          </summary>
          <div className="table-wrap" style={{ marginTop: "0.5rem" }}>
            <table>
              <thead>
                <tr><th>Type</th><th>File</th><th>Uploaded</th><th>Replaced</th><th /></tr>
              </thead>
              <tbody>
                {replaced.map((d) => (
                  <tr key={d.id} className="muted">
                    <td>{label(d.doc_type)}{" "}{d.nature === "test" && <TestBadge />}</td>
                    <td>{d.file_name}</td>
                    <td>{formatDate(d.uploaded_at)}</td>
                    <td>{formatDate(d.replaced_at)}</td>
                    <td>
                      {d.file_id && (
                        <Button size="sm" icon="file" onClick={() => viewFile(d.file_id, setError)}>
                          View
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {replacing && (
        <ReplaceModal
          applicationId={applicationId}
          doc={replacing}
          realUploads={realUploads}
          onClose={() => setReplacing(null)}
          onDone={(newDoc) => {
            setReplacing(null);
            onChange?.();
            // A replacement with a kind goes straight on to its details.
            if (newDoc?.extraction_id) setReviewing(newDoc);
          }}
        />
      )}

      {reviewing && (
        <DocumentReviewForm
          applicationId={applicationId}
          doc={reviewing}
          canEdit={!isAdmin}
          onClose={() => setReviewing(null)}
          onChanged={onChange}
        />
      )}

      <hr className="divider" />

      {isAdmin ? (
        <ViewOnly>View only. The administrator can't add documents.</ViewOnly>
      ) : realUploads ? (
        <RealUploadForm applicationId={applicationId} onChange={onChange} onUploaded={setReviewing}
          setError={setError} />
      ) : (
        <NameOnlyForm applicationId={applicationId} onChange={onChange} setError={setError} />
      )}
    </div>
  );
}
