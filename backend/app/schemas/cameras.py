from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CameraRole


class CameraBase(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Уникальное имя камеры",
        examples=["cam-302-front"],
    )
    capture_group: str = Field(
        default="default",
        max_length=100,
        description="Сетевая зона или capture-узел, обслуживающий камеру",
        examples=["building-a"],
    )
    enabled: bool = Field(
        default=True,
        description="Отключённая камера не участвует в замерах",
    )


class CameraCreate(CameraBase):
    rtsp_url: str = Field(
        min_length=1,
        max_length=1000,
        description="RTSP/HTTP-адрес камеры или путь к видеофайлу для отладки",
        examples=["rtsp://user:password@192.168.1.10:554/stream1"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "cam-302-front",
                "rtsp_url": "rtsp://user:password@192.168.1.10:554/stream1",
                "capture_group": "building-a",
                "enabled": True,
            }
        }
    )


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    rtsp_url: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="Новый адрес; если не передан, адрес не меняется",
    )
    capture_group: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None


class CameraRead(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rtsp_url: str = Field(
        description="Адрес камеры с замаскированными учётными данными",
        examples=["rtsp://user:***@192.168.1.10:554/stream1"],
    )
    classroom_number: str | None = Field(
        default=None,
        description="Аудитория, к которой привязана камера",
        examples=["302"],
    )
    created_at: datetime


class CameraBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ClassroomCameraAssign(BaseModel):
    camera_id: int = Field(description="ID камеры из справочника камер")
    role: CameraRole = Field(
        default=CameraRole.primary,
        description="Роль камеры в аудитории",
    )
    priority: int = Field(default=1, ge=1, le=10, description="Порядок предпочтения")
    zone_code: str | None = Field(
        default=None,
        max_length=50,
        description="Код зоны обзора для непересекающихся камер",
        examples=["left"],
    )


class ClassroomCameraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    camera: CameraBrief
    role: CameraRole
    priority: int
    zone_code: str | None
    enabled: bool = Field(description="Текущее состояние камеры")
