// Piece 27: System administration, the administrator's home page.
//
// The administrator oversees the system: it can see every record and every
// account, but it can't do loan business. This page shows who has an account
// and in which role. Piece 28 adds the system settings here.

import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import EmptyState from "../components/ui/EmptyState";
import { formatDate } from "../utils/format";

// The roles in the order a bank would list them, with a name for one and for many.
const ROLES = [
  { role: "applicant", one: "Customer", many: "Customers" },
  { role: "loan_officer", one: "Loan officer", many: "Loan officers" },
  { role: "branch_manager", one: "Branch manager", many: "Branch managers" },
  { role: "admin", one: "Administrator", many: "Administrators" },
];
const ROLE_NAME = Object.fromEntries(ROLES.map((r) => [r.role, r.one]));

export default function Admin() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/admin/users")
      .then((res) => { setData(res.data); setError(""); })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  if (!data && !error) return <Spinner text="Loading the accounts…" />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>System administration</h1>
          <p className="sub">
            You can see every customer, application, document and edit request, the dashboard and
            the audit log. You can't create, approve, reject or disburse anything, or change a loan record.
          </p>
        </div>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />

      {data && (
        <>
          {/* How many accounts there are of each kind. */}
          <div className="tiles">
            {ROLES.map((r) => (
              <div className="tile" key={r.role}>
                <div className="label">{r.many}</div>
                <div className="big">{data.counts_by_role?.[r.role] ?? 0}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="card-head">
              <h2>Accounts</h2>
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {data.total_count} account{data.total_count === 1 ? "" : "s"}
              </span>
            </div>
            {data.items.length === 0 ? (
              <EmptyState icon="user" title="No accounts yet" />
            ) : (
              <div className="table-wrap">
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Active</th>
                        <th>Joined</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((u) => (
                        <tr key={u.id}>
                          <td>{u.name}</td>
                          <td>{u.email}</td>
                          <td><span className="pill">{ROLE_NAME[u.role] || u.role}</span></td>
                          <td>
                            <span className={u.is_active ? "pill pill-ok" : "pill pill-warn"}>
                              {u.is_active ? "Active" : "Switched off"}
                            </span>
                          </td>
                          <td>{formatDate(u.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          <p className="hint" style={{ marginTop: "1rem" }}>System settings will appear on this page.</p>
        </>
      )}
    </>
  );
}
