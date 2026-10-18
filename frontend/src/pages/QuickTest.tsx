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
import { AudioInput } from "../components/Audio";
import { QuickResults } from "../components/QuickResults";
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
    [captureActive, setCaptureActive] = useState(false),
    [chosen, setChosen] = useState(false),
    [retry, setRetry] = useState(0),
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
  }, [retry]);
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
  }, [credential, busy, retry]);
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
      setChosen(false);
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
  const step = processing
    ? 3
    : file
      ? 2
      : captureActive || chosen
        ? 1
        : report?.artifact
          ? 4
          : 0;
  const steps = [
    ["Choose scenario", "#scenario-panel"],
    ["Record or upload", "#capture-panel"],
    ["Preview & save", "#capture-panel"],
    ["Analyze", "#analyze-recording"],
    ["Review evidence", "#actual-evidence"],
  ];
  const sessionEntry = (
    <section className="panel session-entry" id="quick-start">
      <h2>
        {config?.public_local
          ? "Start a public local test"
          : "Start a private test session"}
      </h2>
      <p>
        {config?.public_local
          ? "No shared code needed for local verification. Admission is limited to protect this shared CPU demo."
          : "Ask the demo operator for an access code. Public local access is disabled on this server."}{" "}
        Audio expires after 30 minutes; each session allows three attempts. Save
        your original recording before submitting it.
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
        <button disabled={busy || !config || (!config.public_local && !code)}>
          {busy ? "Starting session…" : "Start Quick Test"}
        </button>
      </form>
    </section>
  );
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
                Small words.
                <br />
                <em>Critical differences.</em>
              </h1>
              <p className="hero-description">
                Verify recorded instructions against approved scripts using
                evidence-backed AI and human review.
              </p>
              <div className="actions">
                <a className="button" href="#quick-start">
                  Try a Sample <span aria-hidden="true">↗</span>
                </a>
                <Link className="button secondary" to="/workspace">
                  Create Your Own Review
                </Link>
              </div>
              <p className="hero-audience">
                Try one of six samples, or create your own reference script and
                protected requirements. Public custom reviews require no
                sign-in.
              </p>
              {sessionEntry}
            </div>
            <div className="illustration">
              <span className="eyebrow">
                ILLUSTRATIVE EXAMPLE · NOT AN ANALYSIS
              </span>
              <div className="preview-heading">
                <strong>Narration review</strong>
                <span className="badge review">Needs human confirmation</span>
              </div>
              <div className="example-line">
                <span>Approved instruction</span>
                <p>
                  Switch the power <strong>off.</strong>
                </p>
              </div>
              <div className="example-line observed">
                <span>Recognized narration · provisional</span>
                <p>
                  Switch the power <mark>on.</mark>
                </p>
              </div>
              <div className="example-change">
                <strong>off → on</strong>
                <span>Potential mismatch. Listen to confirm.</span>
              </div>
              <p className="preview-next">
                <strong>Next:</strong> Listen to the original, confirm the
                spoken words, then review the evidence.
              </p>
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
          <h1>
            Narration verification<span className="heading-accent">.</span>
          </h1>
          <p>
            Choose the instruction. Capture your take. Inspect the evidence.
          </p>
        </header>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
          <button
            className="text-button"
            onClick={() => {
              setError("");
              setRetry((n) => n + 1);
            }}
          >
            Reload session status
          </button>
        </p>
      )}
      {!credential ? null : (
        <div id="demo-workflow" tabIndex={-1}>
          <ol className="workflow-path" aria-label="Quick Test steps">
            {steps.map(([label, href], i) => (
              <li key={label} aria-current={i === step ? "step" : undefined}>
                {i === 4 && !report?.artifact ? (
                  label
                ) : (
                  <a href={href}>{label}</a>
                )}
              </li>
            ))}
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
          {report?.artifact && (
            <QuickResults
              report={report}
              scenarios={scenarios}
              selected={selected}
              credential={credential}
              audio={audio}
            />
          )}
          {report?.artifact && (
            <div className="section-heading">
              <h2>Try another recording</h2>
              <a href="#actual-evidence">Back to results ↑</a>
            </div>
          )}
          <div className="quick-workspace">
            <section className="panel" id="scenario-panel" tabIndex={-1}>
              <h2>1. Choose a scenario</h2>
              <label className="mobile-scenario-select">
                Demonstration scenario
                <select
                  value={selected}
                  disabled={processing}
                  onChange={(e) => {
                    setSelected(e.target.value);
                    setChosen(true);
                    setConsent(false);
                  }}
                >
                  {scenarios.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </select>
              </label>
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
                      setChosen(true);
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
              <div className="section-heading">
                <div>
                  <span className="eyebrow">CAPTURE STUDIO</span>
                  <h2>2. Add your voice</h2>
                </div>
                <span className="local-label">Original audio</span>
              </div>
              <div className="read-aloud">
                <span className="eyebrow">APPROVED SCRIPT · READ ALOUD</span>
                <p>
                  {scenario?.policy.script.instructions
                    .map((i) => i.text)
                    .join(" ")}
                </p>
              </div>
              <fieldset disabled={processing}>
                <AudioInput
                  file={file}
                  onChange={(f) => {
                    setFile(f);
                    setConsent(false);
                  }}
                  scenarioName={selected}
                  onCaptureActive={setCaptureActive}
                />
                <div className="analysis-settings">
                  <span className="eyebrow">ANALYSIS SETTINGS</span>
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
                      <option value="amd">
                        AMD Semantic Review · protected
                      </option>
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
                        DeepSeek-V4-Flash reviews the approved script, policy
                        and provisional transcript through AMD Token Factory.
                        Original audio stays on this server. One HTTP attempt
                        per run; two AMD runs per session, including failures.
                        Findings remain advisory.
                      </p>
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={consent}
                          onChange={(e) => setConsent(e.target.checked)}
                        />
                        I consent to sending script, policy and transcript text
                        to AMD for this analysis.
                      </label>
                    </div>
                  )}
                </div>

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
                  {processing ? "Analyzing recording…" : "Analyze recording"}
                </button>
              </fieldset>
              <p className="action-help">
                {(report?.runs ?? 0) >= 3
                  ? "All three attempts are used. This session cannot analyze another recording."
                  : mode === "amd" && (report?.amd_runs ?? 0) >= 2
                    ? "Both AMD runs are used, including failed runs. Choose Local Verification if attempts remain."
                    : !file
                      ? "Add a recording to enable analysis. Preview and save it first."
                      : mode === "amd" && (!amdCode || !consent)
                        ? "AMD requires its separate access code and consent for this run."
                        : "Your original audio will be analyzed when you continue."}
              </p>
              {processing && (
                <p className="processing-notice" role="status">
                  Analysis in progress. Uploading or processing original audio
                  with local ASR… Keep this session open. No completion estimate
                  is available.{" "}
                  {report?.mode === "amd" &&
                    `AMD status: ${report.semantic_status}. Requested model: DeepSeek-V4-Flash.`}
                </p>
              )}
            </section>
          </div>
          {report?.error && !report.artifact && (
            <p role="alert" className="error">
              {report.error} Add or record another file to retry if attempts
              remain. Failed analyses may consume an attempt.
            </p>
          )}
        </div>
      )}
    </>
  );
}
