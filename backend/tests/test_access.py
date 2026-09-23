from datetime import date, time
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import password_hasher
from app.main import app
from app.models import (
    AccessGrant,
    Group,
    Discipline,
    Teacher,
    Classroom,
    Schedule,
    Session,
    RecognitionUpload,
    RecognitionJob,
    User,
    AttendanceRecord,
)
from app.models.security import LoginSession

PASSWORD = "correct-password-12345"


@pytest.fixture()
def world():
    dsn = os.environ.get("BACKEND_TEST_DSN")
    control = None
    schema = "access_test_" + uuid4().hex
    if dsn:
        control = create_engine(dsn)
        with control.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        engine = create_engine(dsn, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    encoded = password_hasher.hash(PASSWORD)
    with factory() as db:
        users = [
            User(username=role, role=role, password_hash=encoded)
            for role in ("admin", "operator", "teacher", "analyst")
        ]
        db.add_all(users)
        db.flush()
        for number in (1, 2):
            group = Group(name=f"G{number}", students_count=20)
            schedule = Schedule(
                group=group,
                discipline=Discipline(name=f"D{number}"),
                teacher=Teacher(full_name=f"T{number}"),
                classroom=Classroom(number=f"R{number}"),
                weekday=3,
                starts_at=time(9),
                ends_at=time(10),
            )
            session = Session(
                schedule=schedule, date=date(2026, 9, 23), expected_count_snapshot=20
            )
            db.add(session)
            db.flush()
            db.add(
                RecognitionUpload(
                    filename=f"image{number}.png",
                    media_type="image",
                    original_bucket="private",
                    original_object_key=f"{number}.png",
                    content_type="image/png",
                    size_bytes=100,
                    owner_id=users[1].id,
                    session_id=session.id,
                    jobs=[RecognitionJob()],
                )
            )
        db.add(AccessGrant(user_id=users[2].id, group_id=1))
        db.commit()

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app, base_url="https://testserver") as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()
    if control:
        with control.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        control.dispose()


def login(client, role):
    response = client.post(
        "/api/v1/auth/login", json={"username": role, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_openapi_and_anonymous_denials(world):
    client, _ = world
    assert client.get("/openapi.json").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["APIKeyCookie"]["in"] == "cookie"
    assert schema["paths"]["/api/v1/groups"]["get"]["security"] == [
        {"APIKeyCookie": []}
    ]
    for path in (
        "groups",
        "schedule",
        "sessions/today",
        "recognition/uploads",
        "recognition/evaluation/summary",
        "recognition/uploads/1/media",
        "captures/1/media",
        "stats/summary",
        "admin/users",
        "stats/export.csv?date_from=2026-09-01&date_to=2026-09-30",
    ):
        assert client.get("/api/v1/" + path).status_code == 401, path


def test_teacher_scope_lists_details_and_statistics(world):
    client, _ = world
    login(client, "teacher")
    assert [g["name"] for g in client.get("/api/v1/groups").json()] == ["G1"]
    assert len(client.get("/api/v1/schedule").json()) == 1
    assert len(client.get("/api/v1/sessions?date=2026-09-23").json()) == 1
    assert client.get("/api/v1/sessions/2").status_code == 404
    assert client.get("/api/v1/recognition/uploads/2/media").status_code == 404
    assert len(client.get("/api/v1/recognition/uploads").json()) == 1
    assert client.get("/api/v1/stats/groups/2").status_code == 404
    assert client.get("/api/v1/stats/summary").json()["groups"] == 1


def test_csv_scope_and_formula_injection(world):
    client, factory = world
    with factory() as db:
        db.get(Group, 1).name = "=SUM(1,2)"
        for session_id in (1, 2):
            db.add(
                AttendanceRecord(
                    session_id=session_id,
                    expected_count=20,
                    detected_average=15,
                    detected_max=15,
                    attendance_rate=0.75,
                    calculation_status="complete",
                )
            )
        db.commit()
    login(client, "teacher")
    route = "/api/v1/stats/export.csv?date_from=2026-09-01&date_to=2026-09-30"
    response = client.get(route)
    assert response.status_code == 200, response.text
    assert "'=SUM(1,2)" in response.text
    assert "G2" not in response.text and "D2" not in response.text
    assert len(response.text.strip().splitlines()) == 2
    denied = client.get(route + "&group_id=2")
    assert denied.status_code == 200 and len(denied.text.strip().splitlines()) == 1
    assert (
        client.get(
            "/api/v1/stats/export.csv?date_from=2020-01-01&date_to=2026-09-30"
        ).status_code
        == 422
    )


def test_csrf_role_denial_logout_and_revocation(world):
    client, factory = world
    headers = login(client, "teacher")
    assert client.post("/api/v1/groups", json={"name": "forbidden"}).status_code == 403
    assert (
        client.post(
            "/api/v1/groups", json={"name": "forbidden"}, headers=headers
        ).status_code
        == 403
    )
    assert client.post("/api/v1/sessions/1/cancel", headers=headers).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    login(client, "operator")
    with factory() as db:
        user = db.scalar(select(User).where(User.username == "operator"))
        user.auth_version += 1
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_analyst_cannot_read_media_or_recognition(world):
    client, _ = world
    login(client, "analyst")
    for path in (
        "recognition/uploads",
        "recognition/uploads/1/media",
        "captures/1/media",
        "cameras",
        "sessions/1",
    ):
        assert client.get("/api/v1/" + path).status_code == 403
    assert client.get("/api/v1/stats/summary").status_code == 200


def test_admin_mutation_is_audited_without_password(world):
    client, factory = world
    headers = login(client, "admin")
    response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={"username": "new", "password": PASSWORD, "role": "teacher"},
    )
    assert response.status_code == 201
    assert "password" not in response.text
    records = client.get("/api/v1/admin/audit").json()
    assert any(a["action"] == "create" for a in records)
    assert PASSWORD not in str(records)
    with factory() as db:
        stored = db.scalars(select(LoginSession)).all()
        assert all(
            s.token_hash != client.cookies.get("attendance_session") for s in stored
        )


def test_request_size_before_parser_and_safe_validation_error(world):
    client, _ = world
    response = client.post(
        "/api/v1/auth/login", content=b"x", headers={"Content-Length": "999999999"}
    )
    assert response.status_code == 413
    response = client.post("/api/v1/auth/login", json={"password": PASSWORD})
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert response.json()["error"]["request_id"]
