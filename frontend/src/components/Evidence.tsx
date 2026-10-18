import type { Review, Transcript, Schema } from "../api";
function Difference({
  approved,
  observed,
}: {
  approved: string;
  observed: string;
}) {
  if (!approved || approved === observed) return <>{observed}</>;
  let a = 0,
    b = 0;
  while (
    a < Math.min(approved.length, observed.length) &&
    approved[a] === observed[a]
  )
    a++;
  while (
    b < Math.min(approved.length - a, observed.length - a) &&
    approved[approved.length - 1 - b] === observed[observed.length - 1 - b]
  )
    b++;
  return (
    <>
      {observed.slice(0, a)}
      <mark>{observed.slice(a, observed.length - b)}</mark>
      {observed.slice(observed.length - b)}
    </>
  );
}
export function EvidenceTimeline({
  transcript,
  onSeek,
}: {
  transcript: Transcript;
  onSeek: (s: number | null | undefined) => void;
}) {
  return (
    <section className="timeline" aria-label="Evidence timeline">
      <h3>Evidence timeline</h3>
      <p>
        Jump to a recognized segment in the original audio. These are
        approximate ASR spans.
      </p>
      <div className="actions">
        {transcript.segments
          .filter((s) => s.start_seconds != null)
          .map((s) => (
            <button
              key={s.id}
              className="secondary"
              onClick={() => onSeek(s.start_seconds)}
              title={s.text}
            >
              {s.start_seconds?.toFixed(2)}–{s.end_seconds?.toFixed(2)} s ·{" "}
              {s.id}
            </button>
          ))}
      </div>
      {!transcript.segments.some((s) => s.start_seconds != null) && (
        <small>No timestamped spans available.</small>
      )}
    </section>
  );
}
export function Badge({ value }: { value: string }) {
  const label =
    value === "PASS_CANDIDATE"
      ? "Pass candidate · not approval"
      : value.replaceAll("_", " ").toLowerCase();
  return (
    <span
      className={
        "badge " +
        (value === "CRITICAL_DEVIATION" || value === "VIOLATION"
          ? "critical"
          : value === "APPROVED" || value === "SATISFIED"
            ? "satisfied"
            : "review")
      }
    >
      {label}
    </span>
  );
}
export function Findings({
  result,
  onSeek,
  onAccept,
  onDecision,
  disabled = false,
  title = "Verification findings",
}: {
  result: Review;
  onSeek: (s: number | null | undefined) => void;
  onAccept?: (i: number) => void;
  onDecision?: (
    i: number,
    decision: "CORRECTION_REQUIRED" | "RERECORD_REQUIRED" | "ESCALATED",
  ) => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <section>
      <div className="section-heading">
        <h2>{title}</h2>
        <Badge value={result.decision} />
      </div>
      <p className="notice">{result.safety_notice}</p>
      <p className="finding-guidance">
        {result.decision === "CRITICAL_DEVIATION"
          ? "Critical deviation confirmed from human-verified evidence. A new recording is required."
          : result.decision === "PASS_CANDIDATE"
            ? "No confirmed policy violation from current evidence. Human review and sign-off prerequisites still apply."
            : "Needs human confirmation. Listen to the cited source, confirm the actual words and resolve uncertain evidence before deciding."}
      </p>
      {result.semantic && (
        <p className="notice">
          Semantic provider: {result.semantic.provider} ·{" "}
          {result.semantic.model || "no model response"} ·{" "}
          {result.semantic.status} · {result.semantic.explanation}
          {result.semantic.latency_ms != null &&
            ` · ${(result.semantic.latency_ms / 1000).toFixed(2)} seconds`}
          {` · ${result.semantic.attempts ?? 0} HTTP attempts`}
          {result.semantic.error_class && ` · ${result.semantic.error_class}`}
          {result.semantic.call_id && ` · Call ${result.semantic.call_id}`}
        </p>
      )}
      {!result.findings.length && (
        <p>
          No findings returned. Coverage and human evidence prerequisites still
          apply.
        </p>
      )}
      {result.findings.map((f, i) => (
        <article className={"finding " + f.status.toLowerCase()} key={i}>
          <div className="section-heading">
            <strong>
              {f.rule_id.startsWith("ASR.SUSPECTED")
                ? "Potential instruction mismatch"
                : f.rule_id.startsWith("SEMANTIC")
                  ? "Semantic advisory"
                  : f.rule_id.startsWith("ACOUSTIC")
                    ? "Acoustic evidence"
                    : f.rule_id.replaceAll(".", " · ").replaceAll("_", " ")}
            </strong>
            <Badge value={f.status} />
          </div>
          <small>
            Requirement {f.constraint_id || "evidence quality"} · {f.rule_id}
          </small>
          <div className="comparison">
            <div>
              <span>Approved</span>
              {f.approved.map((e, j) => (
                <p key={j}>{e.text}</p>
              ))}
            </div>
            <div>
              <span>Observed</span>
              {f.observed.length ? (
                f.observed.map((e, j) => (
                  <p key={j}>
                    <Difference
                      approved={
                        f.approved.find(
                          (a) => a.instruction_id === e.instruction_id,
                        )?.text || ""
                      }
                      observed={e.text}
                    />
                    {e.start_seconds != null && (
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => onSeek(e.start_seconds)}
                      >
                        ▶ {e.start_seconds.toFixed(2)}–
                        {e.end_seconds?.toFixed(2)} s
                      </button>
                    )}
                  </p>
                ))
              ) : (
                <p>No observed span supplied.</p>
              )}
            </div>
          </div>
          <p>{f.explanation}</p>
          {!!(f.approved.length + f.observed.length) && (
            <details className="source-references">
              <summary>Source references & exact text spans</summary>
              {[...f.approved, ...f.observed].map((e, j) => (
                <p key={j}>
                  <strong>
                    {e.source === "approved"
                      ? "Approved script"
                      : "Observed evidence"}
                  </strong>{" "}
                  · {e.instruction_id || "unmapped instruction"}{" "}
                  {e.segment_id && `· Segment ${e.segment_id}`} · characters{" "}
                  {e.start_char}–{e.end_char}
                  <br />
                  <q>{e.text}</q>
                </p>
              ))}
            </details>
          )}
          {f.provider && (
            <small>
              {f.provider} · Call {f.model_call_id || "not supplied"}
            </small>
          )}
          {onDecision && (
            <div className="actions">
              <button
                className="secondary"
                disabled={disabled}
                onClick={() => onDecision(i, "CORRECTION_REQUIRED")}
              >
                Request evidence correction
              </button>
              <button
                className="secondary"
                disabled={disabled}
                onClick={() => onDecision(i, "RERECORD_REQUIRED")}
              >
                Request new recording
              </button>
              <button
                className="secondary"
                disabled={disabled}
                onClick={() => onDecision(i, "ESCALATED")}
              >
                Escalate to reviewer
              </button>
            </div>
          )}
          {onAccept && f.status === "SATISFIED" && (
            <button
              className="secondary"
              disabled={disabled}
              onClick={() => onAccept(i)}
            >
              Mark check reviewed
            </button>
          )}
        </article>
      ))}
    </section>
  );
}
export function TranscriptView({
  transcript,
  onSeek,
}: {
  transcript: Transcript;
  onSeek: (s: number | null | undefined) => void;
}) {
  return (
    <div className="transcript">
      {!transcript.segments.length && (
        <p>No spoken segments were recognized. Review the original audio.</p>
      )}
      {transcript.segments.map((s) => (
        <div className="segment" key={s.id}>
          <button
            className="timestamp"
            disabled={s.start_seconds == null}
            onClick={() => onSeek(s.start_seconds)}
          >
            {s.start_seconds?.toFixed(2) ?? "—"} s
          </button>
          <div>
            <p>{s.text || "[no text]"}</p>
            <small>
              {s.id} · {s.instruction_id || "unmapped"}
              {s.uncertain ? " · uncertain" : ""}
            </small>
          </div>
        </div>
      ))}
    </div>
  );
}
export function Coverage({ data }: { data: Schema["AudioCoverage"] }) {
  return (
    <div className="notice">
      <strong>
        {data.processed_seconds.toFixed(2)} / {data.duration_seconds.toFixed(2)}{" "}
        seconds processed
      </strong>
      <p>{data.note}</p>
      {data.gaps.map((g, i) => (
        <p key={i}>
          Gap {g.start_seconds.toFixed(2)}–{g.end_seconds.toFixed(2)} s ·{" "}
          {g.classification.replaceAll("_", " ")}
        </p>
      ))}
    </div>
  );
}
