// The assistant. One chat box for the whole product.
//
// This screen talks to POST /api/v1/chat and nothing else, and it will not need
// rewriting as the later phases land. That address now runs the Phase 3 agent,
// which picks its own tools: one reads the user manual, the others read live
// application data. In Phase 4 the tools move behind MCP, and in Phase 5 it can
// run a full multi-agent review. The screen stays as it is; the brain behind
// the door gets smarter.
//
// Three deliberate choices worth explaining in a walkthrough:
//
//   * Every answer shows the manual extracts it came from. An assistant that
//     cites its source can be checked; one that does not has to be trusted.
//     For a bank that difference matters.
//
//   * Every answer also shows which tools the assistant used to get there, in
//     the order it used them. That is the same reasoning trail the Phase 4
//     Streamlit chat shows staff, and it turns "the AI said so" into something
//     a person can follow step by step.
//
//   * The conversation lives in this component's memory only. It is never put
//     in localStorage, because customer questions are customer data and
//     Rule 13 keeps that off the browser's disk.

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, CHAT_TIMEOUT_MS, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ErrorBanner from "../components/ErrorBanner";
import Button from "../components/ui/Button";
import Icon from "../components/ui/Icon";
import { timeAgo } from "../utils/format";

// What each brain is called on screen, so the routing is visible rather than magic.
const MODES = {
  rag: { text: "Answered from the user manual", icon: "file" },
  agent: { text: "Answered by the assistant", icon: "activity" },
  review: { text: "Multi-agent review", icon: "shield" },
  unavailable: { text: "No AI available", icon: "info" },
  empty: { text: "", icon: "info" },
};

// The agent's tools, in words a customer understands. `get_application_details`
// is a function name; "Looked up an application" is what actually happened.
// Anything not listed here falls back to its raw name rather than being hidden,
// so a tool added later still shows up instead of silently disappearing.
const TOOLS = {
  search_loan_policy: { text: "Read the user manual", icon: "file" },
  get_application_details: { text: "Looked up an application", icon: "applications" },
  list_applications: { text: "Searched the applications list", icon: "search" },
  get_dashboard_summary: { text: "Read the dashboard figures", icon: "dashboard" },
  get_applicant_details: { text: "Looked up an applicant", icon: "user" },

  // Phase 4's tools, which change a record rather than read one.
  update_application_status: { text: "Changed an application's status", icon: "activity" },
  submit_loan_application: { text: "Created a new application", icon: "file" },
  upload_document_metadata: { text: "Recorded a document", icon: "file" },

  // Phase 5's four agents. A review reports one of these per stage, so the
  // "how this was worked out" list becomes the pipeline itself, in order.
  data_collector: { text: "Collected the application data", icon: "applications" },
  risk_assessor: { text: "Assessed the risk", icon: "activity" },
  compliance_checker: { text: "Checked compliance", icon: "shield" },
  decision_maker: { text: "Made the decision", icon: "check" },
};

// Does this look like a request for a full underwriting review?
//
// Used only to decide whether to warn that the answer takes about ten seconds.
// The real decision is made on the server; this is a copy of the pattern in
// `backend/app/services/review_request.py`, and if you change one, change both.
const REVIEW_PHRASE =
  /^\s*(?:please\s+)?(?:assess|review|evaluate|underwrite)\s+(?:loan\s+)?application\s+#?\d{1,9}\s*[.!?]?\s*$/i;

const SUGGESTIONS = [
  "What documents are required for a home loan?",
  "What is the minimum CIBIL score for a personal loan?",
  "How long does a personal loan take to approve?",
  "What happens if my application is rejected?",
];

// Staff can do more than ask questions, and the review has to be asked for by
// name — so without a chip nobody would ever discover it exists.
const STAFF_SUGGESTIONS = [
  "Assess application 1",
  "Show all pending applications",
];

const STAFF_ROLES = ["loan_officer", "branch_manager"];

// The "check my work" strip under every answer: how the assistant worked the
// answer out, and which manual extracts it quoted. Both live in one component
// so the two toggles sit on a single row and the opened panels stack neatly
// beneath it.
//
// They are deliberately not two separate stacked controls. Both toggles are
// borderless grey text, and one directly above the other read as a paragraph
// rather than as buttons — the exact mistake T-73 caught on the briefing card.
// A shared row with a divider makes them legible as a pair of controls.
function Evidence({ tools, sources }) {
  const [openTools, setOpenTools] = useState(false);
  const [openSources, setOpenSources] = useState(false);

  const hasTools = tools?.length > 0;
  const hasSources = sources?.length > 0;
  if (!hasTools && !hasSources) return null;

  return (
    <div className="evidence">
      <div className="evidence-row">
        {hasTools && (
          <button type="button" className="sources-toggle"
                  aria-expanded={openTools}
                  onClick={() => setOpenTools((v) => !v)}>
            <Icon name={openTools ? "chevronDown" : "chevronLeft"} size={13} />
            {openTools ? "Hide" : "Show"} how this was worked out ({tools.length} step
            {tools.length === 1 ? "" : "s"})
          </button>
        )}
        {hasSources && (
          <button type="button" className="sources-toggle"
                  aria-expanded={openSources}
                  onClick={() => setOpenSources((v) => !v)}>
            <Icon name={openSources ? "chevronDown" : "chevronLeft"} size={13} />
            {openSources ? "Hide" : "Show"} the {sources.length} manual extract
            {sources.length === 1 ? "" : "s"} this came from
          </button>
        )}
      </div>

      {openTools && hasTools && (
        <ol className="tools-list">
          {tools.map((t, i) => (
            <li key={i}>
              <Icon name={TOOLS[t.tool]?.icon || "activity"} size={13} />
              <span className="tools-name">{TOOLS[t.tool]?.text || t.tool}</span>
              {t.tool_input && <span className="tools-input">{t.tool_input}</span>}
            </li>
          ))}
        </ol>
      )}

      {openSources && hasSources && (
        <ol className="sources-list">
          {sources.map((s, i) => (
            <li key={s.chunk_id || i}>
              <span className="mono">{s.chunk_id}</span>
              <p>{s.excerpt}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// Piece 36: a saved message from the server, in the shape this page draws.
function fromServer(m) {
  return m.role === "user"
    ? { id: m.id, who: "you", text: m.content }
    : {
        id: m.id, who: "assistant", text: m.content, mode: m.mode, sources: m.sources,
        tools: m.tools_used, ms: m.duration_ms, notice: m.ai_notice,
      };
}

export default function Assistant() {
  const { user } = useAuth();
  // Piece 36: the open conversation lives in the address (/assistant/12), so a
  // refresh reopens it. No number means a new, unsaved conversation.
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  // Set just before moving to a brand-new conversation's address, so the page
  // doesn't reload from the server the two messages it's already showing.
  const justStarted = useRef(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [waitingOnReview, setWaitingOnReview] = useState(false);
  const [waitedSeconds, setWaitedSeconds] = useState(0);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  const loadSessions = useCallback(() => {
    api.get("/chat/sessions")
      .then((res) => setSessions(res.data))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // Opening a conversation: its last 30 messages from the server.
  useEffect(() => {
    if (!sessionId) { setMessages([]); setHasMore(false); return; }
    if (justStarted.current === sessionId) { justStarted.current = null; return; }
    api.get(`/chat/sessions/${sessionId}/messages`)
      .then((res) => { setMessages(res.data.items.map(fromServer)); setHasMore(res.data.has_more); })
      .catch((err) => { setError(errorMessage(err)); navigate("/assistant", { replace: true }); });
  }, [sessionId, navigate]);

  async function loadEarlier() {
    try {
      const res = await api.get(`/chat/sessions/${sessionId}/messages`, {
        params: { before_id: messages[0]?.id },
      });
      setMessages((m) => [...res.data.items.map(fromServer), ...m]);
      setHasMore(res.data.has_more);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function archive(id) {
    try {
      await api.patch(`/chat/sessions/${id}`, { archived: true });
      if (String(id) === sessionId) navigate("/assistant");
      loadSessions();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  // Count the seconds while the assistant is working. A four-agent review is
  // long enough that a silent wait reads as a hang, and seeing the number climb
  // tells you it is still going.
  useEffect(() => {
    if (!busy) return undefined;
    setWaitedSeconds(0);
    const tick = setInterval(() => setWaitedSeconds((s) => s + 1), 1000);
    return () => clearInterval(tick);
  }, [busy]);

  async function send(text) {
    const question = (text ?? draft).trim();
    if (!question || busy) return;

    setMessages((m) => [...m, { who: "you", text: question }]);
    setDraft("");
    setBusy(true);
    // A review takes four agents and roughly ten seconds. Ten silent seconds
    // reads as a hung page, so say what is happening while it works.
    setWaitingOnReview(REVIEW_PHRASE.test(question));
    setError("");

    try {
      // The assistant gets its own, longer patience. A four-agent review takes
      // around twenty seconds, which the app-wide fifteen second limit used to
      // cut off just before the answer arrived.
      const res = await api.post("/chat", { message: question, session_id: sessionId || null },
                                 { timeout: CHAT_TIMEOUT_MS });
      setMessages((m) => [...m, {
        who: "assistant",
        text: res.data.answer,
        mode: res.data.mode,
        sources: res.data.sources,
        tools: res.data.tools_used,
        ms: res.data.duration_ms,
        notice: res.data.ai_notice,
      }]);
      // Piece 36: the first answer of a new conversation gives it a number.
      // Put that in the address so a refresh reopens it, and show it in the list.
      if (!sessionId && res.data.session_id) {
        justStarted.current = String(res.data.session_id);
        navigate(`/assistant/${res.data.session_id}`, { replace: true });
      }
      loadSessions();
    } catch (err) {
      setError(errorMessage(err));
      // Put the question back so nothing the person typed is lost.
      setDraft(question);
      setMessages((m) => m.slice(0, -1));
    } finally {
      setBusy(false);
      setWaitingOnReview(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Assistant</h1>
          <p className="sub">
            Ask about loan policy, eligibility, documents or fees, or about your
            own applications. Every answer shows you how it was worked out.
          </p>
        </div>
        {(messages.length > 0 || sessionId) && (
          <Button variant="ghost" icon="plus" onClick={() => navigate("/assistant")}>
            New chat
          </Button>
        )}
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />

      <div className="assistant-layout">
      {/* Piece 36: your saved conversations. Only ever your own. */}
      <aside className="chat-sessions">
        <Button type="button" size="sm" icon="plus" onClick={() => navigate("/assistant")}>New chat</Button>
        {sessions.length === 0 && <p className="muted" style={{ fontSize: "0.85rem" }}>No saved chats yet.</p>}
        {sessions.map((s) => (
          <div key={s.id} className={`chat-session ${String(s.id) === sessionId ? "active" : ""}`}>
            <button type="button" className="chat-session-open" onClick={() => navigate(`/assistant/${s.id}`)}>
              <span className="chat-session-title">{s.title}</span>
              <span className="muted">{timeAgo(s.updated_at)}</span>
            </button>
            <button type="button" className="chat-session-archive" aria-label="Archive this chat"
              title="Archive this chat" onClick={() => archive(s.id)}>×</button>
          </div>
        ))}
      </aside>

      <div className="chat">
        <div className="chat-log">
          {hasMore && (
            <div style={{ textAlign: "center", marginBottom: "0.75rem" }}>
              <Button type="button" size="sm" variant="ghost" onClick={loadEarlier}>Load earlier</Button>
            </div>
          )}
          {messages.length === 0 && (
            <div className="chat-welcome">
              <div className="empty-icon"><Icon name="shield" size={24} /></div>
              <p className="empty-title">
                Hello{user?.name ? `, ${user.name.split(" ")[0]}` : ""}. What would you like to know?
              </p>
              <p className="empty-text">
                I answer from the bank's user manual and from the loan system
                itself. I only ever show you what you are allowed to see, and if
                I do not know something I will say so rather than guess.
              </p>
              <div className="chips" style={{ justifyContent: "center", marginTop: "1.1rem" }}>
                {[
                  ...SUGGESTIONS,
                  ...(STAFF_ROLES.includes(user?.role) ? STAFF_SUGGESTIONS : []),
                ].map((s) => (
                  <button key={s} type="button" className="chip" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={m.id ?? `new-${i}`} className={`bubble bubble-${m.who}`}>
              {/* Above the answer on purpose: it changes how the answer should
                  be read, so finding it underneath would be too late. */}
              {m.notice && (
                <div className="ai-notice">
                  <Icon name="info" size={13} />
                  <span>{m.notice}</span>
                </div>
              )}
              <div className="bubble-text">{m.text}</div>
              {m.who === "assistant" && (
                <>
                  <Evidence tools={m.tools} sources={m.sources} />
                  <div className="bubble-meta">
                    <Icon name={MODES[m.mode]?.icon || "info"} size={12} />
                    <span>{MODES[m.mode]?.text || m.mode}</span>
                    {m.ms != null && <span>· {(m.ms / 1000).toFixed(1)}s</span>}
                  </div>
                </>
              )}
            </div>
          ))}

          {busy && (
            <div className="bubble bubble-assistant">
              <div className="typing" aria-label="Thinking">
                <span /><span /><span />
              </div>
              {waitingOnReview && (
                <div className="bubble-meta">
                  <Icon name="shield" size={12} />
                  <span>
                    Four agents are reviewing this application — collecting the data,
                    assessing risk, checking compliance, then deciding.
                    {waitedSeconds > 0 && ` ${waitedSeconds}s`}
                  </span>
                </div>
              )}
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form
          className="chat-input"
          onSubmit={(e) => { e.preventDefault(); send(); }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask about eligibility, documents, fees, timelines…"
            aria-label="Your question"
            disabled={busy}
          />
          <Button type="submit" variant="primary" loading={busy} disabled={!draft.trim()}>
            Send
          </Button>
        </form>
      </div>
      </div>
    </>
  );
}
