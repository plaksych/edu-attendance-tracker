from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.schemas.session import CaptureMediaRead, SessionDetail, SessionRead
from app.services import media as media_service
from app.services import sessions as sessions_service

router = APIRouter(tags=["Занятия"])


@router.get(
    "/sessions/today",
    response_model=list[SessionRead],
    summary="Получить занятия на сегодня",
    description="Возвращает занятия текущей даты с состоянием обоих замеров и итогом посещаемости.",
)
def list_today(db: DbSession = Depends(get_db)):
    return sessions_service.list_sessions_for_date(db, date.today())


@router.get(
    "/sessions",
    response_model=list[SessionRead],
    summary="Получить занятия на дату",
    description="Формирует занятия по расписанию с учётом белой/зелёной недели и возвращает их состояние.",
)
def list_by_date(
    session_date: date = Query(alias="date", description="Дата занятий"),
    db: DbSession = Depends(get_db),
):
    return sessions_service.list_sessions_for_date(db, session_date)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetail,
    summary="Получить занятие с деталями замеров",
    description=(
        "Возвращает занятие, оба замера, записи каждой камеры и результаты распознавания. "
        "Ссылки на медиа выдаются отдельно через `GET /captures/{id}/media`."
    ),
    responses={404: {"description": "Занятие не найдено"}},
)
def get_session(session_id: int, db: DbSession = Depends(get_db)):
    return sessions_service.get_session(db, session_id, with_captures=True)


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=SessionRead,
    summary="Отменить занятие",
    description="Отменяет занятие и все его незавершённые замеры и задания записи.",
    responses={409: {"description": "Занятие уже завершено или отменено"}},
)
def cancel_session(session_id: int, db: DbSession = Depends(get_db)):
    return sessions_service.cancel_session(db, session_id)


@router.get(
    "/captures/{capture_id}/media",
    response_model=CaptureMediaRead,
    tags=["Медиа"],
    summary="Получить временные ссылки на медиа записи",
    description=(
        "Выдаёт presigned-ссылки MinIO на исходный ролик и размеченный кадр. "
        "После истечения срока хранения вместо ссылки возвращается причина недоступности."
    ),
    responses={404: {"description": "Запись не найдена"}},
)
def get_capture_media(capture_id: int, db: DbSession = Depends(get_db)):
    return media_service.capture_media_links(db, capture_id)
