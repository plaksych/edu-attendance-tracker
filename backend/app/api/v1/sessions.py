from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.schemas.session import (
    AttendanceRead,
    SessionRead,
    SessionWithSnapshots,
    SnapshotCreate,
    SnapshotRead,
)
from app.services import sessions as sessions_service

router = APIRouter(prefix="/sessions", tags=["Занятия"])


@router.get("/today", response_model=list[SessionRead])
def list_today(db: DbSession = Depends(get_db)):
    return sessions_service.list_sessions_for_date(db, date.today())


@router.get("", response_model=list[SessionRead])
def list_by_date(
    session_date: date = Query(alias="date"), db: DbSession = Depends(get_db)
):
    return sessions_service.list_sessions_for_date(db, session_date)


@router.get("/{session_id}", response_model=SessionWithSnapshots)
def get_session(session_id: int, db: DbSession = Depends(get_db)):
    return sessions_service.get_session(db, session_id, with_snapshots=True)


@router.post("/{session_id}/start", response_model=SessionRead)
def start_session(session_id: int, db: DbSession = Depends(get_db)):
    return sessions_service.start_session(db, session_id)


@router.post("/{session_id}/finish", response_model=SessionRead)
def finish_session(session_id: int, db: DbSession = Depends(get_db)):
    return sessions_service.finish_session(db, session_id)


@router.post(
    "/{session_id}/snapshots",
    response_model=SnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def add_snapshot(
    session_id: int, payload: SnapshotCreate, db: DbSession = Depends(get_db)
):
    return sessions_service.add_snapshot(
        db,
        session_id,
        captured_at=payload.captured_at,
        person_count=payload.person_count,
        confidence=payload.confidence,
        frame_path=payload.frame_path,
    )


@router.get("/{session_id}/attendance", response_model=AttendanceRead)
def get_attendance(session_id: int, db: DbSession = Depends(get_db)):
    session = sessions_service.get_session(db, session_id)
    if session.attendance is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Посещаемость по занятию ещё не рассчитана"
        )
    return session.attendance
