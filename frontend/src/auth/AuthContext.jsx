// Who is logged in, and their role. Shared with every page through React context.
//
// The browser holds only the token (Rule 13). On page load we ask the backend
// "who am I?" with that token rather than trusting anything stored locally.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);      // {id, name, email, role} or null
  const [loading, setLoading] = useState(true); // true until we know either way

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setUser(null);
  }, []);

  // On first load: if there is a token, find out who it belongs to.
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [logout]);

  // The API client fires this when the backend says 401.
  useEffect(() => {
    window.addEventListener("auth:logout", logout);
    return () => window.removeEventListener("auth:logout", logout);
  }, [logout]);

  const login = useCallback(async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    localStorage.setItem("token", res.data.access_token);
    const me = await api.get("/auth/me");
    setUser(me.data);
    return me.data;
  }, []);

  const isStaff = user?.role === "loan_officer" || user?.role === "branch_manager";
  const isManager = user?.role === "branch_manager";
  const isAdmin = user?.role === "admin";

  const value = {
    user,
    loading,
    login,
    logout,
    isApplicant: user?.role === "applicant",
    // isStaff and isManager guard the ACTION buttons, so they never include
    // the admin (Piece 27).
    isStaff,
    isManager,
    isAdmin,
    // Looking is wider than acting: the admin may open the staff screens and
    // the audit log, but only to look.
    canViewStaffScreens: isStaff || isAdmin,
    canViewAudit: isManager || isAdmin,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
