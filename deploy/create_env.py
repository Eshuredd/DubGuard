"""Create new server-only configuration with distinct random secrets; never overwrite."""
import argparse
import json
import os
from pathlib import Path
import secrets

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('path', type=Path)
args = parser.parse_args()
reviewer = secrets.token_urlsafe(32)
config = '\n'.join([
    '# Private server configuration. Do not copy into frontend or commit.',
    'DUBGUARD_REVIEW_TOKENS_JSON=' + json.dumps({'reviewer': reviewer}, separators=(',', ':')),
    'DUBGUARD_CLIENT_EDITS_PER_HOUR=60',
    'DUBGUARD_OPERATOR_LOGINS_PER_HOUR=8',
    'DUBGUARD_PUBLIC_AMD_ENABLED=false',
    'DUBGUARD_AMD_REQUESTS_PER_HOUR=10',
    'DUBGUARD_AMD_REQUESTS_PER_DAY=40',
    'DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY=4',
    'DUBGUARD_CLIENT_SESSIONS_PER_HOUR=4',
    'DUBGUARD_CLIENT_UPLOADS_PER_HOUR=6',
    'DUBGUARD_TRUSTED_PROXIES=',
    'DUBGUARD_SEMANTIC_PROVIDER=amd',
    'AMD_TOKEN_FACTORY_ENDPOINT=https://developer.amd.com.cn/radeon/api/v1',
    'AMD_TOKEN_FACTORY_MODEL=DeepSeek-V4-Flash',
    'AMD_TOKEN_FACTORY_AUDIO_MODEL=MiMo-V2.6-Flash',
    'AMD_TOKEN_FACTORY_API_KEY=',
    'AMD_TOKEN_FACTORY_MAX_RETRIES=0',
    'AMD_TOKEN_FACTORY_TIMEOUT_SECONDS=40',
    'AMD_TOKEN_FACTORY_CONNECT_TIMEOUT_SECONDS=5',
    'DUBGUARD_MAX_UPLOAD_BYTES=25000000',
    'DUBGUARD_MAX_AUDIO_SECONDS=120',
    '',
])
descriptor = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
    output.write(config)
print('Created private server configuration. Local public reviews are ready. Configure optional AMD and private reviewer credentials using your private editor. No secrets printed.')
