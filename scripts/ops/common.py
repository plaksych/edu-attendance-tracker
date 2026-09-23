"""Shared fail-closed configuration helpers. No import-time side effects."""

import json
from datetime import date
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
IMAGE_KEYS = (
    "POSTGRES_IMAGE",
    "MINIO_IMAGE",
    "GATEWAY_IMAGE",
    "BACKEND_IMAGE",
    "FRONTEND_IMAGE",
    "RECOGNITION_IMAGE",
    "CAPTURE_IMAGE",
)
DSN_KEYS = (
    "BACKEND_DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "RECOGNITION_DATABASE_URL",
    "CAPTURE_DATABASE_URL",
)
BAD_SECRETS = {
    "attendance",
    "minioadmin",
    "password",
    "change-me",
    "changeme",
    "example",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_env(path, private=True):
    path = Path(path).resolve()
    require(path.is_file(), "Environment file does not exist")
    if private and os.name != "nt":
        require(path.stat().st_mode & 0o077 == 0, "Environment file must be mode 0600")
    result = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        require(
            sep and re.fullmatch(r"[A-Z][A-Z0-9_]*", key), f"Invalid env line {number}"
        )
        require(key not in result, f"Duplicate env key {key}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        require(
            "$" not in value and "\n" not in value, f"Interpolation forbidden in {key}"
        )
        result[key] = value
    return result


def validate_env(env, production=True):
    mode = env.get("ENVIRONMENT")
    require(
        mode == "production" if production else mode in {"demo", "development"},
        "Wrong environment mode",
    )
    project = env.get("COMPOSE_PROJECT_NAME", "")
    require(
        re.fullmatch(r"attendance-(prod|demo|dev)-[a-z0-9-]+", project),
        "Explicit isolated COMPOSE_PROJECT_NAME required",
    )
    expected = {"production": "prod", "demo": "demo", "development": "dev"}[mode]
    require(project.startswith(f"attendance-{expected}-"), "Project/mode mismatch")
    require(
        env.get("DB_NAME") == project.replace("-", "_"), "Database namespace mismatch"
    )
    require(env.get("MINIO_BUCKET") == project, "Bucket namespace mismatch")
    for key in IMAGE_KEYS:
        require(
            re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", env.get(key, "")),
            f"{key} must be an immutable digest",
        )
    for key in (
        "DB_ADMIN_PASSWORD",
        "MINIO_SECRET_KEY",
        "MINIO_ROOT_PASSWORD",
        "MINIO_INIT_SECRET_KEY",
    ):
        value = env.get(key, "")
        require(
            len(value) >= 24
            and value.lower() not in BAD_SECRETS
            and "change" not in value.lower(),
            f"{key} must be a unique strong secret",
        )
    require(
        len(
            {
                env[k]
                for k in (
                    "MINIO_SECRET_KEY",
                    "MINIO_ROOT_PASSWORD",
                    "MINIO_INIT_SECRET_KEY",
                )
            }
        )
        == 3,
        "Runtime, init and root storage secrets must differ",
    )
    require(
        len(
            {
                env.get(k)
                for k in (
                    "MINIO_ACCESS_KEY",
                    "MINIO_ROOT_USER",
                    "MINIO_INIT_ACCESS_KEY",
                )
            }
        )
        == 3,
        "Runtime, init and root storage accounts must differ",
    )
    users = []
    for key in DSN_KEYS:
        dsn = urlsplit(env.get(key, ""))
        require(
            dsn.scheme in {"postgresql", "postgresql+psycopg2"}
            and dsn.hostname == "db"
            and dsn.path == "/" + env["DB_NAME"]
            and not dsn.query,
            f"{key} must target the isolated Compose database",
        )
        require(
            dsn.username
            and dsn.password
            and len(dsn.password) >= 24
            and dsn.password.lower() not in BAD_SECRETS,
            f"Invalid credentials in {key}",
        )
        users.append(dsn.username)
    require(len(set(users)) == 4, "Each database role must have separate credentials")
    require(
        env.get("DB_ADMIN_USER") not in users,
        "Migration and runtime accounts must differ from DB administrator",
    )
    for key in ("APP_HOST", "MEDIA_HOST"):
        require(
            re.fullmatch(r"[a-z0-9][a-z0-9.-]+[a-z0-9]", env.get(key, "")),
            f"Invalid {key}",
        )
    require(env["APP_HOST"] != env["MEDIA_HOST"], "App and media hosts must differ")
    require(
        re.fullmatch(r"[A-Za-z0-9_-]{43}=", env.get("CAMERA_ENCRYPTION_KEY", "")),
        "A Fernet camera encryption key is required",
    )
    require(
        re.fullmatch(r"[a-f0-9]{64}", env.get("MODEL_SHA256", "")),
        "MODEL_SHA256 required",
    )
    for key in ("MODEL_FILE", "TLS_CERT_FILE", "TLS_KEY_FILE"):
        require(Path(env.get(key, "")).is_absolute(), f"{key} must be an absolute path")
    if mode != "production":
        require(
            env.get("HTTPS_BIND", "127.0.0.1") == "127.0.0.1",
            "Local modes must bind loopback",
        )
    require(
        env.get("DEMO_RESET_ENABLED", "false") == "false",
        "No HTTP reset bypass allowed",
    )
    start = date.fromisoformat(env.get("SEMESTER_START", ""))
    end = date.fromisoformat(env.get("SEMESTER_END", ""))
    require(end >= start, "SEMESTER_END must be on or after SEMESTER_START")
    grace = env.get("MEASUREMENT_INPUT_GRACE_SECONDS", "3600")
    require(
        grace.isascii() and grace.isdigit() and 0 <= int(grace) <= 604800,
        "MEASUREMENT_INPUT_GRACE_SECONDS must be an integer from 0 to 604800",
    )


def compose_args(env, env_file, local=False):
    args = [
        "docker",
        "compose",
        "--env-file",
        str(Path(env_file).resolve()),
        "--project-name",
        env["COMPOSE_PROJECT_NAME"],
        "-f",
        str(ROOT / "docker-compose.yml"),
    ]
    if local:
        overlay = "demo" if env["ENVIRONMENT"] == "demo" else "dev"
        args += ["-f", str(ROOT / f"docker-compose.{overlay}.yml")]
    return args


def compose_environment(env):
    # Inherited COMPOSE_FILE/profiles/DSNs must never override the reviewed file.
    allowed = (
        "PATH",
        "HOME",
        "DOCKER_CONFIG",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
        "SSH_AUTH_SOCK",
        "SYSTEMROOT",
    )
    return {**{key: os.environ[key] for key in allowed if key in os.environ}, **env}


def effective_config(env, env_file, local=False):
    result = subprocess.run(
        compose_args(env, env_file, local)
        + ["--profile", "ops", "--profile", "camera", "config", "--format", "json"],
        cwd=ROOT,
        env=compose_environment(env),
        capture_output=True,
        text=True,
        check=False,
    )
    require(
        result.returncode == 0,
        "Compose rendering failed (raw output withheld: may contain secrets)",
    )
    return json.loads(result.stdout)


def validate_config(config, production=True):
    services = config["services"]
    require(
        {
            "db",
            "minio",
            "backend",
            "scheduler",
            "maintenance",
            "recognition-worker",
            "capture-manager",
            "migrate",
            "storage-init",
            "frontend",
            "gateway",
        }
        == set(services),
        "Unexpected service set",
    )
    require(
        config["networks"]["private"].get("internal") is True,
        "Data network must be internal",
    )
    for name, service in services.items():
        require("build" not in service, f"No builds during deployment: {name}")
        require(
            re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", service.get("image", "")),
            f"Unpinned {name}",
        )
        require(
            not service.get("privileged") and not service.get("network_mode"),
            f"Privileged {name}",
        )
        require(
            service.get("read_only") and "ALL" in service.get("cap_drop", []),
            f"Hardening missing: {name}",
        )
        require(
            "no-new-privileges:true" in service.get("security_opt", []),
            f"Privilege escalation: {name}",
        )
        require(
            int(service.get("pids_limit", 0)) > 0
            and int(service.get("mem_limit", 0)) > 0
            and float(service.get("cpus", 0)) > 0,
            f"Resource limits missing: {name}",
        )
        for port in service.get("ports", []):
            require(
                name == "gateway" or not production, f"Published service port: {name}"
            )
            if name == "gateway":
                require(port["target"] == 8443, "Only TLS ingress allowed")
            else:
                require(
                    port.get("host_ip") == "127.0.0.1",
                    "Local service ports must use loopback",
                )
        for volume in service.get("volumes", []):
            require(
                volume["type"] != "bind"
                or (
                    name == "recognition-worker"
                    and volume["target"] == "/models/model.pt"
                    and volume.get("read_only")
                ),
                f"Unexpected bind mount: {name}",
            )
        if name != "capture-manager":
            require(
                "cameras" not in service.get("networks", {}), "Camera egress leaked"
            )
        require(
            "migrate" not in service.get("depends_on", {}),
            "Migrations must be explicit",
        )
    for name in ("backend", "scheduler", "maintenance"):
        env = services[name]["environment"]
        require(env["SCHEDULER_ENABLED"] == "false", "Embedded scheduler enabled")
        require(
            env["SESSION_SECURE"] == "true" and env["MINIO_PUBLIC_SECURE"] == "true",
            "TLS flags disabled",
        )
        if production:
            require(env["ENVIRONMENT"] == "production", "Production demo bypass")
    for name in ("scheduler", "maintenance"):
        require(
            services[name]["command"] == ["python", "-m", f"app.{name}"],
            f"Wrong {name} entrypoint",
        )
        require(not services[name].get("profiles"), f"{name} must run without camera")
    require(
        not services["recognition-worker"].get("profiles"),
        "Upload worker cannot be optional",
    )
    require(
        services["capture-manager"].get("profiles") == ["camera"],
        "Camera must be optional",
    )
    for name in ("migrate", "storage-init"):
        require(
            services[name].get("profiles") == ["ops"]
            and services[name]["restart"] == "no",
            "Administrative operations must be one-shot",
        )
