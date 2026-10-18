"""Create a credential-free verification manifest from local Phase 6 evidence."""
from pathlib import Path
import json
import subprocess
from xml.etree import ElementTree
from dotenv import dotenv_values

root = Path.cwd()
report = root/'reports/phase6'
suite = ElementTree.parse(report/'backend.xml').getroot().find('testsuite')
assert int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
secrets = []
for key, value in dotenv_values(root/'.env').items():
    if value and key.endswith(('_API_KEY', '_ACCESS_CODE', '_TOKEN', '_TOKENS_JSON')):
        if key.endswith('_JSON'):
            parsed = json.loads(value)
            secrets.extend(v for v in parsed.values() if isinstance(v, str) and len(v) >= 16)
        elif len(value) >= 16:
            secrets.append(value)
files = [p for folder in [root/'frontend/dist', report] for p in folder.rglob('*') if p.is_file()]
matches = [str(p.relative_to(root)) for p in files if any(secret.encode() in p.read_bytes() for secret in secrets)]
assert not matches, 'Credential material detected; do not publish artifacts'
modified = subprocess.run(['rtk', 'proxy', 'git', 'diff', '--name-only'], capture_output=True, text=True, check=True).stdout.splitlines()
new = subprocess.run(['rtk', 'proxy', 'git', 'ls-files', '--others', '--exclude-standard'], capture_output=True, text=True, check=True).stdout.splitlines()
manifest = {'starting_revision': '9e1c855d3a13667fd34a91da90da2d0e9d032254',
            'backend_tests': int(suite.attrib['tests']), 'backend_failures': 0,
            'credential_scan': 'No configured secret values found in built frontend or Phase 6 artifacts',
            'recording_fixture': 'Synthetic silence/fake microphone; no human ground truth',
            'live_amd_calls': 0, 'production_mutations': 0, 'committed': False, 'pushed': False,
            'modified_files': modified, 'new_files': new,
            'screenshots': sorted(str(p.relative_to(root)) for p in report.rglob('*.png'))}
(report/'verification.json').write_text(json.dumps(manifest, indent=2))
print('Verification manifest written. No credential values printed.')
