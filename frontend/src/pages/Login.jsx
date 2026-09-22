import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { homeFor } from "../auth/home";
import { errorMessage } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Button from "../components/ui/Button";
import Icon from "../components/ui/Icon";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const me = await login(email.trim(), password);
      // Go back to where the user was trying to go, or to their own home page:
      // the applications list, or System administration for the admin.
      navigate(location.state?.from || homeFor(me), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark"><Icon name="rupee" size={18} /></span>
          <strong>Loan Application Management</strong>
        </div>
        <h1>Sign in</h1>
        <p className="muted">Customers and bank staff sign in here.</p>
        <ErrorBanner message={error} onClose={() => setError("")} />
        <form onSubmit={handleSubmit} noValidate>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          <Button type="submit" variant="primary" loading={busy} style={{ width: "100%" }}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <div className="auth-foot">
          New customer? <Link to="/signup">Create an account</Link>
          <br />
          Bank staff? <Link to="/register">Register a staff account</Link>
        </div>
      </div>
    </div>
  );
}
