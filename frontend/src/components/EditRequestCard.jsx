// Piece 25: the customer's side of edit requests, on their application page.
//
// What the card shows depends on where things stand:
//   - the loan has been decided        -> "can no longer be changed"
//   - a request is waiting             -> what was asked, and that staff will look
//   - a request was approved           -> a small form with ONLY the unlocked fields
//   - nothing open                     -> a "Request an edit" button (and the
//                                         staff note, if the last one was refused)
//
// Asking is two steps in one pop-up, as Rohit specified: first "are you sure?",
// then pick the fields and say why. Asking does not unlock anything by itself;
// it only sends a request to the bank staff.
//
// The pop-up has text boxes in it, so its onClose is wrapped in useCallback.
// Modal re-runs its focus handling whenever onClose changes, and a fresh
// function on every keystroke would pull the cursor out of the box (T-103).

import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import {
  EDITABLE_FIELDS, FIELD_LABELS, REASON_MAX, REASON_MIN, REQUEST_STATUS, SUPPORT_EMAIL,
  checkText, fieldList, isEditable,
} from "../utils/editRequests";
import { formatDateTime, label } from "../utils/format";
import { checkAmount, checkPurpose, checkTenure, collect } from "../utils/validation";
import ErrorBanner from "./ErrorBanner";
import Button from "./ui/Button";
import Icon from "./ui/Icon";
import Modal from "./ui/Modal";

export default function EditRequestCard({ app, onSaved }) {
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // The two-step pop-up: null (closed), "confirm", then "form".
  const [step, setStep] = useState(null);
  const [picked, setPicked] = useState([]);
  const [reason, setReason] = useState("");
  const [askErrors, setAskErrors] = useState({});
  const [asking, setAsking] = useState(false);

  // The edit form, once staff have said yes.
  const [values, setValues] = useState({});
  const [editErrors, setEditErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const loadRequests = useCallback(async () => {
    try {
      const res = await api.get(`/applications/${app.id}/edit-requests`);
      setRequests(res.data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [app.id]);

  useEffect(() => { loadRequests(); }, [loadRequests]);

  const open = requests?.find((r) => r.status === "pending" || r.status === "approved") || null;
  const latest = requests?.length ? requests[requests.length - 1] : null;

  // Fill the edit form with today's values whenever an approval arrives.
  useEffect(() => {
    if (open?.status !== "approved") return;
    const start = {};
    for (const f of open.fields) start[f] = String(app[f] ?? "");
    setValues(start);
    setEditErrors({});
  }, [open, app]);

  const closeModal = useCallback(() => {
    if (asking) return;
    setStep(null);
  }, [asking]);

  function startAsking() {
    setPicked([]);
    setReason("");
    setAskErrors({});
    setNotice("");
    setStep("confirm");
  }

  function togglePicked(field) {
    setPicked((now) => (now.includes(field) ? now.filter((f) => f !== field) : [...now, field]));
  }

  async function sendRequest() {
    const errors = collect({
      fields: picked.length === 0 ? "Pick at least one thing to change" : "",
      reason: checkText(reason, REASON_MIN, REASON_MAX),
    });
    setAskErrors(errors);
    if (Object.keys(errors).length) return;

    setAsking(true);
    setError("");
    try {
      // Sent in the same order the form lists them, whatever order they were ticked.
      const fields = EDITABLE_FIELDS.filter((f) => picked.includes(f));
      await api.post(`/applications/${app.id}/edit-requests`, { fields, reason: reason.trim() });
      setStep(null);
      setNotice("Your request has been sent. Bank staff will review it.");
      await loadRequests();
    } catch (err) {
      setError(errorMessage(err));
      setStep(null);
    } finally {
      setAsking(false);
    }
  }

  async function saveEdit(e) {
    e.preventDefault();
    const checks = {};
    if ("amount_requested" in values) checks.amount_requested = checkAmount(values.amount_requested, app.loan_type);
    if ("tenure_months" in values) checks.tenure_months = checkTenure(values.tenure_months, app.loan_type);
    if ("purpose" in values) checks.purpose = checkPurpose(values.purpose);
    const errors = collect(checks);
    setEditErrors(errors);
    if (Object.keys(errors).length) return;

    // Numbers go as numbers; purpose is trimmed, as the server would.
    const body = {};
    if ("amount_requested" in values) body.amount_requested = Number(values.amount_requested);
    if ("tenure_months" in values) body.tenure_months = Number(values.tenure_months);
    if ("purpose" in values) body.purpose = values.purpose.trim();

    setSaving(true);
    setError("");
    try {
      await api.patch(`/applications/${app.id}`, body);
      setNotice("Your changes are saved. Eligibility has been checked again with the new figures.");
      await loadRequests();
      await onSaved?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const status = open ? REQUEST_STATUS[open.status] : null;

  return (
    <div className="card">
      <div className="card-head">
        <h2>Changes to this application</h2>
        {status && <span className={status.pill}>{status.text}</span>}
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />
      {notice && (
        <div className="banner banner-ok">
          <Icon name="check" size={16} />
          <span>{notice}</span>
        </div>
      )}

      {requests === null ? (
        <p className="muted">Loading…</p>
      ) : !isEditable(app.status) ? (
        <p className="muted" style={{ marginTop: 0 }}>
          This application is {label(app.status).toLowerCase()} and can no longer be changed.
          Changes are only possible while it is submitted or under review.
        </p>
      ) : open?.status === "pending" ? (
        <>
          <p style={{ marginTop: 0 }}>
            You asked to change the <strong>{fieldList(open.fields)}</strong> on{" "}
            {formatDateTime(open.created_at)}. Bank staff will review your request.
          </p>
          <p className="muted quote">“{open.reason}”</p>
        </>
      ) : open?.status === "approved" ? (
        <form onSubmit={saveEdit} noValidate>
          <p style={{ marginTop: 0 }}>
            Bank staff approved your request. You can change the{" "}
            <strong>{fieldList(open.fields)}</strong> once. Other details stay as they are.
          </p>
          {open.decision_note && <p className="muted quote">“{open.decision_note}”</p>}

          {"amount_requested" in values && (
            <label>
              Amount (₹)
              <input
                type="number" min={10000} step={1000} value={values.amount_requested}
                onChange={(e) => setValues((v) => ({ ...v, amount_requested: e.target.value }))}
              />
              {editErrors.amount_requested
                ? <span className="field-error">{editErrors.amount_requested}</span>
                : <span className="hint">Currently {Number(app.amount_requested).toLocaleString("en-IN")}</span>}
            </label>
          )}
          {"tenure_months" in values && (
            <label>
              Tenure (months)
              <input
                type="number" min={1} step={1} value={values.tenure_months}
                onChange={(e) => setValues((v) => ({ ...v, tenure_months: e.target.value }))}
              />
              {editErrors.tenure_months
                ? <span className="field-error">{editErrors.tenure_months}</span>
                : <span className="hint">Currently {app.tenure_months} months</span>}
            </label>
          )}
          {"purpose" in values && (
            <label>
              Purpose
              <textarea
                rows={3} maxLength={500} value={values.purpose}
                onChange={(e) => setValues((v) => ({ ...v, purpose: e.target.value }))}
              />
              {editErrors.purpose
                ? <span className="field-error">{editErrors.purpose}</span>
                : <span className="hint">3 to 500 characters</span>}
            </label>
          )}
          <Button type="submit" variant="primary" icon="check" loading={saving}>
            Save changes
          </Button>
        </form>
      ) : (
        <>
          {latest?.status === "refused" && (
            <div className="banner banner-warn">
              <Icon name="alert" size={16} />
              <div>
                <strong>Your last request was refused.</strong>
                {latest.decision_note && <div>Reason given: {latest.decision_note}</div>}
              </div>
            </div>
          )}
          {latest?.status === "completed" && (
            <p className="muted" style={{ marginTop: 0 }}>
              Your last change was saved on {formatDateTime(latest.completed_at)}.
            </p>
          )}
          <p style={{ marginTop: 0 }}>
            Spotted a mistake? You can ask the bank to let you change the amount, tenure or purpose.
            Nothing changes until bank staff approve your request.
          </p>
          <Button type="button" icon="refresh" onClick={startAsking}>Request an edit</Button>
        </>
      )}

      <p className="support-note">
        <Icon name="info" size={15} />
        <span>
          Questions about your application? Contact{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </span>
      </p>

      {/* Step 1: are you sure? Step 2: what, and why. */}
      <Modal
        open={step !== null}
        onClose={closeModal}
        title={step === "confirm" ? "Request an edit?" : "What do you want to change?"}
        subtitle={`Application ${app.id}`}
        size="sm"
        footer={
          step === "confirm" ? (
            <>
              <Button type="button" onClick={closeModal}>No, go back</Button>
              <Button type="button" variant="primary" onClick={() => setStep("form")}>Yes, continue</Button>
            </>
          ) : (
            <>
              <Button type="button" onClick={closeModal} disabled={asking}>Cancel</Button>
              <Button type="button" variant="primary" loading={asking} onClick={sendRequest}>
                Send request
              </Button>
            </>
          )
        }
      >
        {step === "confirm" ? (
          <p>
            This sends a request to the bank staff. They will read your reason and either
            allow the change or explain why not. Your application stays exactly as it is
            until they approve.
          </p>
        ) : (
          <>
            <div className="checks">
              {EDITABLE_FIELDS.map((f) => (
                <label key={f} className="check">
                  <input type="checkbox" checked={picked.includes(f)} onChange={() => togglePicked(f)} />
                  <span>{FIELD_LABELS[f]}</span>
                </label>
              ))}
              {askErrors.fields && <span className="field-error">{askErrors.fields}</span>}
            </div>
            <label>
              What is wrong, and why do you need to change it?
              <textarea
                rows={4} maxLength={REASON_MAX} value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="For example: I typed 20,00,000 instead of 2,00,000 for the amount."
              />
              {askErrors.reason
                ? <span className="field-error">{askErrors.reason}</span>
                : <span className="hint">{reason.trim().length} of {REASON_MIN} to {REASON_MAX} characters</span>}
            </label>
          </>
        )}
      </Modal>
    </div>
  );
}
