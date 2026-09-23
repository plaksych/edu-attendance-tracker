import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.config import settings
from app.media_safety import normalize_video, validate_image


class MediaSafetyTests(unittest.TestCase):
    def test_pixel_limit_before_opencv_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            Image.new("RGB", (20, 20)).save(path)
            with patch.object(settings, "max_image_pixels", 100):
                with self.assertRaises((ValueError, Image.DecompressionBombError)):
                    validate_image(str(path))

    def test_video_commands_forbid_file_and_network_input_protocols(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"test")
            probe = SimpleNamespace(
                stdout=json.dumps(
                    {
                        "streams": [{"width": 16, "height": 16}],
                        "format": {"duration": "1"},
                    }
                ).encode()
            )
            with patch("app.media_safety.subprocess.run", return_value=probe) as run:
                normalize_video(str(source), directory)
            for call in run.call_args_list:
                args = call.args[0]
                self.assertEqual(
                    args[args.index("-protocol_whitelist") + 1], "cache,pipe"
                )
                self.assertEqual(args[args.index("-i") + 1], "cache:pipe:0")
                self.assertIn("timeout", call.kwargs)
                self.assertNotIn("shell", call.kwargs)

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable"
    )
    def test_real_tiny_mp4_with_tail_moov_can_be_safely_decoded(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=32x32:d=0.2:r=10",
                    "-c:v",
                    "mpeg4",
                    str(source),
                ],
                check=True,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            output = normalize_video(str(source), directory)
            self.assertGreater(Path(output).stat().st_size, 0)

    @unittest.skipUnless(shutil.which("ffprobe"), "FFprobe unavailable")
    def test_real_playlist_cannot_read_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "playlist"
            source.write_text(
                "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nfile:///etc/passwd\n#EXT-X-ENDLIST\n"
            )
            with self.assertRaises(subprocess.CalledProcessError):
                normalize_video(str(source), directory)
