"""Public AMD regression checks. Every transport is mocked; no paid calls."""
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import sys
import time

from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
import pytest

from dubguard.api import app
from dubguard.public_amd import COOKIE, check_budget, client_identity
from dubguard.quick import database, enqueue_analysis, _DEMO_SLOTS, recover_interrupted
from test_phase4 import amd, quick, submit, report
from test_phase3 import wav_bytes
from test_workspace import reference, headers, correction


def attempts():
    with database() as db:
        return db.execute('SELECT * FROM amd_attempts').fetchall()


def test_no_code_schema_or_operator_dependency(amd, monkeypatch):
    c, s, calls, _ = amd
    monkeypatch.delenv('DUBGUARD_AMD_DEMO_ACCESS_CODE', raising=False)
    monkeypatch.setenv('DUBGUARD_REVIEW_TOKENS_JSON', 'invalid-private-operator-config')
    assert c.get('/quick/config').json()['amd_available']
    for path in ('/quick/analyze', '/workspace/analyze'):
        parameters = c.get('/openapi.json').json()['paths'][path]['post']['parameters']
        assert all('demo' not in p['name'].lower() for p in parameters)
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert len(calls) == 1
    assert 'phase4-private-test-secret' not in json.dumps(report(c, s))
    assert len(attempts()) == 1


@pytest.mark.parametrize('setting', ['DUBGUARD_AMD_REQUESTS_PER_HOUR', 'DUBGUARD_AMD_REQUESTS_PER_DAY', 'DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY'])
def test_budget_survives_delete_cookie_reset_and_restart(amd, monkeypatch, setting):
    c, s, calls, _ = amd
    monkeypatch.setenv(setting, '1')
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert c.delete('/quick/session', headers=headers(s)).status_code == 200
    c.cookies.clear()
    recover_interrupted()
    other = c.post('/quick/sessions').json()
    response = submit(c, other['token'], mode='amd', consent=True)
    assert response.status_code == 429 and response.headers['retry-after'] == '3600'
    assert 'quota' in response.json()['detail'].lower()
    assert len(attempts()) == len(calls) == 1
    # A separate interpreter/connection sees the same reservation on disk.
    import os
    path = os.path.join(os.environ['DUBGUARD_DATA_DIR'], 'quick', 'sessions.sqlite3')
    script = 'import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute("SELECT count(*) FROM amd_attempts").fetchone()[0])'
    result = subprocess.run([sys.executable, '-c', script, path], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == '1'
    assert submit(c, other['token']).status_code == 200


def test_hourly_rollover_does_not_reset_daily_budget(amd, monkeypatch):
    c, s, calls, _ = amd
    monkeypatch.setenv('DUBGUARD_AMD_REQUESTS_PER_HOUR', '1')
    monkeypatch.setenv('DUBGUARD_AMD_REQUESTS_PER_DAY', '1')
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    with database() as db:
        db.execute('UPDATE amd_attempts SET created=?', (time.time()-3601,))
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 429
    with database() as db:
        db.execute('UPDATE amd_attempts SET created=?', (time.time()-86401,))
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert len(calls) == 2


def test_atomic_last_global_budget_across_clients(amd, monkeypatch):
    monkeypatch.setenv('DUBGUARD_AMD_REQUESTS_PER_DAY', '1')
    def reserve(i):
        try:
            with database() as db:
                check_budget(db, (f'browser{i}', f'network{i}'), reserve=True)
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(reserve, range(8)))
    assert statuses.count(200) == 1 and statuses.count(429) == 7
    assert len(attempts()) == 1


def test_concurrent_enqueue_reserves_one_job_and_one_attempt(amd):
    c, a, calls, _ = amd
    b = c.post('/quick/sessions').json()
    def enqueue(s):
        try:
            enqueue_analysis(BackgroundTasks(), s['id'], wav_bytes(), 'audio/wav', 'correct', 'amd',
                             clients=(s['id'], s['id']), consent=True)
            return 200
        except HTTPException as exc:
            return exc.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(enqueue, [a, b]))
        assert sorted(statuses) == [200, 429]
        assert len(attempts()) == 1 and not calls
    finally:
        _DEMO_SLOTS.release()  # queued task intentionally not executed
        recover_interrupted()


def test_browser_identifier_moves_network_but_expires_and_rejects_tampering(amd, monkeypatch):
    monkeypatch.setenv('DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY', '1')
    clients, cookie = client_identity('', '192.0.2.1')
    moved, same = client_identity(cookie, '192.0.2.2')
    assert clients[0] == moved[0] and clients[1] != moved[1] and cookie == same
    with database() as db:
        check_budget(db, clients, reserve=True)
    with pytest.raises(HTTPException) as exc:
        with database() as db:
            check_budget(db, moved, reserve=True)
    assert exc.value.status_code == 429
    forged, _ = client_identity(cookie + 'tampered', '192.0.2.1')
    assert forged[0] != clients[0] and forged[1] == clients[1]
    with database() as db:
        secret = db.execute('SELECT value FROM accounting_secret').fetchone()[0]
    from hashlib import sha256
    import hmac
    expired = 'a'*32 + '.' + str(int(time.time())-1)
    expired += '.' + hmac.new(secret.encode(), expired.encode(), sha256).hexdigest()
    _, replacement = client_identity(expired, '192.0.2.1')
    assert replacement != expired
    assert all('192.0.2' not in str(tuple(row)) for row in attempts())


def test_cookie_is_private_and_no_call_on_creation_or_config(amd):
    c, s, calls, _ = amd
    response = c.post('/quick/sessions')
    # Existing browser cookie is kept, rather than extended on each session.
    c.cookies.clear()
    response = c.post('/quick/sessions')
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=Strict' in response.headers['set-cookie']
    assert 'Max-Age=86400' in response.headers['set-cookie']
    assert COOKIE not in response.text
    assert c.get('/quick/config').status_code == 200 and not calls


def test_custom_amd_revision_citations_corrections_and_export(amd):
    c, _, calls, transport = amd
    s = c.post('/workspace/sessions').json()
    policy = reference()
    policy['instructions'] = [{'text': 'Switch the power off.'}]
    policy['requirements'] = [{'id': 'protected-1', 'kind': 'polarity', 'instruction_id': 'step-1', 'approved_phrase': 'off', 'reversed_phrase': 'on'}]
    assert c.put('/workspace/reference', headers=headers(s), json=policy).status_code == 200
    assert c.get('/workspace/config').json()['amd_available']
    url = '/workspace/analyze?expected_revision=1&mode=amd'
    file = {'file': ('a.wav', wav_bytes(), 'audio/wav')}
    assert c.post(url, headers=headers(s), files=file).status_code == 422
    assert not calls
    # Fixture response's sample IDs must be adapted to the actual custom source.
    previous = transport.handler
    def custom(req):
        response = previous(req)
        envelope = response.json()
        content = json.loads(envelope['choices'][0]['message']['content'])
        source = json.loads(json.loads(req.content)['messages'][1]['content'].split('\n', 1)[1])
        finding = content['findings'][0]
        finding['instruction_id'] = 'step-1'
        finding['approved_evidence'][0]['instruction_id'] = 'step-1'
        finding['observed_evidence'][0].update(instruction_id='step-1', segment_id=source['transcript']['segments'][0]['id'])
        envelope['choices'][0]['message']['content'] = json.dumps(content)
        import httpx
        return httpx.Response(200, json=envelope)
    transport.handler = custom
    assert c.post(url+'&consent=true', headers=headers(s), files=file).status_code == 200
    view = c.get('/workspace/export', headers=headers(s)).json()
    analysis = view['analysis']
    assert analysis['reference_revision'] == 1 and analysis['semantic_status'] == 'completed'
    assert analysis['verification']['semantic'] is None
    assert analysis['semantic_verification']['semantic']['findings'][0]['approved'][0]['text'] == 'Switch the power off.'
    assert view['workspace']['demo_decision'] is None
    revision = view['workspace']['revision']
    assert c.put('/workspace/evidence', headers=headers(s), json=correction(revision)).status_code == 200
    exported = c.get('/workspace/export', headers=headers(s)).json()
    assert exported['analysis']['transcription'] == analysis['transcription']
    assert exported['analysis']['semantic_verification'] == analysis['semantic_verification']
    # Old revision cannot trigger more inference or consume a reservation.
    assert c.post(url+'&consent=true', headers=headers(s), files=file).status_code == 409
    assert len(attempts()) == len(calls) == 1


@pytest.mark.parametrize('failure', ['decode', 'timeout'])
def test_failed_attempts_remain_charged(amd, monkeypatch, failure):
    c, s, calls, transport = amd
    if failure == 'decode':
        def fail(*args):
            raise RuntimeError('private')
        monkeypatch.setattr('dubguard.quick.transcribe_artifact', fail)
    else:
        import httpx
        def fail(req):
            calls.append(req)
            raise httpx.ReadTimeout('private')
        transport.handler = fail
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert len(attempts()) == 1
    assert report(c, s)['amd_runs'] == 1
    recover_interrupted()
    assert len(attempts()) == 1


def test_oversize_text_rejected_without_http_and_local_results_remain(amd, monkeypatch):
    c, s, calls, _ = amd
    from dubguard.providers import AMDTokenFactoryProvider
    real_payload = AMDTokenFactoryProvider._payload
    def oversized(self, *args, **kwargs):
        payload = real_payload(self, *args, **kwargs)
        payload['messages'][1]['content'] += 'x'*32768
        return payload
    monkeypatch.setattr(AMDTokenFactoryProvider, '_payload', oversized)
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    result = report(c, s)
    assert result['verification'] and result['state'] == 'COMPLETE'
    assert result['semantic_verification']['semantic']['error_class'] == 'input_limit'
    assert not calls and len(attempts()) == 1


@pytest.mark.parametrize('setting', ['DUBGUARD_AMD_REQUESTS_PER_HOUR', 'DUBGUARD_AMD_REQUESTS_PER_DAY', 'DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY'])
def test_zero_budget_disables_public_admission(amd, monkeypatch, setting):
    c, s, calls, _ = amd
    monkeypatch.setenv(setting, '0')
    assert c.get('/quick/config').json()['amd_available'] is False
    assert c.get('/quick/config').json()['amd_unavailable_reason'] == 'quota'
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 429
    assert not calls and not attempts()


def test_emergency_stop_after_transcription_keeps_local_evidence(amd, monkeypatch):
    c, s, calls, _ = amd
    import dubguard.quick as module
    transcribe = module.transcribe_artifact
    def stop(*args):
        result = transcribe(*args)
        monkeypatch.setenv('DUBGUARD_PUBLIC_AMD_ENABLED', 'false')
        return result
    monkeypatch.setattr(module, 'transcribe_artifact', stop)
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    result = report(c, s)
    assert result['state'] == 'COMPLETE' and result['verification']
    assert 'Local Verification results remain available' in result['error']
    assert not calls and len(attempts()) == 1


def test_client_limits_are_independent_but_global_budget_is_shared(amd, monkeypatch):
    monkeypatch.setenv('DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY', '1')
    monkeypatch.setenv('DUBGUARD_AMD_REQUESTS_PER_HOUR', '2')
    with database() as db:
        check_budget(db, ('browser-a', 'network-a'), reserve=True)
    with pytest.raises(HTTPException):
        with database() as db:
            check_budget(db, ('browser-a', 'network-new'), reserve=True)
    with database() as db:
        check_budget(db, ('browser-b', 'network-b'), reserve=True)
    with pytest.raises(HTTPException):
        with database() as db:
            check_budget(db, ('browser-c', 'network-c'), reserve=True)
    assert len(attempts()) == 2


def test_expired_accounting_is_swept_without_new_amd_requests(amd):
    from dubguard.quick import cleanup
    with database() as db:
        db.execute('INSERT INTO amd_attempts VALUES (?,?,?)', (time.time()-86401, 'expired-browser', 'expired-network'))
    cleanup()
    assert not attempts()


def test_reference_change_between_snapshot_and_admission_cannot_send_stale_text(amd, monkeypatch):
    import dubguard.workspace as workspace
    c, _, calls, _ = amd
    s = c.post('/workspace/sessions').json()
    assert c.put('/workspace/reference', headers=headers(s), json=reference()).status_code == 200
    snapshot = workspace.view(s['id'])
    updated = reference(1)
    updated['title'] = 'New reference version'
    assert c.put('/workspace/reference', headers=headers(s), json=updated).status_code == 200
    # Simulate a concurrent save after the endpoint read its snapshot, even when
    # the submitted expected revision happens to match the newer document.
    monkeypatch.setattr(workspace, 'view', lambda identity: snapshot)
    response = c.post('/workspace/analyze?expected_revision=2&mode=amd&consent=true',
                      headers=headers(s), files={'file': ('a.wav', wav_bytes(), 'audio/wav')})
    assert response.status_code == 409
    assert not calls and not attempts()
