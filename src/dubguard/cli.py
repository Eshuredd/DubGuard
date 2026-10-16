import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from .engine import verify
from .evaluation import evaluate, export_report
from .schemas import ScriptPolicy, VerificationRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DubGuard local review aid; never safety approval")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate script and policy JSON")
    validate.add_argument("input", type=Path)
    verification = sub.add_parser("verify", help="Review a script, policy, and transcript JSON request")
    verification.add_argument("input", type=Path)
    verification.add_argument("--hybrid", action="store_true", help="Request advisory semantic verification; unavailable inference requires review")
    evaluation = sub.add_parser("evaluate", help="Run explicit synthetic fixtures and export JSON/Markdown")
    evaluation.add_argument("--output", type=Path, default=Path("reports"))
    evaluation.add_argument("--hybrid", action="store_true", help="Show hybrid path; this alone never starts remote calls")
    evaluation.add_argument("--remote", action="store_true", help="Explicitly opt into real basic-LLM and hybrid evaluation calls")
    evaluation.add_argument("--max-cases", type=int, help="Required positive cap for --remote; two model calls per selected case")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            data = ScriptPolicy.model_validate_json(args.input.read_text(encoding="utf-8"))
            print(json.dumps({"valid": True, "script_id": data.script.id, "policy_id": data.policy.id}))
        elif args.command == "verify":
            data = VerificationRequest.model_validate_json(args.input.read_text(encoding="utf-8"))
            print(verify(data, hybrid=args.hybrid).model_dump_json(indent=2))
        else:
            report = evaluate(hybrid=args.hybrid or args.remote, remote=args.remote, max_cases=args.max_cases)
            paths = export_report(report, args.output)
            print(json.dumps({"reports": [str(p.resolve()) for p in paths],
                              "paths": {name: {"status": value["status"], "metrics": value["metrics"]} for name, value in report["paths"].items()}}, indent=2))
    except (ValidationError, ValueError, OSError) as error:
        # Validation details can include input text; do not dump them to server logs.
        print(json.dumps({"error": type(error).__name__, "message": "Invalid input, configuration, or file. Use /validate for schema validation details."}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
