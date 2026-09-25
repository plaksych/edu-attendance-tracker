import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from check_full_stack import check_endpoints  # noqa: E402


class FullStackGuardTests(unittest.TestCase):
    def test_requires_explicit_disposable_endpoints(self):
        dsn = "postgresql://test:unused@127.0.0.1:55439/attendance_test"
        with patch.dict(os.environ, {"CI_DISPOSABLE": "true"}):
            self.assertEqual(
                check_endpoints(dsn, "127.0.0.1:19000")["dbname"], "attendance_test"
            )
            for bad_dsn, bad_s3 in (
                (dsn.replace("attendance_test", "attendance_prod"), "127.0.0.1:19000"),
                (dsn.replace("127.0.0.1", "db.example.org"), "127.0.0.1:19000"),
                (dsn, "s3.example.org:9000"),
                (dsn, "127.0.0.1:9000@remote.example.org"),
            ):
                with (
                    self.subTest(dsn=bad_dsn, s3=bad_s3),
                    self.assertRaises(ValueError),
                ):
                    check_endpoints(bad_dsn, bad_s3)
        with (
            patch.dict(os.environ, {"CI_DISPOSABLE": "false"}),
            self.assertRaises(ValueError),
        ):
            check_endpoints(dsn, "127.0.0.1:19000")


if __name__ == "__main__":
    unittest.main()
