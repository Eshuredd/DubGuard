"""Private operator UI cookie exchange; public capabilities never become operators."""
import json
import time
import pytest
from fastapi.testclient import TestClient
from dubguard.api import app
from dubguard.quick import database


@pytest.fixture
def op(tmp_path, monkeypatch):
    monkeypatch.setenv('DUBGUARD_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DUBGUARD_REVIEW_TOKENS_JSON', json.dumps({'operator': 'operator-only-random-test-token-long'}))
    monkeypatch.setenv('DUBGUARD_PUBLIC_WORKSPACE', 'true')
    monkeypatch.setenv('DUBGUARD_CLIENT_SESSIONS_PER_HOUR', '30')
    return TestClient(app)


def login(c):
    return c.post('/operator/session', json={'token': 'operator-only-random-test-token-long'})


def test_operator_cookie_is_opaque_httponly_and_logout_revokes(op):
    assert op.get('/review/workflows').status_code == 401
    r = login(op)
    assert r.status_code == 200 and r.json() == {'authenticated': True}
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    assert 'operator-only-random-test-token-long' not in r.text+r.headers['set-cookie']
    token = op.cookies['dubguard_operator']
    assert len(token) >= 43
    assert op.get('/review/workflows').status_code == 200
    assert op.delete('/operator/session').status_code == 200
    assert op.get('/review/workflows').status_code == 401
    op.cookies.set('dubguard_operator', token)
    assert op.get('/review/workflows').status_code == 401


def test_cross_origin_cookie_mutations_rejected(op):
    assert login(op).status_code == 200
    assert op.post('/review/policy-drafts', json={}, headers={'Origin':'https://attacker.invalid'}).status_code in {403,422}
    assert op.delete('/operator/session', headers={'Origin':'https://attacker.invalid'}).status_code == 403
    assert op.post('/operator/session', json={'token':'operator-only-random-test-token-long'}, headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403


def test_cookie_expiry_and_credential_rotation_revoke_operator(op, monkeypatch):
    login(op)
    with database() as db:
        db.execute('UPDATE operator_sessions SET expires=0')
    assert op.get('/review/workflows').status_code == 401
    login(op)
    monkeypatch.setenv('DUBGUARD_REVIEW_TOKENS_JSON', json.dumps({'operator':'rotated-private-test-token-long'}))
    assert op.get('/review/workflows').status_code == 401


def test_public_capability_cannot_exchange_or_impersonate_operator_cookie(op):
    cap = op.post('/workspace/sessions').json()['token']
    assert op.post('/operator/session', json={'token': cap}).status_code == 401
    op.cookies.set('dubguard_operator', cap)
    assert op.get('/review/workflows').status_code == 401
    assert op.get('/workspace/session', headers={'Authorization':'Bearer '+cap}).status_code == 200


def test_production_operator_cookie_is_secure(op):
    r = op.post('https://example.test/operator/session', json={'token':'operator-only-random-test-token-long'})
    assert r.status_code == 200 and 'Secure' in r.headers['set-cookie']
