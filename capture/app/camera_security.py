"""Decrypt credentials only at use time; deny unapproved camera destinations."""

import ipaddress
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


class CameraPolicyError(ValueError):
    pass


def camera_url(value: str, settings: Settings) -> str:
    if value.startswith("encrypted:"):
        try:
            value = (
                Fernet(settings.camera_encryption_key.encode())
                .decrypt(value.removeprefix("encrypted:").encode())
                .decode()
            )
        except (ValueError, InvalidToken, UnicodeError) as exc:
            raise CameraPolicyError("camera_credentials_unavailable") from exc
    elif settings.environment == "production":
        raise CameraPolicyError("plaintext_camera_credentials_forbidden")
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "rtsp" or not parsed.hostname or parsed.fragment:
            raise ValueError()
        # Numeric addresses eliminate DNS rebinding and ambiguous DNS allowlists.
        address = ipaddress.ip_address(parsed.hostname)
        _ = parsed.port
        networks = [
            ipaddress.ip_network(item.strip())
            for item in settings.camera_allowed_cidrs.split(",")
            if item.strip()
        ]
        if (
            address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
            or getattr(address, "ipv4_mapped", None) is not None
            or not any(address in network for network in networks)
        ):
            raise ValueError()
    except ValueError as exc:
        raise CameraPolicyError("camera_destination_forbidden") from exc
    return value
