// Piece 31: every document nobody has verified yet, across every
// application — closes B3 ("staff and managers should be able to see and
// verify documents"). Staff mark one verified from here; the administrator
// can open the page too, but only to look (Piece 27), same as Edit requests.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import ViewOnly from "../components/ViewOnly";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Icon from "../components/ui/Icon";
import { fileSize, formatDateTime, label } from "../utils/format";

async function viewFile(fileId, setError) {
  try {
    const res = await api.get(`/files/${fileId}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (err) {
    setError(errorMessage(err));
  }
}

export default function DocumentsToCheck() {
  const { isAdmin } = useAuth();
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const limit = 20;

  const load = useCallback(() => {
    setLoading(true);
    api.get("/documents/unverified", { params: { page, limit } })
      .then((r) => { setData(r.data); setError(""); })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => { load(); }, [load]);

  async function markVerified(doc) {
    setBusyId(doc.id);
    setError("");
    try {
      await api.patch(`/applications/${doc.application_id}/documents/${doc.id}/verify`);
      setNotice(`${label(doc.doc_type)} on application ${doc.application_id} is now marked verified.`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total_count / limit)) : 1;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Documents to check</h1>
          <p className="sub">
            {isAdmin
              ? "Every document nobody has verified yet, across every application. Loan officers and the manager verify these; you can only look."
              : "Every document nobody has verified yet, across every application, newest first."}
          </p>
        </div>
      </div>

      <ErrorBanner message={error} onClose={() => setError("")} />
      {notice && (
        <div className="banner banner-ok">
          <Icon name="check" size={16} />
          <span>{notice}</span>
        </div>
      )}

      {loading && !data ? (
        <Spinner text="Loading documents…" />
      ) : (
        <>
          <div className="table-wrap">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 160 }}>Uploaded</th>
                    <th>Application</th>
                    <th>Type</th>
                    <th>File</th>
                    <th>Size</th>
                    <th style={{ width: 200 }} />
                  </tr>
                </thead>
                <tbody>
                  {data?.items?.length ? data.items.map((d) => (
                    <tr key={d.id}>
                      <td>{formatDateTime(d.uploaded_at)}</td>
                      <td><Link to={`/applications/${d.application_id}`}>Application {d.application_id}</Link></td>
                      <td>{label(d.doc_type)}</td>
                      <td>{d.file_name}</td>
                      <td className="mono">
                        {d.file_id
                          ? `${fileSize(d.original_size_bytes)} → ${fileSize(d.size_bytes)}`
                          : <span className="muted">—</span>}
                      </td>
                      <td>
                        <div className="row" style={{ gap: "0.4rem" }}>
                          {d.file_id && (
                            <Button size="sm" icon="file" onClick={() => viewFile(d.file_id, setError)}>
                              View
                            </Button>
                          )}
                          {isAdmin ? (
                            <ViewOnly />
                          ) : (
                            <Button
                              size="sm" variant="ok" icon="check"
                              loading={busyId === d.id} onClick={() => markVerified(d)}
                            >
                              Mark verified
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={6}>
                        <EmptyState icon="inbox" title="Nothing waiting">
                          Every uploaded document has been checked. New ones appear here as soon as they arrive.
                        </EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {data?.items?.length > 0 && (
            <div className="pager">
              <span className="spacer">{data.total_count} document{data.total_count === 1 ? "" : "s"}</span>
              <Button size="sm" icon="chevronLeft" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <span>Page {page} of {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </>
  );
}
