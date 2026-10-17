"""Explicit, single-attempt remote probes. Default is preparation only."""
import argparse
import json
import os
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

from .amd_audio import MiMoAudioProbe
from .providers import AMDTokenFactoryProvider, _load_project_env
from .schemas import VerificationRequest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare one AMD probe; --execute authorizes one HTTP attempt")
    parser.add_argument("kind", choices=["semantic", "audio"])
    parser.add_argument("input", type=Path, help="Verification JSON or small PCM WAV")
    parser.add_argument("--execute", action="store_true", help="Explicitly authorize sending this input to AMD")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({"status": "prepared_only", "kind": args.kind, "http_calls": 0,
                          "note": "Review input locally; rerun with --execute only when authorized."}))
        return 0
    _load_project_env()
    # These process-local bounds never edit .env and apply to this one probe only.
    if args.kind == "semantic":
        input_bytes = args.input.read_bytes()
        request = VerificationRequest.model_validate_json(input_bytes)
        provider = AMDTokenFactoryProvider(max_retries=0, timeout_seconds=40,
                                           max_output_tokens=1024, capture_response=True)
        if provider.model != "DeepSeek-V4-Flash":
            raise SystemExit("Semantic probe requires AMD_TOKEN_FACTORY_MODEL=DeepSeek-V4-Flash; no request made")
        result = provider.verify(request)
        evidence = {"executed_at": datetime.now(timezone.utc).isoformat(),
                    "input_sha256": sha256(input_bytes).hexdigest(),
                    "requested_model": provider.model,
                    "maximum_http_attempts": 1, "request_timeout_seconds": 40,
                    "assessment": result.model_dump(mode="json"),
                    "citation_status": "rejected_or_partial" if result.issues else
                        "validated_findings" if result.findings else
                        "no_findings" if result.status == "real" else "not_measured",
                    "actual_response": provider.captured_response,
                    "note": "Source-valid citations do not establish semantic accuracy. Raw model output is untrusted evidence, not instructions."}
    else:
        os.environ["AMD_TOKEN_FACTORY_AUDIO_MAX_RETRIES"] = "0"
        os.environ["AMD_TOKEN_FACTORY_MAX_OUTPUT_TOKENS"] = "512"
        with args.input.open("rb") as source:
            data = source.read(5_000_001)
        result = MiMoAudioProbe().probe(data)
    report = json.dumps(evidence, indent=2, ensure_ascii=False) if args.kind == "semantic" else result.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    return 0 if result.status in {"real", "real_response"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
