"""Generate static frontend demo data from a local timetable workbook.

The source xlsx stays local and is not required at runtime. The generated JSON
is used by the GitHub Pages build where the FastAPI backend is not available.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.timetable_import import ParsedLesson, parse_workbook  # noqa: E402


def _time(value) -> str:
    return value.strftime("%H:%M:%S")


def _stable_count(name: str) -> int:
    return 22 + (sum(ord(char) for char in name) % 10)


def _capacity(room: str) -> int | None:
    if room.upper().startswith("Л"):
        return 90
    if any(char.isdigit() for char in room):
        return 36
    return None


def _next_id(cache: dict[str, int], key: str) -> int:
    if key not in cache:
        cache[key] = len(cache) + 1
    return cache[key]


def _brief_camera(camera: dict[str, Any]) -> dict[str, Any]:
    return {"id": camera["id"], "name": camera["name"]}


def build_demo(lessons: list[ParsedLesson], errors: list[str]) -> dict[str, Any]:
    group_ids: dict[str, int] = {}
    teacher_ids: dict[str, int] = {}
    discipline_ids: dict[str, int] = {}
    classroom_ids: dict[str, int] = {}
    seen_slots: set[tuple[str, int, str, str]] = set()

    groups: dict[int, dict[str, Any]] = {}
    teachers: dict[int, dict[str, Any]] = {}
    disciplines: dict[int, dict[str, Any]] = {}
    classrooms: dict[int, dict[str, Any]] = {}
    schedule: list[dict[str, Any]] = []

    for lesson in lessons:
        slot_key = (
            lesson.group,
            lesson.weekday,
            _time(lesson.starts_at),
            lesson.week_type.value,
        )
        if slot_key in seen_slots:
            continue
        seen_slots.add(slot_key)

        group_id = _next_id(group_ids, lesson.group)
        groups.setdefault(
            group_id,
            {
                "id": group_id,
                "name": lesson.group,
                "course": lesson.course,
                "faculty": "ИКН",
                "students_count": _stable_count(lesson.group),
            },
        )

        teacher = None
        if lesson.teacher:
            teacher_id = _next_id(teacher_ids, lesson.teacher)
            teachers.setdefault(
                teacher_id,
                {
                    "id": teacher_id,
                    "full_name": lesson.teacher,
                    "email": None,
                    "department": None,
                },
            )
            teacher = teachers[teacher_id]

        discipline_id = _next_id(discipline_ids, lesson.discipline)
        disciplines.setdefault(
            discipline_id,
            {"id": discipline_id, "name": lesson.discipline},
        )

        classroom = None
        if lesson.classroom:
            classroom_id = _next_id(classroom_ids, lesson.classroom)
            classrooms.setdefault(
                classroom_id,
                {
                    "id": classroom_id,
                    "number": lesson.classroom,
                    "capacity": _capacity(lesson.classroom),
                    "aggregation_mode": "single",
                    "cameras": [],
                },
            )
            classroom = classrooms[classroom_id]

        schedule.append(
            {
                "id": len(schedule) + 1,
                "weekday": lesson.weekday,
                "starts_at": _time(lesson.starts_at),
                "ends_at": _time(lesson.ends_at),
                "week_type": lesson.week_type.value,
                "lesson_type": lesson.lesson_type,
                "group": groups[group_id],
                "teacher": teacher,
                "discipline": disciplines[discipline_id],
                "classroom": classroom,
            }
        )

    cameras: list[dict[str, Any]] = []
    for classroom in classrooms.values():
        slug = (
            classroom["number"]
            .lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("\\", "-")
        )
        camera = {
            "id": len(cameras) + 1,
            "name": f"cam-{slug}",
            "rtsp_url": f"rtsp://demo:***@camera-{slug}.local/stream1",
            "capture_group": "default",
            "enabled": True,
            "classroom_number": classroom["number"],
            "created_at": "2026-07-05T00:00:00",
        }
        cameras.append(camera)
        classroom["cameras"] = [
            {
                "camera": _brief_camera(camera),
                "role": "primary",
                "priority": 1,
                "zone_code": None,
                "enabled": camera["enabled"],
            }
        ]

    return {
        "source": "ikn-bak.xlsx",
        "semester_start": "2026-02-09",
        "generated_at": "2026-07-05T00:00:00",
        "import_result": {
            "created": len(schedule),
            "skipped": len(lessons) - len(schedule),
            "errors": errors[:50],
        },
        "groups": sorted(groups.values(), key=lambda item: item["name"]),
        "teachers": sorted(teachers.values(), key=lambda item: item["full_name"]),
        "disciplines": sorted(disciplines.values(), key=lambda item: item["name"]),
        "classrooms": sorted(classrooms.values(), key=lambda item: item["number"]),
        "cameras": sorted(cameras, key=lambda item: item["name"]),
        "schedule": sorted(
            schedule,
            key=lambda item: (
                item["weekday"],
                item["starts_at"],
                item["group"]["name"],
                item["discipline"]["name"],
            ),
        ),
    }


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "ikn-bak.xlsx"
    target = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else ROOT / "frontend" / "public" / "demo-data.json"
    )

    with source.open("rb") as file:
        lessons, errors = parse_workbook(file)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_demo(lessons, errors), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Generated {target}")


if __name__ == "__main__":
    main()
