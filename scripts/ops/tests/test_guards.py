import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "ops"))

# Standalone CLI modules need the test-only path setup above.
from check_compose import fixture  # noqa: E402
from common import compose_args, compose_environment, read_env, validate_env  # noqa: E402
from data import pg_environment, restic_environment, validate_target  # noqa: E402
from manage import confirm  # noqa: E402
from tasks import python as service_python  # noqa: E402
import install_trivy  # noqa: E402


class EnvironmentTests(unittest.TestCase):
    def test_scanner_checksum_failure_writes_nothing(self):
        import io

        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "bin"
            with patch.object(
                install_trivy, "urlopen", return_value=io.BytesIO(b"invalid")
            ):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    install_trivy.install(destination)
            self.assertFalse(destination.exists())

    def test_scanner_installs_only_regular_pinned_binary(self):
        import hashlib
        import io
        import tarfile

        for regular in (True, False):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
                member = tarfile.TarInfo("trivy")
                if regular:
                    member.size = 4
                    archive.addfile(member, io.BytesIO(b"test"))
                else:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/tmp/untrusted-scanner-target"
                    archive.addfile(member)
            data = buffer.getvalue()
            with (
                tempfile.TemporaryDirectory() as folder,
                patch.object(install_trivy, "urlopen", return_value=io.BytesIO(data)),
                patch.object(install_trivy, "SHA256", hashlib.sha256(data).hexdigest()),
            ):
                target = Path(folder) / "bin"
                if regular:
                    install_trivy.install(target)
                    self.assertEqual((target / "trivy").read_bytes(), b"test")
                else:
                    with self.assertRaisesRegex(ValueError, "archive member"):
                        install_trivy.install(target)
                    self.assertFalse(target.exists())

    def test_frontend_runtime_assets_do_not_fall_back_to_spa(self):
        import re

        config = (SCRIPTS.parent / "frontend/nginx.conf").read_text()
        for folder in ("ort", "models"):
            start = config.index(f"location ^~ /{folder}/")
            following = config.find("\n    location ", start + 1)
            block = config[start : following if following != -1 else len(config)]
            self.assertIn("try_files $uri =404;", block)
            self.assertNotIn("/index.html", block)
        self.assertRegex(config, re.compile(r"application/javascript\s+js\s+mjs;"))
        self.assertIn("application/wasm wasm;", config)

    def test_gateway_limits_login_at_real_peer_without_trusting_forwarded_headers(self):
        config = (SCRIPTS / "ops/gateway.conf.template").read_text()
        self.assertIn(
            "limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m;", config
        )
        self.assertIn("location = /api/v1/auth/login", config)
        self.assertIn("limit_req zone=login burst=5 nodelay;", config)
        self.assertIn("limit_req_status 429;", config)
        self.assertNotIn("real_ip_header", config)

    def test_python_override_preserves_venv_launcher_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "python"
            launcher.symlink_to(sys.executable)
            with patch.dict(os.environ, {"RECOGNITION_PYTHON": str(launcher)}):
                self.assertEqual(
                    service_python("recognition"), str(launcher.absolute())
                )
                self.assertNotEqual(
                    service_python("recognition"), str(launcher.resolve())
                )

    def test_valid_production(self):
        validate_env(fixture())

    def test_semester_end_is_required_and_ordered(self):
        for value in ("", "2026-01-01", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_env({**fixture(), "SEMESTER_END": value})

    def test_weak_and_reused_credentials(self):
        for key in ("DB_ADMIN_PASSWORD", "MINIO_SECRET_KEY", "MINIO_ROOT_PASSWORD"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_env({**fixture(), key: "attendance"})
        with self.assertRaises(ValueError):
            env = fixture()
            env["MINIO_SECRET_KEY"] = env["MINIO_ROOT_PASSWORD"]
            validate_env(env)

    def test_measurement_input_grace_bounds(self):
        for value in ("0", "3600", "604800"):
            validate_env({**fixture(), "MEASUREMENT_INPUT_GRACE_SECONDS": value})
        for value in ("", "-1", "604801", "1.5", "unbounded"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_env({**fixture(), "MEASUREMENT_INPUT_GRACE_SECONDS": value})

    def test_cross_namespace_dsn(self):
        env = fixture()
        env["BACKEND_DATABASE_URL"] = env["BACKEND_DATABASE_URL"].replace(
            "@db:", "@production.example:"
        )
        with self.assertRaises(ValueError):
            validate_env(env)

    def test_compose_does_not_inherit_overrides(self):
        with patch.dict(
            os.environ,
            {
                "COMPOSE_FILE": "evil.yml",
                "COMPOSE_PROFILES": "camera",
                "BACKEND_DATABASE_URL": "ambient-secret",
            },
        ):
            environment = compose_environment(fixture())
        self.assertNotIn("COMPOSE_FILE", environment)
        self.assertNotIn("COMPOSE_PROFILES", environment)
        self.assertNotEqual(environment["BACKEND_DATABASE_URL"], "ambient-secret")
        args = compose_args(fixture(), "/tmp/safe.env")
        self.assertEqual(args.count("-f"), 1)

    def test_env_parser_rejects_expansion_duplicates_and_public_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config"
            for text in ("KEY=$SECRET", "KEY=a\nKEY=b", "export KEY=x"):
                path.write_text(text)
                path.chmod(0o600)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    read_env(path)
            path.write_text("KEY='literal value'\n")
            self.assertEqual(read_env(path), {"KEY": "literal value"})
            if os.name != "nt":
                path.chmod(0o644)
                with self.assertRaises(ValueError):
                    read_env(path)


class DataGuardTests(unittest.TestCase):
    def env(self, mode="demo"):
        namespace = (
            "attendance-"
            + {"demo": "demo", "production": "prod", "restore": "restore"}[mode]
            + "fixture"
        )
        namespace = namespace.replace("fixture", "-fixture")
        return {
            "OPS_MODE": mode,
            "OPS_NAMESPACE": namespace,
            "PGDATABASE": namespace.replace("-", "_"),
            "S3_BUCKET": namespace,
            "OPS_INSTANCE_ID": "00000000-0000-4000-8000-000000000001",
        }

    def test_demo_reset_requires_real_matching_database_identity(self):
        env = self.env()
        identity = ("demo", env["OPS_NAMESPACE"], env["OPS_INSTANCE_ID"])
        validate_target(env, "reset", identity, env["PGDATABASE"])
        for marker in (
            ("production", env["OPS_NAMESPACE"], env["OPS_INSTANCE_ID"]),
            ("demo", env["OPS_NAMESPACE"], "different-id"),
            None,
        ):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                validate_target(env, "reset", marker, env["PGDATABASE"])
        with self.assertRaises(ValueError):
            validate_target(env, "reset", identity, "attendance_prod_fixture")

    def test_production_cannot_reset_or_restore(self):
        for action in ("reset", "restore", "seed"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate_target(self.env("production"), action)

    def test_seed_requires_demo_marker_and_namespace(self):
        env = self.env()
        marker = ("demo", env["OPS_NAMESPACE"], env["OPS_INSTANCE_ID"])
        validate_target(env, "seed", marker, env["PGDATABASE"])
        for wrong in (None, ("production", *marker[1:]), ("demo", marker[1], "wrong")):
            with self.subTest(marker=wrong), self.assertRaises(ValueError):
                validate_target(env, "seed", wrong, env["PGDATABASE"])
        with self.assertRaises(ValueError):
            validate_target(env, "seed", marker, "attendance_prod_fixture")
        with self.assertRaises(ValueError):
            validate_target({**self.env("production"), "OPS_MODE": "demo"}, "seed")

    def test_mode_flag_alone_cannot_turn_production_into_demo(self):
        env = {**self.env("production"), "OPS_MODE": "demo"}
        with self.assertRaises(ValueError):
            validate_target(env, "reset")

    def test_restore_requires_separate_bucket_and_namespace(self):
        env = self.env("restore")
        validate_target(env, "restore")
        for key in ("PGDATABASE", "S3_BUCKET", "OPS_NAMESPACE"):
            wrong = copy.deepcopy(env)
            wrong[key] = "production"
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_target(wrong, "restore")

    def test_no_unencrypted_remote_database(self):
        with self.assertRaises(ValueError):
            pg_environment({"PGHOST": "remote.example", "PGSSLMODE": "disable"})

    def test_local_backup_repository_rejected(self):
        for repository in (
            "/tmp/backups",
            "file:/tmp/backups",
            "rest:http://remote.invalid",
        ):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                restic_environment({"RESTIC_REPOSITORY": repository})

    def test_confirmation_names_exact_target(self):
        with patch("builtins.input", return_value="yes"), self.assertRaises(ValueError):
            confirm("reset", "attendance-demo-fixture")
        with patch("builtins.input", return_value="reset attendance-demo-fixture"):
            confirm("reset", "attendance-demo-fixture")


if __name__ == "__main__":
    unittest.main()
