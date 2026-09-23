import pytest

from app.core.config import Settings


def config(**overrides):
    values = {
        "environment": "production",
        "semester_end": "2026-12-31",
        "database_url": "postgresql+psycopg2://runtime:fixture-password-0123456789012345@db/attendance_prod_fixture",
        "minio_access_key": "fixture-runtime",
        "minio_secret_key": "fixture-storage-0123456789012345",
        "minio_public_endpoint": "media.example.invalid",
        "trusted_hosts": "app.example.invalid",
        "cors_origins": "https://app.example.invalid",
    }
    return Settings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "postgresql://attendance:attendance@db/attendance"},
        {"database_url": "sqlite:///demo.db"},
        {"database_url": "postgresql://runtime@db/attendance"},
        {"minio_public_endpoint": None},
        {"minio_secret_key": "short"},
        {"cors_origins": "http://app.example.invalid"},
        {"cors_origins": ""},
        {"session_secure": False},
        {"semester_end": None},
    ],
)
def test_production_cannot_bypass_boundaries_with_explicit_url(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


def test_explicit_production_config_accepts_encoded_password():
    result = config(
        database_url="postgresql://runtime:fixture%40password-0123456789012345@db/attendance_prod_fixture"
    )
    assert result.minio_public_secure and result.session_secure
