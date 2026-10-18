import type { Review } from "../api";
import { Badge } from "./Evidence";
import { Icon } from "./Icon";
export type Selection = { kind: "local" | "amd"; index: number };
export function findingTitle(rule: string) {
  if (rule === "SEMANTIC.INVALID_EVIDENCE") return "Rejected model citation";
  return rule.startsWith("ASR.SUSPECTED")
    ? "Potential instruction mismatch"
    : rule.startsWith("SEMANTIC")
      ? "Semantic advisory"
      : rule.startsWith("EVIDENCE.COMPLETENESS")
        ? "Confirm all spoken content"
        : rule.startsWith("EVIDENCE.UNCERTAIN")
          ? "Uncertain recognized words"
          : rule.replaceAll(".", " · ").replaceAll("_", " ").toLowerCase();
}
export function EvidenceInspector({
  local,
  semantic,
  selected,
  onSelect,
  children,
}: {
  local?: Review | null;
  semantic?: Review | null;
  selected: Selection;
  onSelect: (selection: Selection) => void;
  children?: React.ReactNode;
}) {
  return (
    <aside className="evidence-inspector" aria-label="Evidence inspector">
      <div className="inspector-heading">
        <Icon name="shield" />
        <div>
          <span className="eyebrow">SOURCE-LED REVIEW</span>
          <h2>Evidence inspector</h2>
        </div>
      </div>
      <p className="inspector-intro">
        Select a finding to inspect its exact source. Recognition alone does not
        establish what was spoken.
      </p>
      {(
        [
          ["local", local, "Local findings"],
          ["amd", semantic, "AMD advisories"],
        ] as const
      ).map(
        ([kind, result, title]) =>
          result && (
            <section className="inspector-group" key={kind}>
              <div className="inspector-group-heading">
                <h3>{title}</h3>
                <span>{result.findings.length}</span>
              </div>
              {!result.findings.length && (
                <p>No findings returned. Evidence prerequisites still apply.</p>
              )}
              {result.findings
                .map((f, index) => ({ f, index }))
                .sort(
                  (a, b) =>
                    Number(a.f.status === "SATISFIED") -
                    Number(b.f.status === "SATISFIED"),
                )
                .map(({ f, index }) => (
                  <button
                    type="button"
                    className={
                      "inspector-item " +
                      (selected.kind === kind && selected.index === index
                        ? "selected"
                        : "")
                    }
                    key={index}
                    aria-pressed={
                      selected.kind === kind && selected.index === index
                    }
                    aria-label={`Inspect ${kind} finding ${index + 1}: ${findingTitle(f.rule_id)}`}
                    onClick={() => onSelect({ kind, index })}
                  >
                    <div>
                      <span className="finding-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <Badge value={f.status} />
                    </div>
                    <strong>{findingTitle(f.rule_id)}</strong>
                    <small>{f.constraint_id || "Evidence quality"}</small>
                  </button>
                ))}
            </section>
          ),
      )}
      {children}
    </aside>
  );
}
