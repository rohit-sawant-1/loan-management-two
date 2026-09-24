// The Manager's Morning Briefing (D-13) — the headline feature.
//
// The manager opens the app and the AI has already read the whole pipeline:
// what is stuck, what is risky, what needs a decision today.
//
// Two deliberate choices here, both about trust:
//
//  1. "How this was worked out" opens the actual numbers the briefing was
//     written from — the overdue files by name and age, what documents are
//     missing, which applications failed the bank's own eligibility check at
//     submission. Nothing is a black box the manager has to take on faith.
//
//  2. When the AI is unavailable the server sends the plain figures instead
//     and says so, and this panel says so too. A briefing that quietly
//     degrades without telling anyone is worse than one that admits it.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, CHAT_TIMEOUT_MS, errorMessage } from "../api/client";
import { label, rupees, whole } from "../utils/format";
import Button from "./ui/Button";
import Icon from "./ui/Icon";

export default function MorningBriefing() {
  const [briefing, setBriefing] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showWorking, setShowWorking] = useState(false);

  const load = useCallback(async ({ isRefresh = false } = {}) => {
    if (isRefresh) setLoading(true);
    try {
      // The briefing waits on the AI, like a chat answer, so it gets the
      // chat's limit instead of the app-wide 15 seconds (T-137).
      const res = await api.get("/briefing", { timeout: CHAT_TIMEOUT_MS });
      setBriefing(res.data);
      setError("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) {
    return (
      <div className="card briefing-card">
        <div className="card-head"><h2>Morning briefing</h2></div>
        <p className="muted">{error}</p>
      </div>
    );
  }

  // Both of these are required by the server's schema, so on a good day neither
  // guard does anything. They are here because this card renders on the
  // manager's dashboard: a field that arrives null throws during render, and a
  // React component that throws while rendering takes the whole page white,
  // not just its own card. A missing briefing should cost the briefing, never
  // the dashboard around it.
  const numbers = briefing?.headline_numbers || {};
  const paragraphs = String(briefing?.narrative || "").split("\n").filter(Boolean);

  return (
    <div className="card briefing-card">
      <div className="card-head">
        <h2>
          <Icon name="clock" size={18} /> Morning briefing
        </h2>
        <div className="row" style={{ gap: "0.5rem", alignItems: "center" }}>
          {briefing && (
            <span className={briefing.written_by_ai ? "pill pill-ai" : "pill pill-warn"}>
              {briefing.written_by_ai ? "Written by AI" : "AI unavailable — figures only"}
            </span>
          )}
          <Button size="sm" variant="ghost" icon="refresh" loading={loading}
                  onClick={() => load({ isRefresh: true })}>
            Refresh
          </Button>
        </div>
      </div>

      {loading && !briefing ? (
        <p className="muted">Reading the pipeline…</p>
      ) : briefing ? (
        <>
          <div className="briefing-narrative">
            {paragraphs.length ? paragraphs.map((para, i) => (
              <p key={i}>{para}</p>
            )) : (
              <p className="muted">
                No summary was written this morning. The figures below are still
                counted from the database.
              </p>
            )}
          </div>

          <div className="briefing-stats">
            <div><strong>{numbers.awaiting_decision ?? "—"}</strong><span>awaiting a decision</span></div>
            <div><strong>{numbers.waiting_too_long ?? "—"}</strong><span>waiting too long</span></div>
            <div><strong>{numbers.missing_documents ?? "—"}</strong><span>missing documents</span></div>
            <div><strong>{rupees(numbers.value_awaiting_decision) || "—"}</strong><span>value in the queue</span></div>
          </div>

          {/* Not a ghost button. A ghost has no border or background until you
              hover it, which is fine in a toolbar where the buttons beside it
              make it obviously clickable — but this one stands alone under a
              divider, and a screenshot showed it reading as a stray line of
              text. Nothing said "press me" until the pointer happened to land
              on it. It is a disclosure control, so it now looks like one, with
              a chevron that turns to show which way it will go. */}
          <button
            type="button"
            className="briefing-toggle"
            aria-expanded={showWorking}
            onClick={() => setShowWorking((v) => !v)}
          >
            <Icon name="chevronDown" size={15} className={showWorking ? "chev-open" : "chev-closed"} />
            <span>{showWorking ? "Hide how this was worked out" : "How this was worked out"}</span>
          </button>

          {showWorking && (
            <div className="briefing-working">
              <p className="muted" style={{ marginTop: "0.75rem" }}>
                Every figure below is counted from the database before the AI is asked
                anything. The AI writes the summary above from these numbers — it never
                calculates them.
              </p>

              {briefing.needs_attention.length > 0 && (
                <>
                  <h3>Waiting longer than the branch's targets</h3>
                  <ul className="briefing-list">
                    {briefing.needs_attention.map((row) => (
                      <li key={row.id}>
                        <Link to={`/applications/${row.id}`}>Application {row.id}</Link>{" "}
                        {row.applicant_name} · {label(row.loan_type)} · {rupees(row.amount)} ·{" "}
                        <strong>{whole(row.days_waiting)} days</strong> in {label(row.status).toLowerCase()}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {briefing.missing_documents.length > 0 && (
                <>
                  <h3>Held up by missing documents</h3>
                  <ul className="briefing-list">
                    {briefing.missing_documents.map((row) => (
                      <li key={row.id}>
                        <Link to={`/applications/${row.id}`}>Application {row.id}</Link> {row.applicant_name} —
                        missing {row.missing.map((m) => label(m)).join(", ")}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {briefing.failed_eligibility.length > 0 && (
                <>
                  <h3>Failed the eligibility check at submission, still open</h3>
                  <ul className="briefing-list">
                    {briefing.failed_eligibility.map((row) => (
                      <li key={row.id}>
                        <Link to={`/applications/${row.id}`}>Application {row.id}</Link> {row.applicant_name} ·{" "}
                        {label(row.loan_type)} · {rupees(row.amount)} ·{" "}
                        {label(row.status).toLowerCase()}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {briefing.needs_attention.length === 0 &&
                briefing.missing_documents.length === 0 &&
                briefing.failed_eligibility.length === 0 && (
                  <p className="muted">Nothing is overdue and no documents are outstanding.</p>
                )}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
