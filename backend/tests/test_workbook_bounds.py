from io import BytesIO
from zipfile import ZipFile

import pytest

from app.services.file_validation import validate_workbook


def sheet_file(body):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + body
            + "</worksheet>",
        )
    stream.seek(0)
    return stream


@pytest.mark.parametrize(
    "body",
    [
        '<dimension ref="A1:XFD1048576"/>',
        '<mergeCells><mergeCell ref="A1:A1048576"/></mergeCells>',
        '<dimension ref="A1:GR10000"/>',
        '<sheetData><row r="1"><c r="XFD1"/></row></sheetData>',
        '<sheetData><row r="1"><c r="A1048576"/></row></sheetData>',
        '<dimension ref="B2:A1"/>',
        '<dimension ref="A:A"/>',
    ],
)
def test_tiny_xml_cannot_expand_unbounded_grid(body):
    stream = sheet_file(body)
    with pytest.raises(ValueError):
        validate_workbook(stream)
    assert stream.tell() == 0


def test_small_grid_and_merged_heading_are_valid():
    validate_workbook(
        sheet_file(
            '<dimension ref="A1:H100"/>'
            '<mergeCells><mergeCell ref="A1:H1"/></mergeCells>'
            '<sheetData><row r="2"><c r="B2"/></row></sheetData>'
        )
    )
