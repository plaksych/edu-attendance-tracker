from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CameraRole


class Camera(Base):
    """Физическая камера. RTSP-адрес во frontend не передаётся."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    rtsp_url: Mapped[str] = mapped_column(String(1000))
    # Сетевая зона / capture-узел, который имеет доступ к камере
    capture_group: Mapped[str] = mapped_column(String(100), default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    classroom_links: Mapped[list["ClassroomCamera"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )


class ClassroomCamera(Base):
    """Привязка камеры к аудитории. Одна камера обслуживает только одну аудиторию."""

    __tablename__ = "classroom_cameras"

    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[CameraRole] = mapped_column(
        Enum(CameraRole, name="camera_role"), default=CameraRole.primary
    )
    priority: Mapped[int] = mapped_column(Integer, default=1)
    zone_code: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("camera_id", name="uq_classroom_cameras_camera"),
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="camera_links")  # noqa: F821
    camera: Mapped[Camera] = relationship(back_populates="classroom_links")

    @property
    def enabled(self) -> bool:
        return self.camera.enabled
