// One Axios instance for the whole app.
//
// - The backend address comes from .env (VITE_API_BASE_URL), never from code.
// - The login token is added to every request automatically.
// - If the backend answers 401 (token missing, expired, or bad), the token is
//   dropped and the app is told to go back to the login page.

import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${baseURL}/api/v1`,
  timeout: 15000,
});

// How long to wait on the assistant, which takes far longer than anything else
// in the app. A Phase 5 review runs four agents in turn; the app-wide 15 second
// limit cut it off mid-answer.
//
// Measured rather than guessed: a real review of application 7 took 21 seconds
// from a script and 25 from the browser, on a good day with a working key. On a
// bad day the key ladder retries across several keys before answering, so the
// limit has to leave room for that — 90 seconds is roughly three times the
// worst measurement, which is enough to absorb a couple of retries without
// letting a genuinely stuck request spin forever.
export const CHAT_TIMEOUT_MS = 90000;

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(error);
  }
);

// Turn a FastAPI error into one readable sentence for an error banner.
// FastAPI sends either {detail: "text"} or {detail: [{loc, msg}, ...]} for validation.
export function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (!detail) {
    if (error?.code === "ERR_NETWORK") return "Cannot reach the server. Is the backend running?";
    return error?.message || "Something went wrong.";
  }
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : "";
        return field ? `${field}: ${e.msg}` : e.msg;
      })
      .join(" · ");
  }
  return JSON.stringify(detail);
}
