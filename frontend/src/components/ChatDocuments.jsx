// The documents a chat message says were attached (Pieces 37 + 38).
//
// The message only knows which application and which document ids. Everything
// shown here is read fresh from the application's document list each time, so
// a chat reopened next week shows each document as it is now, not as it was:
//
//   - with details     → a BatchReview card (filled from the PDF, Confirm all)
//   - "Something else" → counts as uploaded; staff will check it
//   - verified         → says so
//   - gone             → "replaced or removed" (a customer can't tell which:
//                        the list shows current documents only)
//
// Confirm all only ever sees this message's own documents, never others on
// the same application. Nothing here is sent to the AI.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import BatchReview from "./BatchReview";
import ErrorBanner from "./ErrorBanner";
import TestBadge from "./TestBadge";
import { label } from "../utils/format";

export default function ChatDocuments({ applicationId, documentIds }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get(`/applications/${applicationId}/documents`)
      .then((res) => setItems(res.data.items))
      .catch((err) => setError(errorMessage(err)));
  }, [applicationId]);

  useEffect(() => { load(); }, [load]);

  const current = useMemo(
    () => (items || []).filter((d) => documentIds.includes(d.id)),
    [items, documentIds],
  );
  // The same list object unless the set of cards really changes, so a reload
  // after Confirm all doesn't make BatchReview start its cards over.
  const detailKey = current.filter((d) => d.extraction_id).map((d) => `${d.id}:${d.extraction_id}`).join(",");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const withDetails = useMemo(() => current.filter((d) => d.extraction_id), [detailKey]);
  const withoutDetails = current.filter((d) => !d.extraction_id);
  const gone = items ? documentIds.filter((id) => !current.some((d) => d.id === id)).length : 0;

  if (error) return <ErrorBanner message={error} onClose={() => setError("")} />;
  if (!items) return <p className="muted" style={{ fontSize: "0.85rem" }}>Loading the documents…</p>;

  return (
    <div className="chat-documents">
      {withoutDetails.map((d) => (
        <p key={d.id} className="muted" style={{ margin: "0 0 0.4rem" }}>
          {label(d.doc_type)} · {d.file_name}{" "}
          {d.nature === "test" && <TestBadge />}{" "}
          {d.verified
            ? <span className="pill pill-ok">Verified by staff</span>
            : "— counts as uploaded; staff will check it."}
        </p>
      ))}
      {current.filter((d) => d.extraction_id && d.verified).map((d) => (
        <p key={`v-${d.id}`} className="muted" style={{ margin: "0 0 0.4rem" }}>
          {d.file_name} <span className="pill pill-ok">Verified by staff</span>
        </p>
      ))}
      {gone > 0 && (
        <p className="muted" style={{ margin: "0 0 0.4rem" }}>
          {gone === 1 ? "One attached document is" : `${gone} attached documents are`} no longer
          current (replaced or removed).
        </p>
      )}
      {withDetails.length > 0 && (
        <BatchReview docs={withDetails} canEdit embedded onChanged={load} onDone={() => {}} />
      )}
    </div>
  );
}
