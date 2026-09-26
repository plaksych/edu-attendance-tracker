"""Portable task runner. Service packages named app always use separate processes."""

import argparse
import os
import platform
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ("backend", "capture", "recognition")
TYPECHECK_TARGETS = {
    "backend": [
        "app/core/config.py",
        "app/core/security.py",
        "app/services/idempotency.py",
        "app/core/camera_security.py",
    ],
    "capture": ["app/config.py"],
    "recognition": [
        "app/config.py",
        "app/db.py",
        "app/media_keys.py",
        "app/runner.py",
        "app/media_safety.py",
    ],
}


def python(service):
    override = os.environ.get(service.upper() + "_PYTHON")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    path = (
        ROOT
        / ".venv"
        / service
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    if not path.is_file() and not os.environ.get("CI"):
        path = (
            ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
    if not path.is_file():
        raise SystemExit(f"Missing isolated {service} environment; run bootstrap")
    return str(path)


def run(command, cwd=ROOT, env=None):
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "task",
        choices=[
            "bootstrap",
            "lint",
            "typecheck",
            "test",
            "test-integration",
            "test-inference",
            "test-e2e",
            "test-visual",
            "build",
            "demo-static",
            "python-check",
            "diagrams",
            "diagrams-check",
            "verify",
        ],
    )
    parser.add_argument("--service", choices=SERVICES)
    args = parser.parse_args()
    selected = [args.service] if args.service else SERVICES
    if args.task == "verify":
        checks = [
            ([sys.executable, "scripts/check_compose.py", "--self-test"], "compose"),
            ([sys.executable, "scripts/check_workflows.py"], "workflows"),
            (
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "scripts/ops/tests",
                    "-v",
                ],
                "ops-guards",
            ),
            ([sys.executable, "scripts/check_docs.py"], "docs"),
        ]
        for task in ("lint", "typecheck", "test", "build"):
            checks.append(([sys.executable, __file__, task], task))
        results = {}
        for command, name in checks:
            print(f"=== {name} ===", flush=True)
            results[name] = subprocess.run(command, cwd=ROOT).returncode
        print(
            "Verification results: "
            + ", ".join(
                f"{name}={'passed' if code == 0 else 'failed'}"
                for name, code in results.items()
            )
        )
        raise SystemExit(int(any(results.values())))
    if args.task == "bootstrap":
        for service in (*selected, "ops"):
            run([sys.executable, "-m", "venv", str(ROOT / ".venv" / service)])
            requirements = ROOT / (
                "scripts/ops/requirements.txt"
                if service == "ops"
                else f"{service}/requirements.txt"
            )
            lock = service
            if (
                service == "recognition"
                and sys.platform == "darwin"
                and platform.machine() == "arm64"
            ):
                lock = "recognition-macos-arm64"
            extra = (
                ["--extra-index-url", "https://download.pytorch.org/whl/cpu"]
                if service == "recognition" and sys.platform == "linux"
                else []
            )
            run(
                [
                    python(service),
                    "-m",
                    "pip",
                    "install",
                    "--require-hashes",
                    "-r",
                    str(ROOT / f"scripts/ops/locks/{lock}.txt"),
                    "-r",
                    str(requirements),
                ]
                + extra
            )
            if service != "ops":
                run(
                    [
                        python(service),
                        "-m",
                        "pip",
                        "install",
                        "--require-hashes",
                        "-r",
                        str(ROOT / "scripts/ops/locks/ops.txt"),
                    ]
                )
        if not args.service:
            run(["npm", "ci"], ROOT / "frontend")
        return
    if args.task in {"lint", "typecheck", "test", "test-integration", "python-check"}:
        for service in selected:
            cwd = ROOT / service
            exe = python(service)
            if args.task in {"lint", "python-check"}:
                run([python("ops"), "-m", "ruff", "check", "app", "tests"], cwd)
                run(
                    [python("ops"), "-m", "ruff", "format", "--check", "app", "tests"],
                    cwd,
                )
            if args.task in {"typecheck", "python-check"}:
                run(
                    [
                        python("ops"),
                        "-m",
                        "mypy",
                        "--python-executable",
                        exe,
                        "--follow-imports=silent",
                        *TYPECHECK_TARGETS[service],
                    ],
                    cwd,
                )
            if args.task in {"test", "python-check"}:
                run([exe, "-m", "pytest", "tests", "-q"], cwd)
                if service == "backend":
                    run(
                        [
                            exe,
                            "-c",
                            "from app.main import app; assert app.openapi()['paths']",
                        ],
                        cwd,
                    )
            if args.task == "test-integration":
                dsn = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
                    "QUEUE_TEST_DSN"
                )
                if not dsn:
                    raise SystemExit(
                        "TEST_DATABASE_URL or QUEUE_TEST_DSN required; integration must not silently skip"
                    )
                parsed = urlsplit(dsn)
                if (
                    parsed.hostname not in {"localhost", "127.0.0.1"}
                    or parsed.path != "/attendance_test"
                ):
                    raise SystemExit(
                        "Integration tests require isolated loopback attendance_test; restore creates temporary DBs"
                    )
                target = (
                    "tests" if service == "backend" else "tests/test_queue_postgres.py"
                )
                plain_dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
                run(
                    [exe, "-m", "pytest", target, "-q"],
                    cwd,
                    {
                        **os.environ,
                        "QUEUE_TEST_DSN": plain_dsn,
                        "BACKEND_TEST_DSN": dsn,
                        "RESTORE_TEST_DSN": dsn,
                        "ENVIRONMENT": "test",
                    },
                )
        if not args.service and args.task in {"lint", "typecheck", "test"}:
            run(["npm", "run", args.task], ROOT / "frontend")
            if args.task == "typecheck":
                run(
                    ["npm", "run", "check:api"],
                    ROOT / "frontend",
                    {**os.environ, "BACKEND_PYTHON": python("backend")},
                )
        return
    if args.task == "test-inference":
        run([python("recognition"), str(ROOT / "scripts/check_inference.py")])
    elif args.task in {"test-e2e", "test-visual"}:
        extra = (
            ["--", "--grep", "visual artifacts"] if args.task == "test-visual" else []
        )
        run(["npm", "run", "test:e2e"] + extra, ROOT / "frontend")
    elif args.task == "build":
        run(
            ["npm", "run", "build"],
            ROOT / "frontend",
            {**os.environ, "VITE_STATIC_DATA": "false"},
        )
        run([sys.executable, "scripts/check_frontend_bundle.py", "frontend/dist"])
    elif args.task == "demo-static":
        run(
            ["npm", "run", "build", "--", "--outDir", "dist-demo"],
            ROOT / "frontend",
            {**os.environ, "VITE_STATIC_DATA": "true"},
        )
        run(
            [
                "npm",
                "run",
                "preview",
                "--",
                "--outDir",
                "dist-demo",
                "--host",
                "127.0.0.1",
            ],
            ROOT / "frontend",
        )
    elif args.task in {"diagrams", "diagrams-check"}:
        run(
            ["npm", "run", "render" if args.task == "diagrams" else "check"],
            ROOT / "docs/diagrams",
        )


if __name__ == "__main__":
    main()
