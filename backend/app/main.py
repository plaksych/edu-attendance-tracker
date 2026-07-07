import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.object_storage import ensure_bucket
from app.services.scheduler import SchedulerThread


class HealthRead(BaseModel):
    status: str = Field(description="Состояние сервиса", examples=["ok"])


OPENAPI_TAGS = [
    {
        "name": "Служебное",
        "description": "Проверка состояния backend-сервиса.",
    },
    {
        "name": "Справочники",
        "description": "Группы, преподаватели, дисциплины и аудитории с режимом объединения камер.",
    },
    {
        "name": "Камеры",
        "description": "Справочник камер и привязка камер к аудиториям.",
    },
    {
        "name": "Расписание",
        "description": "Загрузка Excel-расписания, ручное управление занятиями в сетке и расчёт типа недели.",
    },
    {
        "name": "Занятия",
        "description": "Занятия на дату, состояние двух замеров каждой камеры и итог посещаемости.",
    },
    {
        "name": "Медиа",
        "description": "Временные presigned-ссылки MinIO на исходные ролики и размеченные кадры.",
    },
    {
        "name": "Статистика",
        "description": "Агрегированные метрики посещаемости для дашборда frontend-приложения.",
    },
]

APP_DESCRIPTION = """
Backend API системы контроля посещаемости.

Фактический поток данных:

1. Frontend работает с backend через REST API.
2. Measurement Scheduler внутри backend создаёт занятия на 14 дней вперёд и по два замера
   на занятие: через 15 минут после начала и за 15 минут до конца.
3. Для каждого замера создаются задания записи по камерам аудитории; Capture Manager
   забирает их из PostgreSQL, пишет ролики с RTSP и загружает их в MinIO.
4. Recognition-воркеры берут задания распознавания из очереди, считают людей локальной
   моделью YOLO и сохраняют агрегаты и размеченный кадр.
5. Backend объединяет результаты камер и двух замеров в итог занятия и выдаёт frontend
   временные presigned-ссылки на медиа.
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_bucket()
    except Exception:
        logger.exception("Не удалось инициализировать бакет MinIO — медиа будут недоступны")

    scheduler = SchedulerThread() if settings.scheduler_enabled else None
    if scheduler is not None:
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.stop()
        scheduler.join(timeout=settings.scheduler_interval_seconds + 5)


app = FastAPI(
    title=settings.app_name,
    description=APP_DESCRIPTION,
    version="2.0.0",
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get(
    "/health",
    response_model=HealthRead,
    tags=["Служебное"],
    summary="Проверить состояние backend",
    description="Возвращает `ok`, если backend-приложение запущено и отвечает на HTTP-запросы.",
)
def health() -> HealthRead:
    return HealthRead(status="ok")
