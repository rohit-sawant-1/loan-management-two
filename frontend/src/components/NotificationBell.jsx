// The bell in the top bar (Piece 30).
//
// One component for everybody. A customer and a member of staff see the same
// bell; what differs is what the server sends them, because every address
// behind it returns the caller's own notifications and nobody else's.
//
// It asks for the unread count every 30 seconds and whenever you change page.
// Polling, not a live connection: 30 seconds is soon enough for a bell, and a
// live connection is a second thing that can fail during a demo.

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import Icon from "./ui/Icon";
import { timeAgo } from "../utils/format";

const POLL_MS = 30000;

export default function NotificationBell() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState(null);      // null until the panel is first opened
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const loadCount = useCallback(() => {
    api.get("/notifications/unread-count")
      .then((res) => setCount(res.data.count))
      // A bell that cannot reach the server simply shows nothing. It must
      // never put an error on a page that is otherwise working.
      .catch(() => {});
  }, []);

  const loadItems = useCallback(() => {
    setBusy(true);
    api.get("/notifications", { params: { limit: 20 } })
      .then((res) => { setItems(res.data.items); setCount(res.data.unread_count); })
      .catch(() => setItems([]))
      .finally(() => setBusy(false));
  }, []);

  // Every 30 seconds, and again whenever the page changes.
  useEffect(() => {
    loadCount();
    const timer = setInterval(loadCount, POLL_MS);
    return () => clearInterval(timer);
  }, [loadCount, pathname]);

  // Close the panel when the page changes, without an extra render (the same
  // reasoning as the account menu in Layout.jsx).
  const [pathWhenOpened, setPathWhenOpened] = useState(pathname);
  if (pathname !== pathWhenOpened) {
    setPathWhenOpened(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e) {
      if (e.key === "Escape") { setOpen(false); buttonRef.current?.focus(); }
    }
    function handleClick(e) {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) loadItems();
  }

  async function openNotification(item) {
    setOpen(false);
    if (!item.read_at) {
      try {
        await api.post(`/notifications/${item.id}/read`);
        setCount((c) => Math.max(0, c - 1));
      } catch {
        // If marking it read fails, still take them where it points. The
        // count corrects itself on the next poll.
      }
    }
    if (item.link) navigate(item.link);
  }

  async function markAllRead() {
    try {
      await api.post("/notifications/read-all");
      setCount(0);
      setItems((current) =>
        (current || []).map((i) => (i.read_at ? i : { ...i, read_at: new Date().toISOString() }))
      );
    } catch {
      loadCount();
    }
  }

  return (
    <div className="bell" ref={wrapRef}>
      <button
        type="button"
        ref={buttonRef}
        className="bell-button"
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={count > 0 ? `Notifications: ${count} unread` : "Notifications"}
      >
        <Icon name="bell" size={18} />
        {count > 0 && <span className="bell-badge">{count > 9 ? "9+" : count}</span>}
      </button>

      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <div className="bell-head">
            <strong>Notifications</strong>
            {count > 0 && (
              <button type="button" className="bell-clear" onClick={markAllRead}>
                Mark all read
              </button>
            )}
          </div>

          {busy && items === null ? (
            <p className="bell-empty">Loading…</p>
          ) : items && items.length > 0 ? (
            <ul className="bell-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={item.read_at ? "bell-item" : "bell-item unread"}
                    onClick={() => openNotification(item)}
                  >
                    <span className="bell-dot" aria-hidden="true" />
                    <span className="bell-text">
                      <strong>{item.title}</strong>
                      <span>{item.body}</span>
                      <small>{timeAgo(item.created_at)}</small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="bell-empty">Nothing yet. You will hear about anything that needs you.</p>
          )}
        </div>
      )}
    </div>
  );
}
