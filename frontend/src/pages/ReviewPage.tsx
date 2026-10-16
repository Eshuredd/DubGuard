import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  request,
  post,
  saveJSON,
  type Workflow,
  type Transcript,
} from "../api";
import { AudioPlayer, jump } from "../components/Audio";
import {
  Badge,
  Coverage,
  Findings,
  TranscriptView,
  EvidenceTimeline,
} from "../components/Evidence";
const pending = new Set(["TRANSCRIBING", "VERIFYING", "ACOUSTIC_RECHECKING"]);
const finalized = new Set(["APPROVED", "REJECTED", "SUPERSEDED"]);
function TranscriptEditor({
  data,
  save,
  disabled,
  onDirty,
}: {
  data: Workflow;
  save: (body: unknown) => Promise<void>;
  disabled: boolean;
  onDirty: () => void;
}) {
  const original =
    data.verified_evidence?.transcript || data.transcription?.transcript;
  const [segments, setSegments] = useState(() =>
      structuredClone(original?.segments || []),
    ),
    [complete, setComplete] = useState(false),
    [listened, setListened] = useState(false),
    [reason, setReason] = useState("");
  function changeSegments(value: Parameters<typeof setSegments>[0]) {
    onDirty();
    setSegments(value);
  }
  function update(index: number, field: string, value: unknown) {
    onDirty();
    changeSegments((old) =>
      old.map((s, i) => (i === index ? { ...s, [field]: value } : s)),
    );
  }
  return (
    <section>
      <h2>Human transcript evidence</h2>
      <p>
        Enter what was actually spoken, including mistakes. This preserves the
        raw ASR. Do not rewrite an incorrect recording to match the script.
      </p>
      <fieldset disabled={disabled}>
        {segments.map((s, index) => (
          <div className="editor-block" key={s.id}>
            <label>
              Actual spoken text · {s.id}
              <textarea
                value={s.text}
                onChange={(e) => update(index, "text", e.target.value)}
              />
            </label>
            <div className="form-grid">
              <label>
                Instruction mapping
                <select
                  aria-label="Instruction mapping"
                  value={s.instruction_id || ""}
                  onChange={(e) =>
                    update(index, "instruction_id", e.target.value || null)
                  }
                >
                  <option value="">Unmapped / extra narration</option>
                  {data.approved_policy.script.instructions.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.id} · {i.text}
                    </option>
                  ))}
                </select>
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={s.uncertain ?? false}
                  onChange={(e) => update(index, "uncertain", e.target.checked)}
                />
                Still unclear or uncertain
              </label>
              <label>
                Start seconds (optional)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={s.start_seconds ?? ""}
                  onChange={(e) =>
                    update(
                      index,
                      "start_seconds",
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                />
              </label>
              <label>
                End seconds (optional)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={s.end_seconds ?? ""}
                  onChange={(e) =>
                    update(
                      index,
                      "end_seconds",
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                />
              </label>
            </div>
            <button
              className="text-button"
              onClick={() =>
                changeSegments((old) => old.filter((_, i) => i !== index))
              }
            >
              Remove segment
            </button>
          </div>
        ))}
        <button
          className="secondary"
          onClick={() =>
            changeSegments((old) => [
              ...old,
              {
                id: "human-" + crypto.randomUUID(),
                text: "",
                instruction_id: null,
                uncertain: true,
              },
            ])
          }
        >
          Add spoken segment
        </button>
        <label className="check">
          <input
            type="checkbox"
            checked={listened}
            onChange={(e) => setListened(e.target.checked)}
          />
          I listened to the original audio and entered the actual spoken words.
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={complete}
            onChange={(e) => setComplete(e.target.checked)}
          />
          I reviewed the entire recording, including gaps; this transcript
          accounts for all spoken content.
        </label>
        <label>
          Correction / verification reason
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Describe what you checked or corrected."
          />
        </label>
        <button
          disabled={!listened || !reason.trim()}
          onClick={() =>
            save({
              expected_revision: data.workflow.revision,
              listened_to_original: true,
              reason,
              transcript: {
                source: "manual",
                completeness: complete ? "complete" : "unknown",
                segments: segments.map((s) => ({
                  ...s,
                  confidence: null,
                  uncertainty_reason: s.uncertain
                    ? "Human review: still unclear"
                    : null,
                })),
              },
            })
          }
        >
          Save human evidence revision
        </button>
      </fieldset>
    </section>
  );
}
export function ReviewPage() {
  const { id } = useParams();
  const [data, setData] = useState<Workflow | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [reason, setReason] = useState(""),
    [signAttest, setSignAttest] = useState(false),
    [resolveAttest, setResolveAttest] = useState(false),
    [dirty, setDirty] = useState(false),
    [editorReset, setEditorReset] = useState(0);
  const audio = useRef<HTMLAudioElement>(null);
  const base = "/review/workflows/" + id;
  async function refresh() {
    const next = await request<Workflow>(base);
    setData(next);
    return next;
  }
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await request<Workflow>(base);
        if (!alive) return;
        setData(next);
        if (pending.has(next.workflow.state)) timer = setTimeout(poll, 1500);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [base, busy]);
  useEffect(() => {
    setSignAttest(false);
    setResolveAttest(false);
  }, [
    data?.workflow.verification_record_id,
    data?.workflow.evidence_record_id,
  ]);
  useEffect(() => {
    const saved = data?.confirmed_alignment?.confirmations;
    setMapping(
      saved && typeof saved === "object"
        ? Object.fromEntries(
            Object.entries(saved).filter(
              (entry): entry is [string, string] =>
                typeof entry[1] === "string",
            ),
          )
        : {},
    );
  }, [data?.workflow.confirmed_alignment_record_id]);
  async function action(path: string, body?: unknown, message = "Saved.") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await post(base + path, body);
      await refresh();
      if (path === "/transcript-evidence") setDirty(false);
      setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return (
      <section className="panel">
        <p role={error ? "alert" : "status"}>
          {error || "Loading review evidence…"}
        </p>
        <Link to="/review">Back to reviews</Link>
      </section>
    );
  const w = data.workflow,
    locked = busy || pending.has(w.state) || finalized.has(w.state),
    run = data.verification;
  const latest = new Map<number, string>();
  data.finding_decisions.forEach((d) => {
    if (d.verification_record_id === w.verification_record_id)
      latest.set(Number(d.finding_index), String(d.decision));
  });
  const accepted =
    run?.findings.filter((_, i) => latest.get(i) === "ACCEPTED_AS_CORRECT")
      .length || 0;
  const canApprove =
    !dirty &&
    !!run &&
    run.decision === "PASS_CANDIDATE" &&
    !!data.verified_evidence &&
    data.verified_evidence.transcript.completeness === "complete" &&
    !!data.transcription?.coverage.complete_processing &&
    run.findings.every((f) => f.status === "SATISFIED") &&
    accepted === run.findings.length;
  const affected = data.acoustic
    ? [
        ...new Set([
          ...data.acoustic.assessment.disagreements.map(
            (d) => d.requirement_id,
          ),
          ...(data.acoustic.assessment.unresolved_requirement_ids ?? []),
        ]),
      ]
    : [];
  return (
    <>
      <header className="page-heading">
        <Link to="/review" className="back">
          ← All reviews
        </Link>
        <div className="section-heading">
          <div>
            <span className="eyebrow">EVIDENCE WORKSPACE</span>
            <h1>{data.approved_policy.script.id}</h1>
          </div>
          <Badge value={w.state} />
        </div>
        <p>
          Script revision {data.approved_policy.script.revision} · Policy
          revision {data.approved_policy.policy.revision} · Evidence revision{" "}
          {w.revision}
        </p>
        <div className="actions">
          <button
            className="secondary"
            onClick={async () => {
              try {
                saveJSON(
                  await request<Workflow>(base + "/export"),
                  `dubguard-${id}.json`,
                );
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Export evidence report
          </button>
          <Link
            className="button secondary"
            to={"/review/new?supersedes=" + id}
          >
            Create superseding review
          </Link>
        </div>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}{" "}
          <button
            className="text-button"
            onClick={() => refresh().catch((e) => setError(e.message))}
          >
            Reload current evidence
          </button>
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {pending.has(w.state) && (
        <p className="notice" role="status">
          {w.state.replaceAll("_", " ")}… Results will update automatically.
          Existing approvals cannot be reused.
        </p>
      )}
      {w.state.endsWith("FAILED") && (
        <p className="error" role="alert">
          Processing failed. No successful result is inferred. Check server
          dependencies; create a superseding review to retry failed processing.
        </p>
      )}
      <section className="panel sticky-audio">
        <AudioPlayer
          path={"/review/artifacts/" + w.audio_record_id + "/audio"}
          audioRef={audio}
        />
        <small className="identity">
          Original SHA-256 {data.audio_artifact.sha256} ·{" "}
          {data.audio_artifact.duration_seconds.toFixed(2)} seconds ·{" "}
          {data.audio_artifact.format}
        </small>
      </section>
      {data.transcription && (
        <section className="panel">
          <EvidenceTimeline
            transcript={data.transcription.transcript}
            onSeek={(s) => jump(audio.current, s)}
          />
        </section>
      )}
      <div className="two-column">
        <section className="panel">
          <h2>Approved script</h2>
          <small>Approved by {data.approved_policy.policy.approved_by}</small>
          {data.approved_policy.script.instructions.map((i) => (
            <article className="script-step" key={i.id}>
              <span className="eyebrow">{i.id}</span>
              <blockquote>{i.text}</blockquote>
              {i.approved_variants?.map((v, j) => (
                <p key={j}>Permitted: {v.text}</p>
              ))}
            </article>
          ))}
          <h3>Protected requirements</h3>
          {data.approved_policy.policy.constraints.map((c) => (
            <p key={c.id}>
              <strong>{c.id}</strong> · {c.kind}
              {c.kind === "polarity"
                ? ` · ${c.approved_phrase} / ${c.reversed_phrase}`
                : c.kind === "sequence"
                  ? ` · ${c.instruction_ids.join(" → ")}`
                  : ""}
            </p>
          ))}
        </section>
        <section className="panel">
          <h2>Raw ASR · unverified</h2>
          {!data.transcription ? (
            <>
              <p>
                No transcription is available. Local ASR needs an installed,
                cached model.
              </p>
              <button
                disabled={locked || w.state !== "DRAFT"}
                onClick={() =>
                  action(
                    "/transcribe",
                    undefined,
                    "Local transcription started.",
                  )
                }
              >
                Transcribe original audio
              </button>
            </>
          ) : (
            <>
              <Coverage data={data.transcription.coverage} />
              <TranscriptView
                transcript={data.transcription.transcript}
                onSeek={(s) => jump(audio.current, s)}
              />
              <small>
                {data.transcription.provider} · {data.transcription.model} ·{" "}
                {data.transcription.processing_seconds.toFixed(2)} seconds
                processing
              </small>
              {data.transcription.uncertainty?.map((u, i) => (
                <p className="notice" key={i}>
                  {u}
                </p>
              ))}
            </>
          )}
        </section>
      </div>
      {data.transcription && (
        <>
          <section className="panel">
            <h2>Alignment</h2>
            <p>
              Proposals help locate evidence. Confirming a mapping never
              verifies the spoken words.
            </p>
            <button
              className="secondary"
              disabled={locked || dirty}
              onClick={() => action("/alignments/propose")}
            >
              Propose alignment
            </button>
            {data.alignment && (
              <div className="notice">
                <p>
                  Missing:{" "}
                  {data.alignment.missing_instruction_ids.join(", ") ||
                    "none proposed"}{" "}
                  · Repeated:{" "}
                  {data.alignment.repeated_instruction_ids.join(", ") ||
                    "none proposed"}{" "}
                  · Extra:{" "}
                  {data.alignment.extra_segment_ids.join(", ") ||
                    "none proposed"}
                </p>
                {data.alignment.proposals.map((p, i) => (
                  <p key={i}>
                    {p.segment_ids.join(", ")} →{" "}
                    {p.instruction_ids.join(", ") || "unmatched"} · {p.status} ·{" "}
                    {p.match_type}
                  </p>
                ))}
              </div>
            )}
            {data.confirmed_alignment && (
              <p className="notice">
                Reviewer-confirmed raw-ASR mapping is saved. It does not clear
                uncertainty.
              </p>
            )}
            <fieldset disabled={locked || dirty}>
              {data.transcription.transcript.segments.map((s) => (
                <label key={s.id}>
                  {s.id} · {s.text}
                  <select
                    aria-label={"Map " + s.id}
                    value={mapping[s.id] ?? ""}
                    onChange={(e) =>
                      setMapping({ ...mapping, [s.id]: e.target.value })
                    }
                  >
                    <option value="">Select mapping / leave unmapped</option>
                    {data.approved_policy.script.instructions.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.id} · {i.text}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              <label>
                Review note / action reason
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Record why you are confirming, resolving, or deciding."
                />
              </label>
              <button
                disabled={!reason.trim()}
                onClick={() =>
                  action("/alignments/confirm", {
                    confirmations: Object.fromEntries(
                      Object.entries(mapping).filter(([, v]) => v),
                    ),
                    reason,
                  })
                }
              >
                Confirm selected mappings
              </button>
            </fieldset>
          </section>
          <section className="panel">
            {dirty && (
              <div className="notice" role="status">
                Unsaved transcript edits. Save and reverify before making a
                decision.{" "}
                <button
                  className="text-button"
                  onClick={() => {
                    setDirty(false);
                    setEditorReset((v) => v + 1);
                  }}
                >
                  Discard unsaved transcript edits
                </button>
              </div>
            )}
            <TranscriptEditor
              key={`${w.revision}-${editorReset}`}
              data={data}
              onDirty={() => {
                setDirty(true);
                setSignAttest(false);
              }}
              disabled={locked}
              save={(body) =>
                action(
                  "/transcript-evidence",
                  body,
                  "Human evidence saved. Run verification on this revision before making decisions.",
                )
              }
            />
          </section>
          <section className="panel">
            <h2>Run verification</h2>
            <div className="actions">
              <button
                disabled={locked || dirty}
                onClick={() =>
                  action(
                    "/verify",
                    undefined,
                    "Deterministic verification completed.",
                  )
                }
              >
                Verify with local rules
              </button>
              <button
                className="secondary"
                disabled={locked || dirty}
                onClick={() =>
                  action(
                    "/verify?mode=hybrid",
                    undefined,
                    "AMD semantic verification requested. Any unavailable or invalid evidence remains unresolved.",
                  )
                }
              >
                Run rules + AMD semantic check
              </button>
              <button
                className="secondary"
                disabled={locked || dirty || !w.confirmed_alignment_record_id}
                onClick={() =>
                  action(
                    "/acoustic-recheck",
                    undefined,
                    "Independent acoustic recheck requested.",
                  )
                }
              >
                Recheck protected audio
              </button>
            </div>
            <p>
              AMD selection sends script, policy and transcript to the
              configured DeepSeek provider. It cannot approve recordings.
              Acoustic recheck requires a separate cached local model; no model
              is downloaded automatically.
            </p>
          </section>
          {data.acoustic && (
            <section className="panel">
              <h2>Independent acoustic evidence</h2>
              <p>
                {data.acoustic.assessment.note} ·{" "}
                {data.acoustic.secondary_provider} /{" "}
                {data.acoustic.secondary_model}
              </p>
              {data.acoustic.assessment.disagreements.map((d, i) => (
                <article className="finding unresolved" key={i}>
                  <h3>{d.requirement_id}</h3>
                  <div className="comparison">
                    <div>
                      Primary<p>{d.primary_text}</p>
                    </div>
                    <div>
                      Secondary<p>{d.secondary_text}</p>
                    </div>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => jump(audio.current, d.start_seconds)}
                  >
                    Listen to original span
                  </button>
                </article>
              ))}
              <TranscriptView
                transcript={data.acoustic.secondary_transcript}
                onSeek={(s) => jump(audio.current, s)}
              />
              <p>
                Unresolved requirements:{" "}
                {data.acoustic.assessment.unresolved_requirement_ids.join(
                  ", ",
                ) || "none"}
              </p>
              {data.acoustic_resolution && (
                <p className="notice">
                  Human resolution is saved against exact acoustic and
                  transcript revisions. Re-run verification.
                </p>
              )}
              {affected.length > 0 && (
                <fieldset disabled={locked || dirty}>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={resolveAttest}
                      onChange={(e) => setResolveAttest(e.target.checked)}
                    />
                    I listened to every affected source span and verified the
                    saved human transcript for: {affected.join(", ")}.
                  </label>
                  <p>
                    Resolution preserves both hypotheses. Ambiguous or unmapped
                    human evidence cannot resolve a check.
                  </p>
                  <button
                    disabled={
                      !resolveAttest || !w.evidence_record_id || !reason.trim()
                    }
                    onClick={() =>
                      action("/acoustic-resolution", {
                        expected_revision: w.revision,
                        evidence_record_id: w.evidence_record_id,
                        acoustic_record_id: w.acoustic_record_id,
                        requirement_ids: affected,
                        listened_to_original: true,
                        reason,
                      })
                    }
                  >
                    Resolve against saved human evidence
                  </button>
                </fieldset>
              )}
            </section>
          )}
          {run && (
            <section className="panel">
              <Findings
                result={run}
                onSeek={(s) => jump(audio.current, s)}
                disabled={locked || dirty || !reason.trim()}
                onDecision={(i, decision) =>
                  action("/findings/" + i + "/decision", {
                    verification_record_id: w.verification_record_id,
                    decision,
                    reason,
                  })
                }
                onAccept={(i) =>
                  action("/findings/" + i + "/decision", {
                    verification_record_id: w.verification_record_id,
                    decision: "ACCEPTED_AS_CORRECT",
                    reason,
                  })
                }
              />
              <p>
                {accepted} / {run.findings.length} checks explicitly reviewed
                for this run.
              </p>
              <small className="identity">
                Run {w.verification_record_id} · Human evidence{" "}
                {w.evidence_record_id || "not recorded"}
              </small>
              <h2>Final human decision</h2>
              <p>
                PASS_CANDIDATE is not APPROVED. Critical or unresolved checks
                block approval. Actual spoken errors require a new recording.
              </p>
              <fieldset disabled={locked || dirty}>
                <label>
                  Final decision reason
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={signAttest}
                    onChange={(e) => setSignAttest(e.target.checked)}
                  />
                  I am making an explicit human decision on this exact
                  recording, evidence revision and verification run.
                </label>
                <div className="actions">
                  <button
                    disabled={!canApprove || !signAttest || !reason.trim()}
                    onClick={() =>
                      action(
                        "/signoff",
                        {
                          verification_record_id: w.verification_record_id,
                          decision: "APPROVED",
                          reason,
                        },
                        "Human approval recorded for this exact evidence and run.",
                      )
                    }
                  >
                    Approve recording
                  </button>
                  <button
                    className="danger"
                    disabled={!signAttest || !reason.trim()}
                    onClick={() =>
                      action(
                        "/signoff",
                        {
                          verification_record_id: w.verification_record_id,
                          decision: "REJECTED",
                          reason,
                        },
                        "Human rejection recorded.",
                      )
                    }
                  >
                    Reject recording
                  </button>
                </div>
              </fieldset>
            </section>
          )}
        </>
      )}
      <section className="panel">
        <h2>Audit & evidence history</h2>
        <p>History is preserved in SQLite; it is not tamper-proof.</p>
        {data.approvals.map((a, i) => (
          <p key={i}>
            <strong>{String(a.decision)}</strong> · {String(a.reviewer_id)} ·{" "}
            {String(a.status)} · {String(a.created_at)}
          </p>
        ))}
        {data.record_history.map((r, i) => (
          <details key={i}>
            <summary>
              {String(r.kind)} · {String(r.created_at)} ·{" "}
              {String(r.id).slice(0, 12)}
            </summary>
            <pre>{JSON.stringify(r.payload, null, 2)}</pre>
          </details>
        ))}
        <details>
          <summary>
            Authenticated audit events ({data.audit_events.length})
          </summary>
          {data.audit_events.map((e, i) => (
            <p key={i}>
              {String(e.created_at)} · {String(e.reviewer_id)} ·{" "}
              {String(e.event)}
            </p>
          ))}
        </details>
      </section>
    </>
  );
}
