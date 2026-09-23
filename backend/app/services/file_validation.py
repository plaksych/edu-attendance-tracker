"""Bound content before handing it to image/video/office parsers."""

import json
import math
import shutil
import subprocess
import tempfile
import warnings
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError
from openpyxl.utils.cell import range_boundaries

from app.core.config import settings


def validate_image(stream, suffix):
    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(stream) as image:
                if image.format != formats[suffix]:
                    raise ValueError(
                        "Содержимое не соответствует расширению изображения"
                    )
                if image.width * image.height > settings.upload_max_pixels:
                    raise ValueError("Превышен лимит пикселей изображения")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Анимация не поддерживается; загрузите видео")
                image.verify()
            stream.seek(0)
            with Image.open(stream) as image:
                image.load()
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ValueError("Повреждённое или недопустимое изображение") from exc
    finally:
        stream.seek(0)


def validate_video(stream, suffix):
    header = stream.read(16)
    stream.seek(0)
    valid = (
        (suffix in {".mp4", ".mov"} and header[4:8] == b"ftyp")
        or (suffix == ".webm" and header.startswith(b"\x1a\x45\xdf\xa3"))
        or (suffix == ".avi" and header.startswith(b"RIFF") and header[8:12] == b"AVI ")
    )
    if not valid:
        raise ValueError("Содержимое не соответствует формату видео")
    with tempfile.NamedTemporaryFile(suffix=suffix) as source:
        shutil.copyfileobj(stream, source, 1024 * 1024)
        source.flush()
        stream.seek(0)
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file",
                    "-probesize",
                    "5000000",
                    "-analyzeduration",
                    "5000000",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name,width,height:format=duration",
                    "-of",
                    "json",
                    source.name,
                ],
                capture_output=True,
                timeout=settings.upload_probe_timeout_seconds,
                check=True,
            )
            info = json.loads(result.stdout)
            video = info["streams"][0]
            width, height = int(video["width"]), int(video["height"])
            duration = float(info["format"]["duration"])
        except (
            FileNotFoundError,
            subprocess.SubprocessError,
            ValueError,
            KeyError,
            IndexError,
        ) as exc:
            raise ValueError(
                "Не удалось проверить видео; требуется корректный файл и ffprobe"
            ) from exc
        if (
            width <= 0
            or height <= 0
            or max(width, height) > settings.upload_max_video_dimension
            or width * height > settings.upload_max_pixels
        ):
            raise ValueError("Разрешение видео превышает лимит")
        if (
            not math.isfinite(duration)
            or not 0 < duration <= settings.upload_max_duration_seconds
        ):
            raise ValueError("Длительность видео превышает лимит или не определена")


def validate_workbook(stream):
    try:
        with ZipFile(stream) as archive:
            files = archive.infolist()
            if len(files) > 1000 or sum(f.file_size for f in files) > 50 * 1024 * 1024:
                raise ValueError("Превышен лимит распакованного XLSX")
            names = {f.filename for f in files}
            if len(names) != len(files):
                raise ValueError("Повторяющиеся записи в XLSX не поддерживаются")
            if "xl/workbook.xml" not in names:
                raise ValueError("Файл не является книгой XLSX")
            cells = 0
            declared_cells = 0
            for item in files:
                if (
                    item.flag_bits & 1
                    or "vbaProject" in item.filename
                    or "externalLinks/" in item.filename
                ):
                    raise ValueError(
                        "Внешние связи, макросы и шифрование XLSX не поддерживаются"
                    )
                if item.filename.endswith(".xml"):
                    data = archive.read(item)
                    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                        raise ValueError("DTD в XLSX не разрешён")
                    if item.filename.startswith("xl/worksheets/"):
                        root = ElementTree.fromstring(data)
                        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                        # openpyxl may expand declared dimensions/merges even when XML is tiny.
                        for element in root.iter():
                            if element.tag in {ns + "dimension", ns + "mergeCell"}:
                                bounds = range_boundaries(element.get("ref", ""))
                                left, top, right, bottom = bounds
                                if (
                                    any(value is None for value in bounds)
                                    or not 1 <= left <= right <= 200
                                    or not 1 <= top <= bottom <= 10000
                                ):
                                    raise ValueError("Недопустимый диапазон XLSX")
                                area = (right - left + 1) * (bottom - top + 1)
                                declared_cells += area
                                if declared_cells > 100000:
                                    raise ValueError("Превышен лимит диапазонов XLSX")
                        rows = root.findall(f".//{ns}row")
                        if len(rows) > 10000 or any(
                            int(r.get("r", "0")) > 10000 for r in rows
                        ):
                            raise ValueError("Превышен лимит строк XLSX")
                        for cell in root.iter(ns + "c"):
                            cells += 1
                            address = cell.get("r", "A1")
                            left, top, right, bottom = range_boundaries(address)
                            if (
                                any(v is None for v in (left, top, right, bottom))
                                or left != right
                                or top != bottom
                                or not 1 <= left <= 200
                                or not 1 <= top <= 10000
                                or cell.find(ns + "f") is not None
                            ):
                                raise ValueError(
                                    "Превышен лимит столбцов или обнаружена формула"
                                )
                        if cells > 100000:
                            raise ValueError("Превышен лимит ячеек XLSX")
    except (BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("Повреждённый XLSX") from exc
    finally:
        stream.seek(0)
