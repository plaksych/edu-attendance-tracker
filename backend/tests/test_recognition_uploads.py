from io import BytesIO
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image

from starlette.datastructures import Headers, UploadFile

from app.models.enums import RecognitionMediaType
from app.services.recognition_uploads import RecognitionUploadError, describe_upload


def upload(filename: str, content_type: str, body: bytes = b"data") -> UploadFile:
    return UploadFile(
        file=BytesIO(body),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class RecognitionUploadValidationTests(unittest.TestCase):
    def test_accepts_image_by_extension_and_content_type(self) -> None:
        stream = BytesIO()
        Image.new("RGB", (8, 8)).save(stream, "PNG")
        body = stream.getvalue()
        descriptor = describe_upload(upload("auditorium.png", "image/png", body))

        self.assertEqual(descriptor.media_type, RecognitionMediaType.image)
        self.assertEqual(descriptor.content_type, "image/png")
        self.assertEqual(descriptor.size_bytes, len(body))

    def test_accepts_video_when_browser_uses_generic_content_type(self) -> None:
        probe = SimpleNamespace(
            stdout=b'{"streams":[{"width":320,"height":240}],"format":{"duration":"1"}}'
        )
        with patch("app.services.file_validation.subprocess.run", return_value=probe):
            descriptor = describe_upload(
                upload("lesson.mp4", "application/octet-stream", b"0000ftypisom0000")
            )

        self.assertEqual(descriptor.media_type, RecognitionMediaType.video)
        self.assertEqual(descriptor.content_type, "video/mp4")

    def test_rejects_fake_image_and_video(self):
        for name, kind in (("fake.png", "image/png"), ("fake.mp4", "video/mp4")):
            with self.assertRaises(RecognitionUploadError):
                describe_upload(upload(name, kind, b"not real media"))

    def test_rejects_mismatched_file_type(self) -> None:
        with self.assertRaisesRegex(RecognitionUploadError, "не соответствует"):
            describe_upload(upload("lesson.mp4", "image/png"))

    def test_rejects_empty_file(self) -> None:
        with self.assertRaisesRegex(RecognitionUploadError, "пустой"):
            describe_upload(upload("frame.jpg", "image/jpeg", b""))


if __name__ == "__main__":
    unittest.main()
