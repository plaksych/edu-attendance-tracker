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


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    manager.stop_all()


app = FastAPI(
    title="Attendance Recognition Service",
    description="Подсчёт людей в аудитории по видеопотоку (YOLOv8)",
    version="1.0.0",
    lifespan=lifespan,
)


class StreamStartRequest(BaseModel):
    session_id: int
    rtsp_url: str = Field(min_length=1, description="RTSP-адрес камеры или путь к видеофайлу")


class StreamStopRequest(BaseModel):
    session_id: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/streams")
def list_streams() -> list[dict]:
    return manager.active()


@app.post("/streams/start", status_code=status.HTTP_202_ACCEPTED)
def start_stream(payload: StreamStartRequest) -> dict[str, str]:
    started = manager.start(payload.session_id, payload.rtsp_url)
    if not started:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Поток для занятия {payload.session_id} уже обрабатывается",
        )
    return {"status": "started"}


@app.post("/streams/stop")
def stop_stream(payload: StreamStopRequest) -> dict[str, str]:
    stopped = manager.stop(payload.session_id)
    if not stopped:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Активный поток для занятия {payload.session_id} не найден",
        )
    return {"status": "stopped"}


@app.post("/detect")
async def detect_image(file: UploadFile = File(...)) -> dict:
    """Разовый подсчёт людей на загруженном изображении. Удобно для проверки модели."""
    data = await file.read()
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Не удалось прочитать изображение"
        )
    result = detector.detect(frame)
    return {
        "person_count": result.person_count,
        "confidence": result.avg_confidence,
    }
