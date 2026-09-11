// The applicant's own borrower profile.
//
// Two fixes here. A missing rupee figure used to render as an empty gap next to
// its label, which reads as a broken page rather than "we never asked for this".
// And a failed load showed a bare red banner with nowhere to go.

import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import { formatDate, label, rupees, whole } from "../utils/format";

/** A value that says so plainly when it was never recorded. */
function Given({ value, render }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted">not provided</span>;
  }
  return render ? render(value) : String(value);
}

export default function MyProfile() {
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/applicants/me")
      .then((r) => { setMe(r.data); setError(""); })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner text="Loading your profile…" />;

  if (!me) {
    return (
      <>
        <div className="page-head"><h1>My profile</h1></div>
        <div className="card">
          <EmptyState
            icon="alert"
            title="Your profile could not be loaded"
            action={<Button icon="refresh" onClick={() => window.location.reload()}>Try again</Button>}
          >
            {error || "Something went wrong fetching your details."}
          </EmptyState>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My profile</h1>
          <p className="sub">What the bank holds about you, and what it uses to assess a loan.</p>
        </div>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />

      <div className="detail-grid">
        <div className="card">
          <div className="card-head"><h2>Your details</h2></div>
          <dl className="kv">
            <dt>Name</dt><dd>{me.name}</dd>
            <dt>Email</dt><dd>{me.email}</dd>
            <dt>Phone</dt><dd>{me.phone}</dd>
            <dt>Date of birth</dt>
            <dd><Given value={me.date_of_birth} render={formatDate} /></dd>
            <dt>Customer since</dt><dd>{formatDate(me.created_at)}</dd>
          </dl>

          <hr className="divider" />
          <div className="card-head"><h2>What we assess a loan against</h2></div>
          <dl className="kv">
            <dt>Employment</dt><dd>{label(me.employment_status)}</dd>
            <dt>Years in current job</dt>
            <dd className="num"><Given value={me.years_with_employer} render={(v) => `${whole(v)} year${Math.round(Number(v)) === 1 ? "" : "s"}`} /></dd>
            <dt>Annual income</dt>
            <dd className="num"><Given value={me.annual_income} render={rupees} /></dd>
            <dt>CIBIL score</dt>
            <dd className="num"><Given value={me.credit_score} /></dd>
            <dt>Existing monthly EMIs</dt>
            <dd className="num"><Given value={me.existing_monthly_emi} render={(v) => `${rupees(v)} / month`} /></dd>
          </dl>
        </div>

        <div className="card">
          <div className="card-head"><h2>Where this is kept</h2></div>
          <ul className="checklist">
            <li>
              <Icon name="shield" size={15} className="tick" />
              <span>Stored on the bank's server, never in this browser.</span>
            </li>
            <li>
              <Icon name="shield" size={15} className="tick" />
              <span>Fetched fresh with your login every time you open this page.</span>
            </li>
            <li>
              <Icon name="shield" size={15} className="tick" />
              <span>Only you and bank staff can see it.</span>
            </li>
          </ul>
          <p className="hint" style={{ marginTop: "1rem" }}>
            To change any of these details, ask your branch. They are used to work
            out how much you can borrow, so the bank keeps the record.
          </p>
        </div>
      </div>
    </>
  );
}
