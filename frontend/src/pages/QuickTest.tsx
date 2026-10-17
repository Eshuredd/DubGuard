import { useEffect, useRef, useState } from "react";
import { ApiError, request, upload, type Scenario, type Quick } from "../api";
import { AudioInput, AudioPlayer, jump } from "../components/Audio";
import {
  Findings,
  TranscriptView,
  Coverage,
  Badge,
  EvidenceTimeline,
} from "../components/Evidence";
export function QuickTest() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]),
    [selected, setSelected] = useState("correct"),
    [file, setFile] = useState<File | null>(null),
    [code, setCode] = useState(""),
    [credential, setCredential] = useState(
      () => sessionStorage.getItem("dubguard-demo") || "",
    ),
    [report, setReport] = useState<Quick | null>(null),
    [busy, setBusy] = useState(false),
    [mode, setMode] = useState<"local" | "amd">("local"),
    [consent, setConsent] = useState(false),
    [error, setError] = useState("");
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    request<Scenario[]>("/quick/scenarios", {}, "")
      .then(setScenarios)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!credential) {
      setReport(null);
      return;
    }
    let alive = true;
    let timeout: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const r = await request<Quick>("/quick/session", {}, credential);
        if (!alive) return;
        setReport(r);
        if (r.scenario_id) setSelected(r.scenario_id);
        if (r.state === "PROCESSING") timeout = setTimeout(poll, 1200);
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          if (e instanceof ApiError && e.status === 401) {
            sessionStorage.removeItem("dubguard-demo");
            setCredential("");
          }
        }
      }
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timeout);
    };
  }, [credential, busy]);
  async function open() {
    setBusy(true);
    setError("");
    try {
      const r = await request<{ token: string }>(
        "/quick/sessions",
        { method: "POST", headers: { "X-Demo-Code": code } },
        "",
      );
      sessionStorage.setItem("dubguard-demo", r.token);
      setCredential(r.token);
      setCode("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function analyze() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await upload(
        "/quick/analyze?scenario_id=" +
          encodeURIComponent(selected) +
          `&mode=${mode}&consent=${mode === "amd" && consent}`,
        file,
        credential,
      );
      setFile(null);
      setConsent(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function discard() {
    try {
      await request("/quick/session", { method: "DELETE" }, credential);
      sessionStorage.removeItem("dubguard-demo");
      setCredential("");
      setFile(null);
      setError("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        sessionStorage.removeItem("dubguard-demo");
        setCredential("");
        setFile(null);
      } else setError((e as Error).message);
    }
  }
  const scenario = scenarios.find((s) => s.id === selected);
  const processing = busy || report?.state === "PROCESSING";
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">INTERACTIVE SANDBOX</span>
        <h1>Hear what changed.</h1>
        <p>
          Try a short narration. Compare the words heard against a protected
          instruction.
        </p>
      </header>
      <div className="notice">
        Demonstration fixtures · English, one speaker · No organizational policy
        approval or release signoff. Local Verification is the default. AMD
        Semantic Review sends text only after your explicit consent.
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!credential ? (
        <section className="panel narrow">
          <h2>Start a private test session</h2>
          <p>
            Ask the demo operator for an access code. Audio expires after 30
            minutes; each session allows three attempts.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void open();
            }}
          >
            <label>
              Demo access code
              <input
                type="password"
                autoComplete="off"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
              />
            </label>
            <button disabled={busy || !code}>Start Quick Test</button>
          </form>
        </section>
      ) : (
        <>
          <div className="session-bar">
            <span>
              Private session · {report?.runs ?? 0}/3 attempts · expires{" "}
              {report
                ? new Date(report.expires_at * 1000).toLocaleTimeString()
                : "…"}
              {` · ${report?.amd_runs ?? 0}/2 AMD runs`}
            </span>
            <button className="text-button" onClick={discard}>
              Delete session and audio
            </button>
          </div>
          <div className="two-column">
            <section className="panel">
              <h2>1. Choose a scenario</h2>
              <div className="scenario-grid">
                {scenarios.map((s) => (
                  <button
                    key={s.id}
                    disabled={processing}
                    className={
                      "scenario " + (selected === s.id ? "selected" : "")
                    }
                    aria-pressed={selected === s.id}
                    onClick={() => setSelected(s.id)}
                  >
                    {s.title}
                  </button>
                ))}
              </div>
              {scenario && (
                <>
                  <span className="eyebrow">DEMONSTRATION SCRIPT</span>
                  {scenario.policy.script.instructions.map((i) => (
                    <blockquote key={i.id}>{i.text}</blockquote>
                  ))}
                  <h3>Protected requirements</h3>
                  {scenario.policy.policy.constraints.map((c) => (
                    <p key={c.id}>
                      <strong>{c.kind}</strong> ·{" "}
                      {c.kind === "polarity"
                        ? `${c.approved_phrase} must not become ${c.reversed_phrase}`
                        : c.kind === "numeric"
                          ? "Keep every value, range and unit unchanged."
                          : c.kind === "sequence"
                            ? "Keep the declared operation order."
                            : "Preserve this warning."}
                    </p>
                  ))}
                  {scenario.policy.script.instructions
                    .flatMap((i) => i.approved_variants ?? [])
                    .map((v, i) => (
                      <p key={i}>Permitted wording: “{v.text}”</p>
                    ))}
                </>
              )}
            </section>
            <section className="panel">
              <h2>2. Add your voice</h2>
              <fieldset disabled={processing}>
                <label>
                  Verification mode
                  <select
                    value={mode}
                    onChange={(e) => {
                      setMode(e.target.value as "local" | "amd");
                      setConsent(false);
                    }}
                  >
                    <option value="local">Local Verification</option>
                    <option value="amd">AMD Semantic Review</option>
                  </select>
                </label>
                {mode === "amd" && (
                  <div className="notice">
                    <p>
                      DeepSeek-V4-Flash reviews the approved script, policy and
                      provisional transcript through AMD Token Factory. Original
                      audio stays on this server. One HTTP attempt per run; two
                      AMD runs per session, including failures. Findings remain
                      advisory.
                    </p>
                    <label>
                      <input
                        type="checkbox"
                        checked={consent}
                        onChange={(e) => setConsent(e.target.checked)}
                      />
                      I consent to sending script, policy and transcript text to
                      AMD for this analysis.
                    </label>
                  </div>
                )}
                <AudioInput file={file} onChange={setFile} />
                <button
                  className="primary wide"
                  disabled={
                    !file ||
                    processing ||
                    (report?.runs ?? 0) >= 3 ||
                    (mode === "amd" &&
                      (!consent || (report?.amd_runs ?? 0) >= 2))
                  }
                  onClick={analyze}
                >
                  Analyze recording
                </button>
              </fieldset>
              {processing && (
                <p role="status">
                  Processing original audio with local ASR… Keep this session
                  open. You can refresh safely.{" "}
                  {report?.mode === "amd" &&
                    `AMD status: ${report.semantic_status}. Requested model: DeepSeek-V4-Flash.`}
                </p>
              )}
            </section>
          </div>
          {report?.error && (
            <p role="alert" className="error">
              {report.error}
            </p>
          )}
          {report?.artifact && (
            <section className="panel">
              <h2>3. Review actual evidence</h2>
              <p>
                Analyzed scenario:{" "}
                <strong>
                  {scenarios.find((s) => s.id === report.scenario_id)?.title ||
                    report.scenario_id}
                </strong>
                .{" "}
                {selected !== report.scenario_id &&
                  "The selected scenario has changed; these results still belong to the previous analysis."}
              </p>
              <Badge value={report.state} />
              <AudioPlayer
                key={report.runs}
                path="/quick/audio"
                credential={credential}
                audioRef={audio}
              />
              <small className="identity">
                SHA-256 {report.artifact.sha256} ·{" "}
                {report.artifact.duration_seconds.toFixed(2)} s ·{" "}
                {report.artifact.format}
              </small>
              {report.transcription && (
                <>
                  <Coverage data={report.transcription.coverage} />
                  <EvidenceTimeline
                    transcript={report.transcription.transcript}
                    onSeek={(s) => jump(audio.current, s)}
                  />
                  <h3>Raw ASR · unverified</h3>
                  <TranscriptView
                    transcript={report.transcription.transcript}
                    onSeek={(s) => jump(audio.current, s)}
                  />
                  <p>
                    Acoustic recheck not run in Quick Test. Recognizer output
                    does not prove what was spoken.
                  </p>
                </>
              )}
              {report.alignment && (
                <details>
                  <summary>Tentative alignment</summary>
                  {report.alignment.proposals.map((p, i) => (
                    <p key={i}>
                      {p.segment_ids.join(", ")} →{" "}
                      {p.instruction_ids.join(", ") || "unmatched"} · {p.status}
                    </p>
                  ))}
                </details>
              )}
              {report.verification && (
                <>
                  <h3>Local deterministic checks · provisional ASR</h3>
                  <Findings
                    result={report.verification}
                    onSeek={(s) => jump(audio.current, s)}
                  />
                </>
              )}
              {report.mode === "amd" && (
                <section aria-label="AMD Semantic Review result">
                  <h3>AMD Semantic Review · DeepSeek-V4-Flash</h3>
                  <p>
                    Status: {report.semantic_status.replaceAll("_", " ")}.
                    Consent recorded{" "}
                    {report.consented_at
                      ? new Date(
                          report.consented_at * 1000,
                        ).toLocaleTimeString()
                      : "not available"}
                    .
                  </p>
                  <p>
                    Source validation checks citations against supplied text; it
                    does not verify spoken words or establish semantic accuracy.
                    Unsupported citations require review. AMD cannot approve a
                    recording.
                  </p>
                  {report.semantic_verification && (
                    <Findings
                      title="AMD semantic findings"
                      result={{
                        ...report.semantic_verification,
                        findings: report.semantic_verification.findings.filter(
                          (f) => f.rule_id.startsWith("SEMANTIC."),
                        ),
                      }}
                      onSeek={(s) => jump(audio.current, s)}
                    />
                  )}
                </section>
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
