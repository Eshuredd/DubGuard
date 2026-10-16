from pathlib import Path
import json
from dubguard.api import app
root = Path(__file__).resolve().parents[1]
(root / "frontend" / "openapi.json").write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
