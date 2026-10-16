"""Reproducible evaluation on explicit synthetic cases, never model-generated labels."""

from collections import Counter
from hashlib import sha256
from importlib import metadata, resources
import json
from pathlib import Path
import platform

from .engine import uncertainty, verify
from .providers import SemanticProvider, provider_from_env
from .schemas import Decision, EvaluationCase, ScriptPolicy, SemanticAssessment, VerificationRequest
from .text import normalize

EXPECTED = {"ACCEPTABLE": "PASS_CANDIDATE", "CRITICAL": "CRITICAL_DEVIATION", "UNRESOLVED": "REVIEW_REQUIRED"}


def load_dataset() -> tuple[dict[str, ScriptPolicy], list[EvaluationCase], str]:
    root = resources.files("dubguard").joinpath("data")
    profile_bytes = root.joinpath("profiles.json").read_bytes()
    case_bytes = root.joinpath("cases.json").read_bytes()
    profiles = {key: ScriptPolicy.model_validate(value) for key, value in json.loads(profile_bytes).items()}
    cases = [EvaluationCase.model_validate(value) for value in json.loads(case_bytes)]
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("evaluation case IDs must be unique")
    if any(c.profile not in profiles for c in cases):
        raise ValueError("unknown profile in evaluation fixture")
    return profiles, cases, sha256(profile_bytes + b"\n" + case_bytes).hexdigest()


def request_for(case: EvaluationCase, profiles: dict[str, ScriptPolicy]) -> VerificationRequest:
    return VerificationRequest(**profiles[case.profile].model_dump(), transcript=case.transcript)


def baseline(request: VerificationRequest) -> Decision:
    """Intentionally naive normalized text difference, with an evidence-quality gate.

    No policy, approved variants, numeric conversions, or semantic model is used.
    It is an evaluation comparator, not the production verification endpoint.
    """
    if request.transcript.completeness != "complete" or any(uncertainty(s, request) for s in request.transcript.segments):
        return Decision.REVIEW_REQUIRED
    approved = " | ".join(normalize(i.text) for i in request.script.instructions)
    observed = " | ".join(normalize(s.text) for s in request.transcript.segments)
    return Decision.PASS_CANDIDATE if approved == observed else Decision.CRITICAL_DEVIATION


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def calculate_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    critical = [r for r in rows if r["label"] == "CRITICAL"]
    acceptable = [r for r in rows if r["label"] == "ACCEPTABLE"]
    tp = sum(r["decision"] == "CRITICAL_DEVIATION" for r in critical)
    fp = sum(r["decision"] == "CRITICAL_DEVIATION" and r["label"] != "CRITICAL" for r in rows)
    false_alerts = sum(r["decision"] == "CRITICAL_DEVIATION" for r in acceptable)
    reviews = sum(r["decision"] == "REVIEW_REQUIRED" for r in rows)
    categories = {}
    for category in sorted({r["category"] for r in rows}):
        selected = [r for r in rows if r["category"] == category]
        categories[category] = {
            "count": len(selected),
            "errors": sum(r["decision"] != EXPECTED[r["label"]] for r in selected),
            "critical_misses": sum(r["label"] == "CRITICAL" and r["decision"] != "CRITICAL_DEVIATION" for r in selected),
            "false_critical_alerts": sum(r["label"] != "CRITICAL" and r["decision"] == "CRITICAL_DEVIATION" for r in selected),
            "unsafe_passes": sum(r["label"] != "ACCEPTABLE" and r["decision"] == "PASS_CANDIDATE" for r in selected),
        }
    return {
        "total": n, "label_counts": dict(sorted(Counter(r["label"] for r in rows).items())),
        "true_positives": tp, "false_positives": fp, "false_negatives": len(critical) - tp,
        "critical_deviation_recall": _ratio(tp, len(critical)),
        "critical_deviation_precision": _ratio(tp, tp + fp),
        "false_alert_count_on_acceptable": false_alerts,
        "false_alert_rate_on_acceptable": _ratio(false_alerts, len(acceptable)),
        "acceptable_escalation_rate": _ratio(sum(r["decision"] != "PASS_CANDIDATE" for r in acceptable), len(acceptable)),
        "unresolved_count": reviews, "unresolved_rate": _ratio(reviews, n),
        "unsafe_passes": sum(r["label"] != "ACCEPTABLE" and r["decision"] == "PASS_CANDIDATE" for r in rows),
        "decision_errors": sum(r["decision"] != EXPECTED[r["label"]] for r in rows),
        "per_category": categories,
    }


def evaluate(*, hybrid: bool = False, provider: SemanticProvider | None = None,
             remote: bool = False, max_cases: int | None = None) -> dict:
    """Local paths always run; live AMD paths require remote=True and a case cap."""
    if remote and not hybrid:
        raise ValueError("remote evaluation requires hybrid=True")
    if remote and (max_cases is None or max_cases < 1):
        raise ValueError("remote evaluation requires an explicit positive max_cases")
    if not remote and max_cases is not None:
        raise ValueError("max_cases requires remote=True")
    profiles, cases, fingerprint = load_dataset()
    rows_a, rows_b, rows_subset, rows_basic, rows_c = [], [], [], [], []
    active_provider = (provider or provider_from_env()) if hybrid else None
    run_remote = bool(remote and active_provider.real_inference_available)
    selected_count = min(max_cases or 0, len(cases)) if remote else 0
    for index, case in enumerate(cases):
        request = request_for(case, profiles)
        base = {"id": case.id, "category": case.category, "label": case.label.value,
                "rationale": case.rationale, "profile": case.profile,
                "approved_text": [i.text for i in request.script.instructions],
                "observed_text": [s.text for s in request.transcript.segments]}
        rows_a.append({**base, "decision": baseline(request).value})
        deterministic = verify(request)
        rows_b.append({**base, "decision": deterministic.decision.value,
                       "result": deterministic.model_dump(mode="json")})
        if run_remote and index < selected_count:
            rows_subset.append(rows_b[-1])
            try:
                baseline_assessment = SemanticAssessment.model_validate(active_provider.verify_basic(request))
            except Exception:
                baseline_assessment = SemanticAssessment(provider="unavailable", status="unavailable",
                                                          explanation="Basic LLM provider failed.")
            basic_decision = {"EQUIVALENT": Decision.PASS_CANDIDATE,
                              "DEVIATION": Decision.CRITICAL_DEVIATION,
                              "UNRESOLVED": Decision.REVIEW_REQUIRED}[baseline_assessment.verdict]
            if baseline_assessment.status != "real":
                basic_decision = Decision.REVIEW_REQUIRED
            rows_basic.append({**base, "decision": basic_decision.value,
                               "semantic": baseline_assessment.model_dump(mode="json")})
            result = verify(request, hybrid=True, provider=active_provider)
            rows_c.append({**base, "decision": result.decision.value, "result": result.model_dump(mode="json")})

    def path_report(rows):
        return {"status": "measured", "metrics": calculate_metrics(rows), "cases": rows,
                "failures": [r for r in rows if r["decision"] != EXPECTED[r["label"]]]}

    if run_remote:
        good_basic = all(r["semantic"]["status"] == "real" and r["semantic"]["response_valid"] for r in rows_basic)
        good_hybrid = all(r["result"]["semantic"]["status"] == "real"
                          and r["result"]["semantic"]["response_valid"]
                          and not r["result"]["semantic"]["issues"] for r in rows_c)
        basic_report = path_report(rows_basic) if good_basic else {
            "status": "incomplete", "metrics": None, "cases": rows_basic,
            "reason": "At least one basic LLM call failed or returned invalid JSON; no aggregate result is claimed."}
        hybrid_report = path_report(rows_c) if good_hybrid else {
            "status": "incomplete", "metrics": None, "cases": rows_c,
            "reason": "At least one hybrid call failed or returned invalid evidence; no aggregate result is claimed."}
    else:
        basic_report = {"status": "skipped", "metrics": None, "cases": [],
                        "reason": "Basic LLM baseline requires explicit remote opt-in and real inference."}
        hybrid_report = {"status": "skipped", "metrics": None, "cases": [],
                         "reason": "Real inference is unavailable or was not requested. No mock/LLM/AMD performance result is claimed."}
    package_root = resources.files("dubguard")
    code_files = ["schemas.py", "text.py", "engine.py", "providers.py", "semantic_validation.py", "evaluation.py"]
    paths = {"A_normalized_diff": path_report(rows_a), "B_policy_engine": path_report(rows_b)}
    if run_remote:
        paths["B_policy_engine_selected_cases"] = path_report(rows_subset)
    paths["D_basic_llm"] = basic_report
    paths["C_hybrid"] = hybrid_report
    return {
        "schema_version": "1", "engine_version": "0.2.0", "dataset_sha256": fingerprint,
        "code_sha256": {name: sha256(package_root.joinpath(name).read_bytes()).hexdigest() for name in code_files},
        "runtime": {"python": platform.python_version(), **{p: metadata.version(p) for p in ("pydantic", "fastapi")}},
        "dataset": {"count": len(cases), "profiles": len(profiles),
                    "remote_selected_count": selected_count if run_remote else 0,
                    "label_origin": "Explicit synthetic fixtures with manually specified labels and rationales; no external LLM labels or industrial validation."},
        "remote_request_attempts": (sum((r["semantic"].get("attempts") or 0) for r in rows_basic)
                                    + sum((r["result"]["semantic"].get("attempts") or 0) for r in rows_c)),
        "metric_definitions": {
            "critical_deviation_recall": "critical predicted critical / all critical; critical sent to review counts as a miss",
            "critical_deviation_precision": "critical predicted critical / all predicted critical; unresolved labels predicted critical count as false positives",
            "false_alert_rate_on_acceptable": "acceptable predicted critical / all acceptable",
            "acceptable_escalation_rate": "acceptable predicted critical or review / all acceptable",
            "unresolved_rate": "REVIEW_REQUIRED decisions / all cases; critical results may also contain unresolved findings",
            "decision_errors": "decision differs from label mapping ACCEPTABLE->PASS_CANDIDATE, CRITICAL->CRITICAL_DEVIATION, UNRESOLVED->REVIEW_REQUIRED",
            "undefined_ratios": "null when denominator is zero",
        },
        "limitations": ["Small, curated synthetic development set, not a held-out industrial benchmark.",
                        "Instruction mappings and transcript completeness are supplied review metadata.",
                        "No audio transcription or industrial safety approval is demonstrated.",
                        "Basic LLM verdicts are diagnostic evaluation outputs, not production approval decisions."],
        "paths": paths,
    }


def markdown_report(report: dict) -> str:
    lines = ["# DubGuard synthetic evaluation", "",
             f"Cases: **{report['dataset']['count']}**. Profiles: **{report['dataset']['profiles']}**.", "",
             f"Dataset SHA-256: `{report['dataset_sha256']}`", "",
             "Local paths are reproducible development results. Remote paths, if measured, use actual calls on the explicit selected subset. None is safety certification.", "",
             "| Path | Count | Recall | Precision | Acceptable false-alert rate | Unresolved rate | Errors | Unsafe passes |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    def percent(value):
        return "n/a" if value is None else f"{value:.2%}"
    for name, path in report["paths"].items():
        m = path.get("metrics")
        if m is None:
            lines.append(f"| {name} ({path['status']}) | — | — | — | — | — | — | — |")
        else:
            lines.append(f"| {name} | {m['total']} | {percent(m['critical_deviation_recall'])} | {percent(m['critical_deviation_precision'])} | {percent(m['false_alert_rate_on_acceptable'])} | {percent(m['unresolved_rate'])} | {m['decision_errors']} | {m['unsafe_passes']} |")
    lines += ["", "## Definitions and scope", ""]
    for key, value in report["metric_definitions"].items():
        lines.append(f"- **{key}**: {value}.")
    lines += ["", "Label counts: " + json.dumps(report["paths"]["B_policy_engine"]["metrics"]["label_counts"], sort_keys=True) + ".", ""]
    for name, path in report["paths"].items():
        lines += [f"## {name}", ""]
        if path.get("metrics") is None:
            lines += [path["reason"], ""]
            continue
        lines += ["| Category | Cases | Errors | Critical misses | False critical alerts | Unsafe passes |",
                  "|---|---:|---:|---:|---:|---:|"]
        for category, counts in path["metrics"]["per_category"].items():
            lines.append(f"| {category} | {counts['count']} | {counts['errors']} | {counts['critical_misses']} | {counts['false_critical_alerts']} | {counts['unsafe_passes']} |")
        lines += ["", "### Failure examples (all decision mismatches)", ""]
        if not path["failures"]:
            lines += ["None on this synthetic set.", ""]
        for failure in path["failures"]:
            lines += [f"- **{failure['id']}** ({failure['category']}): expected {EXPECTED[failure['label']]}; observed {failure['decision']}.",
                      "  Approved: " + json.dumps(failure["approved_text"], ensure_ascii=False) + ".",
                      "  Observed: " + json.dumps(failure["observed_text"], ensure_ascii=False) + ".",
                      "  Label rationale: " + failure["rationale"]]
        lines += [""]
    lines += ["## Limitations", ""] + ["- " + limitation for limitation in report["limitations"]]
    return "\n".join(lines) + "\n"


def export_report(report: dict, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path, md_path = directory / "evaluation.json", directory / "evaluation.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")
    return json_path, md_path
