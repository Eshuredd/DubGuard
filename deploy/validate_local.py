"""Exercise the isolated dubguard-phase5 Compose stack, with generated silence only.

Requires already built/running containers, a cached model and a disposable local
configuration with a BLANK AMD key. Restarts/recreates only this named test stack.
Never use against a public server or retained production evidence.
"""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit
import wave

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'dubguard-phase5'
MODEL_REVISION = '0d3d19a32d3338f10357c0889762bd8d64bbdeba'


def validate(env_file, origin):
    url = urlsplit(origin)
    if url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1'} or url.path or url.query or url.fragment or url.username:
        raise ValueError('This destructive test-stack check requires a plain HTTP localhost origin')
    config = dotenv_values(env_file)
    if config.get('AMD_TOKEN_FACTORY_API_KEY'):
        raise ValueError('Test configuration must have a blank AMD key; no live inference is allowed')
    credentials = json.loads(config['DUBGUARD_REVIEW_TOKENS_JSON'])
    token = next(iter(credentials.values()))
    env = {**os.environ, 'DUBGUARD_SERVER_ENV': str(env_file.resolve()),
           'DUBGUARD_DOMAIN': ':8080', 'DUBGUARD_WHISPER_REVISION': MODEL_REVISION}
    if url.port:
        env['DUBGUARD_LOCAL_PORT'] = str(url.port)
    compose = ['docker', 'compose', '-p', PROJECT, '-f', str(ROOT / 'deploy/compose.yaml'),
               '-f', str(ROOT / 'deploy/compose.local.yaml')]

    def dc(*args):
        process = subprocess.run(compose + list(args), env=env, capture_output=True, text=True, timeout=180)
        if process.returncode:
            raise RuntimeError('Local test Compose operation failed: ' + ' '.join(args[:2]))
        return process.stdout

    def execute(code):
        return dc('exec', '-T', 'api', 'python', '-c', code)

    def wait_ready(client):
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            try:
                response = client.get('/api/ready')
                if response.status_code == 200 and response.json()['ready']:
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError('Local API did not become ready')

    model_inventory = """import os,json,hashlib
from pathlib import Path
assert not os.environ.get('AMD_TOKEN_FACTORY_API_KEY')
assert os.environ['HF_HUB_OFFLINE']=='1'
assert os.getuid()==10001
root=Path('/models/tiny.en')
result={'uid':os.getuid(),'offline':True,'amd_key_present':False,'files':{}}
for path in sorted(root.iterdir()):
    if path.is_file():
        result['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
try:
    (root/'must-not-write').write_text('test')
except OSError:
    result['model_volume_read_only']=True
else:
    raise AssertionError('Model mount is writable')
print(json.dumps(result))
"""
    report = {'project': PROJECT, 'origin': origin, 'input': 'Generated two-second silent PCM; no human speech',
              'amd_calls': 0, 'model_revision': MODEL_REVISION, 'checks': {}}
    before = json.loads(execute(model_inventory))
    report['runtime'] = {k: v for k, v in before.items() if k != 'files'}
    report['model_files'] = before['files']
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000)
        out.writeframes(b'\0\0' * 32000)
    pcm = audio.getvalue()
    report['audio_sha256'] = sha256(pcm).hexdigest()
    with httpx.Client(base_url=origin, timeout=90, trust_env=False) as client:
        wait_ready(client)
        assert client.get('/api/health').json()['status'] == 'ok'
        for path in ('/test', '/login', '/review/example-deep-link'):
            response = client.get(path)
            assert response.status_code == 200 and '<html' in response.text.lower()
        html = client.get('/test')
        assert html.headers['permissions-policy'] == 'microphone=(self)'
        assert "frame-ancestors 'none'" in html.headers['content-security-policy']
        asset = re.search(r'src="([^"]+\.js)"', html.text).group(1)
        assert client.get(asset).status_code == 200
        assert len(client.get('/api/quick/scenarios').json()) == 6
        assert client.get('/api/review/workflows').status_code == 401
        report['checks']['spa_assets_same_origin_headers_auth'] = True

        def post(path, **kwargs):
            response = client.post('/api' + path, headers={'Authorization': 'Bearer ' + token}, **kwargs)
            response.raise_for_status()
            return response.json()

        policy = json.loads((ROOT / 'examples/policy.json').read_text(encoding='utf-8'))
        draft = post('/review/policy-drafts', json=policy)['record_id']
        approved = post('/review/policy-drafts/' + draft + '/approve')['record_id']
        artifact = post('/review/artifacts', files={'file': ('generated-silence.wav', pcm, 'audio/wav')})
        wid = post('/review/workflows', json={'policy_record_id': approved, 'audio_record_id': artifact['record_id']})['workflow_id']
        post('/review/workflows/' + wid + '/transcribe')
        review_headers = {'Authorization': 'Bearer ' + token}
        for _ in range(90):
            details = client.get('/api/review/workflows/' + wid, headers=review_headers).json()
            if details['workflow']['state'] != 'TRANSCRIBING':
                break
            time.sleep(1)
        assert details['workflow']['state'] == 'ANALYZED'
        transcript = details['transcription']
        assert transcript['provider'] == 'faster-whisper' and transcript['coverage']['complete_processing']
        assert transcript['transcript']['source'] == 'asr' and transcript['transcript']['completeness'] == 'unknown'
        run = post('/review/workflows/' + wid + '/verify')
        assert run['result']['decision'] == 'REVIEW_REQUIRED'
        blocked = client.post('/api/review/workflows/' + wid + '/signoff', headers=review_headers,
            json={'verification_record_id': run['record_id'], 'decision': 'APPROVED', 'reason': 'Synthetic protocol check must not approve.'})
        assert blocked.status_code == 409
        report['checks']['real_cpu_transcription_and_signoff_block'] = True
        report['transcription'] = transcript

        opened = client.post('/api/quick/sessions', headers={'X-Demo-Code': config['DUBGUARD_DEMO_ACCESS_CODE']})
        opened.raise_for_status()
        session = opened.json()
        demo_headers = {'Authorization': 'Bearer ' + session['token']}
        response = client.post('/api/quick/analyze?scenario_id=correct', headers=demo_headers,
                               files={'file': ('silence.wav', pcm, 'audio/wav')})
        response.raise_for_status()
        for _ in range(90):
            quick = client.get('/api/quick/session', headers=demo_headers).json()
            if quick['state'] != 'PROCESSING':
                break
            time.sleep(1)
        assert quick['state'] == 'COMPLETE' and quick['mode'] == 'local'
        assert quick['verification']['decision'] == 'REVIEW_REQUIRED' and quick['amd_runs'] == 0
        report['checks']['quick_local_real_asr'] = True

        print('Real local upload/transcription passed; checking restart and persistent storage.', flush=True)
        dc('stop', 'api')
        dc('start', 'api')
        wait_ready(client)
        persisted = client.get('/api/review/workflows/' + wid, headers=review_headers).json()
        assert persisted['workflow']['verification_record_id'] == run['record_id']
        original = client.get('/api/review/artifacts/' + artifact['record_id'] + '/audio', headers=review_headers)
        assert sha256(original.content).hexdigest() == report['audio_sha256']
        assert client.get('/api/quick/session', headers=demo_headers).json()['runs'] == 1
        report['checks']['graceful_shutdown_and_persistence'] = True

        # Seed pending states only in this disposable test DB. This is a recovery
        # protocol test, not a claim to have interrupted an actual inference call.
        seed = """import sqlite3,os
from pathlib import Path
root=Path(os.environ['DUBGUARD_DATA_DIR'])
with sqlite3.connect(root/'review.sqlite3') as db:
    db.execute("UPDATE workflows SET state='VERIFYING' WHERE id=?",(%r,))
with sqlite3.connect(root/'quick/sessions.sqlite3') as db:
    db.execute("UPDATE sessions SET state='PROCESSING' WHERE id=?",(%r,))
""" % (wid, session['id'])
        execute(seed)
        dc('up', '-d', '--no-deps', '--force-recreate', 'api')
        wait_ready(client)
        failed = client.get('/api/review/workflows/' + wid, headers=review_headers).json()
        assert failed['workflow']['state'] == 'VERIFICATION_FAILED'
        assert failed['workflow']['verification_record_id'] is None
        assert any(e['event'] == 'INTERRUPTED_ON_RESTART' for e in failed['audit_events'])
        interrupted = client.get('/api/quick/session', headers=demo_headers).json()
        assert interrupted['state'] == 'FAILED' and interrupted['runs'] == 1 and interrupted['amd_runs'] == 0
        assert client.post('/api/review/workflows/' + wid + '/signoff', headers=review_headers,
            json={'verification_record_id': run['record_id'], 'decision': 'APPROVED', 'reason': 'Stale run must fail.'}).status_code == 409
        assert sha256(client.get('/api/review/artifacts/' + artifact['record_id'] + '/audio', headers=review_headers).content).hexdigest() == report['audio_sha256']
        report['checks']['container_recreation_preserves_audio_sqlite'] = True
        report['checks']['seeded_interruption_invalidates_readiness'] = True
        after = json.loads(execute(model_inventory))
        assert before == after
        report['checks']['offline_asr_model_hashes_unchanged'] = True
        report['restart_method'] = 'Real stop/start and forced API recreation, plus explicitly seeded pending-job recovery states.'
    report['container_ids'] = dc('ps', '-q').splitlines()
    api_id = dc('ps', '-q', 'api').strip()
    stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', api_id],
                           capture_output=True, text=True, check=True, timeout=30)
    report['api_stats_after_restart_not_peak'] = json.loads(stats.stdout)
    report['limitations'] = ['No public TLS, DNS, physical microphone or human speech accuracy measured.',
                             'Silence input only; no remote AMD or secondary acoustic model executed.',
                             'Single point memory sample is not a peak or concurrent-load benchmark.']
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True, type=Path)
    parser.add_argument('--origin', default='http://127.0.0.1:18080')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = validate(args.env_file, args.origin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('PASS: isolated local container protocol. Report saved; zero AMD calls. Test stack remains running until explicitly stopped.')
