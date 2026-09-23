from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import select

from app.core.security import utc
from app.models.requests import IdempotencyRecord


def reserve(db, owner_id, route, key, fingerprint):
    if not key or len(key) > 120 or not key.isascii():
        raise HTTPException(
            422, "Нужен заголовок Idempotency-Key длиной 1–120 ASCII-символов"
        )
    now = datetime.now(timezone.utc)
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(IdempotencyRecord)
        .values(
            owner_id=owner_id,
            route=route,
            key=key,
            fingerprint=fingerprint,
            expires_at=now + timedelta(hours=24),
        )
        .on_conflict_do_nothing(index_elements=["owner_id", "route", "key"])
    )
    record = db.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.owner_id == owner_id,
            IdempotencyRecord.route == route,
            IdempotencyRecord.key == key,
        )
        .with_for_update()
    )
    if utc(record.expires_at) < now:
        raise HTTPException(409, "Ключ запроса истёк; используйте новый")
    if record.fingerprint != fingerprint:
        raise HTTPException(409, "Ключ уже использован для другого запроса")
    return record
