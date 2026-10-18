"""Public admission/security regressions. Synthetic audio; no remote inference."""
import asyncio
import json
import time
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from dubguard.api import app
from dubguard.quick import cleanup, database, recover_interrupted
from dubguard.quick_admission import QuickAdmissionMiddleware, MAX_BODY, _UPLOAD_SLOTS, client_address
from test_phase3 import wav_bytes
from test_phase4 import amd, quick


@pytest.fixture
def public(tmp_path, monkeypatch):
    monkeypatch.setenv('DUBGUARD_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('DUBGUARD_PUBLIC_LOCAL_DEMO', raising=False)
    monkeypatch.setenv('DUBGUARD_DEMO_ACCESS_CODE', 'private-test-code-at-least-24-chars')
    monkeypatch.setenv('DUBGUARD_AMD_DEMO_ACCESS_CODE', '')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_API_KEY', '')
    monkeypatch.setenv('DUBGUARD_TRUSTED_PROXIES', '')
    monkeypatch.delenv('DUBGUARD_CLIENT_SESSIONS_PER_HOUR', raising=False)
    monkeypatch.delenv('DUBGUARD_CLIENT_UPLOADS_PER_HOUR', raising=False)
    monkeypatch.setenv('DUBGUARD_REVIEW_TOKENS_JSON', json.dumps({'human': 'private-reviewer-token-test-only'}))
    def forbidden(*a, **kw):
        pytest.fail('Unauthorized demo must not even construct a provider')
    monkeypatch.setattr('dubguard.quick.AMDTokenFactoryProvider', forbidden)
    return TestClient(app)


def create(c, monkeypatch):
    monkeypatch.setenv('DUBGUARD_PUBLIC_LOCAL_DEMO', 'true')
    r = c.post('/quick/sessions')
    assert r.status_code == 200
    return r.json()


def bearer(s):
    return {'Authorization': 'Bearer ' + s['token']}


def upload(c, s, **params):
    return c.post('/quick/analyze', params={'scenario_id': 'correct', **params}, headers=bearer(s), files={'file': ('silence.wav', wav_bytes(), 'audio/wav')})


def test_default_private_gate_and_public_configuration(public, monkeypatch):
    c = public
    assert c.get('/quick/config').json() == {'public_local': False, 'amd_available': False}
    assert c.post('/quick/sessions').status_code == 401
    assert c.post('/quick/sessions', headers={'X-Demo-Code': 'private-test-code-at-least-24-chars'}).status_code == 200
    monkeypatch.setenv('DUBGUARD_DEMO_ACCESS_CODE', '')
    assert c.post('/quick/sessions').status_code == 503
    assert create(c, monkeypatch)['max_runs'] == 3


def test_random_scoped_expiring_capabilities(public, monkeypatch):
    c = public
    a, b = create(c, monkeypatch), create(c, monkeypatch)
    assert a['token'] != b['token'] and len(a['token']) >= 43
    with database() as db:
        row = db.execute('SELECT * FROM sessions WHERE id=?', (a['id'],)).fetchone()
        assert row['digest'] == sha256(a['token'].encode()).hexdigest()
        assert a['token'] not in dict(row).values()
    for method, path in [('GET', '/quick/session'), ('GET', '/quick/audio'), ('DELETE', '/quick/session'), ('POST', '/quick/analyze?scenario_id=correct')]:
        assert c.request(method, path, headers={'Authorization': 'Bearer invalid'}).status_code == 401
    for path in ['/review/workflows', '/review/policy-records']:
        assert c.get(path, headers=bearer(a)).status_code == 401
    for path in ['/review/policy-drafts', '/review/workflows', '/review/artifacts']:
        assert c.post(path, headers=bearer(a), json={}).status_code in {401, 422}
    assert c.delete('/quick/session', headers=bearer(a)).status_code == 200
    assert c.get('/quick/session', headers=bearer(a)).status_code == 401
    assert c.get('/quick/session', headers=bearer(b)).status_code == 200
    with database() as db:
        db.execute('UPDATE sessions SET expires=? WHERE id=?', (time.time()-1, b['id']))
    for path in ['/quick/session', '/quick/audio']:
        assert c.get(path, headers=bearer(b)).status_code == 401


def test_client_admissions_survive_delete_expiry_and_restart(public, monkeypatch):
    c = public
    for i in range(4):
        s = create(c, monkeypatch)
        if i % 2:
            c.delete('/quick/session', headers=bearer(s))
        else:
            with database() as db:
                db.execute('UPDATE sessions SET expires=0 WHERE id=?', (s['id'],))
            cleanup()
        recover_interrupted()
    denied = c.post('/quick/sessions')
    assert denied.status_code == 429 and denied.headers['Retry-After'] == '3600'
    with database() as db:
        events = db.execute('SELECT * FROM client_events').fetchall()
        assert len(events) == 4
        assert all(len(r['digest']) == 64 and 'testclient' not in str(dict(r)) for r in events)
        db.execute('UPDATE client_events SET created=0')
    assert c.post('/quick/sessions').status_code == 200


def test_client_cannot_spoof_forwarded_headers(public, monkeypatch):
    monkeypatch.setenv('DUBGUARD_PUBLIC_LOCAL_DEMO', 'true')
    c = TestClient(app, client=('198.51.100.7', 2345))
    for i in range(4):
        assert c.post('/quick/sessions', headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code == 200
    assert c.post('/quick/sessions', headers={'X-Forwarded-For': '203.0.113.99'}).status_code == 429
    monkeypatch.setenv('DUBGUARD_TRUSTED_PROXIES', '10.1.0.5/32')
    proxy = TestClient(app, client=('10.1.0.5', 1234))
    for i in range(4):
        assert proxy.post('/quick/sessions', headers={'X-Forwarded-For': f'203.0.113.{i}, 198.51.100.8'}).status_code == 200
    assert proxy.post('/quick/sessions', headers={'X-Forwarded-For': 'spoofed, 198.51.100.8'}).status_code == 429


@pytest.mark.parametrize('peer,trust,forwarded,expected', [
    ('2001:db8::2', '', '1.2.3.4', '2001:db8::2'),
    ('10.0.0.2', '10.0.0.2/32', '2001:db8::3', '2001:db8::3'),
    ('10.0.0.2', '10.0.0.2/32', 'bad-ip', 'unknown'),
    ('10.0.0.2', 'invalid', '1.2.3.4', 'unknown'),
])
def test_proxy_address_parsing(monkeypatch, peer, trust, forwarded, expected):
    monkeypatch.setenv('DUBGUARD_TRUSTED_PROXIES', trust)
    assert client_address({'client': (peer, 1234)}, Headers({'x-forwarded-for': forwarded})) == expected


def test_global_sessions_and_admission_history(public, monkeypatch):
    monkeypatch.setenv('DUBGUARD_PUBLIC_LOCAL_DEMO', 'true')
    sessions = []
    for i in range(20):
        c = TestClient(app, client=(f'192.0.2.{i+1}', 1234))
        sessions.append(c.post('/quick/sessions').json())
    c = TestClient(app, client=('192.0.2.100', 1234))
    assert c.post('/quick/sessions').status_code == 429
    for s in sessions:
        c.delete('/quick/session', headers=bearer(s))
    for i in range(10):
        client = TestClient(app, client=(f'192.0.2.{i+50}', 1234))
        s = client.post('/quick/sessions').json()
        client.delete('/quick/session', headers=bearer(s))
    assert TestClient(app, client=('192.0.2.200', 1)).post('/quick/sessions').status_code == 429


def test_upload_limit_survives_sessions_and_invalid_audio(public, monkeypatch):
    c = public
    s = create(c, monkeypatch)
    monkeypatch.setenv('DUBGUARD_CLIENT_UPLOADS_PER_HOUR', '2')
    # Decode fails locally. Failures still consume admission and session budgets.
    for _ in range(2):
        assert upload(c, s).status_code == 200
    c.delete('/quick/session', headers=bearer(s))
    other = create(c, monkeypatch)
    assert upload(c, other).status_code == 429


def test_runtime_upload_slots_and_global_processing(public, monkeypatch):
    c = public
    s = create(c, monkeypatch)
    assert _UPLOAD_SLOTS.acquire(False) and _UPLOAD_SLOTS.acquire(False)
    try:
        assert upload(c, s).status_code == 429
    finally:
        _UPLOAD_SLOTS.release()
        _UPLOAD_SLOTS.release()
    a, b = create(c, monkeypatch), create(c, monkeypatch)
    with database() as db:
        db.execute("UPDATE sessions SET state='PROCESSING' WHERE id IN (?,?)", (a['id'], b['id']))
    assert upload(c, s).status_code == 429


def test_anonymous_amd_denied_without_consent_code_or_config(amd, monkeypatch):
    c, s, calls, _ = amd
    monkeypatch.setenv('DUBGUARD_PUBLIC_LOCAL_DEMO', 'true')
    s = c.post('/quick/sessions').json()
    for code, consent, status in [('', True, 403), ('wrong', True, 403), ('phase6-separate-test-amd-code-long', False, 422)]:
        r = c.post('/quick/analyze?scenario_id=correct&mode=amd&consent='+str(consent).lower(), headers={**bearer(s), 'X-AMD-Demo-Code': code}, files={'file': ('test.wav', wav_bytes(), 'audio/wav')})
        assert r.status_code == status
    for override in ['', 'private-test-code-short']:
        monkeypatch.setenv('DUBGUARD_AMD_DEMO_ACCESS_CODE', override)
        assert upload(c, s, mode='amd', consent=True).status_code == 503
    assert not calls
    assert c.get('/quick/session', headers=bearer(s)).json()['runs'] == 0
    assert upload(c, s).status_code == 200 and not calls


@pytest.mark.parametrize('setting,value', [
    ('DUBGUARD_AMD_DEMO_ACCESS_CODE', 'test-only-demo-access-code-long'),
    ('DUBGUARD_REVIEW_TOKENS_JSON', '{"human":"phase6-separate-test-amd-code-long"}'),
    ('DUBGUARD_REVIEW_TOKENS_JSON', 'not-json'),
    ('AMD_TOKEN_FACTORY_API_KEY', ''),
    ('AMD_TOKEN_FACTORY_API_KEY', 'phase6-separate-test-amd-code-long'),
    ('AMD_TOKEN_FACTORY_ENDPOINT', 'http://insecure.invalid'),
    ('AMD_TOKEN_FACTORY_MODEL', 'MiMo-V2.6-Flash'),
])
def test_misconfigured_amd_fails_before_inference(amd, monkeypatch, setting, value):
    c, s, calls, _ = amd
    monkeypatch.setenv(setting, value)
    assert c.get('/quick/config').json()['amd_available'] is False
    assert upload(c, s, mode='amd', consent=True).status_code == 503
    assert not calls


@pytest.mark.parametrize('query', ['mode=local&mode=amd&consent=true', 'mode=amd&mode=local&consent=true', 'mode=amd&consent=false&consent=true'])
def test_duplicate_parameters_cannot_escalate(amd, query):
    c, s, calls, _ = amd
    assert c.post('/quick/analyze?scenario_id=correct&'+query, headers=bearer(s), content=b'not parsed').status_code == 422
    assert not calls


def test_early_unauthorized_and_oversized_bodies_are_never_consumed(public, monkeypatch):
    s = create(public, monkeypatch)
    async def exercise(headers, messages):
        received, sent = [], []
        async def downstream(*args):
            pytest.fail('Rejected body must not reach multipart parsing')
        async def receive():
            received.append(True)
            return messages.pop(0)
        async def send(message):
            sent.append(message)
        scope = {'type': 'http', 'method': 'POST', 'path': '/quick/analyze', 'query_string': b'scenario_id=correct', 'client': ('198.51.100.1', 1), 'headers': [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
        await QuickAdmissionMiddleware(downstream)(scope, receive, send)
        return received, sent[0]['status']
    received, status = asyncio.run(exercise({}, []))
    assert not received and status == 401
    received, status = asyncio.run(exercise({**bearer(s), 'Content-Length': str(MAX_BODY+1)}, []))
    assert not received and status == 413
    received, status = asyncio.run(exercise(bearer(s), [{'type': 'http.request', 'body': b'x'*(MAX_BODY+1), 'more_body': False}]))
    assert len(received) == 1 and status == 413


def test_body_timeout_releases_upload_admission(public, monkeypatch):
    import dubguard.quick_admission as admission
    s = create(public, monkeypatch)
    monkeypatch.setattr(admission, 'BODY_SECONDS', .01)
    async def exercise():
        sent = []
        async def receive():
            await asyncio.sleep(.1)
        async def downstream(*a):
            pytest.fail('Stalled body must not reach parser')
        async def send(message):
            sent.append(message)
        scope = {'type': 'http', 'method': 'POST', 'path': '/quick/analyze', 'query_string': b'scenario_id=correct', 'client': ('192.0.2.33', 1), 'headers': [(b'authorization', bearer(s)['Authorization'].encode())]}
        await QuickAdmissionMiddleware(downstream)(scope, receive, send)
        assert sent[0]['status'] == 408
        assert not admission._ACTIVE_CLIENTS
    asyncio.run(exercise())


def test_new_install_configuration_is_private_distinct_and_never_overwrites(tmp_path):
    import subprocess
    import sys
    path = tmp_path/'server.env'
    result = subprocess.run([sys.executable, 'deploy/create_env.py', str(path)], capture_output=True, text=True)
    assert result.returncode == 0
    values = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))
    codes = [values['DUBGUARD_DEMO_ACCESS_CODE'], values['DUBGUARD_AMD_DEMO_ACCESS_CODE'], json.loads(values['DUBGUARD_REVIEW_TOKENS_JSON'])['reviewer']]
    assert len(set(codes)) == 3 and all(len(code) >= 24 and code not in result.stdout+result.stderr for code in codes)
    assert values['DUBGUARD_PUBLIC_LOCAL_DEMO'] == 'false' and values['AMD_TOKEN_FACTORY_API_KEY'] == ''
    prior = path.read_bytes()
    assert subprocess.run([sys.executable, 'deploy/create_env.py', str(path)], capture_output=True).returncode != 0
    assert path.read_bytes() == prior


def test_same_client_cannot_hold_parallel_upload_bodies(public, monkeypatch):
    import dubguard.quick_admission as admission
    a, b = create(public, monkeypatch), create(public, monkeypatch)
    async def exercise():
        started, finish = asyncio.Event(), asyncio.Event()
        sent = []
        consumed_second = []
        async def downstream(*a):
            pytest.fail('Disconnected / blocked bodies must not reach parser')
        async def receive_first():
            started.set()
            await finish.wait()
            return {'type': 'http.disconnect'}
        async def receive_second():
            consumed_second.append(True)
            return {'type': 'http.disconnect'}
        async def send(message):
            sent.append(message)
        def scope(s):
            return {'type': 'http', 'method': 'POST', 'path': '/quick/analyze', 'query_string': b'scenario_id=correct', 'client': ('192.0.2.47', 1), 'headers': [(b'authorization', bearer(s)['Authorization'].encode())]}
        middleware = QuickAdmissionMiddleware(downstream)
        first = asyncio.create_task(middleware(scope(a), receive_first, send))
        await started.wait()
        await middleware(scope(b), receive_second, send)
        assert sent[0]['status'] == 429 and not consumed_second
        finish.set()
        await first
        assert not admission._ACTIVE_CLIENTS
    asyncio.run(exercise())


def test_non_ascii_code_headers_are_rejected_without_server_errors(amd):
    c, s, calls, _ = amd
    # Raw bytes exercise HTTP Latin-1 header decoding without httpx ASCII encoding.
    assert c.post('/quick/analyze?scenario_id=correct&mode=amd&consent=true', headers=[(b'authorization', bearer(s)['Authorization'].encode()), (b'x-amd-demo-code', b'\xff'*25)]).status_code == 403
    assert c.post('/quick/sessions', headers=[(b'x-demo-code', b'\xff'*25)]).status_code == 401
    assert not calls


def test_invalid_amd_code_attempts_share_client_upload_budget(amd, monkeypatch):
    c, s, calls, _ = amd
    monkeypatch.setenv('DUBGUARD_CLIENT_UPLOADS_PER_HOUR', '2')
    for _ in range(2):
        assert upload(c, s, mode='amd', consent=True).status_code == 403
    assert upload(c, s).status_code == 429
    assert not calls
