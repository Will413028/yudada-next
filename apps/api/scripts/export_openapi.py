import argparse
import json
from pathlib import Path

from app.main import app

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
target = Path(__file__).resolve().parents[1] / "openapi.json"
content = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
if args.check:
    if not target.exists() or target.read_text() != content:
        raise SystemExit("OpenAPI drift: run make generate-client")
else:
    target.write_text(content)
