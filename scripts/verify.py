"""Reproducible local gates, using throwaway PostgreSQL and owned subprocesses."""

import argparse
import fcntl
import filecmp
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps/api"
WEB = ROOT / "apps/web"
Env = dict[str, str]


def run(command: list[str], env: Env, cwd: Path = ROOT) -> None:
    # Print executable/arguments only; environment may include caller configuration.
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def uv(*args: str) -> list[str]:
    return ["uv", "run", "--no-sync", "--project", str(API), *args]


def pnpm(*args: str) -> list[str]:
    return ["pnpm", "--dir", str(ROOT), *args]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_http(origin: str, process: subprocess.Popen[bytes], timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Service exited during startup; inspect .artifacts logs")
        try:
            with urllib.request.urlopen(origin + "/api/v1/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.1)
    raise RuntimeError("Service startup timed out; inspect .artifacts logs")


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


@contextmanager
def service(
    command: list[str], env: Env, log: Path, cwd: Path
) -> Iterator[subprocess.Popen[bytes]]:
    with log.open("wb") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            yield process
        finally:
            stop(process)


@contextmanager
def postgres(env: Env) -> Iterator[Env]:
    if env.get("TEST_POSTGRES_BIN"):
        with native_postgres(env) as configured:
            yield configured
        return
    port = free_port()
    name = f"yudada-test-{uuid.uuid4().hex[:12]}"
    # Passwordless, disposable database bound to localhost only. No existing data is accessed.
    run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--pull=never",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=512m",
            "--name",
            name,
            "--env",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "--env",
            "POSTGRES_DB=yudada_test",
            "--publish",
            f"127.0.0.1:{port}:5432",
            env.get("TEST_POSTGRES_IMAGE", "postgres:17-alpine"),
        ],
        env,
    )
    try:
        for _ in range(100):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    "-d",
                    "yudada_test",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("PostgreSQL did not become ready")
        yield {
            **env,
            "DATABASE_URL": f"postgresql+asyncpg://postgres@127.0.0.1:{port}/yudada_test",
        }
    finally:
        result = subprocess.run(["docker", "inspect", name], capture_output=True, check=False)
        if result.returncode == 0:
            run(["docker", "stop", name], env)


@contextmanager
def native_postgres(env: Env) -> Iterator[Env]:
    binaries = Path(env["TEST_POSTGRES_BIN"])
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="yudada-postgres-") as directory:
        run(
            [
                str(binaries / "initdb"),
                "-D",
                directory,
                "-U",
                "postgres",
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=C",
            ],
            env,
        )
        with service(
            [
                str(binaries / "postgres"),
                "-D",
                directory,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
            ],
            env,
            ROOT / ".artifacts/native-postgres.log",
            ROOT,
        ) as process:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Local test PostgreSQL exited during startup")
                result = subprocess.run(
                    [
                        str(binaries / "psql"),
                        "-h",
                        "127.0.0.1",
                        "-p",
                        str(port),
                        "-U",
                        "postgres",
                        "-d",
                        "postgres",
                        "-c",
                        "SELECT 1",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode == 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Local test PostgreSQL startup timed out")
            run(
                [
                    str(binaries / "createdb"),
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(port),
                    "-U",
                    "postgres",
                    "yudada_test",
                ],
                env,
            )
            yield {
                **env,
                "DATABASE_URL": f"postgresql+asyncpg://postgres@127.0.0.1:{port}/yudada_test",
            }


def generate(env: Env) -> None:
    run(uv("python", "scripts/export_openapi.py"), env, API)
    run(pnpm("run", "generate:client"), env)


def check(env: Env) -> None:
    run(
        uv(
            "ruff",
            "check",
            "app",
            "migrations",
            "scripts",
            "tests",
            str(ROOT / "scripts"),
            str(ROOT / "tests"),
        ),
        env,
        API,
    )
    run(
        uv(
            "ruff",
            "format",
            "--check",
            "app",
            "migrations",
            "scripts",
            "tests",
            str(ROOT / "scripts"),
            str(ROOT / "tests"),
        ),
        env,
        API,
    )
    run(uv("mypy", "app", "scripts", "tests/unit", str(ROOT / "scripts")), env, API)
    run(uv("pytest"), env, API)
    run(uv("python", "scripts/export_openapi.py", "--check"), env, API)
    generated = ROOT / ".artifacts/schema.d.ts"
    run(
        pnpm(
            "exec",
            "openapi-typescript",
            str(API / "openapi.json"),
            "-o",
            str(generated),
        ),
        env,
    )
    if not filecmp.cmp(generated, WEB / "src/lib/api/schema.d.ts", shallow=False):
        raise RuntimeError("Generated client drift: run make generate-client")
    for task in ["lint", "typecheck", "test", "build"]:
        run(pnpm("--filter", "@yudada/web", "run", task), env)


def browser_test(env: Env, expected_failure: str | None = None) -> None:
    command = pnpm("run", "test:e2e")
    if expected_failure is not None:
        command.append("tests/e2e/skeleton.spec.ts")
    if expected_failure is None:
        run(command, env)
        return
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    (ROOT / ".artifacts" / f"mutation-{expected_failure}.log").write_text(
        result.stdout + result.stderr
    )
    if result.returncode == 0 or "expect(locator).toBeVisible()" not in result.stdout:
        raise RuntimeError(f"Mutation {expected_failure} did not fail the expected UI assertion")
    print(f"Mutation rejected: {expected_failure}", flush=True)


def database_statement(sql: str, env: Env) -> None:
    program = (
        "import asyncio\nfrom sqlalchemy import text\nfrom app.db import create_engine\n"
        "async def main():\n    engine = create_engine()\n    try:\n"
        "        async with engine.begin() as connection:\n"
        f"            await connection.execute(text({sql!r}))\n"
        "    finally:\n        await engine.dispose()\nasyncio.run(main())"
    )
    run(uv("python", "-c", program), env, API)


def verify_live(mode: str, env: Env) -> None:
    api_port, web_port = free_port(), free_port()
    env = {
        **env,
        "API_ORIGIN": f"http://127.0.0.1:{api_port}",
        "WEB_ORIGIN": f"http://127.0.0.1:{web_port}",
        "PUBLIC_ORIGIN": f"http://127.0.0.1:{web_port}",
    }
    with ExitStack() as stack:
        env = {
            **env,
            "UPLOAD_ROOT": stack.enter_context(
                tempfile.TemporaryDirectory(prefix="yudada-uploads-")
            ),
        }
        if mode != "faults":
            env = stack.enter_context(postgres(env))
            run(uv("alembic", "upgrade", "0002"), env, API)
            database_statement(
                "INSERT INTO learning_apps (id, name) VALUES "
                "('00000000-0000-4000-8000-000000000001', 'Legacy skeleton fixture')",
                env,
            )
            run(uv("alembic", "upgrade", "head"), env, API)
            run(uv("alembic", "check"), env, API)
            # Exercise rollback and recreate against the same disposable database.
            run(uv("alembic", "downgrade", "base"), env, API)
            run(uv("alembic", "upgrade", "head"), env, API)
            run(uv("python", "scripts/seed.py"), env, API)
        api_process = stack.enter_context(
            service(
                uv(
                    "uvicorn",
                    "tests.transport_service:app" if mode == "faults" else "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                ),
                env,
                ROOT / ".artifacts" / f"{mode}-api.log",
                ROOT if mode == "faults" else API,
            )
        )
        wait_http(env["API_ORIGIN"], api_process)
        if mode == "integration":
            run(uv("pytest", "tests/integration"), env, API)
            stop(api_process)
            from auth_mutation import verify_owner_boundary
            from version_mutation import verify_version_boundaries

            verify_owner_boundary(env)
            verify_version_boundaries(env)
            return
        run(pnpm("--filter", "@yudada/web", "run", "build"), env)
        web_process = stack.enter_context(
            service(
                pnpm("--filter", "@yudada/web", "run", "start", "--port", str(web_port)),
                env,
                ROOT / ".artifacts" / f"{mode}-web.log",
                ROOT,
            )
        )
        wait_http(env["WEB_ORIGIN"], web_process)
        if mode == "faults":
            run(uv("pytest", str(ROOT / "tests/test_transport.py")), env, API)
            stop(api_process)
            mutant_env = {**env, "PROBE_BUFFER_STREAM": "1"}
            mutant = stack.enter_context(
                service(
                    uv(
                        "uvicorn",
                        "tests.transport_service:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--no-access-log",
                    ),
                    mutant_env,
                    ROOT / ".artifacts/faults-buffered-api.log",
                    ROOT,
                )
            )
            wait_http(env["API_ORIGIN"], mutant)
            result = subprocess.run(
                uv("pytest", str(ROOT / "tests/test_transport.py"), "-k", "flushes"),
                cwd=API,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            (ROOT / ".artifacts/mutation-sse-buffering.log").write_text(
                result.stdout + result.stderr
            )
            if result.returncode == 0 or "httpx.ReadTimeout" not in result.stdout:
                raise RuntimeError("Buffering mutation did not fail the expected stream read")
            print("Mutation rejected: SSE compression buffering", flush=True)
        else:
            browser_test(env)
            run(
                uv("python", "scripts/seed.py", "--name", "故意破壞 fixture 名稱"),
                env,
                API,
            )
            browser_test(env, "fixture-name")
            run(uv("python", "scripts/seed.py"), env, API)
            stop(api_process)
            browser_test(env, "api-stopped")


def dev(env: Env) -> None:
    web_port = int(env.get("DEV_WEB_PORT", "3300"))
    api_port = int(env.get("DEV_API_PORT", "8300"))
    db_port = int(env.get("DEV_DB_PORT", "55433"))
    if not all(1024 <= port <= 65535 for port in (web_port, api_port, db_port)):
        raise RuntimeError("DEV_*_PORT must be between 1024 and 65535")
    env = {**env, "DEV_DB_PORT": str(db_port)}
    run(
        [
            "docker",
            "compose",
            "--project-name",
            "yudada-next",
            "--file",
            str(ROOT / "compose.yml"),
            "up",
            "--detach",
            "--wait",
            "--pull",
            "never",
            "db",
        ],
        env,
    )
    env = {
        **env,
        "DATABASE_URL": f"postgresql+asyncpg://postgres@127.0.0.1:{db_port}/yudada_dev",
        "API_ORIGIN": f"http://127.0.0.1:{api_port}",
        "PUBLIC_ORIGIN": f"http://127.0.0.1:{web_port}",
    }
    run(uv("alembic", "upgrade", "head"), env, API)
    run(uv("python", "scripts/seed.py"), env, API)
    with ExitStack() as stack:
        api = stack.enter_context(
            service(
                uv(
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                    "--reload",
                ),
                env,
                ROOT / ".artifacts/dev-api.log",
                API,
            )
        )
        wait_http(env["API_ORIGIN"], api)
        web = stack.enter_context(
            service(
                pnpm("--filter", "@yudada/web", "run", "dev", "--port", str(web_port)),
                env,
                ROOT / ".artifacts/dev-web.log",
                ROOT,
            )
        )
        wait_http(f"http://127.0.0.1:{web_port}", web)
        print(
            f"Ready: http://127.0.0.1:{web_port} (Ctrl-C stops Web/API; DB volume retained)",
            flush=True,
        )
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
        raise RuntimeError("Development service exited; inspect .artifacts logs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=["dev", "check", "generate", "integration", "e2e", "faults"]
    )
    args = parser.parse_args()
    (ROOT / ".artifacts").mkdir(exist_ok=True)
    env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "PYTHONPATH": str(API)}
    with (ROOT / ".artifacts/verify.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "Another gate/dev process owns this checkout; run commands sequentially"
            ) from error
        if args.mode == "dev":
            dev(env)
        elif args.mode == "generate":
            generate(env)
        elif args.mode == "check":
            check(env)
        else:
            verify_live(args.mode, env)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Development services stopped; database remains available.")
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
