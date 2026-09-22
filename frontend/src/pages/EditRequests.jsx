// Piece 25: the staff queue of edit requests. Loan officers and the manager.
//
// Customers ask to change an application from its own page. Their requests
// land here, oldest waiting first, so whoever has waited longest is on top.
// Staff approve (a note is optional) or refuse (a note is required, because
// the customer is owed a reason and sees it on their page).
//
// The decision pop-up has a text box, so its onClose is wrapped in
// useCallback. Without that, every keystroke would pull the cursor out of the
// box (T-103).

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import Modal from "../components/ui/Modal";
import { NOTE_MAX, NOTE_MIN, REQUEST_STATUS, checkText, fieldList } from "../utils/editRequests";
import { formatDateTime, label } from "../utils/format";

// The filter chips. "" means every status.
const FILTERS = [
  { value: "pending", text: "Waiting" },
  { value: "approved", text: "Approved" },
  { value: "refused", text: "Refused" },
  { value: "completed", text: "Edit saved" },
  { value: "closed", text: "Closed" },
  { value: "", text: "All" },
];

const EMPTY_TEXT = {
  pending: "Nothing is waiting. When a customer asks to change an application, it appears here.",
  "": "No customer has asked to change an application yet.",
};

export default function EditRequests() {
  const [filter, setFilter] = useState("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  // The decision pop-up: which request, approve or refuse, and the note.
  const [deciding, setDeciding] = useState(null);   // { request, approve }
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState("");
  const [busy, setBusy] = useState(false);
  const limit = 20;

  const load = useCallback(() => {
    setLoading(true);
    const params = { page, limit };
    if (filter) params.status = filter;
    api.get("/edit-requests", { params })
      .then((r) => { setData(r.data); setError(""); })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [filter, page]);

  useEffect(() => { load(); }, [load]);

  function choose(value) {
    setPage(1);
    setFilter(value);
  }

  function startDeciding(request, approve) {
    setDeciding({ request, approve });
    setNote("");
    setNoteError("");
    setNotice("");
  }

  const closeModal = useCallback(() => {
    if (busy) return;
    setDeciding(null);
  }, [busy]);

  async function decide() {
    const { request, approve } = deciding;
    // A refusal must say why; an approval's note is optional but still capped.
    const problem = approve
      ? (note.trim().length > NOTE_MAX ? `Up to ${NOTE_MAX} characters` : "")
      : checkText(note, NOTE_MIN, NOTE_MAX);
    setNoteError(problem);
    if (problem) return;

    setBusy(true);
    setError("");
    try {
      const action = approve ? "approve" : "refuse";
      await api.post(`/edit-requests/${request.id}/${action}`, { note: note.trim() || null });
      setNotice(approve
        ? `Approved. ${request.applicant_name || "The customer"} can now change the ${fieldList(request.fields)} on application ${request.application_id}.`
        : `Refused. ${request.applicant_name || "The customer"} will see your reason on application ${request.application_id}.`);
      setDeciding(null);
      load();
    } catch (err) {
      setError(errorMessage(err));
      setDeciding(null);
      load();
    } finally {
      setBusy(false);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total_count / limit)) : 1;
  const approving = deciding?.approve;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Edit requests</h1>
          <p className="sub">
            Customers asking to change an application after submitting it. Nothing changes until you approve.
          </p>
        </div>
      </div>

      <div className="toolbar">
        <div className="chips" role="group" aria-label="Show requests that are">
          {FILTERS.map((f) => (
            <button
              key={f.value || "all"} type="button"
              className={`chip${filter === f.value ? " chip-on" : ""}`}
              onClick={() => choose(f.value)}
            >
              {f.text}
            </button>
          ))}
        </div>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />
      {notice && (
        <div className="banner banner-ok">
          <Icon name="check" size={16} />
          <span>{notice}</span>
        </div>
      )}

      {loading && !data ? (
        <Spinner text="Loading edit requests…" />
      ) : (
        <>
          <div className="table-wrap">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 160 }}>Asked</th>
                    <th>Application</th>
                    <th>Wants to change</th>
                    <th>Reason</th>
                    <th>Request</th>
                    <th style={{ width: 190 }} />
                  </tr>
                </thead>
                <tbody>
                  {data?.items?.length ? data.items.map((r) => {
                    const state = REQUEST_STATUS[r.status] || { text: label(r.status), pill: "pill" };
                    return (
                      <tr key={r.id}>
                        <td>{formatDateTime(r.created_at)}</td>
                        <td>
                          <Link to={`/applications/${r.application_id}`}>Application {r.application_id}</Link>
                          <div className="muted" style={{ fontSize: "0.78rem" }}>
                            {r.applicant_name || r.requested_by}
                            {r.loan_type ? ` · ${label(r.loan_type)}` : ""}
                          </div>
                          {r.application_status && (
                            <div style={{ marginTop: "0.25rem" }}><StatusBadge status={r.application_status} /></div>
                          )}
                        </td>
                        <td>{label(fieldList(r.fields))}</td>
                        <td style={{ maxWidth: 320 }}>
                          <div className="quote" style={{ margin: 0 }}>{r.reason}</div>
                          {r.decision_note && (
                            <div className="muted" style={{ fontSize: "0.78rem", marginTop: "0.35rem" }}>
                              {r.status === "closed" ? "" : "Staff note: "}{r.decision_note}
                              {r.decided_by && r.status !== "closed" ? ` (${r.decided_by})` : ""}
                            </div>
                          )}
                        </td>
                        <td><span className={state.pill}>{state.text}</span></td>
                        <td>
                          {r.status === "pending" && (
                            <div className="row" style={{ gap: "0.4rem" }}>
                              <Button size="sm" variant="ok" icon="check" onClick={() => startDeciding(r, true)}>
                                Approve
                              </Button>
                              <Button size="sm" variant="danger" icon="close" onClick={() => startDeciding(r, false)}>
                                Refuse
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  }) : (
                    <tr>
                      <td colSpan={6}>
                        <EmptyState icon="inbox" title="No edit requests here">
                          {EMPTY_TEXT[filter] ?? "Nothing matches this filter."}
                        </EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {data?.items?.length > 0 && (
            <div className="pager">
              <span className="spacer">{data.total_count} request{data.total_count === 1 ? "" : "s"}</span>
              <Button size="sm" icon="chevronLeft" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <span>Page {page} of {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}

      <Modal
        open={Boolean(deciding)}
        onClose={closeModal}
        title={approving ? "Approve this edit request?" : "Refuse this edit request?"}
        subtitle={deciding ? `Application ${deciding.request.application_id} · ${deciding.request.applicant_name || deciding.request.requested_by}` : ""}
        tone={approving ? "default" : "danger"}
        size="sm"
        footer={
          <>
            <Button type="button" onClick={closeModal} disabled={busy}>Go back</Button>
            <Button type="button" variant={approving ? "ok" : "danger"} loading={busy} onClick={decide}>
              {approving ? "Yes, approve" : "Yes, refuse"}
            </Button>
          </>
        }
      >
        {deciding && (
          <>
            <dl className="kv">
              <dt>Wants to change</dt><dd>{label(fieldList(deciding.request.fields))}</dd>
              <dt>Their reason</dt><dd className="quote">{deciding.request.reason}</dd>
            </dl>
            <p className="muted">
              {approving
                ? "The customer will be able to change these details once. Eligibility is checked again automatically when they save."
                : "The customer will see your reason on their application page."}
            </p>
            <label>
              {approving ? "Note to the customer (optional)" : "Why are you refusing? (the customer sees this)"}
              <textarea
                rows={3} maxLength={NOTE_MAX} value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={approving ? "Optional" : "For example: your payslips support the original amount."}
              />
              {noteError
                ? <span className="field-error">{noteError}</span>
                : <span className="hint">
                    {approving ? `Up to ${NOTE_MAX} characters` : `${note.trim().length} of ${NOTE_MIN} to ${NOTE_MAX} characters`}
                  </span>}
            </label>
          </>
        )}
      </Modal>
    </>
  );
}
