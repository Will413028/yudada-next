"""Check source coverage and nonempty dispositions; mutation runs only in memory."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(data):
    assert data["commit"] == json.loads((ROOT / "source-manifest.json").read_text())["commit"]
    controller_root = ROOT / "reference-source/yudada-backend/src/main/java/com/yupi/yudada/controller"
    expected = set()
    for p in controller_root.glob("*Controller.java"):
        text = p.read_text()
        base = re.search(r'@RequestMapping\("([^"]+)"\)', text)[1]
        for method, route in re.findall(r'@(Get|Post|Put|Delete)Mapping\("([^"]+)"\)', text):
            expected.add((method.upper(), base + route))
    actual = {(r["http"], r["path"]) for r in data["routes"]}
    assert expected == actual, "REST identity coverage mismatch"
    assert len(actual) == len(data["routes"]), "Duplicate route"
    sql = (ROOT / "reference-source/yudada-backend/sql/create_table.sql").read_text()
    expected_tables = set(re.findall(r"create table if not exists (\w+)\s*\(", sql, re.I))
    assert expected_tables == {t["table"] for t in data["tables"]}, "Table coverage mismatch"
    assert len(expected_tables) == len(data["tables"]), "Duplicate table"
    router_path = "yudada-frontend/src/router/routes.ts"
    router = (ROOT / "reference-source" / router_path).read_text()
    expected_pages = {(m[1], router_path, router[:m.start()].count("\n") + 1) for m in re.finditer(r'path:\s*"([^"]+)"', router)}
    actual_pages = {(p["path"], p["source"], p["line"]) for p in data["web_routes"]}
    assert expected_pages == actual_pages, "Web declaration coverage mismatch"
    assert len(actual_pages) == len(data["web_routes"]), "Duplicate Web declaration"
    for group, identity in (("routes", "path"), ("tables", "table"), ("web_routes", "path")):
        assert data[group], group
        for row in data[group]:
            assert row[identity] and row["disposition"] and row["step"], f"Missing disposition: {group}"
            assert (ROOT / "reference-source" / row["source"]).exists(), row["source"]
            assert row["line"] > 0, row
    text = (ROOT / "inventory.md").read_text()
    for number in range(1, 17):
        assert re.search(rf"\| R{number:02d} \|.+\|[^|]+\|[^|]+\|[^|]+\|", text), f"R{number:02d} missing mapping"
    assert "B6" in text and "B7" in text, "New scoring defects missing dispositions"


parser = argparse.ArgumentParser()
parser.add_argument("--mutation", action="store_true")
args = parser.parse_args()
manifest = json.loads((ROOT / "source-manifest.json").read_text())
for item in manifest["files"]:
    assert hashlib.sha256((ROOT / "reference-source" / item["path"]).read_bytes()).hexdigest() == item["sha256"], "Source integrity mismatch"
data = json.loads((ROOT / "source-inventory.json").read_text())
validate(data)
if args.mutation:
    for label in ("disposition", "rest-deletion", "rest-identity", "table-deletion", "web-deletion"):
        changed = copy.deepcopy(data)
        if label == "disposition":
            changed["routes"][0]["disposition"] = ""
        elif label == "rest-deletion":
            changed["routes"].pop()
        elif label == "rest-identity":
            changed["routes"][0]["path"] = "/does-not-exist"
        elif label == "table-deletion":
            changed["tables"].pop()
        else:
            changed["web_routes"].pop()
        try:
            validate(changed)
        except AssertionError:
            print(f"Mutation rejected: {label}")
        else:
            raise AssertionError(f"Mutation escaped: {label}")
print(f"Inventory OK: {len(data['routes'])} REST, {len(data['tables'])} tables, {len(data['web_routes'])} Web routes; R01–R16 mapped")
