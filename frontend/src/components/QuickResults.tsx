import { useState, useEffect, type RefObject } from "react";
import { Link } from "react-router-dom";
import type { Quick, Scenario } from "../api";
import { AudioPlayer, jump } from "./Audio";
import {
  Badge,
  Coverage,
  EvidenceTimeline,
  Findings,
  TranscriptView,
} from "./Evidence";
import { TextComparison } from "./TextComparison";
import { EvidenceInspector, type Selection } from "./EvidenceInspector";

export function QuickResults({
  report,
  scenarios,
  selected,
  credential,
  audio,
}: {
  report: Quick;
  scenarios: Scenario[];
  selected: string;
  credential: string;
  audio: RefObject<HTMLAudioElement | null>;
}) {
  const [selection, setSelection] = useState<Selection>({
    kind: "local",
    index: 0,
  });
  useEffect(() => {
    setSelection({ kind: "local", index: 0 });
  }, [report.runs]);
  if (!report.artifact) return null;
  const scenario = scenarios.find((s) => s.id === report.scenario_id);
  const onSeek = (seconds?: number | null) => jump(audio.current, seconds);
  const semantic = report.semantic_verification
    ? {
        ...report.semantic_verification,
        findings: report.semantic_verification.findings.filter((f) =>
          f.rule_id.startsWith("SEMANTIC."),
        ),
      }
    : null;
  const activeResult =
    selection.kind === "amd" ? semantic : report.verification;
  const activeFinding = activeResult?.findings[selection.index];
  const unresolved = [
    ...(report.verification?.findings || []),
    ...(semantic?.findings || []),
  ].filter((f) => f.status !== "SATISFIED").length;
  return (
    <section
      className="panel results-panel"
      id="actual-evidence"
      tabIndex={-1}
      aria-labelledby="results-title"
    >
      <div className="section-heading result-heading">
        <div>
          <span className="eyebrow">YOUR RECORDING · EVIDENCE REVIEW</span>
          <h2 id="results-title">Review actual evidence</h2>
          <span className="results-kicker">
            {unresolved} findings need human attention ·{" "}
            {report.artifact.duration_seconds.toFixed(2)} s of source audio
          </span>
          <p>
            Analyzed scenario:{" "}
            <strong>{scenario?.title || report.scenario_id}</strong>
          </p>
          <p>
            Analyzed mode:{" "}
            <strong>
              {report.mode === "amd"
                ? "AMD Semantic Review"
                : "Local Verification"}
            </strong>
          </p>
        </div>
        <div className="result-state">
          <Badge
            value={
              report.state === "FAILED"
                ? "ANALYSIS_FAILED"
                : report.verification?.decision || "REVIEW_REQUIRED"
            }
          />
          <small>
            {report.state === "FAILED"
              ? "Analysis incomplete · review the error"
              : "Human confirmation required"}
          </small>
        </div>
      </div>
      {report.error && (
        <p className="error" role="alert">
          {report.error} Add another recording to retry if attempts remain.
        </p>
      )}
      <p className="notice uncertainty-notice">
        Recognized narration is provisional. Listen to the original audio to
        confirm a potential instruction mismatch; Quick Test cannot confirm a
        spoken error or approve a release.
      </p>
      {!!semantic?.semantic?.issues.length && (
        <div className="notice uncertainty-notice">
          <strong>
            AMD source citations were rejected. Human review is required.
          </strong>
          <ul>
            {semantic.semantic.issues.map((issue, i) => (
              <li key={i}>{issue.explanation}</li>
            ))}
          </ul>
        </div>
      )}
      {selected !== report.scenario_id && (
        <p className="notice">
          The selected scenario has changed; these results still belong to the
          previous analysis.
        </p>
      )}
      <div className="studio-grid">
        <div className="studio-canvas">
          <div className="original-player sticky-audio">
            <div className="section-heading">
              <strong>Listen to the original</strong>
              <small>
                {report.artifact.duration_seconds.toFixed(2)} s ·{" "}
                {report.artifact.format.toUpperCase()}
              </small>
            </div>
            <AudioPlayer
              key={report.runs}
              path="/quick/audio"
              credential={credential}
              audioRef={audio}
              segments={report.transcription?.transcript.segments}
            />
          </div>
          <TextComparison
            approvedLines={scenario?.policy.script.instructions.map((i) => ({
              id: i.id,
              text: i.text,
            }))}
            recognizedLines={report.transcription?.transcript.segments}
            activeIds={[
              ...(activeFinding?.instruction_ids || []),
              ...(activeFinding?.observed.map((e) => e.segment_id || "") || []),
            ]}
            onSeek={onSeek}
            approved={
              scenario?.policy.script.instructions
                .map((i) => i.text)
                .join(" ") || "Approved script unavailable"
            }
            recognized={
              report.transcription?.transcript.segments
                .map((s) => s.text)
                .join(" ") || ""
            }
          />
          <div
            className="selected-evidence"
            id="selected-evidence"
            tabIndex={-1}
          >
            <span id="local-findings" />
            {activeResult && activeFinding ? (
              <>
                <span className="eyebrow">
                  SELECTED FINDING · EXACT SOURCE EVIDENCE
                </span>
                <Findings
                  result={{ ...activeResult, findings: [activeFinding] }}
                  provisional
                  providerDetails={selection.kind !== "amd"}
                  title={
                    selection.kind === "amd"
                      ? "AMD semantic findings"
                      : "Verification findings"
                  }
                  onSeek={onSeek}
                />
              </>
            ) : (
              <p className="notice">
                No finding is selected. Listen to the source and inspect
                evidence completeness before deciding.
              </p>
            )}
          </div>
        </div>
        <EvidenceInspector
          local={report.verification}
          semantic={semantic}
          selected={selection}
          onSelect={(value) => {
            setSelection(value);
            requestAnimationFrame(() => {
              const node = document.getElementById("selected-evidence");
              node?.focus({ preventScroll: true });
              node?.scrollIntoView({ block: "nearest", behavior: "instant" });
            });
          }}
        >
          <div className="inspector-coverage">
            {report.transcription && (
              <Coverage data={report.transcription.coverage} />
            )}
            {!!report.transcription?.uncertainty?.length && (
              <ul
                className="uncertainty-list"
                aria-label="Transcription limitations"
              >
                {report.transcription.uncertainty.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            )}
          </div>
        </EvidenceInspector>
      </div>
      <div className="next-action compact-next">
        <div>
          <span className="eyebrow">NEXT HUMAN ACTION</span>
          <h3>Listen, compare, then confirm.</h3>
          <p>
            Check highlighted words and any unclear spans against the recording.
            Create a Review to define your own reference and save temporary
            evidence corrections and demo notes.
          </p>
        </div>
        <div className="actions">
          <a className="button secondary" href="#capture-panel">
            Record another take
          </a>
          <Link to="/workspace" className="button">
            Create a Review
          </Link>
        </div>
      </div>
      <nav className="evidence-nav" aria-label="Result sections">
        <a
          href="#local-findings"
          onClick={() => setSelection({ kind: "local", index: 0 })}
        >
          Local findings
        </a>
        {report.mode === "amd" && <a href="#amd-findings">AMD findings</a>}
        <a href="#source-evidence">Source & audit details</a>
      </nav>
      {report.mode === "amd" && (
        <section
          id="amd-findings"
          className="result-section"
          aria-label="AMD Semantic Review result"
        >
          <span className="eyebrow">OPTIONAL TEXT ANALYSIS · ADVISORY</span>
          <h3>AMD Semantic Review · DeepSeek-V4-Flash</h3>
          <p>
            Status: {report.semantic_status.replaceAll("_", " ")}. AMD cannot
            approve a recording.
          </p>
          <p>
            Source validation checks citations against supplied text; it does
            not verify spoken words or establish semantic accuracy. Unsupported
            citations require review.
          </p>
          {!semantic?.findings.length && (
            <p>
              No supported AMD findings returned. Review provider status and
              rejected citations below.
            </p>
          )}
          {semantic?.semantic && selection.kind !== "amd" && (
            <p className="notice">
              {semantic.semantic.explanation}
              {semantic.semantic.error_class &&
                ` · ${semantic.semantic.error_class}`}
            </p>
          )}
          {semantic && (
            <details>
              <summary>Provider request details</summary>
              <p>
                {semantic.semantic?.attempts ?? 0} HTTP attempts ·{" "}
                {semantic.semantic?.provider} · {semantic.semantic?.status}
              </p>
            </details>
          )}
          <details>
            <summary>AMD model & consent details</summary>
            <p>
              Requested model: DeepSeek-V4-Flash. Returned model:{" "}
              {report.semantic_verification?.semantic?.model ||
                "No model response"}
              .
            </p>
            <p>
              Consent recorded{" "}
              {report.consented_at
                ? new Date(report.consented_at * 1000).toLocaleString()
                : "not available"}
              .
            </p>
          </details>
        </section>
      )}
      <details id="source-evidence" className="source-evidence">
        <summary>Source evidence & audit details</summary>
        <p>Processing state: {report.state.toLowerCase()}.</p>
        <small className="identity">SHA-256 {report.artifact.sha256}</small>
        {report.transcription && (
          <>
            <h3>Raw ASR · unverified</h3>
            <TranscriptView
              transcript={report.transcription.transcript}
              onSeek={onSeek}
            />
            <EvidenceTimeline
              transcript={report.transcription.transcript}
              onSeek={onSeek}
            />
            <p>
              Acoustic recheck not run in Quick Test. Recognizer output does not
              prove what was spoken.
            </p>
            <p>
              Recognizer: {report.transcription.provider} ·{" "}
              {report.transcription.model}
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
      </details>
    </section>
  );
}
