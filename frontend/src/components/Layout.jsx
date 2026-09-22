// The frame every signed-in page sits inside: a dark sidebar on the left,
// the page itself on the right.
//
// The sidebar links change with the role, so an applicant, an officer and a
// manager each see only what they can actually use (D-06, D-07).

import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Icon from "./ui/Icon";
import { label } from "../utils/format";

/**
 * Which sidebar link counts as "where you are".
 *
 * React Router's own matching was not quite right here. Without `end`,
 * "Applications" also lit up while you were on "New application", because
 * /applications/new starts with /applications. With `end`, opening an
 * application (/applications/5) lit up nothing at all, so the sidebar went
 * blank and you lost your place. Neither is what a person expects, so the rule
 * is written out: an application's own page belongs under Applications, and
 * the new-application form does not.
 */
function isActive(to, pathname) {
  if (to === "/applications") {
    return pathname === "/applications" || /^\/applications\/\d+$/.test(pathname);
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

export default function Layout() {
  const { user, logout, isApplicant, isStaff, isManager } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  // Each entry: where it goes, what it says, which icon, and who may see it.
  const links = [
    { to: "/applications", text: isApplicant ? "My applications" : "Applications", icon: "applications", show: true },
    { to: "/applications/new", text: isApplicant ? "Apply for a loan" : "New application", icon: "plus", show: true },
    { to: "/assistant", text: "Assistant", icon: "shield", show: true },
    { to: "/dashboard", text: "Dashboard", icon: "dashboard", show: isStaff },
    { to: "/edit-requests", text: "Edit requests", icon: "inbox", show: isStaff },
    { to: "/activity", text: "Activity", icon: "activity", show: isManager },
    { to: "/profile", text: "My profile", icon: "user", show: isApplicant },
  ].filter((l) => l.show);

  // Two initials for the round avatar at the bottom.
  const initials = (user?.name || "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">
            <Icon name="rupee" size={18} />
          </span>
          <span className="brand-text">
            <strong>Loan Management</strong>
            <small>Branch portal</small>
          </span>
        </div>

        <nav className="sidebar-nav" aria-label="Main">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} className={isActive(l.to, pathname) ? "active" : undefined}>
              <Icon name={l.icon} size={18} />
              <span>{l.text}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="who">
            <span className="avatar" aria-hidden="true">{initials}</span>
            <span className="who-text">
              <strong>{user?.name}</strong>
              <small>{label(user?.role)}</small>
            </span>
          </div>
          <button type="button" className="signout" onClick={handleLogout}>
            <Icon name="logout" size={16} />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="page">
        <Outlet />
      </main>
    </div>
  );
}
