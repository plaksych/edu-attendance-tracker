import logging
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.detector import detector
from app.worker import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

OPENAPI_TAGS = [
    {
        "name": "Служебное",
        "description": "Проверка состояния recognition-сервиса.",
    },
    {
        "name": "Потоки",
        "description": "Управление фоновыми обработчиками RTSP/видеофайлов для занятий.",
    },
    {
        "name": "Распознавание",
        "description": "Разовый подсчёт людей на загруженном изображении.",
    },
]

APP_DESCRIPTION = """
Recognition-сервис получает команды от backend и выполняет подсчёт людей через YOLOv8.

Основной сценарий:

1. Backend вызывает `/streams/start` с `session_id` и адресом камеры.
2. Сервис запускает фоновый worker, периодически берёт кадр из потока и сохраняет размеченный jpg.
3. Worker отправляет результат в backend на `/api/v1/sessions/{session_id}/snapshots`.
4. Backend завершает занятие через `/streams/stop` и рассчитывает посещаемость.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    manager.stop_all()


app = FastAPI(
    title="Attendance Recognition Service",
    description=APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
)


class StreamStartRequest(BaseModel):
    session_id: int = Field(description="ID занятия в backend", examples=[12])
    rtsp_url: str = Field(
        min_length=1,
        description="RTSP/HTTP-адрес камеры или путь к видеофайлу",
        examples=["rtsp://user:password@192.168.1.10:554/stream1"],
    )


class StreamStopRequest(BaseModel):
    session_id: int = Field(description="ID занятия, поток которого нужно остановить", examples=[12])


class HealthRead(BaseModel):
    status: str = Field(description="Состояние сервиса", examples=["ok"])


class StreamInfo(BaseModel):
    session_id: int = Field(description="ID занятия в обработке", examples=[12])
    source: str = Field(description="Источник видео", examples=["rtsp://camera/stream1"])


class StreamActionRead(BaseModel):
    status: str = Field(description="Результат команды", examples=["started"])


class DetectionRead(BaseModel):
    person_count: int = Field(description="Количество найденных людей", examples=[24])
    confidence: float | None = Field(
        description="Средняя уверенность по найденным людям",
        examples=[0.82],
    )


@app.get(
    "/health",
    response_model=HealthRead,
    tags=["Служебное"],
    summary="Проверить состояние recognition-сервиса",
    description="Возвращает `ok`, если сервис запущен и отвечает на HTTP-запросы.",
)
def health() -> HealthRead:
    return HealthRead(status="ok")


@app.get(
    "/streams",
    response_model=list[StreamInfo],
    tags=["Потоки"],
    summary="Получить активные потоки",
    description="Возвращает список фоновых workers, которые сейчас обрабатывают камеры или видеофайлы.",
)
def list_streams() -> list[dict]:
    return manager.active()


@app.post(
    "/streams/start",
    response_model=StreamActionRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Потоки"],
    summary="Запустить обработку потока",
    description="Создаёт фоновый worker для занятия. Повторный запуск для активного `session_id` вернёт 409.",
    responses={
        409: {"description": "Поток для занятия уже обрабатывается"},
    },
)
def start_stream(payload: StreamStartRequest) -> StreamActionRead:
    started = manager.start(payload.session_id, payload.rtsp_url)
    if not started:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Поток для занятия {payload.session_id} уже обрабатывается",
        )
    return StreamActionRead(status="started")


@app.post(
    "/streams/stop",
    response_model=StreamActionRead,
    tags=["Потоки"],
    summary="Остановить обработку потока",
    description="Останавливает worker по `session_id`. Если активного потока нет, возвращает 404.",
    responses={
        404: {"description": "Активный поток для занятия не найден"},
    },
)
def stop_stream(payload: StreamStopRequest) -> StreamActionRead:
    stopped = manager.stop(payload.session_id)
    if not stopped:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Активный поток для занятия {payload.session_id} не найден",
        )
    return StreamActionRead(status="stopped")


@app.post(
    "/detect",
    response_model=DetectionRead,
    tags=["Распознавание"],
    summary="Распознать людей на изображении",
    description="Принимает изображение, запускает детектор и возвращает количество найденных людей.",
    responses={
        400: {"description": "Файл не удалось прочитать как изображение"},
    },
)
async def detect_image(
    file: UploadFile = File(..., description="Изображение аудитории для разового распознавания"),
) -> DetectionRead:
    """Разовый подсчёт людей на загруженном изображении. Удобно для проверки модели."""
    data = await file.read()
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Не удалось прочитать изображение"
        )
    result = detector.detect(frame)
    return DetectionRead(
        person_count=result.person_count,
        confidence=result.avg_confidence,
    )
