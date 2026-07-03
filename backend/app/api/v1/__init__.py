from fastapi import APIRouter

from app.api.v1 import catalog, schedule, sessions, stats

router = APIRouter()
router.include_router(catalog.router)
router.include_router(schedule.router)
router.include_router(sessions.router)
router.include_router(stats.router)
