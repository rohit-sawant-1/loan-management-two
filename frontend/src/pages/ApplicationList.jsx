// User story 09: the table with filters and the exact status colours.
// Staff see everything; an applicant's list is already limited to their own by the server.
//
// Piece 18 reshaped this page. The filters used to be four controls crowded in
// a row; they are now a proper toolbar with search on the left, the two
// dropdowns the user story names in the middle, and the count and clear on the
// right. The dates moved behind "More filters" so the common case is calm.
//
// Searching and sorting are asked of the server, not done here. The page only
// ever holds 20 rows, so sorting in the browser would order this page while
// hiding a bigger amount on the next one.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import ViewOnly from "../components/ViewOnly";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import { formatDate, label, rupees } from "../utils/format";
import { LOAN_TYPES } from "../utils/validation";

const STATUSES = ["submitted", "under_review", "approved", "rejected", "disbursed"];
const EMPTY = { search: "", status: "", loan_type: "", from_date: "", to_date: "" };

// Which column each heading sorts by. The names match what the backend allows;
// anything else comes back as a 400.
const COLUMNS = [
  { key: "id", head: "ID" },
  { key: "applicant_name", head: "Applicant" },
  { key: "loan_type", head: "Loan type" },
  { key: "amount_requested", head: "Amount", num: true },
  { key: "tenure_months", head: "Tenure", num: true },
  { key: "status", head: "Status" },
  { key: "submitted_at", head: "Submitted" },
];

export default function ApplicationList() {
  const { isApplicant, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [typed, setTyped] = useState("");          // what is in the search box right now
  const [filters, setFilters] = useState(EMPTY);   // what we have actually asked the server for
  const [sort, setSort] = useState({ by: "submitted_at", order: "desc" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showMore, setShowMore] = useState(false);
  const limit = 20;

  // Wait until typing stops before asking the server. Without this, "anita"
  // would be five separate requests, and the answers could arrive out of order.
  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((f) => (f.search === typed ? f : { ...f, search: typed }));
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [typed]);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    const params = { page, limit, sort_by: sort.by, order: sort.order };
    for (const [k, v] of Object.entries(filters)) if (v) params[k] = v;
    api
      .get("/applications", { params })
      .then((res) => { if (!cancelled) { setData(res.data); setError(""); } })
      .catch((err) => { if (!cancelled) setError(errorMessage(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [filters, sort, page]);

  useEffect(() => load(), [load]);

  const set = (field) => (e) => { setPage(1); setFilters({ ...filters, [field]: e.target.value }); };

  // First click sorts by that column; clicking the same one again flips it.
  // A new column starts descending for dates and amounts, ascending for words,
  // because that is what people expect of each.
  function sortBy(key) {
    setPage(1);
    setSort((current) => {
      if (current.by === key) return { by: key, order: current.order === "asc" ? "desc" : "asc" };
      const startsDescending = ["submitted_at", "amount_requested", "tenure_months", "id"];
      return { by: key, order: startsDescending.includes(key) ? "desc" : "asc" };
    });
  }

  function clearAll() {
    setPage(1);
    setTyped("");
    setFilters(EMPTY);
  }

  const pages = data ? Math.max(1, Math.ceil(data.total_count / limit)) : 1;
  const activeFilters = useMemo(() => Object.values(filters).filter(Boolean).length, [filters]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{isApplicant ? "My applications" : "Applications"}</h1>
          <p className="sub">
            {isApplicant
              ? "Every loan you have applied for, newest first."
              : "Every loan application in the branch. Search, filter, or sort by any column."}
          </p>
        </div>
        {/* The admin sees every application but can't create one (Piece 27). */}
        {isAdmin ? (
          <ViewOnly />
        ) : (
          <Link className="btn btn-primary" to="/applications/new">
            <Icon name="plus" size={16} />
            <span>{isApplicant ? "Apply for a loan" : "New application"}</span>
          </Link>
        )}
      </div>

      <div className="toolbar">
        <div className="grow search">
          <Icon name="search" size={16} />
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Search by applicant, email, or application number"
            aria-label="Search applications"
          />
        </div>
        <label>
          Status
          <select value={filters.status} onChange={set("status")}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        </label>
        <label>
          Loan type
          <select value={filters.loan_type} onChange={set("loan_type")}>
            <option value="">All types</option>
            {LOAN_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        </label>
        <div className="toolbar-right">
          <Button size="sm" variant="ghost" icon="filter" onClick={() => setShowMore((v) => !v)}>
            {showMore ? "Fewer filters" : "Dates"}
          </Button>
          {activeFilters > 0 && (
            <Button size="sm" variant="ghost" onClick={clearAll}>Clear {activeFilters}</Button>
          )}
        </div>
      </div>

      {showMore && (
        <div className="toolbar" style={{ marginTop: "-0.35rem" }}>
          <label>
            Submitted from
            <input type="date" value={filters.from_date} onChange={set("from_date")} />
          </label>
          <label>
            Submitted to
            <input type="date" value={filters.to_date} onChange={set("to_date")} />
          </label>
        </div>
      )}

      <ErrorBanner message={error} onClose={() => setError("")} />

      {loading && !data ? (
        <Spinner text="Loading applications…" />
      ) : (
        <>
          <div className="table-wrap">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    {COLUMNS.map((col) => {
                      const active = sort.by === col.key;
                      return (
                        <th
                          key={col.key}
                          className={[col.num ? "num" : "", "sortable", active ? "sorted" : ""].filter(Boolean).join(" ")}
                          onClick={() => sortBy(col.key)}
                          title={`Sort by ${col.head.toLowerCase()}`}
                          aria-sort={active ? (sort.order === "asc" ? "ascending" : "descending") : "none"}
                        >
                          <span className="th-inner">
                            {col.head}
                            {active && <Icon name={sort.order === "asc" ? "sortAsc" : "sortDesc"} size={13} />}
                          </span>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {data?.items?.length ? data.items.map((a) => (
                    <tr key={a.id} className="row-link" onClick={() => navigate(`/applications/${a.id}`)}>
                      <td className="id">{a.id}</td>
                      <td>{a.applicant_name || `Applicant ${a.applicant_id}`}</td>
                      <td>{label(a.loan_type)}</td>
                      <td className="num">{rupees(a.amount_requested)}</td>
                      <td className="num">{a.tenure_months} mo</td>
                      <td><StatusBadge status={a.status} /></td>
                      <td>{formatDate(a.submitted_at)}</td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={COLUMNS.length}>
                        <EmptyState
                          icon="inbox"
                          title={activeFilters > 0 ? "Nothing matches those filters" : "No applications yet"}
                          action={activeFilters > 0
                            ? <Button size="sm" onClick={clearAll}>Clear filters</Button>
                            : isAdmin
                              ? <ViewOnly />
                              : <Link className="btn btn-sm btn-primary" to="/applications/new">
                                  {isApplicant ? "Apply for a loan" : "New application"}
                                </Link>}
                        >
                          {activeFilters > 0
                            ? "Try a shorter search, or clear the filters to see everything."
                            : "Applications will appear here as soon as the first one is submitted."}
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
              <span className="spacer">
                {data.total_count} application{data.total_count === 1 ? "" : "s"}
                {activeFilters > 0 && " matching"}
              </span>
              <Button size="sm" icon="chevronLeft" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <span>Page {page} of {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </>
  );
}
