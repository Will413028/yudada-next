"""Regenerate pinned route/schema/client inventory; output is a proposal, not approval."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "reference-source"
manifest = json.loads((ROOT / "source-manifest.json").read_text())
tree = json.loads((ROOT / "source-tree.json").read_text())
tree_files = {item["path"]: item for item in tree["tree"] if item["type"] == "blob"}
for item in manifest["files"]:
    data = (SRC / item["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
    blob = b"blob " + str(len(data)).encode() + b"\0" + data
    assert hashlib.sha1(blob).hexdigest() == tree_files[item["path"]]["sha"], item["path"]

controllers = SRC / "yudada-backend/src/main/java/com/yupi/yudada/controller"
web = SRC / "yudada-frontend/src"
ui_files = [p for p in web.rglob("*") if p.is_file() and "api" not in p.relative_to(web).parts]
mini_files = list((SRC / "mbti-test-mini/src").rglob("*.tsx"))
clients = []
for p in (web / "api").glob("*.ts"):
    text = p.read_text()
    for m in re.finditer(r"/\*\*\s+\w+\s+(GET|POST|PUT|DELETE)\s+(/[^\s*]+)\s*\*/\s*export async function (\w+)", text):
        consumers = []
        for target in ui_files:
            for number, line in enumerate(target.read_text().splitlines(), 1):
                if re.search(r"\b" + re.escape(m[3]) + r"\b", line):
                    consumers.append(f"{target.relative_to(SRC)}:{number}")
        clients.append({"http": m[1], "path": m[2].removeprefix("/api"), "symbol": m[3], "source": str(p.relative_to(SRC)), "line": text[:m.start()].count("\n") + 1, "ui_references": consumers})

routes = []
steps = {"User": "2/4", "App": "2/4", "Question": "3/4/5b", "ScoringResult": "3/4", "UserAnswer": "3/4/5c", "AppStatistic": "6a", "File": "4"}
for p in sorted(controllers.glob("*Controller.java")):
    text = p.read_text()
    base = re.search(r'@RequestMapping\("([^"]+)"\)', text)[1]
    for m in re.finditer(r'@(Get|Post|Put|Delete)Mapping\("([^"]+)"\)', text):
        tail = text[m.end():]
        symbol = re.search(r"public\s+[^\n]+?\s+(\w+)\s*\(", tail)[1]
        path = base + m[2]
        http = m[1].upper()
        generated = [x for x in clients if x["http"] == http and x["path"] == path]
        direct = []
        for target in ui_files:
            for number, line in enumerate(target.read_text().splitlines(), 1):
                if path in line and ("/api" + path in line or '"' + path + '"' in line):
                    direct.append(f"{target.relative_to(SRC)}:{number}")
        group = p.stem.removesuffix("Controller")
        disposition = f"rewrite {group} business flow; REST contract in contracts.md"
        decision = "none"
        step = steps.get(group, "0")
        if group.startswith("Post"):
            disposition, decision = "propose omit template post/social APIs", "D7"
        elif path.endswith("/sse/test"):
            disposition, decision = "propose omit public test endpoint; fault tests replace it", "D7"
        elif path.endswith("/generate/id"):
            disposition = "replace frontend preallocated ID with Idempotency-Key + server ID"
        elif group == "UserAnswer" and m[2] in {"/update", "/edit"}:
            disposition, decision = "propose omit post-score answer mutation; preserve history", "D7"
        routes.append({"http": http, "path": path, "symbol": symbol, "source": str(p.relative_to(SRC)), "line": text[:m.start()].count("\n") + 1, "generated_clients": generated, "direct_ui_references": direct, "disposition": disposition, "requires_decision": decision, "step": step, "acceptance": f"step {step} UI/API behavior, permissions and failure fixtures"})

sql_path = SRC / "yudada-backend/sql/create_table.sql"
sql = sql_path.read_text()
tables = []
for m in re.finditer(r"create table if not exists (\w+)\s*\((.*?)\) comment", sql, re.S | re.I):
    name = m[1]
    fields = [re.match(r"\s*(\w+)\s+(\w+)", line).group(1) for line in m[2].splitlines() if re.match(r"\s*\w+\s+(bigint|varchar|text|tinyint|datetime|int)\b", line)]
    disposition = "rewrite PostgreSQL schema and versioned model; no data migration"
    decision = "none"
    if name.startswith("post"):
        disposition, decision = "omit unused template social tables", "D7"
    elif name.startswith("user_answer_"):
        disposition = "consolidate into answers; no sharding until measured need"
    tables.append({"table": name, "fields": fields, "source": str(sql_path.relative_to(SRC)), "line": sql[:m.start()].count("\n") + 1, "disposition": disposition, "requires_decision": decision, "step": "2/3/4"})

route_file = web / "router/routes.ts"
route_text = route_file.read_text()
pages = [{"path": m[1], "source": str(route_file.relative_to(SRC)), "line": route_text[:m.start()].count("\n") + 1, "disposition": "rewrite Next.js route; omit /hide alias by D7", "step": "2/3/4/6a"} for m in re.finditer(r'path:\s*"([^"]+)"', route_text)]
result = {"commit": manifest["commit"], "source_files": len(manifest["files"]), "routes": routes, "tables": tables, "web_routes": pages, "mini_pages": [str(p.relative_to(SRC)) for p in mini_files], "license_paths": [p for p in tree_files if Path(p).name.lower().startswith(("license", "copying"))], "decisions": {"D7": "approved by Will 2026-10-01"}}
(ROOT / "source-inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
lines = ["# 固定來源盤點", "", f"Commit: `{manifest['commit']}`。以 `python3 <本附件絕對路徑>/audit-source.py` 重跑；所有 source blob 已與 GitHub tree hash 核對。", "", "D7 的模板省略／不可編輯答案／規則缺陷修正已由 Will 在 2026-10-01 確認。generated client 與 UI 呼叫分開，不把匯出當實際 UI 使用；去向包含已決方向與待實作契約。", "", "## REST", "", "| HTTP／route | symbol | source／line | UI references | 去向／步驟 |", "|---|---|---|---|---|"]
for r in routes:
    consumers = sorted({x for c in r["generated_clients"] for x in c["ui_references"]} | set(r["direct_ui_references"]))
    lines.append(f"| {r['http']} `{r['path']}` | `{r['symbol']}` | `{r['source']}:{r['line']}` | " + ("<br>".join(f"`{x}`" for x in consumers) or "無已盤點 Web UI references；生成宣告見 JSON") + f" | {r['disposition']}；{r['step']}；{r['requires_decision']} |")
lines += ["", "## Schema", "", "| table／source line | fields | 去向 |", "|---|---|---|"]
for t in tables:
    lines.append(f"| `{t['table']}`／{t['line']} | " + ", ".join(t["fields"]) + f" | {t['disposition']}；{t['requires_decision']} |")
lines += ["", "## Web routes", "", "| route | source line | 去向 |", "|---|---|---|"]
for p in pages:
    lines.append(f"| `{p['path']}` | {p['line']} | {p['disposition']}；{p['step']} |")
(ROOT / "source-inventory.md").write_text("\n".join(lines) + "\n")
print(json.dumps({"source_files": result["source_files"], "rest": len(routes), "tables": len(tables), "web_routes": len(pages), "controllers": dict(Counter(r["source"].split("/")[-1] for r in routes)), "table_names": [t["table"] for t in tables], "license_paths": result["license_paths"]}, ensure_ascii=False))
