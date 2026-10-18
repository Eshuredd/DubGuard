import type { Quick } from "../api";
import { Findings } from "./Evidence";

export function PublicAMD({
  mode,
  consent,
  available,
  unavailableReason,
  onMode,
  onConsent,
}: {
  mode: "local" | "amd";
  consent: boolean;
  available: boolean;
  unavailableReason?: "configuration" | "quota" | null;
  onMode: (mode: "local" | "amd") => void;
  onConsent: (value: boolean) => void;
}) {
  return (
    <div className="analysis-settings">
      <label>
        Verification mode
        <select
          value={mode}
          onChange={(e) => {
            onMode(e.target.value as "local" | "amd");
            onConsent(false);
          }}
        >
          <option value="local">Local Verification</option>
          <option value="amd">AMD Semantic Review</option>
        </select>
      </label>
      <p>
        Local Verification checks protected values, warnings, polarity and order
        on this server.
      </p>
      {mode === "amd" && (
        <div className="notice">
          {!available && (
            <p>
              {unavailableReason === "quota"
                ? "Public AMD quota is exhausted. Local Verification remains available. Try AMD again after the shared budget recovers."
                : "AMD Semantic Review is temporarily unavailable. Local Verification remains available."}
            </p>
          )}
          <p>
            AMD Semantic Review sends your reference script, protected
            requirements, and provisional transcript text to AMD Token Factory
            for analysis. Original audio is not sent to DeepSeek.
          </p>
          <p>
            Requested model: DeepSeek-V4-Flash. Findings are advisory. Two AMD
            attempts per session; shared hourly, daily and client budgets apply.
            Failed attempts count. No automatic retries.
          </p>
          <label className="check">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => onConsent(e.target.checked)}
            />
            I consent to sending script, policy and transcript text to AMD for
            this analysis.
          </label>
        </div>
      )}
    </div>
  );
}

export function WorkspaceAMDResults({
  report,
  onSeek,
}: {
  report: Quick;
  onSeek: (seconds?: number | null) => void;
}) {
  if (report.mode !== "amd") return null;
  const result = report.semantic_verification;
  return (
    <section aria-label="AMD Semantic Review result">
      <h3>AMD Semantic Review · advisory findings</h3>
      <p>
        Status: {report.semantic_status.replaceAll("_", " ")}. Requested model:
        DeepSeek-V4-Flash. Returned model:{" "}
        {result?.semantic?.model || "No model response"}.
      </p>
      <p>
        These findings cite the analyzed reference version{" "}
        {report.reference_revision} and raw provisional transcript. Visitor
        corrections are evaluated separately by local rules. AMD cannot approve
        a recording.
      </p>
      {result && (
        <Findings
          demo
          title="AMD advisory findings"
          result={{
            ...result,
            findings: result.findings.filter((f) =>
              f.rule_id.startsWith("SEMANTIC."),
            ),
          }}
          onSeek={onSeek}
        />
      )}
      {result?.semantic?.issues.map((issue, i) => (
        <p className="notice" key={i}>
          Rejected citation: {issue.explanation}
        </p>
      ))}
    </section>
  );
}
