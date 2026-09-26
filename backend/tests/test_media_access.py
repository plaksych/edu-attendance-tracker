from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from minio.error import S3Error

from test_access import login
from app.models import RecognitionUpload


def test_media_scope_is_checked_before_contacting_storage(world):
    client, _ = world
    login(client, "teacher")
    with patch("app.services.media.get_client") as storage:
        assert client.get("/api/v1/recognition/uploads/2/media").status_code == 404
        storage.assert_not_called()


def test_absent_media_is_reported_without_broken_link(world):
    client, _ = world
    login(client, "operator")
    with patch("app.services.media.get_client") as storage:
        storage.return_value.stat_object.side_effect = S3Error(
            "NoSuchKey", "missing", "key", "id", "host", None
        )
        response = client.get("/api/v1/recognition/uploads/1/media")
        assert response.status_code == 200, response.text
        assert response.json()["source_url"] is None
        assert response.json()["source_unavailable_reason"]


def test_expired_media_is_not_signed(world):
    client, factory = world
    login(client, "operator")
    with factory() as db:
        upload = db.get(RecognitionUpload, 1)
        upload.created_at = datetime.now(timezone.utc) - timedelta(days=365)
        db.commit()
    with patch("app.services.media.get_client") as storage:
        response = client.get("/api/v1/recognition/uploads/1/media")
        assert response.status_code == 200
        assert response.json()["source_url"] is None
        storage.assert_not_called()
