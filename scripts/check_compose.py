"""Validate actual Compose JSON; --self-test uses fake inputs, never a daemon."""

import argparse
import copy
import json
from pathlib import Path
import tempfile

from ops.common import (
    DSN_KEYS,
    IMAGE_KEYS,
    effective_config,
    read_env,
    require,
    validate_config,
    validate_env,
)


def fixture():
    env = {
        "ENVIRONMENT": "production",
        "COMPOSE_PROJECT_NAME": "attendance-prod-fixture",
        "DB_NAME": "attendance_prod_fixture",
        "DB_ADMIN_USER": "owner",
        "DB_ADMIN_PASSWORD": "test-only-owner-" + "a" * 32,
        "MINIO_BUCKET": "attendance-prod-fixture",
        "MINIO_ACCESS_KEY": "runtime-fixture",
        "MINIO_SECRET_KEY": "runtime-fixture-" + "b" * 32,
        "MINIO_ROOT_USER": "root-fixture",
        "MINIO_ROOT_PASSWORD": "root-fixture-" + "c" * 32,
        "MINIO_INIT_ACCESS_KEY": "init-fixture",
        "MINIO_INIT_SECRET_KEY": "init-fixture-" + "d" * 32,
        "APP_HOST": "app.invalid",
        "MEDIA_HOST": "media.invalid",
        "SEMESTER_START": "2026-09-01",
        "SEMESTER_END": "2027-01-31",
        "CAMERA_ENCRYPTION_KEY": "e" * 43 + "=",
        "MODEL_SHA256": "f" * 64,
        "MODEL_FILE": "/nonexistent/model.pt",
        "TLS_CERT_FILE": "/nonexistent/tls.crt",
        "TLS_KEY_FILE": "/nonexistent/tls.key",
        "RECOGNITION_MODEL_NAME": "fixture",
        "RECOGNITION_MODEL_VERSION": "fixture",
    }
    env.update(
        {key: "example.invalid/never-pull@sha256:" + "a" * 64 for key in IMAGE_KEYS}
    )
    env.update(
        {
            key: f"postgresql://role{i}:{'b' * 32}@db:5432/attendance_prod_fixture"
            for i, key in enumerate(DSN_KEYS)
        }
    )
    return env


def rejected(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("Unsafe configuration was accepted")


def self_test():
    env = fixture()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "fixture.env"
        path.write_text("\n".join(f"{k}={v}" for k, v in env.items()))
        path.chmod(0o600)
        validate_env(env)
        config = effective_config(env, path)
        validate_config(config)
        for name in ("db", "minio", "backend", "recognition-worker"):
            bad = copy.deepcopy(config)
            bad["services"][name]["ports"] = [{"target": 8000, "published": "8000"}]
            rejected(lambda: validate_config(bad))
        for name, key, value in [
            ("backend", "ENVIRONMENT", "demo"),
            ("backend", "SCHEDULER_ENABLED", "true"),
            ("backend", "SESSION_SECURE", "false"),
        ]:
            bad = copy.deepcopy(config)
            bad["services"][name]["environment"][key] = value
            rejected(lambda: validate_config(bad))
        for key in IMAGE_KEYS + DSN_KEYS + ("DB_ADMIN_PASSWORD", "MINIO_SECRET_KEY"):
            bad_env = {**env, key: ""}
            rejected(lambda: validate_env(bad_env))
            path.write_text("\n".join(f"{k}={v}" for k, v in bad_env.items()))
            rejected(lambda: effective_config(bad_env, path))
        rejected(
            lambda: validate_env({**env, "MINIO_ACCESS_KEY": env["MINIO_ROOT_USER"]})
        )
        rejected(lambda: validate_env({**env, "ENVIRONMENT": "demo"}))
    print(
        "PASS: rendered production Compose and 35 negative policy cases; no containers started"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        require(args.env_file, "--env-file required; no implicit .env")
        env = read_env(args.env_file)
        validate_env(env)
        validate_config(effective_config(env, args.env_file))
        print(
            json.dumps(
                {
                    "status": "passed",
                    "project": env["COMPOSE_PROJECT_NAME"],
                    "check": "effective-compose-policy",
                    "runtime_verified": False,
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from None
