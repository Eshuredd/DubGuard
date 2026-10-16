import { useEffect, useState } from "react";
import {
  request,
  post,
  type Policy,
  type PolicyRecord,
  type Schema,
} from "../api";
type Constraint = Schema["ReviewPolicy"]["constraints"][number];
const initial = (): Policy => ({
  script: {
    id: "script-1",
    revision: "1",
    language: "en",
    speaker_count: 1,
    instructions: [
      { id: "step-1", text: "Switch the power off.", approved_variants: [] },
    ],
  },
  policy: {
    id: "policy-1",
    revision: "1",
    min_asr_confidence: 0.9,
    approved_by: "pending-human-review",
    constraints: [
      {
        id: "power-state",
        kind: "polarity",
        instruction_id: "step-1",
        approved_phrase: "off",
        reversed_phrase: "on",
      },
    ],
  },
});
export function Policies() {
  const [policy, setPolicy] = useState<Policy>(initial),
    [records, setRecords] = useState<PolicyRecord[]>([]),
    [draft, setDraft] = useState(""),
    [saved, setSaved] = useState(false),
    [attest, setAttest] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  function refresh() {
    request<PolicyRecord[]>("/review/policy-records")
      .then(setRecords)
      .catch((e) => setError(e.message));
  }
  useEffect(refresh, []);
  function edit(fn: (p: Policy) => void) {
    const next = structuredClone(policy);
    fn(next);
    setPolicy(next);
    setSaved(false);
    setAttest(false);
    setMessage("");
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      const r = await post<{ record_id: string }>(
        draft
          ? `/review/policy-drafts/${draft}/revise`
          : "/review/policy-drafts",
        policy,
      );
      setDraft(r.record_id);
      setSaved(true);
      setMessage(
        "Draft saved. Review the instructions, constraints and permitted wording before approval.",
      );
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function approve() {
    setBusy(true);
    try {
      await post(`/review/policy-drafts/${draft}/approve`);
      setMessage(
        "Policy revision explicitly approved by your authenticated identity.",
      );
      setSaved(false);
      setAttest(false);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function changeKind(index: number, kind: Constraint["kind"]) {
    edit((p) => {
      const id = p.policy.constraints[index].id,
        instruction_id = p.script.instructions[0]?.id || "";
      p.policy.constraints[index] =
        kind === "numeric"
          ? { id, kind, instruction_id }
          : kind === "polarity"
            ? {
                id,
                kind,
                instruction_id,
                approved_phrase: "",
                reversed_phrase: "",
              }
            : kind === "warning"
              ? { id, kind, instruction_id, forbidden_wordings: [] }
              : {
                  id,
                  kind,
                  instruction_ids: p.script.instructions.map((i) => i.id),
                };
    });
  }
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">POLICY WORKBENCH</span>
        <h1>Define what must stay true.</h1>
        <p>
          Explicit requirements and permitted wording. Drafts are never treated
          as approved policy.
        </p>
      </header>
      <div className="two-column policy-layout">
        <aside className="panel">
          <h2>Saved revisions</h2>
          <button
            className="secondary"
            onClick={() => {
              setPolicy(initial());
              setDraft("");
              setSaved(false);
              setAttest(false);
            }}
          >
            New draft
          </button>
          {records.map((r) => (
            <button
              className="record-item"
              key={r.id}
              onClick={() => {
                setPolicy(structuredClone(r.payload));
                setDraft(r.kind === "policy_draft" ? r.id : "");
                setSaved(r.kind === "policy_draft");
                setAttest(false);
                setMessage(
                  r.kind === "approved_policy"
                    ? "Loaded approved policy. Change revision IDs before saving a new draft."
                    : "Loaded draft.",
                );
              }}
            >
              <strong>
                {r.payload.script.id} · {r.payload.policy.revision}
              </strong>
              <small>
                {r.kind === "approved_policy" ? "Human-approved" : "Draft"} ·{" "}
                {r.payload.script.instructions.length} instructions
              </small>
            </button>
          ))}
        </aside>
        <section className="panel">
          <fieldset disabled={busy}>
            <div className="form-grid">
              <label>
                Script ID
                <input
                  value={policy.script.id}
                  onChange={(e) =>
                    edit((p) => {
                      p.script.id = e.target.value;
                    })
                  }
                />
              </label>
              <label>
                Script revision
                <input
                  value={policy.script.revision}
                  onChange={(e) =>
                    edit((p) => {
                      p.script.revision = e.target.value;
                    })
                  }
                />
              </label>
              <label>
                Policy ID
                <input
                  value={policy.policy.id}
                  onChange={(e) =>
                    edit((p) => {
                      p.policy.id = e.target.value;
                    })
                  }
                />
              </label>
              <label>
                Policy revision
                <input
                  value={policy.policy.revision}
                  onChange={(e) =>
                    edit((p) => {
                      p.policy.revision = e.target.value;
                    })
                  }
                />
              </label>
            </div>
            <h2>Instructions & permitted variants</h2>
            {policy.script.instructions.map((ins, index) => (
              <div className="editor-block" key={index}>
                <label>
                  Instruction ID
                  <input
                    value={ins.id}
                    onChange={(e) =>
                      edit((p) => {
                        p.script.instructions[index].id = e.target.value;
                      })
                    }
                  />
                </label>
                <label>
                  Approved instruction
                  <textarea
                    value={ins.text}
                    onChange={(e) =>
                      edit((p) => {
                        p.script.instructions[index].text = e.target.value;
                      })
                    }
                  />
                </label>
                {(ins.approved_variants ?? []).map((v, j) => (
                  <div className="variant" key={j}>
                    <label>
                      Permitted wording
                      <textarea
                        value={v.text}
                        onChange={(e) =>
                          edit((p) => {
                            p.script.instructions[index].approved_variants![
                              j
                            ].text = e.target.value;
                          })
                        }
                      />
                    </label>
                    <label>
                      Reason for variant
                      <input
                        value={v.reason}
                        onChange={(e) =>
                          edit((p) => {
                            p.script.instructions[index].approved_variants![
                              j
                            ].reason = e.target.value;
                          })
                        }
                      />
                    </label>
                    <button
                      className="text-button"
                      onClick={() =>
                        edit((p) => {
                          p.script.instructions[
                            index
                          ].approved_variants!.splice(j, 1);
                        })
                      }
                    >
                      Remove variant
                    </button>
                  </div>
                ))}
                <div className="actions">
                  <button
                    className="secondary"
                    onClick={() =>
                      edit((p) => {
                        (p.script.instructions[index].approved_variants ??=
                          []).push({
                          text: "",
                          reason: "",
                          approved_by: "pending-human-review",
                        });
                      })
                    }
                  >
                    Add permitted wording
                  </button>
                  <button
                    className="text-button"
                    onClick={() =>
                      edit((p) => {
                        p.script.instructions.splice(index, 1);
                      })
                    }
                  >
                    Remove instruction
                  </button>
                </div>
              </div>
            ))}
            <button
              className="secondary"
              onClick={() =>
                edit((p) => {
                  p.script.instructions.push({
                    id: `step-${p.script.instructions.length + 1}`,
                    text: "",
                    approved_variants: [],
                  });
                })
              }
            >
              Add instruction
            </button>
            <h2>Protected requirements</h2>
            {policy.policy.constraints.map((c, index) => (
              <div className="editor-block" key={index}>
                <div className="form-grid">
                  <label>
                    Requirement ID
                    <input
                      value={c.id}
                      onChange={(e) =>
                        edit((p) => {
                          p.policy.constraints[index].id = e.target.value;
                        })
                      }
                    />
                  </label>
                  <label>
                    Check type
                    <select
                      value={c.kind}
                      onChange={(e) =>
                        changeKind(index, e.target.value as Constraint["kind"])
                      }
                    >
                      <option value="polarity">
                        Polarity / opposite meaning
                      </option>
                      <option value="numeric">Numbers, limits and units</option>
                      <option value="warning">Protected warning</option>
                      <option value="sequence">Operation sequence</option>
                    </select>
                  </label>
                </div>
                {c.kind === "sequence" ? (
                  <label>
                    Instruction IDs in required order (comma separated)
                    <input
                      value={c.instruction_ids.join(",")}
                      onChange={(e) =>
                        edit((p) => {
                          (
                            p.policy.constraints[
                              index
                            ] as Schema["SequenceConstraint"]
                          ).instruction_ids = e.target.value
                            .split(",")
                            .map((s) => s.trim());
                        })
                      }
                    />
                  </label>
                ) : (
                  <label>
                    Protected instruction
                    <select
                      value={c.instruction_id}
                      onChange={(e) =>
                        edit((p) => {
                          const constraint = p.policy.constraints[index];
                          if (constraint.kind !== "sequence")
                            constraint.instruction_id = e.target.value;
                        })
                      }
                    >
                      {policy.script.instructions.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.id} · {i.text}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {c.kind === "polarity" && (
                  <div className="form-grid">
                    <label>
                      Approved phrase
                      <input
                        value={c.approved_phrase}
                        onChange={(e) =>
                          edit((p) => {
                            (
                              p.policy.constraints[
                                index
                              ] as Schema["PolarityConstraint"]
                            ).approved_phrase = e.target.value;
                          })
                        }
                      />
                    </label>
                    <label>
                      Dangerous reversal
                      <input
                        value={c.reversed_phrase}
                        onChange={(e) =>
                          edit((p) => {
                            (
                              p.policy.constraints[
                                index
                              ] as Schema["PolarityConstraint"]
                            ).reversed_phrase = e.target.value;
                          })
                        }
                      />
                    </label>
                  </div>
                )}
                {c.kind === "warning" && (
                  <label>
                    Declared dangerous alternatives (one per line)
                    <textarea
                      value={(c.forbidden_wordings ?? []).join("\n")}
                      onChange={(e) =>
                        edit((p) => {
                          (
                            p.policy.constraints[
                              index
                            ] as Schema["WarningConstraint"]
                          ).forbidden_wordings = e.target.value
                            .split("\n")
                            .filter(Boolean);
                        })
                      }
                    />
                  </label>
                )}
                {c.kind === "numeric" && (
                  <p>
                    Protects all supported quantities, ranges and units in the
                    selected instruction.
                  </p>
                )}
                <button
                  className="text-button"
                  onClick={() =>
                    edit((p) => {
                      p.policy.constraints.splice(index, 1);
                    })
                  }
                >
                  Remove requirement
                </button>
              </div>
            ))}
            <button
              className="secondary"
              onClick={() =>
                edit((p) => {
                  p.policy.constraints.push({
                    id: `requirement-${p.policy.constraints.length + 1}`,
                    kind: "numeric",
                    instruction_id: p.script.instructions[0]?.id || "",
                  });
                })
              }
            >
              Add requirement
            </button>
            <hr />
            <button onClick={save}>Save policy draft</button>
            <label className="check">
              <input
                type="checkbox"
                checked={attest}
                onChange={(e) => setAttest(e.target.checked)}
                disabled={!saved}
              />
              I reviewed the saved instructions, constraints and every permitted
              wording.
            </label>
            <button disabled={!saved || !attest} onClick={approve}>
              Approve saved policy revision
            </button>
          </fieldset>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="notice">
              {message}
            </p>
          )}
        </section>
      </div>
    </>
  );
}
