"""Local-container public demo boundary checks. Never accepts an external host.

Use only with the documented disposable public-mode override and blank AMD key.
Synthetic silence, real CPU decode/ASR. No paid inference or human ground truth.
"""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import time
import wave

import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True, help='Ignored private local state file; never publish')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--after-restart', action='store_true')
args = parser.parse_args()
base = 'http://127.0.0.1:18080/api'
c = httpx.Client(base_url=base, timeout=90, follow_redirects=False)
if args.after_restart:
    state = json.loads(args.state.read_text())
    headers = {'Authorization': 'Bearer '+state['token']}
    assert c.post('/quick/sessions').status_code == 429
    assert sha256(c.get('/quick/audio', headers=headers).content).hexdigest() == state['audio_hash']
    for token in state['tokens']:
        assert c.delete('/quick/session', headers={'Authorization': 'Bearer '+token}).status_code == 200
    assert c.get('/quick/audio', headers=headers).status_code == 401
    assert c.post('/quick/sessions').status_code == 429
    result = json.loads(args.output.read_text())
    result.update(restart_preserved_audio_and_client_quota=True, deletion_preserved_client_quota=True, authenticated_deletion=True)
    args.state.unlink()
else:
    config = c.get('/quick/config').json()
    assert config == {'public_local': True, 'amd_available': False}
    assert c.get('/health').status_code == 200 and c.get('/ready').status_code == 200
    for method, path in [('GET','/quick/audio'),('GET','/quick/session'),('DELETE','/quick/session')]:
        assert c.request(method, path).status_code == 401
    sessions = []
    for i in range(4):
        r = c.post('/quick/sessions', headers={'X-Forwarded-For': f'203.0.113.{i}'})
        assert r.status_code == 200, r.status_code
        sessions.append(r.json())
    assert c.post('/quick/sessions', headers={'X-Forwarded-For': '198.51.100.99'}).status_code == 429
    s = sessions[0]
    headers = {'Authorization': 'Bearer '+s['token']}
    assert c.post('/quick/analyze?scenario_id=correct&mode=amd&consent=true', headers=headers, content=b'not parsed').status_code == 503
    assert c.post('/quick/analyze?scenario_id=correct', headers=headers, content=b'x'*10_065_537).status_code == 413
    b = io.BytesIO()
    with wave.open(b, 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(b'\0\0'*32000)
    audio = b.getvalue()
    start = time.perf_counter()
    assert c.post('/quick/analyze?scenario_id=correct', headers=headers, files={'file': ('synthetic-silence.wav', audio, 'audio/wav')}).status_code == 200
    report = {}
    for _ in range(90):
        report = c.get('/quick/session', headers=headers).json()
        if report['state'] != 'PROCESSING':
            break
        time.sleep(.5)
    assert report['state'] == 'COMPLETE', report.get('error')
    assert report['amd_runs'] == 0 and report['mode'] == 'local' and report['semantic_verification'] is None
    assert report['verification']['decision'] == 'REVIEW_REQUIRED'
    assert c.get('/quick/audio', headers=headers).content == audio
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps({'token': s['token'], 'tokens': [s['token'] for s in sessions], 'audio_hash': sha256(audio).hexdigest()}))
    args.state.chmod(0o600)
    result = {'fixture': 'Synthetic two-second silence; real CPU ASR, no speech/ground-truth claims',
              'public_local': True, 'amd_available': False, 'amd_calls': 0,
              'anonymous_audio_rejected': True, 'caddy_forwarded_spoof_rejected': True,
              'client_admission_limit': 4, 'oversized_body_rejected': True,
              'amd_without_configuration_rejected_before_body': True, 'local_decision': report['verification']['decision'],
              'original_audio_bytes_preserved': True, 'local_pipeline_seconds': round(time.perf_counter()-start,3)}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2))
print('Local public boundary checks passed; report contains no session capability or credential.')
