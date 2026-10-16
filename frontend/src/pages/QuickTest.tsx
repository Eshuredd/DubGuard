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
        "/quick/analyze?scenario_id=" + encodeURIComponent(selected),
        file,
        credential,
      );
      setFile(null);
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
        approval or release signoff. Quick Test runs local ASR and rules only;
        no AMD request is made.
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
                <AudioInput file={file} onChange={setFile} />
                <button
                  className="primary wide"
                  disabled={!file || processing || (report?.runs ?? 0) >= 3}
                  onClick={analyze}
                >
                  Analyze recording
                </button>
              </fieldset>
              {processing && (
                <p role="status">
                  Processing original audio with local ASR… Keep this session
                  open. You can refresh safely.
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
                <Findings
                  result={report.verification}
                  onSeek={(s) => jump(audio.current, s)}
                />
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
