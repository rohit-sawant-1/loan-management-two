// Piece 27: System administration, the administrator's home page.
//
// The administrator oversees the system: it can see every record and every
// account, but it can't do loan business. This page shows who has an account
// and in which role. Piece 28 adds the system settings here.

import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import Modal from "../components/ui/Modal";
import { formatDate, formatDateTime } from "../utils/format";

// The roles in the order a bank would list them, with a name for one and for many.
const ROLES = [
  { role: "applicant", one: "Customer", many: "Customers" },
  { role: "loan_officer", one: "Loan officer", many: "Loan officers" },
  { role: "branch_manager", one: "Branch manager", many: "Branch managers" },
  { role: "admin", one: "Administrator", many: "Administrators" },
];
const ROLE_NAME = Object.fromEntries(ROLES.map((r) => [r.role, r.one]));

// Piece 28: the one system setting there is so far. OFF is what the app has
// always done; ON is what Piece 31's real uploads will read.
//
// Switching it changes how the app behaves for every person using it, so it
// asks first. The words for each position come from the server, which reads
// them from rules.py — the screen never keeps its own copy of what a setting
// means.
function SettingsCard() {
  const [setting, setSetting] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [wanted, setWanted] = useState(null);   // the value the pop-up is asking about
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get("/admin/settings/real-uploads")
      .then((res) => { setSetting(res.data); setError(""); })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => { load(); }, [load]);

  const closeModal = useCallback(() => { if (!busy) setWanted(null); }, [busy]);

  async function save() {
    setBusy(true);
    try {
      const res = await api.put("/admin/settings/real-uploads", { enabled: wanted });
      setSetting(res.data);
      setNotice(wanted ? "Real document uploads are on." : "Real document uploads are off.");
      setError("");
      setWanted(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (!setting) return null;

  const on = setting.value;

  return (
    <div className="card">
      <div className="card-head">
        <h2>Settings</h2>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />
      {notice && (
        <div className="banner banner-ok">
          <Icon name="check" size={16} />
          <span>{notice}</span>
        </div>
      )}

      <div className="setting-row">
        <label className="switch">
          <input
            type="checkbox"
            checked={on}
            onChange={(e) => setWanted(e.target.checked)}
            aria-describedby="real-uploads-help"
          />
          <span className="switch-track" aria-hidden="true"><span className="switch-knob" /></span>
          <span className="switch-label">{setting.label}</span>
        </label>
        <span className={on ? "pill pill-ok" : "pill"}>{on ? "On" : "Off"}</span>
      </div>

      <p className="muted" id="real-uploads-help">{on ? setting.on_text : setting.off_text}</p>

      <p className="hint">
        {setting.updated_by
          ? `Last changed by ${setting.updated_by} on ${formatDateTime(setting.updated_at)}.`
          : "Never changed. This is the setting the app started with."}
      </p>

      <Modal
        open={wanted !== null}
        onClose={closeModal}
        title={wanted ? "Switch real document uploads on?" : "Switch real document uploads off?"}
        tone={wanted ? "warn" : "default"}
        footer={
          <>
            <Button type="button" onClick={closeModal} disabled={busy}>Go back</Button>
            <Button type="button" variant="primary" loading={busy} onClick={save}>
              {wanted ? "Switch on" : "Switch off"}
            </Button>
          </>
        }
      >
        <p>{wanted ? setting.on_text : setting.off_text}</p>
        <p className="muted">
          This applies to everybody using the app, not just to you, and it is recorded in the
          activity log with your name against it.
        </p>
      </Modal>
    </div>
  );
}

// Piece 32: clears out demo documents. Only ever touches documents the
// server itself classified TEST — a REAL or UNDECLARED document is never
// affected, and `nature` can't be changed once set, so this is the only way
// a TEST document ever leaves the system.
const PURGE_PHRASE = "DELETE TEST DOCUMENTS";

function PurgeTestDocumentsCard() {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function closeModal() {
    if (busy) return;
    setOpen(false);
    setTyped("");
  }

  async function purge() {
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/admin/test-documents/purge", { confirm: typed });
      setNotice(
        res.data.purged_count === 0
          ? "There were no TEST documents to remove."
          : `Removed ${res.data.purged_count} TEST document${res.data.purged_count === 1 ? "" : "s"}.`
      );
      setOpen(false);
      setTyped("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <h2>Demo documents</h2>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />
      {notice && (
        <div className="banner banner-ok">
          <Icon name="check" size={16} />
          <span>{notice}</span>
        </div>
      )}

      <p className="muted">
        Every document the system recognised as TEST material — a specimen, sample or demo file —
        can be cleared out in one go. Real customer documents are never touched.
      </p>

      <Button type="button" variant="danger" icon="trash" onClick={() => setOpen(true)}>
        Purge TEST documents
      </Button>

      <Modal
        open={open}
        onClose={closeModal}
        title="Purge every TEST document?"
        tone="danger"
        footer={
          <>
            <Button type="button" onClick={closeModal} disabled={busy}>Go back</Button>
            <Button
              type="button" variant="danger" loading={busy}
              disabled={typed !== PURGE_PHRASE}
              onClick={purge}
            >
              Purge
            </Button>
          </>
        }
      >
        <p>This permanently deletes every document marked TEST, everywhere in the app. There is no undo.</p>
        <p className="muted">
          Real and undeclared documents are never affected. This is recorded in the activity log
          with your name against it.
        </p>
        <label>
          Type <strong>{PURGE_PHRASE}</strong> to confirm
          <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        </label>
      </Modal>
    </div>
  );
}

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

          <SettingsCard />
          <PurgeTestDocumentsCard />
        </>
      )}
    </>
  );
}
