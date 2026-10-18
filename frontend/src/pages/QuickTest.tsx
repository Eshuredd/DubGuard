import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  request,
  upload,
  type Scenario,
  type Quick,
  type QuickConfig,
} from "../api";
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
    [amdCode, setAmdCode] = useState(""),
    [config, setConfig] = useState<QuickConfig | null>(null),
    [error, setError] = useState("");
  const audio = useRef<HTMLAudioElement>(null);
  const submitted = useRef(false);
  useEffect(() => {
    request<QuickConfig>("/quick/config", {}, "")
      .then(setConfig)
      .catch((e) => setError(e.message));
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
        if (r.state !== "PROCESSING" && submitted.current) {
          submitted.current = false;
          requestAnimationFrame(() => {
            const evidence = document.getElementById("actual-evidence");
            evidence?.focus({ preventScroll: true });
            evidence?.scrollIntoView({ block: "start", behavior: "instant" });
          });
        }
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
      requestAnimationFrame(() =>
        document.getElementById("demo-workflow")?.focus(),
      );
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
        mode === "amd" ? { "X-AMD-Demo-Code": amdCode } : undefined,
      );
      setFile(null);
      submitted.current = true;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConsent(false);
      setBusy(false);
    }
  }
  async function discard() {
    setAmdCode("");
    setConsent(false);
    setMode("local");
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
      {!credential ? (
        <>
          <section className="product-hero" aria-labelledby="product-title">
            <div>
              <span className="eyebrow">
                NARRATION VERIFICATION · EVIDENCE FIRST
              </span>
              <h1 id="product-title">
                <span className="hero-brand">DubGuard —</span> Catch the one
                word that changes everything.
              </h1>
              <p className="hero-description">
                Verify recorded instructions against approved scripts using
                evidence-backed AI and human review.
              </p>
              <div className="actions">
                <a className="button" href="#quick-start">
                  Try DubGuard <span aria-hidden="true">↗</span>
                </a>
                <Link className="button secondary" to="/review">
                  Reviewer Workspace
                </Link>
              </div>
              <p className="hero-audience">
                For training, localization and quality assurance.
              </p>
            </div>
            <div className="illustration">
              <span className="eyebrow">
                ILLUSTRATIVE EXAMPLE · NOT AN ANALYSIS
              </span>
              <div className="example-line">
                <span>Approved instruction</span>
                <p>
                  Switch the power <strong>off.</strong>
                </p>
              </div>
              <div className="example-line observed">
                <span>Observed instruction</span>
                <p>
                  Switch the power <mark>on.</mark>
                </p>
              </div>
              <div className="example-change">
                <strong>off → on</strong>
                <span>A small change. A different instruction.</span>
              </div>
              <div className="example-types">
                <span>
                  Polarity <b>off → on</b>
                </span>
                <span>
                  Number <b>15 → 50</b>
                </span>
                <span>
                  Sequence <b>before → after</b>
                </span>
              </div>
            </div>
          </section>
          <div className="method-strip" aria-label="How DubGuard works">
            <div>
              <span>01 / LOCAL RULES</span>
              <p>Check values, warnings, polarity and order.</p>
            </div>
            <div>
              <span>02 / AMD SEMANTICS</span>
              <p>Optional DeepSeek text review. Separate authorization.</p>
            </div>
            <div>
              <span>03 / HUMAN REVIEW</span>
              <p>Listen, confirm evidence and make the release decision.</p>
            </div>
          </div>
        </>
      ) : (
        <header className="page-heading compact">
          <span className="eyebrow">QUICK TEST · DEMONSTRATION WORKSPACE</span>
          <h1>Listen closely. Verify with evidence.</h1>
          <p>
            Select a scenario, add your voice and inspect what the evidence
            supports.
          </p>
        </header>
      )}
      <div className="demo-intro" id="quick-start">
        <div>
          <span className="eyebrow">TRY IT YOURSELF</span>
          <h2>A short recording. A clear comparison.</h2>
          <p>
            English · one speaker · demonstration policies. No release sign-off.
          </p>
        </div>
        <span className="local-label">Local Verification by default</span>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!credential ? (
        <section className="panel session-entry">
          <h2>
            {config?.public_local
              ? "Start a public local test"
              : "Start a private test session"}
          </h2>
          <p>
            {config?.public_local
              ? "No shared code needed for local verification. Admission is limited to protect this shared CPU demo."
              : "Ask the demo operator for an access code. Public local access is disabled on this server."}{" "}
            Audio expires after 30 minutes; each session allows three attempts.
            Save your original recording before submitting it.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void open();
            }}
          >
            {!config?.public_local && (
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
            )}
            <button
              disabled={busy || !config || (!config.public_local && !code)}
            >
              {busy ? "Starting session…" : "Start Quick Test"}
            </button>
          </form>
        </section>
      ) : (
        <div id="demo-workflow" tabIndex={-1}>
          <ol className="workflow-path" aria-label="Quick Test steps">
            <li>
              <a href="#scenario-panel">Select scenario</a>
            </li>
            <li>
              <a href="#capture-panel">Record or upload</a>
            </li>
            <li>
              <a href="#capture-panel">Preview & save</a>
            </li>
            <li>
              <a href="#analyze-recording">Analyze</a>
            </li>
            <li>
              {report?.artifact ? (
                <a href="#actual-evidence">Inspect evidence</a>
              ) : (
                "Inspect evidence"
              )}
            </li>
          </ol>
          <div className="session-bar">
            <span>
              Scoped demo session · {report?.runs ?? 0}/3 attempts · expires{" "}
              {report
                ? new Date(report.expires_at * 1000).toLocaleTimeString()
                : "…"}
              {` · ${report?.amd_runs ?? 0}/2 AMD runs`}
            </span>
            <button className="text-button" onClick={discard}>
              Delete session and audio
            </button>
          </div>
          <div className="quick-workspace">
            <section className="panel" id="scenario-panel" tabIndex={-1}>
              <h2>1. Choose a scenario</h2>
              <div className="scenario-grid">
                {scenarios.map((s) => (
                  <button
                    key={s.id}
                    aria-label={s.title}
                    aria-describedby={`scenario-script-${s.id} scenario-requirement-${s.id}`}
                    disabled={processing}
                    className={
                      "scenario " + (selected === s.id ? "selected" : "")
                    }
                    aria-pressed={selected === s.id}
                    onClick={() => {
                      setSelected(s.id);
                      setConsent(false);
                    }}
                  >
                    <span className="scenario-top">
                      <strong>{s.title}</strong>
                      <span aria-hidden="true">
                        {selected === s.id ? "●" : "○"}
                      </span>
                    </span>
                    <span
                      className="scenario-script"
                      id={`scenario-script-${s.id}`}
                    >
                      {s.policy.script.instructions
                        .map((i) => i.text)
                        .join(" ")}
                    </span>
                    <span
                      className="scenario-requirement"
                      id={`scenario-requirement-${s.id}`}
                    >
                      {s.policy.policy.constraints
                        .map((c) =>
                          c.kind === "polarity"
                            ? `${c.approved_phrase} must not become ${c.reversed_phrase}`
                            : c.kind === "numeric"
                              ? "Keep the specified values and units"
                              : c.kind === "sequence"
                                ? "Keep the approved operation order"
                                : "Preserve the warning",
                        )
                        .join(" · ")}
                    </span>
                    <span className="scenario-hint">
                      {s.id === "unclear"
                        ? "Unclear speech needs human confirmation."
                        : s.title.includes("paraphrase")
                          ? "Compare permitted wording."
                          : s.id === "correct"
                            ? "Establish a baseline comparison."
                            : s.id === "fifteen-fifty"
                              ? "Detect a changed quantity."
                              : "Detect a changed instruction."}
                    </span>
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
            <section className="panel" id="capture-panel" tabIndex={-1}>
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
                    <option value="amd">AMD Semantic Review · protected</option>
                  </select>
                </label>
                {mode === "amd" && (
                  <div className="notice">
                    {!config?.amd_available && (
                      <p className="restricted">
                        AMD analysis unavailable on this server. Choose Local
                        Verification to continue.
                      </p>
                    )}
                    <label>
                      AMD demo access code
                      <input
                        type="password"
                        autoComplete="off"
                        value={amdCode}
                        onChange={(e) => {
                          setAmdCode(e.target.value);
                          setConsent(false);
                        }}
                        placeholder="Separate authorization from the operator"
                      />
                    </label>
                    <p>
                      DeepSeek-V4-Flash reviews the approved script, policy and
                      provisional transcript through AMD Token Factory. Original
                      audio stays on this server. One HTTP attempt per run; two
                      AMD runs per session, including failures. Findings remain
                      advisory.
                    </p>
                    <label className="check">
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
                <AudioInput
                  file={file}
                  onChange={(f) => {
                    setFile(f);
                    setConsent(false);
                  }}
                  scenarioName={selected}
                />
                <button
                  className="primary wide"
                  id="analyze-recording"
                  disabled={
                    !file ||
                    processing ||
                    (report?.runs ?? 0) >= 3 ||
                    (mode === "amd" &&
                      (!config?.amd_available ||
                        !amdCode ||
                        !consent ||
                        (report?.amd_runs ?? 0) >= 2))
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
            <section className="panel" id="actual-evidence" tabIndex={-1}>
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
              <p>
                Analyzed mode:{" "}
                <strong>
                  {report.mode === "amd"
                    ? "AMD Semantic Review"
                    : "Local Verification"}
                </strong>
                .
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
                  <h3>Recognized narration · provisional</h3>
                  <small>Raw ASR · unverified</small>
                  <p className="notice">
                    Recognized narration is provisional. Listen to the original
                    audio to confirm a potential instruction mismatch; Quick
                    Test cannot confirm a spoken error or approve a release.
                  </p>
                  <TranscriptView
                    transcript={report.transcription.transcript}
                    onSeek={(s) => jump(audio.current, s)}
                  />
                  <Coverage data={report.transcription.coverage} />
                  <EvidenceTimeline
                    transcript={report.transcription.transcript}
                    onSeek={(s) => jump(audio.current, s)}
                  />
                  <p>
                    Acoustic recheck not run in Quick Test. Recognizer output
                    does not prove what was spoken.
                  </p>
                </>
              )}
              <div className="analyzed-script">
                <span className="eyebrow">
                  APPROVED SCRIPT FOR THIS ANALYSIS
                </span>
                {scenarios
                  .find((s) => s.id === report.scenario_id)
                  ?.policy.script.instructions.map((i) => (
                    <blockquote key={i.id}>{i.text}</blockquote>
                  ))}
              </div>
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
                    Requested model: DeepSeek-V4-Flash. Returned model:{" "}
                    {report.semantic_verification?.semantic?.model ||
                      "No model response"}
                    .
                  </p>
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
        </div>
      )}
    </>
  );
}
