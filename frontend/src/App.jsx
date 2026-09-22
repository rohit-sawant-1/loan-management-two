// The routes, and which role may see which page.

import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import Spinner from "./components/Spinner";
import Login from "./pages/Login";
import StaffRegister from "./pages/StaffRegister";
import ApplicantSignup from "./pages/ApplicantSignup";
import ApplicationList from "./pages/ApplicationList";
import ApplicationDetail from "./pages/ApplicationDetail";
import NewApplication from "./pages/NewApplication";
import NewApplicant from "./pages/NewApplicant";
import Dashboard from "./pages/Dashboard";
import Activity from "./pages/Activity";
import MyProfile from "./pages/MyProfile";
import Assistant from "./pages/Assistant";
import EditRequests from "./pages/EditRequests";

// Wraps pages that need a login. `roles` narrows it further.
function RequireAuth({ roles, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/applications" replace />;
  return children;
}

// Pages for people who are NOT logged in. A logged-in user is sent onward.
function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (user) return <Navigate to="/applications" replace />;
  return children;
}

const STAFF = ["loan_officer", "branch_manager"];
const MANAGER = ["branch_manager"];
const APPLICANT = ["applicant"];

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
          <Route path="/register" element={<PublicOnly><StaffRegister /></PublicOnly>} />
          <Route path="/signup" element={<PublicOnly><ApplicantSignup /></PublicOnly>} />

          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/assistant" element={<Assistant />} />
            <Route path="/applications" element={<ApplicationList />} />
            <Route path="/applications/new" element={<NewApplication />} />
            <Route path="/applications/:id" element={<ApplicationDetail />} />
            <Route path="/applicants/new" element={<RequireAuth roles={STAFF}><NewApplicant /></RequireAuth>} />
            <Route path="/dashboard" element={<RequireAuth roles={STAFF}><Dashboard /></RequireAuth>} />
            <Route path="/edit-requests" element={<RequireAuth roles={STAFF}><EditRequests /></RequireAuth>} />
            <Route path="/activity" element={<RequireAuth roles={MANAGER}><Activity /></RequireAuth>} />
            <Route path="/profile" element={<RequireAuth roles={APPLICANT}><MyProfile /></RequireAuth>} />
          </Route>

          <Route path="*" element={<Navigate to="/applications" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
