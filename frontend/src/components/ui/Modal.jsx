// A popup panel for things that need a decision or a closer look.
//
// Three pages use one: confirming a submission that failed eligibility,
// showing the full story of an activity row, and confirming a status change.
//
// It behaves the way people expect a dialog to behave:
//   - Escape closes it
//   - clicking the dark area behind it closes it
//   - the keyboard stays inside it while it is open, so Tab cannot wander
//     off to the page underneath
//   - when it closes, the keyboard goes back to whatever opened it
//   - the page behind cannot be scrolled while it is open

import { useEffect, useRef } from "react";
import Icon from "./Icon";

export default function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  size = "md",          // sm | md | lg
  tone = "default",     // default | warn | danger — tints the header strip
}) {
  const panelRef = useRef(null);
  const openerRef = useRef(null);

  // The latest onClose, kept in a ref. Pages pass a brand-new onClose function
  // every time they re-render (every keystroke in a box inside the pop-up). If
  // the effect below listed onClose as a dependency, each keystroke would tear
  // the effect down, which sends focus back to the page, and set it up again,
  // which focuses the panel. Either way, the text box would lose focus.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;

    // Remember what was focused, so we can put focus back on close.
    openerRef.current = document.activeElement;

    // Stop the page behind from scrolling.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Move focus into the panel.
    const panel = panelRef.current;
    panel?.focus();

    function handleKeyDown(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current?.();
        return;
      }
      if (e.key !== "Tab" || !panel) return;

      // Keep Tab inside the panel by looping from the last item back to the first.
      const focusable = panel.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      document.body.style.overflow = previousOverflow;
      openerRef.current?.focus?.();
    };
    // Only opening and closing should run this again, never a re-render.
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div
        ref={panelRef}
        className={`modal modal-${size} modal-tone-${tone}`}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        tabIndex={-1}
      >
        <header className="modal-head">
          <div>
            <h2 className="modal-title">{title}</h2>
            {subtitle && <p className="modal-subtitle">{subtitle}</p>}
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}
