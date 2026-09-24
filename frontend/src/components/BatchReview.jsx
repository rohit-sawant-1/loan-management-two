// Several documents' details at once (Piece 35): one card per document just
// uploaded together, each with its own table of fields, and one "Confirm all"
// button for the lot. Piece 38 reuses this inside the chat.
//
// Confirm all goes through the cards one at a time: save anything typed, then
// confirm. Each card gets its own result ("confirmed", or what it still
// needs), and one card failing never stops the others. A card that still needs
// something stays open with the server's message beside each field.

import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import DetailsTable from "./DetailsTable";
import ErrorBanner from "./ErrorBanner";
import Button from "./ui/Button";
import { recheckValues } from "../utils/documentKinds";

// What one card's result says, from the server's answer.
function problemSummary(err) {
  const fields = err?.response?.data?.detail?.fields;
  if (fields) {
    const n = Object.keys(fields).length;
    return `needs ${n} more field${n === 1 ? "" : "s"}`;
  }
  return errorMessage(err);
}

// `embedded` (Piece 37): inside a chat there's nothing to close, so the
// Done/Finish-later button is hidden. Everything else is the same.
export default function BatchReview({ docs, canEdit, onChanged, onDone, embedded = false }) {
  // One entry per document, keyed by its details id:
  // { doc, data, edits, fieldErrors, result }
  const [cards, setCards] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all(docs.map((d) => api.get(`/extractions/${d.extraction_id}`)))
      .then((answers) => {
        const loaded = {};
        answers.forEach((res, i) => {
          loaded[res.data.id] = { doc: docs[i], data: res.data, edits: {}, fieldErrors: {}, result: "" };
        });
        setCards(loaded);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [docs]);

  function updateCard(id, patch) {
    setCards((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }

  async function confirmAll() {
    setBusy(true);
    setError("");
    // Read from the current state once; each card is then updated as it goes.
    for (const [id, card] of Object.entries(cards)) {
      if (card.data.status !== "needs_input") continue;
      try {
        const values = { ...recheckValues(card.data), ...card.edits };
        let data = card.data;
        if (Object.keys(values).length > 0) {
          data = (await api.patch(`/extractions/${id}/fields`, { values })).data;
        }
        data = (await api.post(`/extractions/${id}/confirm`)).data;
        updateCard(id, { data, edits: {}, fieldErrors: {}, result: "confirmed" });
      } catch (err) {
        updateCard(id, {
          fieldErrors: err?.response?.data?.detail?.fields || {},
          result: problemSummary(err),
        });
      }
    }
    setBusy(false);
    onChanged?.();
  }

  const list = Object.entries(cards);
  const allDone = list.length > 0 && list.every(([, c]) => c.data.status === "confirmed");
  const summary = list.filter(([, c]) => c.result).map(([, c]) => `${c.data.kind_label} ${c.result}`).join(" · ");

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <div className="card-head">
        <h2>Check the details</h2>
      </div>
      <ErrorBanner message={error} onClose={() => setError("")} />
      {list.length === 0 && !error && <p className="muted">Loading…</p>}
      {list.map(([id, card]) => (
        <div key={id} style={{ marginBottom: "1.25rem" }}>
          <h3 style={{ margin: "0 0 0.4rem" }}>
            {card.data.kind_label}{" "}
            <span className="muted" style={{ fontWeight: 400, fontSize: "0.85rem" }}>{card.doc.file_name}</span>{" "}
            {card.result && (
              <span className={`pill ${card.result === "confirmed" ? "pill-ok" : "pill-warn"}`}>{card.result}</span>
            )}
          </h3>
          <DetailsTable
            data={card.data}
            doc={card.doc}
            editable={canEdit && card.data.status === "needs_input"}
            edits={card.edits}
            onEdit={(key, v) => setCards((prev) => ({
              ...prev, [id]: { ...prev[id], edits: { ...prev[id].edits, [key]: v } },
            }))}
            fieldErrors={card.fieldErrors}
            busy={busy}
            restartHint="replace it from the documents list"
          />
        </div>
      ))}
      {summary && <p className="muted">{summary}</p>}
      <div className="row" style={{ gap: "0.5rem" }}>
        {canEdit && !allDone && (
          <Button type="button" variant="primary" icon="check" loading={busy} onClick={confirmAll}
            disabled={list.length === 0}>
            Confirm all
          </Button>
        )}
        {!embedded && (
          <Button type="button" onClick={onDone} disabled={busy}>{allDone ? "Done" : "Finish later"}</Button>
        )}
      </div>
    </div>
  );
}
