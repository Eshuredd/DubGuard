"""Local CPU pipeline smoke using generated silence, never a speech accuracy test."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import wave

from dubguard.audio import AudioStore, FasterWhisperProvider, transcribe_artifact
from dubguard.engine import verify
from dubguard.quick import scenarios
from dubguard.schemas import VerificationRequest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model-path', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
model = args.model_path.resolve()
data = io.BytesIO()
with wave.open(data, 'wb') as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16000)
    output.writeframes(b'\0\0' * 32000)
began = time.perf_counter()
with TemporaryDirectory(prefix='dubguard-cpu-smoke-') as temp:
    store = AudioStore(Path(temp))
    artifact = store.ingest(data.getvalue(), content_type='audio/wav')
    transcription = transcribe_artifact(store, artifact, FasterWhisperProvider(str(model), local_files_only=True))
    result = verify(VerificationRequest(**scenarios()[0].policy.model_dump(mode='json'), transcript=transcription.transcript))
    report = {'input': 'Generated two seconds of silent PCM. No human speech or accuracy labels.',
        'input_sha256': artifact.sha256, 'model': 'Systran/faster-whisper-tiny.en',
        'model_bin_sha256': sha256((model / 'model.bin').read_bytes()).hexdigest(),
        'model_bytes': sum(p.stat().st_size for p in model.iterdir() if p.is_file()),
        'backend': 'faster-whisper / CTranslate2 CPU int8', 'gpu_used': False,
        'amd_calls': 0, 'quark_used': False, 'transcription': transcription.model_dump(mode='json'),
        'verification': result.model_dump(mode='json'), 'wall_seconds': time.perf_counter() - began,
        'limitations': 'Execution/coverage smoke only. Silence is not real speech; no speech accuracy, GPU speedup, or semantic validity measured.'}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(args.output)
