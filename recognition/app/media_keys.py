"""Стабильные ключи объектов для исходных и размеченных медиафайлов."""


def annotated_camera_object_key(
    session_id: int, measurement_id: int, camera_id: int
) -> str:
    """Ключ размеченного кадра камеры; повторная попытка перезаписывает объект."""
    return (
        f"annotated/sessions/{session_id}/measurements/{measurement_id}"
        f"/cameras/{camera_id}.jpg"
    )


def annotated_upload_object_key(upload_id: int) -> str:
    """Ключ размеченного кадра для файла, загруженного без камеры."""
    return f"annotated/uploads/{upload_id}.jpg"
