import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.api.v1 import router as api_v1_router
from app.core.config import settings


class HealthRead(BaseModel):
    status: str = Field(description="Состояние сервиса", examples=["ok"])


OPENAPI_TAGS = [
    {
        "name": "Служебное",
        "description": "Проверка состояния backend-сервиса.",
    },
    {
        "name": "Справочники",
        "description": "Группы, преподаватели, дисциплины и аудитории с адресами камер.",
    },
    {
        "name": "Расписание",
        "description": "Загрузка Excel-расписания, ручное управление занятиями в сетке и расчёт типа недели.",
    },
    {
        "name": "Занятия",
        "description": "Формирование занятий на дату, запуск обработки камеры, приём замеров и расчёт посещаемости.",
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
2. Backend хранит справочники, расписание, занятия, замеры и агрегированную посещаемость в PostgreSQL.
3. При старте занятия backend отправляет recognition-сервису `session_id` и адрес камеры аудитории.
4. Recognition-сервис сохраняет размеченные кадры в общий volume и отправляет результаты обратно в backend.
5. Backend отдаёт сохранённые кадры как статику по `/media`.
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    description=APP_DESCRIPTION,
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

# Кадры с камер: recognition-сервис пишет в общий volume, backend отдаёт как статику
media_dir = Path(settings.media_dir)
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_dir), name="media")


@app.get(
    "/health",
    response_model=HealthRead,
    tags=["Служебное"],
    summary="Проверить состояние backend",
    description="Возвращает `ok`, если backend-приложение запущено и отвечает на HTTP-запросы.",
)
def health() -> HealthRead:
    return HealthRead(status="ok")
