"""Validate private human-recording manifest and hashes without ASR or inference."""
import argparse
from hashlib import sha256
from pathlib import Path
from pydantic import ValidationError
from dubguard.audio_evaluation import RecordedManifest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('manifest', type=Path)
args = parser.parse_args()
try:
    manifest = RecordedManifest.model_validate_json(args.manifest.read_bytes())
    for case in manifest.cases:
        if not case.audio_path.is_absolute():
            raise ValueError('Every audio_path must be absolute')
        with case.audio_path.open('rb') as source:
            digest = sha256()
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != case.audio_sha256:
            raise ValueError('Recording hash mismatch')
        if 'REPLACE_WITH' in case.policy.policy.approved_by:
            raise ValueError('Replace policy reviewer placeholders after actual review')
except (ValidationError, ValueError, OSError):
    raise SystemExit('Manifest incomplete or invalid: check required human evidence, absolute audio paths, hashes and policy review. No inference performed.') from None
print(f'Validated schema and recording hashes for {len(manifest.cases)} cases. Human labels remain supplied metadata, not independently authenticated facts. No inference performed.')
