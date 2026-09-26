import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.http import RequestBoundary, internal_error


def test_unhandled_exception_is_correlated_without_secret(caplog):
    app = FastAPI()
    app.add_middleware(RequestBoundary)
    app.add_exception_handler(Exception, internal_error)

    @app.get("/failure")
    def failure():
        raise RuntimeError("db_password=do-not-log-me")

    with (
        TestClient(app, raise_server_exceptions=False) as client,
        caplog.at_level(logging.ERROR),
    ):
        response = client.get("/failure")
    assert response.status_code == 500
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert response.json()["error"]["code"] == "internal_error"
    assert "do-not-log-me" not in response.text + caplog.text
    assert "RuntimeError" in caplog.text
