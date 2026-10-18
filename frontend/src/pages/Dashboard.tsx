import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  request,
  post,
  upload,
  token,
  type Summary,
  type PolicyRecord,
} from "../api";
import { Badge } from "../components/Evidence";
import { AudioInput } from "../components/Audio";
export function Login() {
  const [value, setValue] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  return (
    <section className="panel narrow">
      <span className="eyebrow">
        REVIEWER WORKSPACE · AUTHENTICATION REQUIRED
      </span>
      <h1>Reviewer access</h1>
      <p>
        Manage approved policies, original audio, human corrections, review
        decisions and release sign-off. Quick Test evaluates a demonstration
        recording; this workspace preserves professional review history.
      </p>
      <p>
        Your token stays in this browser tab’s session storage. Sign out to
        remove it.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await request("/review/workflows?limit=1", {}, value);
            sessionStorage.setItem("dubguard-reviewer", value);
            setValue("");
            navigate("/review");
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Reviewer token
          <input
            type="password"
            autoComplete="off"
            required
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <button disabled={busy}>Sign in</button>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
export function Dashboard() {
  const [rows, setRows] = useState<Summary[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [page, setPage] = useState(0),
    [view, setView] = useState("all");
  const historical = (r: Summary) =>
    ["APPROVED", "REJECTED", "SUPERSEDED"].includes(r.workflow.state);
  const visible = rows.filter(
    (r) =>
      view === "all" || (view === "history" ? historical(r) : !historical(r)),
  );
  useEffect(() => {
    let active = true;
    setLoading(true);
    request<Summary[]>("/review/workflows?limit=25&offset=" + page * 25)
      .then((r) => {
        if (active) setRows(r);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page]);
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">HUMAN REVIEW WORKSPACE</span>
        <h1>Narration reviews</h1>
        <p>
          Source audio, protected requirements and accountable human decisions.
        </p>
        <div className="actions">
          <Link className="button" to="/review/new">
            New review
          </Link>
          <Link className="button secondary" to="/policies">
            Scripts & policies
          </Link>
        </div>
      </header>
      {error && (
        <p className="error" role="alert">
          {error} <Link to="/login">Sign in again</Link>
        </p>
      )}
      <div className="workspace-overview">
        <div>
          <span className="eyebrow">ON THIS PAGE</span>
          <strong>{rows.filter((r) => !historical(r)).length}</strong>
          <span>Current reviews</span>
        </div>
        <div>
          <span className="eyebrow">EVIDENCE TO CONFIRM</span>
          <strong>
            {
              rows.filter(
                (r) => !historical(r) && !r.workflow.evidence_record_id,
              ).length
            }
          </strong>
          <span>Awaiting human evidence</span>
        </div>
        <div>
          <span className="eyebrow">HISTORY</span>
          <strong>{rows.filter(historical).length}</strong>
          <span>Completed or superseded</span>
        </div>
      </div>
      <div className="list-heading">
        <h2>Review queue</h2>
        <label>
          Show reviews on this page
          <select value={view} onChange={(e) => setView(e.target.value)}>
            <option value="all">All reviews</option>
            <option value="current">Current work</option>
            <option value="history">Historical reviews</option>
          </select>
        </label>
      </div>
      {loading ? (
        <p role="status">Loading reviews…</p>
      ) : !rows.length ? (
        <div className="panel">
          <h2>No reviews yet</h2>
          <p>Create a policy and add a recording to start.</p>
        </div>
      ) : (
        <div className="review-list">
          {!visible.length && (
            <p className="panel">
              No {view === "history" ? "historical" : "current"} reviews on this
              page.
            </p>
          )}
          {visible.map((r) => (
            <Link
              className="review-row"
              key={r.workflow.id}
              to={"/review/" + r.workflow.id}
            >
              <div>
                <strong>{r.policy.script.id}</strong>
                <p>
                  Script rev {r.policy.script.revision} · Policy rev{" "}
                  {r.policy.policy.revision}
                </p>
                <small>
                  {r.audio.duration_seconds.toFixed(1)} s ·{" "}
                  {r.audio.format.toUpperCase()} ·{" "}
                  {new Date(r.workflow.created_at).toLocaleString()}
                </small>
                <div className="row-stages" aria-label="Evidence progress">
                  <span>✓ Script approved</span>
                  <span>
                    {r.workflow.transcription_record_id ? "✓" : "○"}{" "}
                    Transcription
                  </span>
                  <span>
                    {r.workflow.evidence_record_id ? "✓" : "○"} Human evidence
                  </span>
                  <span>
                    {r.workflow.verification_record_id ? "✓" : "○"} Verification
                  </span>
                </div>
              </div>
              <Badge value={r.workflow.state} />
              <span aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      )}
      <div className="actions">
        <button
          className="secondary"
          disabled={!page || loading}
          onClick={() => setPage(page - 1)}
        >
          Previous
        </button>
        <button
          className="secondary"
          disabled={rows.length < 25 || loading}
          onClick={() => setPage(page + 1)}
        >
          Next
        </button>
      </div>
    </>
  );
}
export function NewReview() {
  const [policies, setPolicies] = useState<PolicyRecord[]>([]),
    [policy, setPolicy] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const supersedes = new URLSearchParams(useLocation().search).get(
    "supersedes",
  );
  useEffect(() => {
    request<PolicyRecord[]>("/review/policy-records")
      .then((rows) =>
        setPolicies(rows.filter((r) => r.kind === "approved_policy")),
      )
      .catch((e) => setError(e.message));
  }, []);
  async function create() {
    if (!file || !policy) return;
    setBusy(true);
    try {
      const a = await upload("/review/artifacts", file);
      const w = await post<{ workflow_id: string }>("/review/workflows", {
        policy_record_id: policy,
        audio_record_id: a.record_id,
        supersedes,
      });
      navigate("/review/" + w.workflow_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="page-heading">
        <h1>{supersedes ? "Superseding review" : "New narration review"}</h1>
        <p>Use a human-approved policy and original recording.</p>
      </header>
      <section className="panel narrow">
        {supersedes && (
          <p className="notice">
            Creating this workflow supersedes {supersedes}, invalidating its
            approvals while retaining history.
          </p>
        )}
        <label>
          Approved script & policy
          <select value={policy} onChange={(e) => setPolicy(e.target.value)}>
            <option value="">Select approved policy</option>
            {policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.payload.script.id} · script {p.payload.script.revision} ·
                policy {p.payload.policy.revision}
              </option>
            ))}
          </select>
        </label>
        {!policies.length && (
          <p>
            No approved policies.{" "}
            <Link to="/policies">Create and approve one.</Link>
          </p>
        )}
        <fieldset disabled={busy}>
          <AudioInput
            file={file}
            onChange={setFile}
            maxSeconds={1200}
            maxBytes={25_000_000}
          />
          <button disabled={!file || !policy || busy} onClick={create}>
            {busy ? "Uploading and creating review…" : "Create review"}
          </button>
        </fieldset>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </section>
    </>
  );
}
