"""Run an owner-boundary mutation against a private disposable source copy."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from verify import API, ROOT, Env, service, uv, wait_http


def verify_owner_boundary(env: Env) -> None:
    with tempfile.TemporaryDirectory(prefix="yudada-owner-mutation-") as directory:
        source = Path(directory)
        shutil.copytree(API / "app", source / "app", ignore=shutil.ignore_patterns("__pycache__"))
        draft = source / "app/drafts.py"
        original = draft.read_text()
        guard = '(application.owner_id != actor.id and actor.role != "admin")'
        if original.count(guard) != 1:
            raise RuntimeError("Owner guard mutation must change exactly one condition")
        draft.write_text(original.replace(guard, "False"))
        configured = {**env, "PYTHONPATH": str(source)}
        port = env["API_ORIGIN"].rsplit(":", 1)[1]
        with service(
            uv(
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                port,
                "--no-access-log",
            ),
            configured,
            ROOT / ".artifacts/owner-mutant-api.log",
            source,
        ) as process:
            wait_http(env["API_ORIGIN"], process)
            result = subprocess.run(
                uv(
                    "pytest",
                    "tests/integration/test_accounts.py",
                    "-k",
                    "owner_csrf",
                    "-o",
                    f"pythonpath={source}",
                ),
                cwd=API,
                env=configured,
                capture_output=True,
                text=True,
                check=False,
            )
            (ROOT / ".artifacts/mutation-owner-boundary.log").write_text(
                result.stdout + result.stderr
            )
            if result.returncode == 0 or "assert 200 == 404" not in result.stdout:
                raise RuntimeError("Owner mutation did not fail the cross-owner assertion")
            print("Mutation rejected: cross-owner draft access", flush=True)
