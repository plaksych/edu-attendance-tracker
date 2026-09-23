from fastapi import APIRouter, Depends

from app.api.v1 import auth, cameras, catalog, recognition, schedule, sessions, stats
from app.core.security import catalog_access, require_roles

router = APIRouter()
router.include_router(auth.router)
router.include_router(catalog.router, dependencies=[Depends(catalog_access)])
router.include_router(cameras.router, dependencies=[Depends(require_roles("admin"))])
router.include_router(recognition.router, dependencies=[Depends(require_roles("admin", "operator", "teacher"))])
router.include_router(schedule.router, dependencies=[Depends(catalog_access)])
router.include_router(sessions.router, dependencies=[Depends(require_roles("admin", "operator", "teacher"))])
router.include_router(stats.router, dependencies=[Depends(require_roles("admin", "operator", "teacher", "analyst"))])
