"""Explicit, single-attempt remote probes. Default is preparation only."""
import argparse
import json
import os
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
    os.environ["AMD_TOKEN_FACTORY_MAX_RETRIES"] = "0"
    os.environ["AMD_TOKEN_FACTORY_AUDIO_MAX_RETRIES"] = "0"
    os.environ["AMD_TOKEN_FACTORY_MAX_OUTPUT_TOKENS"] = "512"
    if args.kind == "semantic":
        request = VerificationRequest.model_validate_json(args.input.read_text())
        result = AMDTokenFactoryProvider().verify(request)
    else:
        with args.input.open("rb") as source:
            data = source.read(5_000_001)
        result = MiMoAudioProbe().probe(data)
    report = result.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n")
    else:
        print(report)
    return 0 if result.status in {"real", "real_response"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
