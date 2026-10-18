"""Private measurements from unchanged original files and the actual local pipeline."""
from pathlib import Path
import hashlib, json, subprocess, sys, os, wave
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dubguard.audio import AudioStore, FasterWhisperProvider, transcribe_artifact, _ffmpeg
from dubguard.quick import scenarios
from dubguard.engine import verify
from dubguard.schemas import VerificationRequest
out=ROOT/'demo/private'; out.mkdir(parents=True,exist_ok=True)
provider=FasterWhisperProvider(str(ROOT/'.dubguard-data/models/tiny.en'))
results=[]
for scenario in scenarios():
    p=ROOT/'recorded-evaluation'/f'{scenario.id}.wav'
    original=p.read_bytes()
    store=AudioStore(out/'evaluation'/scenario.id)
    artifact=store.ingest(original,content_type='audio/wav')
    result=transcribe_artifact(store,artifact,provider=provider)
    verification=verify(VerificationRequest(**scenario.policy.model_dump(),transcript=result.transcript))
    row={'file':str(p),'sha256':hashlib.sha256(original).hexdigest(),'transcription':result.model_dump(mode='json'),'verification':verification.model_dump(mode='json'),'independent_human_ground_truth':None}
    results.append(row)
    (out/'recording-results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps({'file':p.name,'duration':artifact.duration_seconds,'sha256':row['sha256'],'transcript':result.transcript.model_dump(mode='json'),'decision':verification.decision,'rules':[x.rule_id for x in verification.findings]}),flush=True)
print('FFMPEG',_ffmpeg())
