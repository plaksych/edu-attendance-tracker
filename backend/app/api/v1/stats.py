from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.schemas.stats import EntityStats, GroupTimeline, SummaryStats
from app.services import stats as stats_service

router = APIRouter(prefix="/stats", tags=["Статистика"])


@router.get("/summary", response_model=SummaryStats)
def get_summary(db: DbSession = Depends(get_db)):
    return stats_service.summary(db)


@router.get("/teachers/{teacher_id}", response_model=EntityStats)
def get_teacher_stats(teacher_id: int, db: DbSession = Depends(get_db)):
    return stats_service.teacher_stats(db, teacher_id)


@router.get("/disciplines/{discipline_id}", response_model=EntityStats)
def get_discipline_stats(discipline_id: int, db: DbSession = Depends(get_db)):
    return stats_service.discipline_stats(db, discipline_id)


@router.get("/groups/{group_id}", response_model=EntityStats)
def get_group_stats(group_id: int, db: DbSession = Depends(get_db)):
    return stats_service.group_stats(db, group_id)


@router.get("/groups/{group_id}/timeline", response_model=GroupTimeline)
def get_group_timeline(
    group_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: DbSession = Depends(get_db),
):
    return stats_service.group_timeline(db, group_id, date_from, date_to)
