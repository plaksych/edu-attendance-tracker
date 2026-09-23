from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook
from PIL import Image
from sqlalchemy import select

from test_access import world, login
from app.models import RecognitionJob, RecognitionStatus, Schedule
from app.services.file_validation import validate_workbook


def png():
    buffer = BytesIO()
    Image.new("RGB", (24,24), "white").save(buffer, "PNG")
    return buffer.getvalue()


def workbook(rows):
    wb = Workbook()
    wb.active.append(["Группа","Преподаватель","Дисциплина","Аудитория","День недели","Начало","Конец"])
    for row in rows:
        wb.active.append(row)
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def test_upload_idempotency_real_decode_scope_and_retry(world):
    client, factory = world
    headers = {**login(client,"teacher"), "Idempotency-Key":"upload-one"}
    with patch("app.services.recognition_uploads.store_upload", return_value=("private","unit.png")) as store:
        response = client.post("/api/v1/recognition/uploads", headers=headers,
            files={"file":("unit.png",png(),"image/png")}, data={"session_id":"1"})
        assert response.status_code == 202, response.text
        identity = response.json()["id"]
        second = client.post("/api/v1/recognition/uploads", headers=headers,
            files={"file":("unit.png",png(),"image/png")}, data={"session_id":"1"})
        assert second.status_code == 202 and second.json()["id"] == identity
        assert store.call_count == 1
        changed = client.post("/api/v1/recognition/uploads", headers=headers,
            files={"file":("different.png",png(),"image/png")})
        assert changed.status_code == 409
        forbidden = client.post("/api/v1/recognition/uploads", headers=headers,
            files={"file":("unit.png",png(),"image/png")}, data={"session_id":"2"})
        assert forbidden.status_code == 404
    with factory() as db:
        job = db.scalar(select(RecognitionJob).where(RecognitionJob.upload_id==identity))
        old_id = job.id
        job.status = RecognitionStatus.failed
        db.commit()
    retry_headers = {**headers, "Idempotency-Key":"retry-one"}
    first = client.post(f"/api/v1/recognition/uploads/{identity}/retry", headers=retry_headers)
    assert first.status_code == 202, first.text
    assert first.json()["job"]["id"] != old_id
    second = client.post(f"/api/v1/recognition/uploads/{identity}/retry", headers=retry_headers)
    assert second.status_code == 202, second.text
    history = client.get(f"/api/v1/recognition/uploads/{identity}/history").json()
    assert len(history["jobs"]) == 2
    assert history["jobs"][0]["status"] == "failed"


def test_preview_no_writes_confirm_atomic_replay(world):
    client, factory = world
    headers = login(client,"operator")
    data = workbook([["NEW","Teacher","Math","301",1,"09:00","10:30"]])
    response = client.post("/api/v1/schedule/import/preview", headers=headers,
        files={"file":("schedule.xlsx", data)})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["created"] == 1 and not preview["errors"]
    with factory() as db:
        assert len(db.scalars(select(Schedule)).all()) == 2
    route = f'/api/v1/schedule/import/{preview["preview_id"]}/confirm'
    assert client.post(route, headers=headers).json()["created"] == 1
    assert client.post(route, headers=headers).json()["created"] == 0
    with factory() as db:
        assert len(db.scalars(select(Schedule)).all()) == 3


def test_import_errors_never_partially_commit(world):
    client, factory = world
    headers = login(client,"operator")
    data = workbook([["NEW","T","D","R",1,"09:00","10:30"],
                     ["NEW","T","D","R",1,"10:00","11:30"]])
    preview = client.post("/api/v1/schedule/import/preview", headers=headers,
        files={"file":("schedule.xlsx", data)}).json()
    assert preview["errors"]
    assert client.post(f'/api/v1/schedule/import/{preview["preview_id"]}/confirm', headers=headers).status_code==409
    with factory() as db:
        assert len(db.scalars(select(Schedule)).all()) == 2


def test_formula_workbook_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        validate_workbook(BytesIO(workbook([["=2+2","T","D","R",1,"9:00","10:00"]])))
