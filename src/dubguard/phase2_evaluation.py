"""Separate development subsets and explicit gaps for real-audio evaluation."""

import argparse
from hashlib import sha256
from importlib import resources
import json
from pathlib import Path

from .evaluation import calculate_metrics, evaluate


def phase2_report() -> dict:
    source = resources.files("dubguard").joinpath("data/phase2_sets.json").read_bytes()
    definitions = json.loads(source)
    local = evaluate()
    rows = {name: {row["id"]: row for row in local["paths"][name]["cases"]}
            for name in ("A_normalized_diff", "B_policy_engine")}
    result = {}
    for name, definition in definitions.items():
        ids = definition["case_ids"]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate case ID in {name}")
        if any(case_id not in rows["B_policy_engine"] for case_id in ids):
            raise ValueError(f"unknown case ID in {name}")
        if definition["origin"] != "synthetic_text_development":
            result[name] = {"status": "awaiting_human_verified_data", "count": 0,
                            "origin": definition["origin"], "metrics": None}
            continue
        result[name] = {"status": "measured_development_only", "count": len(ids),
                        "origin": definition["origin"],
                        "paths": {path: calculate_metrics([rows[path][case_id] for case_id in ids])
                                  for path in rows}}
    return {"schema_version": "1", "set_definition_sha256": sha256(source).hexdigest(),
            "source_dataset_sha256": local["dataset_sha256"], "sets": result,
            "remote_paths": {"basic_llm": "not_run", "well_prompted_llm": "not_run",
                             "hybrid_amd": "not_run"},
            "limitations": ["Text subsets reuse the original 60 synthetic development cases; they are not new held-out evidence.",
                            "No human-verified recorded audio or review sessions were supplied, so audio and workload metrics are undefined.",
                            "No remote benchmark or MiMo audio probe was run."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate local Phase 2 evaluation subset report")
    parser.add_argument("--output", type=Path, default=Path("reports/phase2_sets.json"))
    args = parser.parse_args(argv)
    report = phase2_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
