"""Explicit setup-time model download; never runs inside the request pipeline."""
import os
import re
import argparse
from huggingface_hub import snapshot_download

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', default=os.environ.get('DUBGUARD_WHISPER_REVISION', ''))
parser.add_argument('--output', default='/models/tiny.en')
args = parser.parse_args()
revision = args.revision
if not re.fullmatch(r"[0-9a-f]{40}", revision):
    raise SystemExit("Set DUBGUARD_WHISPER_REVISION to the reviewed Hugging Face model commit SHA")
snapshot_download("Systran/faster-whisper-tiny.en", revision=revision,
                  local_dir=args.output, token=False, allow_patterns=["*.json", "*.txt", "*.bin"])
from faster_whisper import WhisperModel
WhisperModel(args.output, device="cpu", compute_type="int8", local_files_only=True,
             cpu_threads=2, num_workers=1)
print("Cached tiny.en model loads on CPU; speech accuracy has not been measured.")
