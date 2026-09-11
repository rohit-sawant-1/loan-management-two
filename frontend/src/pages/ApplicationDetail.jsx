// User story 11: everything about one application. The timeline, the documents,
// and for staff, the update-status control. A manager also sees the activity trail.
//
// This page was still the pre-design-system version: plain buttons, no icons,
// and the manager's activity panel printed the stored details as a line of raw
// JSON into a table cell — the same complaint that was fixed on the Activity
// page but never here. Both now share one description in utils/activity.js.
//
// Two things were also genuinely wrong rather than merely plain. Rejecting or
// disbursing a loan could not be undone, and both were one careless click on a
// dropdown away, with no confirmation. And when the page failed to load — a
// customer opening someone else's application, say — it showed a red banner
// with no way back to anywhere.

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ActivityDetails from "../components/ActivityDetails";
import DocumentChecklist from "../components/DocumentChecklist";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import Timeline from "../components/Timeline";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import Modal from "../components/ui/Modal";
import { describe, summarise } from "../utils/activity";
import { formatDate, formatDateTime, label, rupees } from "../utils/format";

// Mirrors VALID_TRANSITIONS in backend/app/domain/rules.py. The server still decides.
const NEXT = {
  submitted: ["under_review"],
  under_review: ["approved", "rejected"],
  approved: ["disbursed"],
  rejected: [],
  disbursed: [],
};
const MANAGER_ONLY = new Set(["disbursed"]);

// Moves that cannot be undone. The status machine has no way back out of any of
// these, so they get a confirmation step rather than happening on one click.
const FINAL = {
  rejected: {
    title: "Reject this application?",
    body: "A rejected application cannot be reopened or moved to any other status. The applicant will see the reason you write in the remarks.",
    confirm: "Yes, reject it",
    variant: "danger",
  },
  disbursed: {
    title: "Mark this loan as paid out?",
    body: "Disbursed is the last status. It records that the money has actually left the bank, and it cannot be undone.",
    confirm: "Yes, it has been paid",
    variant: "ok",
  },
};

/** A rupee figure that stays sensible when the value was never recorded. */
function Money({ value, suffix = "" }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted">not recorded</span>;
  }
  return <>{rupees(value)}{suffix}</>;
}

export default function ApplicationDetail() {
  const { id } = useParams();
  const { isStaff, isManager } = useAuth();
  const [app, setApp] = useState(null);
  const [docs, setDocs] = useState(null);
  const [activity, setActivity] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [newStatus, setNewStatus] = useState("");
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(null);   // a status awaiting confirmation
  const [chosen, setChosen] = useState(null);           // an activity row open in the popup
  const [showEligibility, setShowEligibility] = useState(false);   // Piece 19 panel, closed by default

  const load = useCallback(async () => {
    try {
      const [a, d] = await Promise.all([
        api.get(`/applications/${id}`),
        api.get(`/applications/${id}/documents`),
      ]);
      setApp(a.data);
      setDocs(d.data);
      if (isManager) {
        const act = await api.get(`/activity/entity/application/${id}`);
        setActivity(act.data);
      }
      setError("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id, isManager]);

  useEffect(() => { load(); }, [load]);

  async function applyStatus(status) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.patch(`/applications/${id}/status`, { new_status: status, remarks: remarks || null });
      setNotice(`Status changed to ${label(status)}.`);
      setNewStatus("");
      setRemarks("");
      setConfirming(null);
      await load();
    } catch (err) {
      setError(errorMessage(err));
      setConfirming(null);
    } finally {
      setBusy(false);
    }
  }

  function submitStatus(e) {
    e.preventDefault();
    if (!newStatus) return;
    // The moves that cannot be undone ask first.
    if (FINAL[newStatus]) setConfirming(newStatus);
    else applyStatus(newStatus);
  }

  if (loading) return <Spinner text="Loading application…" />;

  // A failed load used to be a bare red banner with nowhere to go. A customer
  // opening someone else's application landed on a dead end.
  if (!app) {
    return (
      <>
        <div className="page-head">
          <Link to="/applications" className="back-link">
            <Icon name="chevronLeft" size={14} /> Back to applications
          </Link>
        </div>
        <div className="card">
          <EmptyState
            icon="alert"
            title="This application cannot be shown"
            action={<Link className="btn btn-primary" to="/applications">Back to applications</Link>}
          >
            {error || "It may have been removed, or it may belong to someone else."}
          </EmptyState>
        </div>
      </>
    );
  }

  const options = (NEXT[app.status] || []).filter((s) => isManager || !MANAGER_ONLY.has(s));
  const managerNeeded = (NEXT[app.status] || []).some((s) => MANAGER_ONLY.has(s)) && !isManager;
  const readyDocs = docs ? (docs.missing?.length ?? 0) === 0 : null;

  return (
    <>
      <div className="page-head">
        <div>
          <Link to="/applications" className="back-link">
            <Icon name="chevronLeft" size={14} /> Back to applications
          </Link>
          <h1 style={{ marginTop: "0.3rem", display: "flex", alignItems: "center", gap: "0.6rem" }}>
            Application {app.id} <StatusBadge status={app.status} />
          </h1>
          <p className="sub">
            {label(app.loan_type)} loan of {rupees(app.amount_requested)} over {app.tenure_months} months
            {app.applicant ? ` · ${app.applicant.name}` : ""}
          </p>
        </div>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />
      {notice && (
        <div className="banner banner-ok">
          <Icon name="check" size={16} />
          <span>{notice}</span>
        </div>
      )}

      <div className="detail-grid">
        <div>
          <div className="card">
            <div className="card-head"><h2>The loan</h2></div>
            <dl className="kv">
              <dt>Loan type</dt><dd>{label(app.loan_type)}</dd>
              <dt>Amount</dt><dd className="num"><Money value={app.amount_requested} /></dd>
              <dt>Tenure</dt><dd className="num">{app.tenure_months} months</dd>
              <dt>Purpose</dt><dd>{app.purpose}</dd>
              <dt>Submitted</dt><dd>{formatDateTime(app.submitted_at)}</dd>
              <dt>Last updated</dt><dd>{formatDateTime(app.updated_at)}</dd>
            </dl>
          </div>

          {app.applicant && (
            <div className="card">
              <div className="card-head"><h2>The applicant</h2></div>
              <dl className="kv">
                <dt>Name</dt><dd>{app.applicant.name}</dd>
                <dt>Email</dt><dd>{app.applicant.email}</dd>
                <dt>Phone</dt><dd>{app.applicant.phone}</dd>
                <dt>Employment</dt><dd>{label(app.applicant.employment_status)}</dd>
                <dt>Annual income</dt><dd className="num"><Money value={app.applicant.annual_income} /></dd>
                <dt>CIBIL score</dt>
                <dd className="num">{app.applicant.credit_score ?? <span className="muted">not provided</span>}</dd>
                <dt>Date of birth</dt>
                <dd>{app.applicant.date_of_birth ? formatDate(app.applicant.date_of_birth) : <span className="muted">not provided</span>}</dd>
                <dt>Existing EMIs</dt>
                <dd className="num"><Money value={app.applicant.existing_monthly_emi} suffix=" / month" /></dd>
              </dl>
            </div>
          )}

          {/* Piece 19: the server's own eligibility assessment, taken at the
              moment of submission and never changed afterwards — a permanent
              record of what the bank knew and what its rules said. */}
          {app.eligibility_summary && (
            <div className="card">
              <div className="card-head">
                <h2>Eligibility at submission</h2>
                <span className={app.eligibility_passed ? "pill pill-ok" : "pill pill-warn"}>
                  {app.eligibility_passed ? "Passed" : "Did not pass"}
                </span>
              </div>
              <p className="muted" style={{ marginTop: 0 }}>
                Assessed automatically by the server when this application was submitted
                {app.eligibility_checked_at ? `, on ${formatDateTime(app.eligibility_checked_at)}` : ""}.
                This is the bank's own record, separate from anything shown to the applicant
                while filling in the form.
              </p>
              <Button size="sm" variant="ghost" onClick={() => setShowEligibility((v) => !v)}>
                {showEligibility ? "Hide the full assessment" : "Show the full assessment"}
              </Button>
              {showEligibility && (
                <pre className="eligibility-summary">{app.eligibility_summary}</pre>
              )}
            </div>
          )}

          <div className="card">
            <div className="card-head">
              <h2>Documents</h2>
              {readyDocs !== null && (
                <span className={readyDocs ? "pill pill-ok" : "pill pill-warn"}>
                  {readyDocs ? "All required documents in" : `${docs.missing.length} still missing`}
                </span>
              )}
            </div>
            <DocumentChecklist applicationId={app.id} data={docs} onChange={load} />
          </div>

          {isManager && (
            <div className="card">
              <div className="card-head">
                <h2>Everything that happened to this application</h2>
                <span className="muted" style={{ fontSize: "0.82rem" }}>
                  {activity.length} event{activity.length === 1 ? "" : "s"}
                </span>
              </div>
              {activity.length === 0 ? (
                <p className="muted">Nothing recorded.</p>
              ) : (
                <div className="table-wrap">
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th style={{ width: 170 }}>When</th>
                          <th>Who</th>
                          <th>What happened</th>
                          <th style={{ width: 70 }} />
                        </tr>
                      </thead>
                      <tbody>
                        {activity.map((row) => {
                          const what = describe(row.action);
                          const gist = summarise(row.action, row.details);
                          return (
                            <tr key={row.id} className="row-link" onClick={() => setChosen(row)}>
                              <td>{formatDateTime(row.created_at)}</td>
                              <td>
                                <div className="row" style={{ gap: "0.4rem" }}>
                                  <span>{row.actor_id}</span>
                                  {row.actor_type === "ai" && <span className="pill pill-ai">AI</span>}
                                </div>
                                {row.actor_type === "ai" && row.on_behalf_of ? (
                                  <div className="muted" style={{ fontSize: "0.78rem" }}>for {row.on_behalf_of}</div>
                                ) : row.actor_role ? (
                                  <div className="muted" style={{ fontSize: "0.78rem" }}>{label(row.actor_role)}</div>
                                ) : null}
                              </td>
                              <td>
                                <div className="row" style={{ gap: "0.45rem" }}>
                                  <Icon name={what.icon} size={15} className="muted" />
                                  <span>{what.text}</span>
                                </div>
                                {gist && <div className="muted" style={{ fontSize: "0.78rem" }}>{gist}</div>}
                              </td>
                              <td>
                                <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setChosen(row); }}>
                                  View
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div>
          <div className="card">
            <div className="card-head"><h2>Status history</h2></div>
            <Timeline history={app.status_history} />
          </div>

          {isStaff && (
            <div className="card">
              <div className="card-head"><h2>Update status</h2></div>
              {options.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>
                  {managerNeeded
                    ? "Only a branch manager can disburse this loan."
                    : `This application is ${label(app.status).toLowerCase()} and cannot move any further.`}
                </p>
              ) : (
                <form onSubmit={submitStatus} noValidate>
                  <label>
                    Move to
                    <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                      <option value="">Choose…</option>
                      {options.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                    </select>
                    {FINAL[newStatus] && (
                      <span className="hint">This cannot be undone. You will be asked to confirm.</span>
                    )}
                  </label>
                  <label>
                    Remarks
                    <textarea
                      rows={3} maxLength={1000} value={remarks}
                      onChange={(e) => setRemarks(e.target.value)}
                      placeholder={newStatus === "rejected" ? "The reason is shown to the applicant" : "Optional"}
                    />
                    <span className="hint">Recorded against your name in the history below.</span>
                  </label>
                  <Button type="submit" variant="primary" loading={busy} disabled={!newStatus}>
                    Update status
                  </Button>
                </form>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Rejecting and disbursing cannot be undone, so they ask first. */}
      <Modal
        open={Boolean(confirming)}
        onClose={() => setConfirming(null)}
        title={confirming ? FINAL[confirming].title : ""}
        tone={confirming === "rejected" ? "danger" : "warn"}
        footer={
          <>
            <Button onClick={() => setConfirming(null)} disabled={busy}>Go back</Button>
            <Button
              variant={confirming ? FINAL[confirming].variant : "primary"}
              loading={busy}
              onClick={() => applyStatus(confirming)}
            >
              {confirming ? FINAL[confirming].confirm : ""}
            </Button>
          </>
        }
      >
        {confirming && (
          <>
            <p>{FINAL[confirming].body}</p>
            <dl className="kv">
              <dt>Application</dt><dd>{app.id} · {app.applicant?.name}</dd>
              <dt>Moving from</dt><dd><StatusBadge status={app.status} /></dd>
              <dt>Moving to</dt><dd><StatusBadge status={confirming} /></dd>
              <dt>Remarks</dt>
              <dd>{remarks ? remarks : <span className="muted">none written</span>}</dd>
            </dl>
          </>
        )}
      </Modal>

      {/* The full story of one activity event. */}
      <Modal
        open={Boolean(chosen)}
        onClose={() => setChosen(null)}
        title={chosen ? describe(chosen.action).text : ""}
        subtitle={chosen ? formatDateTime(chosen.created_at) : ""}
        footer={<Button onClick={() => setChosen(null)}>Close</Button>}
      >
        {chosen && (
          <>
            <h3>Who did it</h3>
            <dl className="kv">
              <dt>{chosen.actor_type === "ai" ? "AI assistant" : "Person"}</dt>
              <dd>
                {chosen.actor_id}
                {chosen.actor_type === "ai" && <span className="pill pill-ai" style={{ marginLeft: 6 }}>AI</span>}
              </dd>
              {chosen.actor_role && (<><dt>Role</dt><dd>{label(chosen.actor_role)}</dd></>)}
              {chosen.on_behalf_of && (<><dt>Acting for</dt><dd>{chosen.on_behalf_of}</dd></>)}
            </dl>

            <hr className="divider" />
            <h3>Details</h3>
            <ActivityDetails raw={chosen.details} />

            {chosen.request_id && (
              <>
                <hr className="divider" />
                <h3>Reference</h3>
                <dl className="kv">
                  <dt>Reference</dt><dd className="mono">{chosen.request_id}</dd>
                </dl>
                <p className="hint">
                  Give this to a developer and they can pull up every step the system
                  took while handling this one action.
                </p>
              </>
            )}
          </>
        )}
      </Modal>
    </>
  );
}
