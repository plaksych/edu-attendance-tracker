from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import settings


def protect_camera_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        address = ip_address(parts.hostname or "")
        networks = [ip_network(c.strip()) for c in settings.camera_allowed_cidrs.split(",") if c.strip()]
        if (parts.scheme != "rtsp" or parts.fragment or address.is_loopback
                or address.is_link_local or address.is_multicast or address.is_unspecified
                or not any(address in network for network in networks)):
            raise ValueError("destination denied")
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError("port denied")
    except ValueError:
        raise HTTPException(422, "Нужен RTSP-адрес с IP из разрешённой сети камер") from None
    if not settings.camera_encryption_key:
        raise HTTPException(503, "Не настроен ключ шифрования камеры")
    try:
        return "encrypted:" + Fernet(settings.camera_encryption_key.encode()).encrypt(url.encode()).decode()
    except ValueError:
        raise HTTPException(503, "Некорректный ключ шифрования камеры") from None
