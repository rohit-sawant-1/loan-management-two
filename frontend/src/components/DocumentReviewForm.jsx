// A document's details (Piece 33): the pop-up where the uploader types in
// what the document says, field by field, then confirms. Only then does the
// document tick its box in the checklist.
//
// The fields, their labels and which are required all come from the server
// (backend/app/domain/document_kinds.py), so this form never has its own
// copy of them. Every check is done by the server too; its message for each
// field is shown right under that field's box.
//
// The table of fields itself lives in DetailsTable.jsx (Piece 35), shared
// with the several-at-once cards. This file is the pop-up around it: loading,
// saving, confirming, and starting again.

import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import DetailsTable from "./DetailsTable";
import ErrorBanner from "./ErrorBanner";
import Button from "./ui/Button";
import Modal from "./ui/Modal";
import { kindsForType, recheckValues } from "../utils/documentKinds";
import { label } from "../utils/format";

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
      // "Please check" values are sent again so the server re-checks them.
      if (!(await save(recheckValues(data)))) return;
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
        <DetailsTable
          data={data}
          doc={doc}
          editable={editable}
          edits={edits}
          onEdit={(key, v) => setEdits((prev) => ({ ...prev, [key]: v }))}
          fieldErrors={fieldErrors}
          busy={busy}
          restartHint='use "Wrong document? Start again"'
        />
      )}
    </Modal>
  );
}
