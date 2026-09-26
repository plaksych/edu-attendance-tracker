import unittest

from cryptography.fernet import Fernet

from app.camera_security import CameraPolicyError, camera_url
from app.config import Settings
from app.storage import original_object_key


class CameraSecurityTests(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key()
        self.settings = Settings(
            _env_file=None,
            environment="production",
            camera_encryption_key=self.key.decode(),
            camera_allowed_cidrs="192.168.8.0/24",
        )

    def encrypted(self, url):
        return "encrypted:" + Fernet(self.key).encrypt(url.encode()).decode()

    def test_encrypted_private_camera_allowed(self):
        url = "rtsp://operator:secret@192.168.8.3/stream"
        self.assertEqual(camera_url(self.encrypted(url), self.settings), url)

    def test_plaintext_forbidden_in_production(self):
        with self.assertRaises(CameraPolicyError):
            camera_url("rtsp://192.168.8.3/stream", self.settings)

    def test_forbidden_destinations(self):
        for url in (
            "http://192.168.8.3/",
            "rtsp://127.0.0.1/",
            "rtsp://169.254.169.254/",
            "rtsp://192.168.9.1/",
            "rtsp://camera.example/",
            "rtsp://[::1]/",
            "rtsp://[::ffff:192.168.8.3]/",
            "file:///etc/passwd",
        ):
            with self.subTest(url=url), self.assertRaises(CameraPolicyError):
                camera_url(self.encrypted(url), self.settings)

    def test_ciphertext_tampering_rejected(self):
        with self.assertRaises(CameraPolicyError):
            camera_url("encrypted:invalid", self.settings)

    def test_artifacts_are_attempt_specific(self):
        first = original_object_key(1, 1, "00000000-0000-0000-0000-000000000001")
        second = original_object_key(1, 2, "00000000-0000-0000-0000-000000000002")
        self.assertNotEqual(first, second)
