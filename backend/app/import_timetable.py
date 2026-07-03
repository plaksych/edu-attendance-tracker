"""Импорт институтского расписания из файла.

Запуск: python -m app.import_timetable <путь к .xlsx>
"""

import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.services import schedule_import, timetable_import


def main() -> int:
    if len(sys.argv) != 2:
        print("Использование: python -m app.import_timetable <файл.xlsx>")
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"Файл не найден: {path}")
        return 2

    db = SessionLocal()
    try:
        with path.open("rb") as file:
            if timetable_import.looks_like_timetable(file):
                result = timetable_import.import_timetable(db, file)
            else:
                result = schedule_import.import_schedule(db, file)
    finally:
        db.close()

    print(f"Добавлено: {result.created}, пропущено дублей: {result.skipped}")
    for error in result.errors:
        print(f"  ! {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
