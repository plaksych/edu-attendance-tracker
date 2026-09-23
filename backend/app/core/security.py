from datetime import datetime, timezone
from hashlib import sha256
from secrets import compare_digest

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.security import AccessGrant, AuditEvent, LoginSession, User

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
_DUMMY_HASH = password_hasher.hash("not-a-valid-account-password")


def verify_password(encoded: str, password: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.session_cookie_name, "")
    session = db.get(LoginSession, token_hash(token)) if token else None
    user = db.get(User, session.user_id) if session else None
    if (not session or not user or not user.enabled
            or session.auth_version != user.auth_version
            or utc(session.expires_at) <= datetime.now(timezone.utc)):
        raise HTTPException(401, "Требуется вход в систему")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not compare_digest(csrf, session.csrf_token):
            raise HTTPException(403, "Недействительный CSRF-токен")
    request.state.user = user
    request.state.login_session = session
    db.info["audit_request"] = request
    if user.role == "teacher":
        db.info["allowed_groups"] = tuple(db.scalars(
            select(AccessGrant.group_id).where(AccessGrant.user_id == user.id)
        ))
        db.info["user_id"] = user.id
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Недостаточно прав")
        return user
    return dependency


def catalog_access(request: Request, user: User = Depends(current_user)):
    if request.method not in {"GET", "HEAD"} and user.role not in {"admin", "operator"}:
        raise HTTPException(403, "Изменение справочников недоступно")
    return user


def audit(db: Session, request: Request, action: str, object_type: str,
          object_id=None, reason=None, actor_id=None):
    user = getattr(request.state, "user", None)
    db.add(AuditEvent(actor_id=actor_id if actor_id is not None else (user.id if user else None),
                      action=action, object_type=object_type,
                      object_id=str(object_id) if object_id is not None else None,
                      reason=reason, request_id=request.state.request_id))
