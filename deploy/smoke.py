"""Opt-in operator smoke for a running local container stack or approved public URL.
Checks routing/TLS/readiness only; never uploads speech or calls inference.
"""
import argparse
import json
import urllib.request
from urllib.error import URLError

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('origin', help='HTTPS origin, or http://localhost for local testing')
args = parser.parse_args()
origin = args.origin.rstrip('/')
if not origin.startswith(('https://', 'http://localhost', 'http://127.0.0.1')):
    raise SystemExit('Use HTTPS, or HTTP localhost for a local smoke test')
try:
    with urllib.request.urlopen(origin + '/test', timeout=15) as response:
        assert response.status == 200 and '<html' in response.read(10000).decode().lower()
    with urllib.request.urlopen(origin + '/api/health', timeout=15) as response:
        assert json.load(response)['status'] == 'ok'
    with urllib.request.urlopen(origin + '/api/ready', timeout=15) as response:
        assert json.load(response)['ready']
    with urllib.request.urlopen(origin + '/api/quick/scenarios', timeout=15) as response:
        assert len(json.load(response)) == 6
except (URLError, AssertionError, ValueError) as error:
    raise SystemExit('Stack smoke failed; check TLS, same-origin proxy and cached model readiness.') from None
print('PASS: SPA deep link, same-origin API, readiness and six scenarios. Inference not executed. Test physical microphone separately.')
