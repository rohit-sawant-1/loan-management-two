// The manager's record of everything that has happened (D-11).
//
// This page used to show the stored details as raw data — a line of JSON in a
// table cell. That is fine for a developer reading a log file and wrong for a
// bank manager reading an app. Now each row reads as a sentence, and "View"
// opens the full story laid out properly.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import ActivityDetails from "../components/ActivityDetails";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import Modal from "../components/ui/Modal";
import { ACTIONS, describe } from "../utils/activity";
import { formatDateTime, label } from "../utils/format";

const ENTITY_TYPES = ["application", "applicant", "document", "user"];
const EMPTY = { actor_id: "", actor_type: "", action: "", entity_type: "", entity_id: "", from_date: "", to_date: "" };

export default function Activity() {
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showMore, setShowMore] = useState(false);
  const [chosen, setChosen] = useState(null);   // the row open in the popup
  const limit = 50;

  const load = useCallback(() => {
    setLoading(true);
    const params = { page, limit };
    for (const [k, v] of Object.entries(filters)) if (v) params[k] = v;
    api.get("/activity", { params })
      .then((r) => { setData(r.data); setError(""); })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [filters, page]);

  useEffect(() => { load(); }, [load]);

  const set = (field) => (e) => { setPage(1); setFilters({ ...filters, [field]: e.target.value }); };
  const pages = data ? Math.max(1, Math.ceil(data.total_count / limit)) : 1;
  const activeFilters = useMemo(() => Object.values(filters).filter(Boolean).length, [filters]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Activity</h1>
          <p className="sub">Everything that has happened, by people and by the AI assistants.</p>
        </div>
      </div>

      {/* Search on the left, the common filters next, the count and clear on the
          right. The rarely-used ones hide behind "More filters" so the row is
          no longer a crowd. Nothing was removed. */}
      <div className="toolbar">
        <div className="grow search">
          <Icon name="search" size={16} />
          <input
            value={filters.actor_id}
            onChange={set("actor_id")}
            placeholder="Search a person or AI agent — part of a name is enough"
            aria-label="Search a person or AI agent"
          />
        </div>
        <label>
          Done by
          <select value={filters.actor_type} onChange={set("actor_type")}>
            <option value="">Anyone</option>
            <option value="human">A person</option>
            <option value="ai">An AI assistant</option>
          </select>
        </label>
        <label>
          Event
          <select value={filters.action} onChange={set("action")}>
            <option value="">Any event</option>
            {Object.keys(ACTIONS).map((a) => (
              <option key={a} value={a}>{ACTIONS[a].text}</option>
            ))}
          </select>
        </label>
        <div className="toolbar-right">
          <Button size="sm" variant="ghost" icon="filter" onClick={() => setShowMore((v) => !v)}>
            {showMore ? "Fewer filters" : "More filters"}
          </Button>
          {activeFilters > 0 && (
            <Button size="sm" variant="ghost" onClick={() => { setPage(1); setFilters(EMPTY); }}>
              Clear {activeFilters}
            </Button>
          )}
        </div>
      </div>

      {showMore && (
        <div className="toolbar" style={{ marginTop: "-0.35rem" }}>
          <label>
            From date
            <input type="date" value={filters.from_date} onChange={set("from_date")} />
          </label>
          <label>
            To date
            <input type="date" value={filters.to_date} onChange={set("to_date")} />
          </label>
          <label>
            Record type
            <select value={filters.entity_type} onChange={set("entity_type")}>
              <option value="">Any</option>
              {ENTITY_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
            </select>
          </label>
          <label>
            Record number
            <input type="number" min={1} value={filters.entity_id} onChange={set("entity_id")} style={{ minWidth: 110 }} />
          </label>
        </div>
      )}

      <ErrorBanner message={error} onClose={() => setError("")} />

      {loading && !data ? (
        <Spinner text="Loading activity…" />
      ) : (
        <>
          <div className="table-wrap">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 170 }}>When</th>
                    <th>Who</th>
                    <th>What happened</th>
                    <th>Record</th>
                    <th style={{ width: 70 }} />
                  </tr>
                </thead>
                <tbody>
                  {data?.items?.length ? data.items.map((row) => {
                    const what = describe(row.action);
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
                        </td>
                        <td className="muted">
                          {/* "Application 3" rather than "Application #3" —
                              it reads as a sentence instead of a database
                              reference. The number is only printed when there
                              is one, so a row with a type but no id can never
                              render as "Chat #null" again (T-91). */}
                          {row.entity_type
                            ? `${label(row.entity_type)}${row.entity_id != null ? ` ${row.entity_id}` : ""}`
                            : "—"}
                        </td>
                        <td>
                          <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setChosen(row); }}>
                            View
                          </Button>
                        </td>
                      </tr>
                    );
                  }) : (
                    <tr>
                      <td colSpan={5}>
                        <EmptyState
                          icon="activity"
                          title="Nothing matches those filters"
                          action={activeFilters > 0 && (
                            <Button size="sm" onClick={() => { setPage(1); setFilters(EMPTY); }}>
                              Clear filters
                            </Button>
                          )}
                        >
                          Try widening the search, or clear the filters to see everything.
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
              <span className="spacer">{data.total_count} event{data.total_count === 1 ? "" : "s"}</span>
              <Button size="sm" icon="chevronLeft" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <span>Page {page} of {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}

      {/* The full story of one event. */}
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

            {chosen.entity_type && (
              <>
                <hr className="divider" />
                <h3>What it was about</h3>
                <dl className="kv">
                  <dt>Record</dt>
                  <dd>
                    {label(chosen.entity_type)}
                    {chosen.entity_id != null && ` ${chosen.entity_id}`}
                  </dd>
                </dl>
              </>
            )}

            <hr className="divider" />
            <h3>Details</h3>
            <ActivityDetails raw={chosen.details} />

            <hr className="divider" />
            <h3>If something looked wrong</h3>
            {chosen.request_id ? (
              <>
                <dl className="kv">
                  <dt>Reference</dt>
                  <dd className="mono">{chosen.request_id}</dd>
                  {chosen.ip_address && (<><dt>Came from</dt><dd className="mono">{chosen.ip_address}</dd></>)}
                </dl>
                <p className="hint">
                  Every step the system took while handling this one action was recorded
                  against this reference — who was signed in, what was sent, how long each
                  part took, and the full error if anything failed. Give this reference to
                  a developer and they can pull up exactly those records, instead of
                  searching through everything that happened that day.
                </p>
              </>
            ) : (
              <p className="muted" style={{ margin: 0 }}>
                No reference, because this event did not come from someone using the app.
                It was created directly by the demo setup script.
              </p>
            )}
          </>
        )}
      </Modal>
    </>
  );
}
