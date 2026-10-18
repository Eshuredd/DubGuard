import { PublicAMD, WorkspaceAMDResults } from "../components/PublicAMD";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  audioBlob,
  request,
  saveJSON,
  upload,
  type Schema,
  type Policy,
  type Transcript,
} from "../api";
import {
  AudioInput,
  AudioPlayer,
  jump,
  recordingFilename,
} from "../components/Audio";
import {
  Badge,
  Findings,
  TranscriptView,
  Coverage,
} from "../components/Evidence";

type View = Schema["WorkspaceView"];
type Requirement = Policy["policy"]["constraints"][number];
type Step = { text: string; alternatives: string };
type Segment = Transcript["segments"][number];
const initial: Step[] = [
  { text: "Wait 15 minutes before restarting.", alternatives: "" },
];
const numeric: Requirement[] = [
  { id: "requirement-1", kind: "numeric", instruction_id: "step-1" },
];

export function PublicWorkspace() {
  const [cap, setCap] = useState(
    () => sessionStorage.getItem("dubguard-custom") || "",
  );
  const [data, setData] = useState<View | null>(null);
  const [title, setTitle] = useState("My narration review");
  const [steps, setSteps] = useState<Step[]>(initial);
  const [requirements, setRequirements] = useState<Requirement[]>(numeric);
  const [mode, setMode] = useState<"local" | "amd">("local");
  const [consent, setConsent] = useState(false);
  const [amdAvailable, setAmdAvailable] = useState(false);
  const [amdReason, setAmdReason] = useState<"configuration" | "quota" | null>(
    null,
  );
  useEffect(() => {
    request<{
      amd_available: boolean;
      amd_unavailable_reason?: "configuration" | "quota" | null;
    }>("/workspace/config")
      .then((c) => {
        setAmdAvailable(c.amd_available);
        setAmdReason(c.amd_unavailable_reason ?? null);
      })
      .catch(() => setAmdAvailable(false));
  }, []);
  const [dirty, setDirty] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [listened, setListened] = useState(false),
    [complete, setComplete] = useState(false),
    [reason, setReason] = useState("");
  const [notes, setNotes] = useState(""),
    [reviewed, setReviewed] = useState<number[]>([]);
  const [decision, setDecision] = useState<
    "NEEDS_REVIEW" | "REVIEWED" | "REQUEST_NEW_RECORDING"
  >("NEEDS_REVIEW");
  const submitted = useRef(false);
  const hydrated = useRef(false),
    sequence = useRef(0),
    audio = useRef<HTMLAudioElement>(null);
  const processing = busy || data?.analysis.state === "PROCESSING";
  const stale =
    !!data?.analysis.artifact &&
    data.analysis.reference_revision !== data.workspace.reference_version;
  const canReview =
    !!data?.analysis.verification && !stale && !dirty && !processing;
  const result =
    data?.workspace.evidence?.result || data?.analysis.verification;

  useEffect(() => {
    if (!cap) return;
    let alive = true,
      timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const v = await request<View>("/workspace/session", {}, cap);
        if (!alive) return;
        setData(v);
        if (v.analysis.state !== "PROCESSING" && submitted.current) {
          submitted.current = false;
          requestAnimationFrame(() => {
            const target = document.getElementById("custom-evidence");
            target?.focus({ preventScroll: true });
            target?.scrollIntoView({ behavior: "instant", block: "start" });
          });
        }
        if (!hydrated.current && v.workspace.reference) {
          hydrated.current = true;
          setTitle(v.workspace.title);
          setSteps(
            v.workspace.reference.script.instructions.map((i) => ({
              text: i.text,
              alternatives: i.approved_variants.map((a) => a.text).join("\n"),
            })),
          );
          setRequirements(v.workspace.reference.policy.constraints);
          setDirty(false);
        }
        if (v.analysis.state === "PROCESSING") timer = setTimeout(poll, 1200);
      } catch (e) {
        if (alive) fail(e);
      }
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [cap, busy]);
  useEffect(() => {
    if (!data) return;
    setSegments(
      data.workspace.evidence?.transcript.segments ||
        data.analysis.transcription?.transcript.segments ||
        [],
    );
    setListened(false);
    setComplete(false);
  }, [data?.analysis.runs, data?.analysis.transcription?.artifact.sha256]);
  useEffect(() => {
    if (data) {
      setNotes(data.workspace.notes);
      setReviewed(data.workspace.reviewed);
      setDecision(data.workspace.demo_decision || "NEEDS_REVIEW");
    }
  }, [data?.workspace.revision]);
  function fail(e: unknown) {
    setError(
      e instanceof ApiError && e.status === 422
        ? "Check your reference, protected phrases, instruction order and audio timestamps. Numbers must use supported values and units; alternatives must preserve protected quantities."
        : (e as Error).message,
    );
    if (e instanceof ApiError && e.status === 401) {
      sessionStorage.removeItem("dubguard-custom");
      setCap("");
      setData(null);
      setConsent(false);
      hydrated.current = false;
      setDirty(true);
    }
  }
  async function act(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(message);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  function edited() {
    setConsent(false);
    setDirty(true);
    setNotice("");
  }
  async function saveReference() {
    await act(async () => {
      let token = cap;
      if (!token) {
        const v = await request<{ token: string }>(
          "/workspace/sessions",
          { method: "POST" },
          "",
        );
        token = v.token;
        sessionStorage.setItem("dubguard-custom", token);
        setCap(token);
        hydrated.current = true;
      }
      await request(
        "/workspace/reference",
        {
          method: "PUT",
          body: JSON.stringify({
            expected_revision: data?.workspace.revision || 0,
            title,
            instructions: steps.map((s) => ({
              text: s.text,
              alternatives: s.alternatives.split("\n").filter((s) => s.trim()),
            })),
            requirements,
          }),
        },
        token,
      );
      hydrated.current = true;
      setDirty(false);
    }, "Reference saved as a temporary Demo Policy. No organizational approval was created.");
  }
  function template(kind: "number" | "polarity" | "blank") {
    setSteps(
      kind === "blank"
        ? [{ text: "", alternatives: "" }]
        : kind === "number"
          ? initial
          : [
              {
                text: "Switch the power off.",
                alternatives: "Turn the power off.",
              },
            ],
    );
    setRequirements(
      kind === "blank"
        ? []
        : kind === "number"
          ? numeric
          : [
              {
                id: "requirement-1",
                kind: "polarity",
                instruction_id: "step-1",
                approved_phrase: "off",
                reversed_phrase: "on",
              },
            ],
    );
    edited();
  }
  function changeRequirement(index: number, value: Requirement) {
    setRequirements((r) => r.map((old, i) => (i === index ? value : old)));
    edited();
  }
  function addRequirement(kind: Requirement["kind"]) {
    const id = `requirement-${++sequence.current}-${requirements.length + 1}`;
    const common = { id, instruction_id: "step-1" };
    setRequirements((r) => [
      ...r,
      kind === "sequence"
        ? { id, kind, instruction_ids: steps.map((_, i) => `step-${i + 1}`) }
        : kind === "polarity"
          ? { ...common, kind, approved_phrase: "", reversed_phrase: "" }
          : kind === "warning"
            ? { ...common, kind, forbidden_wordings: [] }
            : { ...common, kind },
    ]);
    edited();
  }
  async function analyze() {
    if (!file || !data) return;
    setConsent(false);
    await act(
      async () => {
        await upload(
          `/workspace/analyze?expected_revision=${data.workspace.revision}&mode=${mode}&consent=${mode === "amd" && consent}`,
          file,
          cap,
        );
        setFile(null);
        submitted.current = true;
      },
      mode === "amd"
        ? "Analysis started: local transcription, then consented AMD text review. Results update automatically."
        : "Local analysis started. Results update automatically; no AMD request is made.",
    );
  }
  async function correct() {
    if (!data) return;
    await act(async () => {
      await request(
        "/workspace/evidence",
        {
          method: "PUT",
          body: JSON.stringify({
            expected_revision: data.workspace.revision,
            listened_to_original: listened,
            reason,
            transcript: {
              source: "manual",
              completeness: complete ? "complete" : "unknown",
              segments,
            },
          }),
        },
        cap,
      );
      setListened(false);
    }, "Visitor corrections saved and local rules rerun. Raw ASR remains preserved; this is demo evidence only.");
  }
  async function download() {
    await act(async () => {
      const blob = await audioBlob("/workspace/audio", cap),
        url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = recordingFilename(
        new File([blob], `original.${data?.analysis.artifact?.format}`, {
          type: blob.type,
        }),
        title,
      );
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    }, "Original bytes downloaded. Server retention and transcript annotation remain separate.");
  }
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">YOUR TEMPORARY REVIEW · NO SIGN-IN</span>
        <h1>
          Create a Review<span className="heading-accent">.</span>
        </h1>
        <p>
          Your reference script, your recording, evidence you can inspect. Demo
          decisions never authorize a release.
        </p>
      </header>
      <ol className="workflow-path">
        <li>
          <a href="#custom-reference">Reference Script</a>
        </li>
        <li>
          <a href="#custom-requirements">Protected Requirements</a>
        </li>
        <li>
          <a href="#custom-audio">Record Audio</a>
        </li>
        <li>
          <a href="#custom-analyze">Analyze</a>
        </li>
        <li>
          <a href="#custom-evidence">Inspect Evidence & Review</a>
        </li>
      </ol>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          <span aria-label="Workspace update">{notice}</span>
        </p>
      )}
      {data && (
        <div className="session-bar">
          <span>
            Temporary session · {data.analysis.runs}/3 analyses · expires{" "}
            {new Date(data.analysis.expires_at * 1000).toLocaleTimeString()} ·
            save originals and export before expiry
          </span>
          <button
            className="text-button"
            disabled={busy}
            onClick={() =>
              act(async () => {
                await request("/workspace/session", { method: "DELETE" }, cap);
                sessionStorage.removeItem("dubguard-custom");
                setCap("");
                setData(null);
                setFile(null);
                setConsent(false);
                setMode("local");
                hydrated.current = true;
                setDirty(true);
              }, "Temporary session and server recordings deleted.")
            }
          >
            Delete temporary review
          </button>
        </div>
      )}
      <div className="custom-editor-grid">
        <section className="panel" id="custom-reference">
          <span className="eyebrow">01 / REFERENCE SCRIPT</span>
          <h2>What should the narration say?</h2>
          <fieldset disabled={processing}>
            <div className="actions template-actions">
              <button className="secondary" onClick={() => template("number")}>
                Number example
              </button>
              <button
                className="secondary"
                onClick={() => template("polarity")}
              >
                Polarity example
              </button>
              <button className="text-button" onClick={() => template("blank")}>
                Start blank
              </button>
            </div>
            <label>
              Script title
              <input
                maxLength={100}
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  edited();
                }}
              />
            </label>
            {steps.map((step, index) => (
              <div className="editor-block" key={index}>
                <label>
                  Reference narration · Instruction {index + 1}
                  <textarea
                    rows={3}
                    maxLength={2000}
                    placeholder="Enter the words the speaker should say."
                    value={step.text}
                    onChange={(e) => {
                      setSteps((s) =>
                        s.map((v, i) =>
                          i === index ? { ...v, text: e.target.value } : v,
                        ),
                      );
                      edited();
                    }}
                  />
                </label>
                <details>
                  <summary>Allowed alternative wording · optional</summary>
                  <label>
                    Alternatives for instruction {index + 1}
                    <textarea
                      value={step.alternatives}
                      onChange={(e) => {
                        setSteps((s) =>
                          s.map((v, i) =>
                            i === index
                              ? { ...v, alternatives: e.target.value }
                              : v,
                          ),
                        );
                        edited();
                      }}
                      placeholder="One alternative per line; up to five. Protected numbers and polarity must stay unchanged."
                    />
                  </label>
                </details>
                {steps.length > 1 && (
                  <button
                    className="text-button"
                    onClick={() => {
                      setSteps((s) => s.filter((_, i) => i !== index));
                      setRequirements([]);
                      edited();
                    }}
                  >
                    Remove instruction {index + 1}
                  </button>
                )}
              </div>
            ))}
            <button
              className="secondary"
              disabled={steps.length >= 12}
              onClick={() => {
                setSteps((s) => [...s, { text: "", alternatives: "" }]);
                edited();
              }}
            >
              Add instruction
            </button>
            <p className="help">
              Use one instruction per step when order matters. Removing a step
              clears requirements so references cannot silently shift.
            </p>
          </fieldset>
        </section>
        <section className="panel" id="custom-requirements">
          <span className="eyebrow">02 / DEMO POLICY</span>
          <h2>What must stay unchanged?</h2>
          <p>
            Protect supported values, opposite meanings, warnings and operation
            order. This is your reference, not an approved organizational
            policy.
          </p>
          <fieldset disabled={processing}>
            {requirements.map((r, index) => (
              <div className="editor-block" key={r.id}>
                <div className="section-heading">
                  <h3>
                    {r.kind === "numeric"
                      ? "Number & units"
                      : r.kind === "polarity"
                        ? "Polarity / opposite meaning"
                        : r.kind === "warning"
                          ? "Protected warning"
                          : "Operation order"}
                  </h3>
                  <button
                    className="text-button"
                    aria-label={`Remove requirement ${index + 1}`}
                    onClick={() => {
                      setRequirements((a) => a.filter((_, i) => i !== index));
                      edited();
                    }}
                  >
                    Remove
                  </button>
                </div>
                {r.kind !== "sequence" ? (
                  <label>
                    Instruction for requirement {index + 1}
                    <select
                      value={r.instruction_id}
                      onChange={(e) =>
                        changeRequirement(index, {
                          ...r,
                          instruction_id: e.target.value,
                        })
                      }
                    >
                      {steps.map((s, i) => (
                        <option value={`step-${i + 1}`} key={i}>
                          Instruction {i + 1} ·{" "}
                          {s.text.slice(0, 55) || "New instruction"}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <>
                    <p>
                      The selected instructions must stay in their reference
                      order. Select at least two.
                    </p>
                    {steps.map((s, i) => (
                      <label className="check" key={i}>
                        <input
                          type="checkbox"
                          checked={r.instruction_ids.includes(`step-${i + 1}`)}
                          onChange={(e) =>
                            changeRequirement(index, {
                              ...r,
                              instruction_ids: steps
                                .map((_, j) => `step-${j + 1}`)
                                .filter((id) =>
                                  id === `step-${i + 1}`
                                    ? e.target.checked
                                    : r.instruction_ids.includes(id),
                                ),
                            })
                          }
                        />
                        Instruction {i + 1} · {s.text}
                      </label>
                    ))}
                  </>
                )}
                {r.kind === "numeric" && (
                  <p className="help">
                    Protect every supported number, range and unit in this
                    instruction. For “Wait 15 minutes”, a changed delay such as
                    50 minutes needs review.
                  </p>
                )}
                {r.kind === "polarity" && (
                  <>
                    <label>
                      Required phrase
                      <input
                        value={r.approved_phrase}
                        placeholder="off"
                        onChange={(e) =>
                          changeRequirement(index, {
                            ...r,
                            approved_phrase: e.target.value,
                          })
                        }
                      />
                    </label>
                    <label>
                      Dangerous reversal
                      <input
                        value={r.reversed_phrase}
                        placeholder="on"
                        onChange={(e) =>
                          changeRequirement(index, {
                            ...r,
                            reversed_phrase: e.target.value,
                          })
                        }
                      />
                    </label>
                  </>
                )}
                {r.kind === "warning" && (
                  <label>
                    Dangerous alternative wordings
                    <textarea
                      value={r.forbidden_wordings.join("\n")}
                      placeholder="One per line, e.g. Gloves are optional."
                      onChange={(e) =>
                        changeRequirement(index, {
                          ...r,
                          forbidden_wordings: e.target.value.split("\n"),
                        })
                      }
                    />
                  </label>
                )}
              </div>
            ))}
            <div className="actions">
              <button
                className="secondary"
                disabled={requirements.length >= 30}
                onClick={() => addRequirement("numeric")}
              >
                Protect numbers
              </button>
              <button
                className="secondary"
                disabled={requirements.length >= 30}
                onClick={() => addRequirement("polarity")}
              >
                Protect polarity
              </button>
              <button
                className="secondary"
                disabled={requirements.length >= 30}
                onClick={() => addRequirement("warning")}
              >
                Protect warning
              </button>
              <button
                className="secondary"
                disabled={steps.length < 2 || requirements.length >= 30}
                onClick={() => addRequirement("sequence")}
              >
                Protect order
              </button>
            </div>
            {!requirements.length && (
              <p className="notice">
                No protected requirements yet. Add checks to catch the changes
                that matter to you.
              </p>
            )}
            <button
              className="wide"
              disabled={
                !title.trim() || steps.some((s) => !s.text.trim()) || !dirty
              }
              onClick={saveReference}
            >
              Save reference & demo policy
            </button>
          </fieldset>
        </section>
      </div>
      <section className="panel" id="custom-audio">
        <div className="section-heading">
          <div>
            <span className="eyebrow">03 / ORIGINAL AUDIO</span>
            <h2>Record your narration</h2>
          </div>
          <span className="local-label">
            Local rules and optional AMD text review
          </span>
        </div>
        <p>
          Up to 60 seconds and 10 MB. Download the original before submitting;
          this temporary workspace expires after 30 minutes.
        </p>
        <fieldset disabled={processing}>
          <AudioInput
            file={file}
            onChange={(f) => {
              setFile(f);
              setConsent(false);
            }}
            scenarioName={title}
          />
          <PublicAMD
            mode={mode}
            consent={consent}
            available={amdAvailable}
            unavailableReason={amdReason}
            onMode={setMode}
            onConsent={setConsent}
          />
          <button
            id="custom-analyze"
            disabled={
              !cap ||
              dirty ||
              !file ||
              processing ||
              (data?.analysis.runs || 0) >= 3 ||
              (mode === "amd" &&
                (!amdAvailable ||
                  !consent ||
                  (data?.analysis.amd_runs || 0) >= 2))
            }
            onClick={analyze}
          >
            {processing
              ? "Analyzing recording…"
              : mode === "amd"
                ? "Analyze recording with AMD"
                : "Analyze recording locally"}
          </button>
          {dirty && (
            <p className="help">Save the current reference before analyzing.</p>
          )}
        </fieldset>
        {data?.analysis.state === "PROCESSING" && (
          <p role="status" className="notice">
            Decoding original audio and transcribing locally. You can refresh
            safely.{" "}
            {data.analysis.mode === "amd" &&
              `AMD status: ${data.analysis.semantic_status}. Requested model: DeepSeek-V4-Flash.`}
          </p>
        )}
        {data?.analysis.error && (
          <p className="error" role="alert">
            {data.analysis.error}
          </p>
        )}
      </section>
      {data?.analysis.artifact && (
        <section className="panel" id="custom-evidence" tabIndex={-1}>
          <span className="eyebrow">04 / ACTUAL EVIDENCE</span>
          <h2>{data.workspace.title || "Your recording"}</h2>
          {(stale || dirty) && (
            <p className="notice">
              These results belong to reference version{" "}
              {data.analysis.reference_revision}. Save and analyze the edited
              reference before reviewing its evidence.
            </p>
          )}
          <AudioPlayer
            key={data.analysis.runs}
            path="/workspace/audio"
            credential={cap}
            audioRef={audio}
          />
          <button className="secondary" disabled={busy} onClick={download}>
            Download submitted original
          </button>
          <small className="identity">
            Original SHA-256 {data.analysis.artifact.sha256} ·{" "}
            {data.analysis.artifact.format}
          </small>
          <div className="two-column">
            <div>
              <h3>Reference Script · analyzed version</h3>
              {data.analysis.reference_policy?.script.instructions.map((i) => (
                <blockquote key={i.id}>{i.text}</blockquote>
              ))}
            </div>
            <div>
              <h3>Recognized narration · provisional</h3>
              {data.analysis.transcription && (
                <>
                  <TranscriptView
                    transcript={data.analysis.transcription.transcript}
                    onSeek={(s) => jump(audio.current, s)}
                  />
                  <Coverage data={data.analysis.transcription.coverage} />
                  <small>
                    {data.analysis.transcription.provider} ·{" "}
                    {data.analysis.transcription.model}
                  </small>
                </>
              )}
              <p className="help">
                ASR can be wrong. Listen to the original before confirming
                actual words; reference text is never copied into spoken
                evidence.
              </p>
            </div>
          </div>
          {result && (
            <Findings
              title="Local verification findings"
              demo
              result={result}
              onSeek={(s) => jump(audio.current, s)}
            />
          )}
          <WorkspaceAMDResults
            report={data.analysis}
            onSeek={(s) => jump(audio.current, s)}
          />
          <details className="visitor-corrections" open>
            <summary>Correct spoken evidence after listening</summary>
            <p>
              Enter only what you actually hear. This visitor attestation is
              temporary demo evidence, not an authenticated reviewer identity.
            </p>
            <fieldset disabled={!canReview}>
              {segments.map((s, index) => (
                <div className="editor-block" key={s.id}>
                  <label>
                    Actual spoken words · Segment {index + 1}
                    <textarea
                      value={s.text}
                      onChange={(e) =>
                        setSegments((a) =>
                          a.map((v, i) =>
                            i === index ? { ...v, text: e.target.value } : v,
                          ),
                        )
                      }
                    />
                  </label>
                  <div className="form-grid">
                    <label>
                      Match to reference instruction {index + 1}
                      <select
                        value={s.instruction_id || ""}
                        onChange={(e) =>
                          setSegments((a) =>
                            a.map((v, i) =>
                              i === index
                                ? {
                                    ...v,
                                    instruction_id: e.target.value || null,
                                  }
                                : v,
                            ),
                          )
                        }
                      >
                        <option value="">Unmapped / unsure</option>
                        {data.analysis.reference_policy?.script.instructions.map(
                          (i, j) => (
                            <option value={i.id} key={i.id}>
                              Instruction {j + 1} · {i.text.slice(0, 55)}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                    <label>
                      Start seconds · Segment {index + 1}
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={s.start_seconds ?? 0}
                        onChange={(e) =>
                          setSegments((a) =>
                            a.map((v, i) =>
                              i === index
                                ? {
                                    ...v,
                                    start_seconds: Number(e.target.value),
                                  }
                                : v,
                            ),
                          )
                        }
                      />
                    </label>
                    <label>
                      End seconds · Segment {index + 1}
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max={data.analysis.artifact!.duration_seconds}
                        value={
                          s.end_seconds ??
                          data.analysis.artifact!.duration_seconds
                        }
                        onChange={(e) =>
                          setSegments((a) =>
                            a.map((v, i) =>
                              i === index
                                ? { ...v, end_seconds: Number(e.target.value) }
                                : v,
                            ),
                          )
                        }
                      />
                    </label>
                  </div>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={s.uncertain}
                      onChange={(e) =>
                        setSegments((a) =>
                          a.map((v, i) =>
                            i === index
                              ? {
                                  ...v,
                                  uncertain: e.target.checked,
                                  uncertainty_reason: e.target.checked
                                    ? "Visitor still uncertain"
                                    : null,
                                }
                              : v,
                          ),
                        )
                      }
                    />
                    Words remain unclear · Segment {index + 1}
                  </label>
                  <button
                    className="text-button"
                    onClick={() =>
                      setSegments((a) => a.filter((_, i) => i !== index))
                    }
                  >
                    Remove spoken segment {index + 1}
                  </button>
                </div>
              ))}
              <button
                className="secondary"
                disabled={segments.length >= 50}
                onClick={() =>
                  setSegments((a) => [
                    ...a,
                    {
                      id: `visitor-${++sequence.current}`,
                      text: "",
                      instruction_id: null,
                      start_seconds: 0,
                      end_seconds: data.analysis.artifact!.duration_seconds,
                      uncertain: true,
                      confidence: null,
                    },
                  ])
                }
              >
                Add spoken segment
              </button>
              <label>
                Reason for correction
                <textarea
                  value={reason}
                  maxLength={2000}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={listened}
                  onChange={(e) => setListened(e.target.checked)}
                />
                I listened to this original recording and entered the actual
                spoken words.
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={complete}
                  onChange={(e) => setComplete(e.target.checked)}
                />
                I checked the entire recording for missing words.
              </label>
              <button disabled={!listened || !reason.trim()} onClick={correct}>
                Save demo evidence & rerun local rules
              </button>
            </fieldset>
          </details>
          <h2>Demo decision & notes</h2>
          <p>
            Acknowledging a finding never approves a release. Critical
            deviations and uncertain evidence remain visible in the assessment.
          </p>
          <fieldset disabled={!canReview}>
            {result?.findings.map((f, i) => (
              <label className="check" key={i}>
                <input
                  type="checkbox"
                  checked={reviewed.includes(i)}
                  onChange={(e) =>
                    setReviewed((a) =>
                      e.target.checked ? [...a, i] : a.filter((v) => v !== i),
                    )
                  }
                />
                Mark finding {i + 1} reviewed · {f.rule_id}
              </label>
            ))}
            <label>
              Temporary review notes
              <textarea
                value={notes}
                maxLength={2000}
                onChange={(e) => setNotes(e.target.value)}
              />
            </label>
            <label>
              Demo decision
              <select
                aria-label="Demo decision"
                value={decision}
                onChange={(e) => setDecision(e.target.value as typeof decision)}
              >
                <option value="NEEDS_REVIEW">Needs further review</option>
                <option value="REVIEWED">Reviewed · no release approval</option>
                <option value="REQUEST_NEW_RECORDING">
                  Request a new recording
                </option>
              </select>
            </label>
            <button
              onClick={() =>
                act(
                  () =>
                    request(
                      "/workspace/review",
                      {
                        method: "PUT",
                        body: JSON.stringify({
                          expected_revision: data.workspace.revision,
                          notes,
                          reviewed,
                          demo_decision: decision,
                        }),
                      },
                      cap,
                    ),
                  "Demo decision saved. No organizational approval or authenticated sign-off was created.",
                )
              }
            >
              Save demo decision & notes
            </button>
          </fieldset>
          {data.workspace.demo_decision && (
            <p className="notice">
              Saved demo decision:{" "}
              {data.workspace.demo_decision.replaceAll("_", " ")} · No release
              authorization.
            </p>
          )}
          <div className="actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const v = await request<View>("/workspace/export", {}, cap);
                  saveJSON(v, "dubguard-demo-evidence.json");
                }, "Demonstration evidence report exported; includes no session capability or operator credential.")
              }
            >
              Export demonstration evidence report
            </button>
          </div>
          <details>
            <summary>Temporary demo activity</summary>
            {data.workspace.events.map((e, i) => (
              <p key={i}>{e}</p>
            ))}
          </details>
        </section>
      )}
      {!data?.analysis.artifact && (
        <div className="panel custom-empty" id="custom-evidence" tabIndex={-1}>
          <h2>Your evidence will appear here</h2>
          <p>
            Save your reference, add a recording and run local verification.
            Your script is a comparison source, never a ground-truth transcript.
          </p>
          <Link to="/test">Prefer a guided example? Try a sample.</Link>
        </div>
      )}
    </>
  );
}
