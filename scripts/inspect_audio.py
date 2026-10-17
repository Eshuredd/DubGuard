"""Inspect/decode one local recording without ASR, uploads or remote inference."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from dubguard.audio import AudioStore, AudioError


def inspect(path: Path):
    with path.open('rb') as source:
        data = source.read(25_000_001)
    if len(data) > 25_000_000:
        raise AudioError('Recording exceeds 25 MB; split or re-record it before evaluation')
    with TemporaryDirectory(prefix='dubguard-inspect-') as directory:
        artifact = AudioStore(Path(directory)).ingest(data, max_bytes=25_000_000, max_seconds=120)
    return {'artifact': artifact.model_dump(mode='json'), 'decode_validated': True,
            'asr_performed': False, 'remote_calls': 0,
            'note': 'Container/decoding validity does not establish speech or ground truth. Quick Test has a stricter 10 MB / 60 second limit.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.audio), indent=2))
    except (AudioError, OSError):
        raise SystemExit('Audio validation failed: check supported format, decoding and 25 MB / 120 second limits.') from None
