from io import BytesIO
import unittest

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
        descriptor = describe_upload(upload("auditorium.png", "image/png", b"image"))

        self.assertEqual(descriptor.media_type, RecognitionMediaType.image)
        self.assertEqual(descriptor.content_type, "image/png")
        self.assertEqual(descriptor.size_bytes, 5)

    def test_accepts_video_when_browser_uses_generic_content_type(self) -> None:
        descriptor = describe_upload(
            upload("lesson.mp4", "application/octet-stream", b"video")
        )

        self.assertEqual(descriptor.media_type, RecognitionMediaType.video)
        self.assertEqual(descriptor.content_type, "video/mp4")

    def test_rejects_mismatched_file_type(self) -> None:
        with self.assertRaisesRegex(
            RecognitionUploadError, "не соответствует"
        ):
            describe_upload(upload("lesson.mp4", "image/png"))

    def test_rejects_empty_file(self) -> None:
        with self.assertRaisesRegex(RecognitionUploadError, "пустой"):
            describe_upload(upload("frame.jpg", "image/jpeg", b""))


if __name__ == "__main__":
    unittest.main()
