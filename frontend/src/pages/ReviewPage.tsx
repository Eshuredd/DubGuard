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
import { TextComparison } from "../components/TextComparison";
import {
  EvidenceInspector,
  type Selection,
} from "../components/EvidenceInspector";
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
    [editorReset, setEditorReset] = useState(0),
    [selectedFinding, setSelectedFinding] = useState<Selection>({
      kind: "local",
      index: 0,
    });
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
    setSelectedFinding({ kind: "local", index: 0 });
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
  const localReview = run
    ? {
        ...run,
        findings: run.findings.filter(
          (f) => !f.rule_id.startsWith("SEMANTIC."),
        ),
      }
    : null;
  const amdReview = run?.findings.some((f) => f.rule_id.startsWith("SEMANTIC."))
    ? {
        ...run,
        findings: run.findings.filter((f) => f.rule_id.startsWith("SEMANTIC.")),
      }
    : null;
  const selectedKind = run?.findings[selectedFinding.index]?.rule_id.startsWith(
    "SEMANTIC.",
  )
    ? "amd"
    : "local";
  const inspectorSelection: Selection = {
    kind: selectedKind,
    index: Math.max(
      0,
      (selectedKind === "amd" ? amdReview : localReview)?.findings.findIndex(
        (f) => f === run?.findings[selectedFinding.index],
      ) ?? 0,
    ),
  };
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
      <section
        className="next-action review-next"
        aria-label="Next review action"
      >
        <div>
          <span className="eyebrow">
            {finalized.has(w.state) ? "REVIEW HISTORY" : "NEXT HUMAN ACTION"}
          </span>
          <h2>
            {finalized.has(w.state)
              ? "This review is finalized"
              : pending.has(w.state)
                ? "Processing evidence"
                : w.state.endsWith("FAILED")
                  ? "Processing needs attention"
                  : dirty
                    ? "Save your transcript corrections"
                    : !data.transcription
                      ? "Transcribe the original recording"
                      : !data.verified_evidence
                        ? "Listen and confirm the spoken words"
                        : !run
                          ? "Verify the saved evidence revision"
                          : run.decision === "CRITICAL_DEVIATION"
                            ? "A new recording is required"
                            : !canApprove
                              ? "Resolve the approval blockers"
                              : "Make an explicit human decision"}
          </h2>
          <p>
            {finalized.has(w.state)
              ? "The decision and its exact evidence are preserved in history."
              : pending.has(w.state)
                ? "Results update automatically. No completion estimate is available."
                : !data.verified_evidence
                  ? "Approval is blocked until human evidence and verification prerequisites are met. Recognizer output alone does not establish what was spoken."
                  : "Approval requires complete human evidence, resolved checks and a decision on this exact verification run."}
          </p>
        </div>
        {!pending.has(w.state) && (
          <a
            className="button secondary"
            href={
              finalized.has(w.state)
                ? "#audit"
                : w.state.endsWith("FAILED")
                  ? "#audit"
                  : !data.transcription
                    ? "#transcription"
                    : dirty || !data.verified_evidence
                      ? "#human-evidence"
                      : !run
                        ? "#run-verification"
                        : "#signoff"
            }
          >
            {finalized.has(w.state)
              ? "View decision history"
              : !data.transcription
                ? "Review source"
                : dirty || !data.verified_evidence
                  ? "Confirm human evidence"
                  : !run
                    ? "Run verification"
                    : "Review decision blockers"}
          </a>
        )}
      </section>
      <nav className="review-stages" aria-label="Review stages">
        <a href="#approved-script" data-stage="approved">
          <b>01</b> Approved script
        </a>
        <a href="#original-audio" data-stage="available">
          <b>02</b> Original recording
        </a>
        <a
          href="#transcription"
          data-stage={
            w.confirmed_alignment_record_id
              ? "mapped"
              : data.transcription
                ? "confirm mapping"
                : "pending"
          }
        >
          <b>03</b> Transcription & alignment
        </a>
        {data.transcription ? (
          <a
            href="#human-evidence"
            data-stage={
              data.verified_evidence?.transcript.completeness === "complete"
                ? "saved"
                : "required"
            }
          >
            <b>04</b> Human confirmation
          </a>
        ) : (
          <span>
            <b>04</b> Human confirmation · waiting
          </span>
        )}
        {run ? (
          <a
            href="#verification"
            data-stage={
              run.decision === "PASS_CANDIDATE" ? "candidate" : "needs review"
            }
          >
            <b>05</b> Verification findings
          </a>
        ) : (
          <span>
            <b>05</b> Verification · waiting
          </span>
        )}
        {data.acoustic ? (
          <a
            href="#acoustic"
            data-stage={data.acoustic_resolution ? "resolved" : "inspect"}
          >
            <b>06</b> Acoustic resolution
          </a>
        ) : (
          <span>
            <b>06</b> Acoustic recheck · not run
          </span>
        )}
        {run ? (
          <a
            href="#signoff"
            data-stage={
              finalized.has(w.state)
                ? w.state.toLowerCase()
                : canApprove
                  ? "human decision"
                  : "blocked"
            }
          >
            <b>07</b> Human sign-off
          </a>
        ) : (
          <span>
            <b>07</b> Human sign-off · waiting
          </span>
        )}
        <a href="#audit" data-stage="available">
          <b>08</b> Audit & export
        </a>
      </nav>
      <section className="panel sticky-audio" id="original-audio">
        <div className="section-heading">
          <strong>Original recording</strong>
          <small>
            {data.audio_artifact.duration_seconds.toFixed(2)} s ·{" "}
            {data.audio_artifact.format.toUpperCase()}
          </small>
        </div>
        <AudioPlayer
          segments={data.transcription?.transcript.segments}
          path={"/review/artifacts/" + w.audio_record_id + "/audio"}
          audioRef={audio}
        />
        <details className="audio-identity">
          <summary>Audio identity & provenance</summary>
          <small className="identity">
            Original SHA-256 {data.audio_artifact.sha256} ·{" "}
            {data.audio_artifact.duration_seconds.toFixed(2)} seconds ·{" "}
            {data.audio_artifact.format}
          </small>
        </details>
      </section>
      <div className="review-evidence-grid">
        <section className="panel" id="approved-script">
          <h2 id="transcription">Compare the narration</h2>
          <TextComparison
            approvedLines={data.approved_policy.script.instructions.map(
              (i) => ({ id: i.id, text: i.text }),
            )}
            recognizedLines={
              (
                data.verified_evidence?.transcript ||
                data.transcription?.transcript
              )?.segments
            }
            onSeek={(seconds) => jump(audio.current, seconds)}
            activeIds={
              run?.findings[selectedFinding.index]?.instruction_ids || []
            }
            approved={data.approved_policy.script.instructions
              .map((i) => i.text)
              .join(" ")}
            recognized={
              (
                data.verified_evidence?.transcript ||
                data.transcription?.transcript
              )?.segments
                .map((s) => s.text)
                .join(" ") || ""
            }
            verified={!!data.verified_evidence}
          />
          {data.transcription ? (
            <>
              <Coverage data={data.transcription.coverage} />
              {data.transcription.uncertainty?.map((u, i) => (
                <p className="notice" key={i}>
                  {u}
                </p>
              ))}
              <details>
                <summary>Raw ASR & timestamped source evidence</summary>
                <h3>Raw ASR · unverified</h3>
                <TranscriptView
                  transcript={data.transcription.transcript}
                  onSeek={(s) => jump(audio.current, s)}
                />
                <EvidenceTimeline
                  transcript={data.transcription.transcript}
                  onSeek={(s) => jump(audio.current, s)}
                />
                <small>
                  {data.transcription.provider} · {data.transcription.model} ·{" "}
                  {data.transcription.processing_seconds.toFixed(2)} seconds
                  processing
                </small>
              </details>
            </>
          ) : (
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
          )}
          <details>
            <summary>Approved policy, requirements & permitted wording</summary>
            <p>Approved by {data.approved_policy.policy.approved_by}</p>
            {data.approved_policy.script.instructions.map((i) => (
              <article key={i.id}>
                <h3>{i.id}</h3>
                <p>{i.text}</p>
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
                  ? " · " + c.approved_phrase + " / " + c.reversed_phrase
                  : c.kind === "sequence"
                    ? " · " + c.instruction_ids.join(" → ")
                    : ""}
              </p>
            ))}
          </details>
        </section>
        {data.transcription && (
          <>
            <section className="panel human-evidence-panel">
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
              <div id="human-evidence" />
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
          </>
        )}
      </div>
      {data.transcription && (
        <>
          <div className="review-tools-grid">
            <section className="panel alignment-panel">
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
                      {p.instruction_ids.join(", ") || "unmatched"} · {p.status}{" "}
                      · {p.match_type}
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
            <section className="panel verification-controls">
              <h2 id="run-verification">Run verification</h2>
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
                Acoustic recheck requires a separate cached local model; no
                model is downloaded automatically.
              </p>
            </section>
          </div>
          {data.acoustic && (
            <section className="panel">
              <h2 id="acoustic">Independent acoustic evidence</h2>
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
            <section className="panel decision-panel">
              <div id="verification" />
              <div className="review-findings-grid">
                <div>
                  <Findings
                    result={run}
                    idPrefix="review-finding"
                    selectedIndex={selectedFinding.index}
                    provisional={!data.verified_evidence}
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
                </div>
                <EvidenceInspector
                  local={localReview}
                  semantic={amdReview}
                  selected={inspectorSelection}
                  onSelect={(selection) => {
                    const group =
                      selection.kind === "amd" ? amdReview : localReview;
                    const originalIndex = run.findings.indexOf(
                      group!.findings[selection.index],
                    );
                    setSelectedFinding({
                      kind: selection.kind,
                      index: originalIndex,
                    });
                    requestAnimationFrame(() => {
                      const node = document.getElementById(
                        "review-finding-" + originalIndex,
                      );
                      node?.focus({ preventScroll: true });
                      node?.scrollIntoView({ block: "nearest" });
                    });
                  }}
                >
                  <label>
                    Finding action reason
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Explain your review decision…"
                      disabled={locked || dirty}
                    />
                  </label>
                </EvidenceInspector>
              </div>
              <p>
                {accepted} / {run.findings.length} checks explicitly reviewed
                for this run.
              </p>
              <small className="identity">
                Run {w.verification_record_id} · Human evidence{" "}
                {w.evidence_record_id || "not recorded"}
              </small>
              <h2 id="signoff">Final human decision</h2>
              <div
                className={
                  canApprove ? "approval-state ready" : "approval-state"
                }
              >
                <strong>
                  {finalized.has(w.state)
                    ? "This review is finalized"
                    : canApprove
                      ? "Evidence prerequisites met — human decision required"
                      : "Approval is blocked"}
                </strong>
                <p>
                  {finalized.has(w.state)
                    ? "This decision is retained against its exact evidence and verification run. Create a superseding review for a new recording or further changes."
                    : dirty
                      ? "Save your transcript corrections and run verification again."
                      : !data.verified_evidence
                        ? "Listen to the original recording and save complete human evidence."
                        : run.decision === "CRITICAL_DEVIATION"
                          ? "A critical deviation requires a new recording; ordinary approval is blocked."
                          : run.decision !== "PASS_CANDIDATE"
                            ? "Resolve uncertain or conflicting evidence and reverify this revision."
                            : accepted !== run.findings.length
                              ? "Explicitly review every satisfied check for this exact verification run."
                              : "Record your decision reason and confirm the exact evidence and run below. The server rechecks every prerequisite."}
                </p>
              </div>
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
      <section className="panel audit-panel">
        <h2 id="audit">Audit & evidence history</h2>
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
