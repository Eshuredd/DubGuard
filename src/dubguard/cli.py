import argparse
import json
import os
from pathlib import Path
import sys

from pydantic import ValidationError

from .engine import verify
from .evaluation import evaluate, export_report
from .schemas import ScriptPolicy, VerificationRequest
from .audio import AudioStore, transcribe_artifact
from .providers import _load_project_env


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
    evaluation.add_argument("--max-cases", type=int, help="Required positive cap for --remote; two calls per case, or three with --policy-baseline")
    evaluation.add_argument("--policy-baseline", action="store_true",
                            help="With --remote, add one policy-prompted LLM call per selected case")
    transcription = sub.add_parser("transcribe-audio", help="Locally transcribe a WAV/MP3 with provisional CPU ASR")
    transcription.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            data = ScriptPolicy.model_validate_json(args.input.read_text(encoding="utf-8"))
            print(json.dumps({"valid": True, "script_id": data.script.id, "policy_id": data.policy.id}))
        elif args.command == "verify":
            data = VerificationRequest.model_validate_json(args.input.read_text(encoding="utf-8"))
            print(verify(data, hybrid=args.hybrid).model_dump_json(indent=2))
        elif args.command == "transcribe-audio":
            _load_project_env()
            root = Path(os.getenv("DUBGUARD_DATA_DIR", ".dubguard-data")) / "artifacts"
            store = AudioStore(root)
            maximum = int(os.getenv("DUBGUARD_MAX_UPLOAD_BYTES", "25000000"))
            with args.input.open("rb") as stream:
                data = stream.read(maximum + 1)
            artifact = store.ingest(data)
            print(transcribe_artifact(store, artifact).model_dump_json(indent=2))
        else:
            report = evaluate(hybrid=args.hybrid or args.remote, remote=args.remote,
                              max_cases=args.max_cases, policy_baseline=args.policy_baseline)
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
