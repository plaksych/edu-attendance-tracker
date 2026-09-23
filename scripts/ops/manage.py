"""Explicit operational commands. No operation is a build/test side effect."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

from common import (
    ROOT,
    compose_args,
    compose_environment,
    effective_config,
    read_env,
    require,
    validate_config,
    validate_env,
)

SERVICES = [
    "backend",
    "scheduler",
    "maintenance",
    "recognition-worker",
    "frontend",
    "gateway",
]


def confirm(action, project):
    expected = f"{action} {project}"
    require(
        input(f"Target: {project}. Type '{expected}': ") == expected,
        "Confirmation mismatch",
    )


def smoke(env):
    base = f"https://{env['APP_HOST']}:{env.get('HTTPS_PORT', '8443')}"
    with urllib.request.urlopen(base + "/health/ready", timeout=10) as response:
        require(json.load(response).get("status") == "ready", "API readiness failed")
    with urllib.request.urlopen(base + "/", timeout=10) as response:
        require(
            response.status == 200
            and "text/html" in response.headers.get("Content-Type", ""),
            "Frontend smoke failed",
        )
    try:
        urllib.request.urlopen(base + "/api/v1/groups", timeout=10)
    except urllib.error.HTTPError as exc:
        require(
            exc.code in (401, 403), "Unauthenticated API request did not fail closed"
        )
    else:
        raise ValueError("Unauthenticated API access accepted")
    print(
        "PASS: TLS, frontend, API readiness and anonymous denial; not an upload/inference test"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "preflight",
            "infra-up",
            "storage-init",
            "migrate",
            "deploy",
            "rollback",
            "smoke",
            "demo-up",
            "demo-down",
            "dev",
        ],
    )
    parser.add_argument("--env-file", required=True)
    parser.add_argument(
        "--approval-file", help="Reviewed JSON release evidence, not an approval bypass"
    )
    args = parser.parse_args()
    env = read_env(args.env_file)
    local = args.action in {"demo-up", "demo-down", "dev"}
    if local:
        require(
            env.get("ENVIRONMENT")
            == ("development" if args.action == "dev" else "demo"),
            "Wrong local mode",
        )
    validate_env(env, production=not local)
    config = effective_config(env, args.env_file, local)
    validate_config(config, production=not local)
    command = compose_args(env, args.env_file, local)

    def run(*arguments):
        # Tool output may contain credentials; operational logs stay private on host.
        subprocess.run(
            command + list(arguments),
            env=compose_environment(env),
            cwd=ROOT,
            check=True,
        )

    if args.action == "demo-down":
        run("down")  # No volume deletion, ever.
        return
    if args.action == "smoke":
        for attempt in range(30):
            try:
                smoke(env)
                break
            except (ValueError, OSError):
                if attempt == 29:
                    raise
                time.sleep(2)
        return
    for key in ("MODEL_FILE", "TLS_CERT_FILE", "TLS_KEY_FILE"):
        require(Path(env[key]).is_file(), f"Missing {key}")
    with Path(env["MODEL_FILE"]).open("rb") as model:
        require(
            hashlib.file_digest(model, "sha256").hexdigest() == env["MODEL_SHA256"],
            "Model checksum mismatch",
        )
    if args.action == "preflight":
        print(
            "PASS: static preflight; IAM, TLS SAN, readiness and recovery still require runtime checks"
        )
        return
    confirm(args.action, env["COMPOSE_PROJECT_NAME"])
    if args.action in {"deploy", "rollback"}:
        require(args.approval_file, "Release approval/evidence file is required")
        evidence = json.loads(Path(args.approval_file).read_text())
        for key in (
            "reviewer",
            "ci_run",
            "backup_snapshot",
            "restore_evidence",
            "revision",
        ):
            require(evidence.get(key), f"Missing reviewed {key}")
        require(
            evidence.get("schema_compatible") is True,
            "Schema compatibility not approved",
        )
        require(
            evidence.get("images")
            == {name: service["image"] for name, service in config["services"].items()},
            "Approved image set differs from effective Compose",
        )
        run("pull", *SERVICES)
        run("up", "-d", "--no-build", "--no-deps", *SERVICES)
        smoke(env)
    elif args.action == "infra-up":
        run("up", "-d", "--no-build", "db", "minio")
    elif args.action in {"migrate", "storage-init"}:
        run("--profile", "ops", "run", "--rm", "--no-deps", args.action)
    elif args.action in {"demo-up", "dev"}:
        run("up", "-d", "--no-build", "db", "minio")
        run("--profile", "ops", "run", "--rm", "storage-init")
        run("--profile", "ops", "run", "--rm", "migrate")
        run("up", "-d", "--no-build", *SERVICES)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        raise SystemExit(
            f"Operation stopped: {detail}; inspect private host logs/configuration"
        ) from None
