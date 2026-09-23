// The frame every signed-in page sits inside: a sticky bar across the top,
// and the page underneath it.
//
// This was a dark sidebar down the left until Piece 29. The links, and who
// sees which, are exactly the same — an applicant, an officer, a manager and
// the administrator each see only what they can use (D-06, D-07, Piece 27).
// What changed is where they sit: a bar that stays put while the page scrolls,
// with the page showing faintly through it, and room on the right for the
// notification bell that Piece 30 fills in.
//
// The person's name, role and Sign out moved into a menu behind their initials,
// because seven links plus an account block will not fit across a laptop screen
// (D9).

import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import NotificationBell from "./NotificationBell";
import Icon from "./ui/Icon";
import { label } from "../utils/format";

/**
 * Which link counts as "where you are".
 *
 * React Router's own matching was not quite right here. Without `end`,
 * "Applications" also lit up while you were on "New application", because
 * /applications/new starts with /applications. With `end`, opening an
 * application (/applications/5) lit up nothing at all, so the bar went blank
 * and you lost your place. Neither is what a person expects, so the rule is
 * written out: an application's own page belongs under Applications, and the
 * new-application form does not.
 */
function isActive(to, pathname) {
  if (to === "/applications") {
    return pathname === "/applications" || /^\/applications\/\d+$/.test(pathname);
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

// Two initials for the round button on the right.
function initialsOf(name) {
  return (name || "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
}

/**
 * The account menu: initials on the bar, and behind them the person's name,
 * their role, and Sign out.
 *
 * It behaves the way a menu is expected to: Escape closes it and puts the
 * keyboard back on the button, clicking anywhere else closes it, and moving to
 * another page closes it too — otherwise it would hang open over the new page.
 */
function AccountMenu({ user, onSignOut }) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef(null);
  const wrapRef = useRef(null);
  const { pathname } = useLocation();

  const close = useCallback(({ refocus = false } = {}) => {
    setOpen(false);
    if (refocus) buttonRef.current?.focus();
  }, []);

  // Close when the page changes, so the menu is never left hanging open over
  // a page you have already moved on from. Done by comparing the address
  // while rendering rather than in an effect: an effect would render the new
  // page once with the menu still open and then again with it closed, which
  // is the "cascading renders" the linter warns about. React calls this
  // adjusting state during render, and it is the documented way.
  const [pathWhenOpened, setPathWhenOpened] = useState(pathname);
  if (pathname !== pathWhenOpened) {
    setPathWhenOpened(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(e) {
      if (e.key === "Escape") close({ refocus: true });
    }
    function handleClick(e) {
      if (!wrapRef.current?.contains(e.target)) close();
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open, close]);

  return (
    <div className="account" ref={wrapRef}>
      <button
        type="button"
        ref={buttonRef}
        className="account-button"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`Account: ${user?.name || "signed in"}`}
      >
        <span className="avatar" aria-hidden="true">{initialsOf(user?.name)}</span>
        <Icon name="chevronDown" size={14} className="account-chevron" />
      </button>

      {open && (
        <div className="account-menu" role="menu">
          <div className="account-who">
            <strong>{user?.name}</strong>
            <small>{user?.email}</small>
            <span className="pill">{label(user?.role)}</span>
          </div>
          <button type="button" className="account-item" role="menuitem" onClick={onSignOut}>
            <Icon name="logout" size={16} />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { user, logout, isApplicant, isAdmin, canViewStaffScreens, canViewAudit } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  // Start each page at the top. React Router leaves the scroll position where
  // it was, so opening a page from halfway down a long list used to drop you
  // halfway down the new one — which also made the fade below look like a
  // glitch rather than a transition.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  // Each entry: where it goes, what it says, which icon, and who may see it.
  // The admin sees everything but creates nothing, so it has no "New application".
  const links = [
    { to: "/admin", text: "Administration", icon: "settings", show: isAdmin },
    { to: "/applications", text: isApplicant ? "My applications" : isAdmin ? "All applications" : "Applications", icon: "applications", show: true },
    { to: "/applications/new", text: isApplicant ? "Apply for a loan" : "New application", icon: "plus", show: !isAdmin },
    { to: "/assistant", text: "Assistant", icon: "shield", show: true },
    { to: "/dashboard", text: "Dashboard", icon: "dashboard", show: canViewStaffScreens },
    { to: "/edit-requests", text: "Edit requests", icon: "inbox", show: canViewStaffScreens },
    { to: "/documents-to-check", text: "Documents to check", icon: "file", show: canViewStaffScreens },
    { to: "/activity", text: "Activity", icon: "activity", show: canViewAudit },
    { to: "/profile", text: "My profile", icon: "user", show: isApplicant },
  ].filter((l) => l.show);

  return (
    <div className="shell">
      {/* For anyone using a keyboard: one Tab to jump past the links. */}
      <a className="skip-link" href="#main">Skip to content</a>

      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-brand">
            <span className="brand-mark">
              <Icon name="rupee" size={18} />
            </span>
            <span className="brand-text">
              <strong>Loan Management</strong>
              <small>Branch portal</small>
            </span>
          </div>

          <nav className="topnav" aria-label="Main">
            {links.map((l) => {
              const here = isActive(l.to, pathname);
              return (
                <NavLink
                  key={l.to}
                  to={l.to}
                  className={here ? "active" : undefined}
                  aria-current={here ? "page" : undefined}
                >
                  <Icon name={l.icon} size={17} />
                  <span>{l.text}</span>
                </NavLink>
              );
            })}
          </nav>

          <div className="topbar-actions">
            {/* Empty until Piece 30 gives it something to show. */}
            <NotificationBell />
            <AccountMenu user={user} onSignOut={handleLogout} />
          </div>
        </div>
      </header>

      {/* The key changes with the address, which remounts the page and so
          restarts its fade-in. Without it the animation runs once, on the
          first load, and never again. */}
      <main className="page" id="main" key={pathname}>
        <Outlet />
      </main>
    </div>
  );
}
