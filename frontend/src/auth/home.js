// Where each person lands after signing in, or when they open a page their
// role can't see (Piece 27).
//
// Kept in its own file rather than in AuthContext.jsx, because a file that
// exports components should export nothing else, or Vite's fast refresh
// stops working for it.

export function homeFor(user) {
  // The administrator has no applications of its own, so its home is the
  // System administration page.
  if (user?.role === "admin") return "/admin";
  return "/applications";
}
