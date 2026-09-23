from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (_DUMMY_HASH, audit, current_user, require_roles,
                               password_hasher, token_hash, utc, verify_password)
from app.models.security import AccessGrant, AuditEvent, LoginAttempt, LoginSession, User
from app.models import Group

router = APIRouter(tags=["Доступ"])


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class UserInput(BaseModel):
    username: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern=r"^(admin|operator|teacher|analyst)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|operator|teacher|analyst)$")
    enabled: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)
    group_ids: list[int] | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=3, max_length=500)


def user_read(user):
    return {"id": user.id, "username": user.username, "role": user.role, "enabled": user.enabled}


def throttle(db, key):
    now = datetime.now(timezone.utc)
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(LoginAttempt).values(key=key, attempts=0, window_start=now)
               .on_conflict_do_nothing(index_elements=["key"]))
    entry = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
    if now - utc(entry.window_start) >= timedelta(seconds=settings.login_window_seconds):
        entry.window_start, entry.attempts = now, 0
    entry.attempts += 1
    exceeded = entry.attempts > settings.login_limit
    db.commit()
    if exceeded:
        raise HTTPException(429, "Слишком много попыток входа. Повторите позже",
                            headers={"Retry-After": str(settings.login_window_seconds)})


@router.post("/auth/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    # Do not trust forwarded IP headers. Limit both account and actual peer.
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origins_list and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Источник запроса не разрешён")
    throttle(db, token_hash("account:" + payload.username.lower()))
    throttle(db, token_hash("peer:" + (request.client.host if request.client else "unknown")))
    user = db.scalar(select(User).where(User.username == payload.username.lower()))
    valid = verify_password(user.password_hash if user else _DUMMY_HASH, payload.password)
    if not valid or not user or not user.enabled:
        audit(db, request, "login_denied", "user")
        db.commit()
        raise HTTPException(401, "Неверное имя пользователя или пароль")
    raw = token_urlsafe(32)
    session = LoginSession(token_hash=token_hash(raw), user_id=user.id,
                           csrf_token=token_urlsafe(32), auth_version=user.auth_version,
                           expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.session_ttl_seconds))
    db.add(session)
    audit(db, request, "login", "user", user.id, actor_id=user.id)
    db.commit()
    response.set_cookie(settings.session_cookie_name, raw, httponly=True,
                        secure=settings.session_secure, samesite="strict",
                        max_age=settings.session_ttl_seconds, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {**user_read(user), "csrf_token": session.csrf_token}


@router.get("/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {**user_read(user), "csrf_token": request.state.login_session.csrf_token}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(request.state.login_session)
    audit(db, request, "logout", "user", user.id)
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.session_secure,
                           httponly=True, samesite="strict")


@router.get("/admin/users", dependencies=[Depends(require_roles("admin"))])
def users(db: Session = Depends(get_db), limit: int = 50, offset: int = 0):
    return [user_read(u) for u in db.scalars(select(User).order_by(User.id).limit(max(1,min(limit,100))).offset(max(0,offset)))]


@router.post("/admin/users", status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_user(payload: UserInput, request: Request, db: Session = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    user = User(username=payload.username.lower(), role=payload.role,
                password_hash=password_hasher.hash(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Имя пользователя уже занято") from None
    audit(db, request, "create", "user", user.id)
    db.commit()
    return user_read(user)


@router.patch("/admin/users/{user_id}", dependencies=[Depends(require_roles("admin"))])
def update_user(user_id: int, payload: UserUpdate, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if user_id == request.state.user.id and (payload.enabled is False or payload.role not in {None, "admin"}):
        raise HTTPException(409, "Нельзя отозвать собственный административный доступ")
    if payload.group_ids is not None:
        ids = set(payload.group_ids)
        if set(db.scalars(select(Group.id).where(Group.id.in_(ids)))) != ids:
            raise HTTPException(422, "Указана несуществующая группа")
        for grant in db.scalars(select(AccessGrant).where(AccessGrant.user_id == user.id)):
            db.delete(grant)
        db.flush()
        db.add_all(AccessGrant(user_id=user.id, group_id=g) for g in ids)
    if payload.role is not None:
        user.role = payload.role
    if payload.enabled is not None:
        user.enabled = payload.enabled
    if payload.password is not None:
        user.password_hash = password_hasher.hash(payload.password)
    user.auth_version += 1
    audit(db, request, "access_changed", "user", user.id, payload.reason)
    db.commit()
    return user_read(user)


@router.get("/admin/audit", dependencies=[Depends(require_roles("admin"))])
def audit_events(db: Session = Depends(get_db), limit: int = 50, offset: int = 0):
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc())
                        .limit(max(1,min(limit,100))).offset(max(0,offset)))
    return [{key: getattr(e,key) for key in ("id","actor_id","action","object_type","object_id",
                                             "reason","request_id","created_at")} for e in events]


@router.get("/admin/system", dependencies=[Depends(require_roles("admin"))])
def system_status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from app.models import RecognitionJob
    from app.core.object_storage import get_client
    try:
        storage_ready = get_client().bucket_exists(settings.minio_bucket)
    except Exception:
        storage_ready = False
    states = db.execute(select(RecognitionJob.status, func.count(RecognitionJob.id))
                        .group_by(RecognitionJob.status)).all()
    return {"database": "ready", "storage": "ready" if storage_ready else "unavailable",
            "recognition_queue": {state.value:count for state,count in states},
            "last_job_heartbeat": db.scalar(select(func.max(RecognitionJob.heartbeat_at))),
            "timezone": settings.timezone, "environment": settings.environment,
            "camera_enabled": bool(settings.camera_allowed_cidrs and settings.camera_encryption_key),
            "backup_status": "not_verified"}
