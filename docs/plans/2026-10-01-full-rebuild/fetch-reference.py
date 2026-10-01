"""Download only approved public source at a pinned commit; no config or seed data."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
commit = json.loads((ROOT / "source-commit.json").read_text())["sha"]
tree = json.loads((ROOT / "source-tree.json").read_text())
assert not tree.get("truncated"), "Incomplete GitHub tree"


def allowed(path):
    p = Path(path)
    if any(part.lower() in {"config", "generate", "node_modules", "dist"} for part in p.parts):
        return False
    if path in {"README.md", "LICENSE", "LICENSE.md", "LICENSE.txt", "yudada-backend/sql/create_table.sql"}:
        return True
    return (
        path.startswith("yudada-backend/src/main/java/") and p.suffix == ".java"
        or path.startswith("yudada-frontend/src/") and p.suffix in {".ts", ".vue"}
        or path.startswith("mbti-test-mini/src/") and p.suffix in {".ts", ".tsx"} and ".config." not in p.name
        or path.startswith("yudada-backend/src/main/resources/mapper/") and p.suffix == ".xml"
    )


paths = [item["path"] for item in tree["tree"] if item["type"] == "blob" and allowed(item["path"])]


def fetch(path):
    url = f"https://raw.githubusercontent.com/liyupi/yudada/{commit}/{path}"
    with urlopen(url, timeout=30) as response:
        data = response.read()
    target = ROOT / "reference-source" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    files = sorted(pool.map(fetch, paths), key=lambda item: item["path"])
(ROOT / "source-manifest.json").write_text(json.dumps({"commit": commit, "files": files}, indent=2) + "\n")
print(f"Pinned {commit}: {len(files)} approved source files; excluded configs, credentials and seed data.")
