"""Run unmodified production API from this checkout with isolated demo storage."""
from pathlib import Path
import os, sys, json, hashlib, subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
os.environ.update(DUBGUARD_DATA_DIR=str(ROOT/'demo/private/runtime'),DUBGUARD_WHISPER_MODEL=str(ROOT/'.dubguard-data/models/tiny.en'),AMD_TOKEN_FACTORY_API_KEY='',DUBGUARD_AMD_DEMO_ACCESS_CODE='',DUBGUARD_REVIEW_TOKENS_JSON='{}')
from dubguard.api import app
import dubguard.api, uvicorn
receipt={'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'api_source':dubguard.api.__file__,'api_sha256':hashlib.sha256(Path(dubguard.api.__file__).read_bytes()).hexdigest(),'asr':'real faster-whisper CPU int8; cached tiny.en','amd_calls_enabled':False,'port':8011}
out=ROOT/'demo/private'; out.mkdir(parents=True,exist_ok=True)
(out/'runtime-provenance.json').write_text(json.dumps(receipt,indent=2))
uvicorn.run(app,host='127.0.0.1',port=8011,log_level='warning')
