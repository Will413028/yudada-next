"""Break version invariants only in disposable test source/database."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from verify import API, ROOT, Env, database_statement, service, uv, wait_http


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text()
    if source.count(old) != 1:
        raise RuntimeError("Version mutation must target exactly one expression")
    path.write_text(source.replace(old, new))


def verify_version_boundaries(env: Env) -> None:
    cases = [
        ("latest-draft", "test_answers.py", "published_answers", "assert '交流型' == '探索型'"),
        ("pending-version", "test_public_versions.py", "public_pagination", "assert 200 == 404"),
        ("missing-unique", "test_answers.py", "published_answers", "assert 500 == 201"),
        ("private-upload", "test_uploads.py", "owner_scoped", "assert 200 == 404"),
        ("disabled-session-race", "test_admin.py", "waiting_login", "assert 200 == 401"),
    ]
    for name, filename, selection, assertion in cases:
        with tempfile.TemporaryDirectory(prefix="yudada-version-mutation-") as directory:
            source = Path(directory)
            shutil.copytree(
                API / "app", source / "app", ignore=shutil.ignore_patterns("__pycache__")
            )
            for package in ("scripts", "tests"):
                shutil.copytree(
                    API / package, source / package, ignore=shutil.ignore_patterns("__pycache__")
                )
            if name == "latest-draft":
                answers = source / "app/answers.py"
                replace_once(
                    answers,
                    "from app.models import Answer",
                    "from app.models import Answer, AppDraft",
                )
                replace_once(
                    answers,
                    "Content.model_validate(version.content)",
                    "Content.model_validate((await session.get(AppDraft, version.app_id)).content)",
                )
            elif name == "pending-version":
                replace_once(
                    source / "app/versions.py", 'PublicationReview.status == "approved"', "True"
                )
            elif name == "private-upload":
                replace_once(
                    source / "app/uploads.py",
                    "if not (actor is not None and "
                    '(actor.id == upload.owner_id or actor.role == "admin")):',
                    "if False:",
                )
            elif name == "disabled-session-race":
                replace_once(
                    source / "app/security.py",
                    "    await session.refresh(user, with_for_update=True)\n",
                    "",
                )
            if name == "missing-unique":
                alter_constraint(env, restore=False)
            try:
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
                    ROOT / f".artifacts/{name}-mutant-api.log",
                    source,
                ) as process:
                    wait_http(env["API_ORIGIN"], process)
                    result = subprocess.run(
                        uv(
                            "pytest",
                            f"tests/integration/{filename}",
                            "-k",
                            selection,
                            "-o",
                            f"pythonpath={source}",
                        ),
                        cwd=API,
                        env=configured,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    (ROOT / f".artifacts/mutation-{name}.log").write_text(
                        result.stdout + result.stderr
                    )
                    if result.returncode == 0 or assertion not in result.stdout:
                        raise RuntimeError(
                            f"Version mutation {name} missed its behavioral assertion"
                        )
                    print(f"Mutation rejected: {name}", flush=True)
            finally:
                if name == "missing-unique":
                    alter_constraint(env, restore=True)


def alter_constraint(env: Env, *, restore: bool) -> None:
    sql = (
        "ALTER TABLE answers ADD CONSTRAINT uq_answer_owner_key UNIQUE (owner_id, idempotency_key)"
        if restore
        else "ALTER TABLE answers DROP CONSTRAINT uq_answer_owner_key"
    )
    database_statement(sql, env)
