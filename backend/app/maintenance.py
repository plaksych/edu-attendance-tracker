"""Always-on queue recovery and conservative attempt-orphan collection."""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session
from minio import Minio
import urllib3

from app.core.config import settings
from app.scheduler import MAINTENANCE_LOCK, process_stop, run_service
from app.services.scheduler import reap_expired_leases, fail_stale_pending_captures

logger = logging.getLogger(__name__)
ATTEMPT_KEY = re.compile(
    r"^(annotated/jobs|original/captures)/(\d+)/attempts/\d+/([0-9a-f-]{36})\.(jpg|mp4)$"
)
_scan_positions: dict[str, str] = {}


def cleanup_orphans(connection, client=None, limit: int = 500) -> int:
    client = client or Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        http_client=urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=3, read=5), retries=False
        ),
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    removed = 0
    deadline = time.monotonic() + 10
    for prefix in ("annotated/jobs/", "original/captures/"):
        scanned = 0
        for obj in client.list_objects(
            settings.minio_bucket,
            prefix=prefix,
            recursive=True,
            start_after=_scan_positions.get(prefix),
        ):
            if time.monotonic() > deadline:
                return removed
            scanned += 1
            if scanned > max(1, limit // 2):
                break
            _scan_positions[prefix] = obj.object_name
            match = ATTEMPT_KEY.fullmatch(obj.object_name)
            if not match or obj.last_modified is None or obj.last_modified >= cutoff:
                continue
            kind, job_id, token, _ = match.groups()
            with Session(bind=connection) as db:
                if kind == "annotated/jobs":
                    protected = db.scalar(
                        text("""SELECT EXISTS (
                        SELECT 1 FROM recognition_results WHERE annotated_bucket = :bucket
                            AND annotated_object_key = :key
                        UNION ALL SELECT 1 FROM recognition_jobs WHERE id = :id
                            AND claim_token = :token AND status = 'processing'
                            AND lease_until > clock_timestamp())"""),
                        {
                            "bucket": settings.minio_bucket,
                            "key": obj.object_name,
                            "id": int(job_id),
                            "token": token,
                        },
                    )
                else:
                    protected = db.scalar(
                        text("""SELECT EXISTS (
                        SELECT 1 FROM camera_captures WHERE original_bucket = :bucket
                            AND original_object_key = :key
                        UNION ALL SELECT 1 FROM camera_captures WHERE id = :id
                            AND claim_token = :token AND status IN ('recording', 'uploading')
                            AND lease_until > clock_timestamp())"""),
                        {
                            "bucket": settings.minio_bucket,
                            "key": obj.object_name,
                            "id": int(job_id),
                            "token": token,
                        },
                    )
            if not protected:
                client.remove_object(settings.minio_bucket, obj.object_name)
                removed += 1
        else:
            _scan_positions.pop(prefix, None)
    return removed


def run_tick(connection) -> None:
    with Session(bind=connection) as db:
        reap_expired_leases(db)
        fail_stale_pending_captures(db)
    # Storage failures must not suppress independent upload lease recovery.
    try:
        cleanup_orphans(connection)
    except Exception:
        logger.error("Orphan cleanup failed; retry next maintenance pass")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_service(run_tick, MAINTENANCE_LOCK, 30, process_stop())


if __name__ == "__main__":
    main()
