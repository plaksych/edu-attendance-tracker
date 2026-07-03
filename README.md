# Educational Attendance Tracker

Информационная система для контроля посещаемости учебных занятий. Проект объединяет веб-интерфейс, backend API, сервис распознавания людей на кадрах и PostgreSQL.

Система рассчитана на учебное расписание с белой и зелёной неделей, импорт занятий из Excel, фиксацию замеров с камер и построение статистики по группам, преподавателям и дисциплинам.

## Возможности

- ведение справочников групп, преподавателей, дисциплин и аудиторий;
- импорт расписания из Excel в двух форматах: институтская сетка и построчный шаблон;
- поддержка занятий по белой, зелёной или каждой учебной неделе;
- формирование занятий на выбранную дату по расписанию;
- запуск и остановка обработки видеопотока для занятия;
- подсчёт людей на кадрах через YOLOv8;
- хранение снимков и сырых замеров распознавания;
- расчёт средней, максимальной и процентной посещаемости;
- дашборд со сводкой и динамикой по учебным группам.

## Архитектура

Проект состоит из четырёх контейнеров:

| Сервис | Назначение | Порт |
|---|---|---:|
| `frontend` | React-приложение с дашбордом, занятиями и расписанием | `3000` |
| `backend` | FastAPI API, бизнес-логика, миграции, доступ к БД | `8000` |
| `recognition` | FastAPI-сервис для обработки потока и разового распознавания | `8001` |
| `db` | PostgreSQL 16 | `5432` |

```text
Frontend  ->  Backend API  ->  PostgreSQL
                 |
                 v
          Recognition service
                 |
                 v
          Shared snapshots volume
```

Backend является единственной точкой доступа к базе данных. Recognition-сервис не хранит состояние занятий в БД: он получает `session_id` и адрес камеры от backend, обрабатывает поток и отправляет результаты обратно через REST.

Кадры сохраняются в общий Docker volume `snapshots`. Backend отдаёт их как статические файлы по пути `/media`.

## Стек

| Часть | Технологии |
|---|---|
| Frontend | React 18, TypeScript, Vite, Recharts |
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Recognition | Python 3.11, FastAPI, Ultralytics YOLOv8, OpenCV |
| Database | PostgreSQL 16 |
| Infrastructure | Docker, Docker Compose, Nginx |

## Структура проекта

```text
edu-attendance-tracker/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST API
│   │   ├── core/                # настройки и подключение к БД
│   │   ├── models/              # SQLAlchemy-модели
│   │   ├── schemas/             # Pydantic-схемы
│   │   ├── services/            # импорт, статистика, занятия, recognition-клиент
│   │   ├── import_timetable.py  # CLI-импорт расписания
│   │   └── main.py
│   ├── alembic/                 # миграции БД
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # клиент API и типы
│   │   ├── components/          # общие UI-компоненты
│   │   └── pages/               # дашборд, занятия, расписание
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── recognition/
│   ├── app/
│   │   ├── detector.py          # обёртка над YOLOv8
│   │   ├── worker.py            # обработка видеопотока
│   │   ├── config.py
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

## Быстрый старт

Требования:

- Docker и Docker Compose;
- свободные порты `3000`, `5432`, `8000`, `8001`;
- при локальном запуске без контейнеров: Python 3.11+ и Node.js 18+.

```bash
git clone <repo_url>
cd edu-attendance-tracker

cp .env.example .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

После запуска доступны:

- frontend: `http://localhost:3000`;
- backend API: `http://localhost:8000`;
- backend Swagger UI: `http://localhost:8000/docs`;
- recognition Swagger UI: `http://localhost:8001/docs`.

## Импорт расписания

Расписание можно загрузить на странице `Расписание` во frontend или через API:

```bash
curl -F "file=@schedule.xlsx" http://localhost:8000/api/v1/schedule/import
```

Поддерживаются два формата:

| Формат | Описание |
|---|---|
| Институтская сетка | Листы с группами по колонкам, слот пары из двух строк: верхняя строка для белой недели, нижняя для зелёной |
| Построчный шаблон | Колонки `Группа`, `Преподаватель`, `Дисциплина`, `Аудитория`, `День недели`, `Начало`, `Конец`, `Неделя` |

Шаблон построчного формата можно скачать из интерфейса или по адресу:

```text
GET http://localhost:8000/api/v1/schedule/template
```

## Локальная разработка

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Recognition:

```bash
cd recognition
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8001
```

## Переменные окружения

| Переменная | Сервис | Описание |
|---|---|---|
| `DB_HOST` | backend | Хост PostgreSQL |
| `DB_PORT` | backend | Порт PostgreSQL |
| `DB_NAME` | backend | Имя базы данных |
| `DB_USER` | backend | Пользователь БД |
| `DB_PASSWORD` | backend | Пароль БД |
| `DATABASE_URL` | backend | Полная строка подключения к PostgreSQL |
| `RECOGNITION_URL` | backend | Адрес recognition-сервиса |
| `SEMESTER_START` | backend | Понедельник первой учебной недели семестра |
| `CORS_ORIGINS` | backend | Разрешённые origins для CORS через запятую |
| `BACKEND_URL` | recognition | Адрес backend для отправки результатов |
| `SNAPSHOT_INTERVAL` | recognition | Интервал между замерами, сек |
| `CONFIDENCE_THRESHOLD` | recognition | Порог уверенности детектора |
| `MODEL_PATH` | recognition | Путь к весам модели |
| `SNAPSHOT_DIR` | recognition | Каталог для сохранения кадров |

## Основные эндпоинты

Backend:

```text
GET    /health

GET    /api/v1/groups
POST   /api/v1/groups
GET    /api/v1/teachers
POST   /api/v1/teachers
GET    /api/v1/disciplines
POST   /api/v1/disciplines
GET    /api/v1/classrooms
POST   /api/v1/classrooms

GET    /api/v1/schedule
POST   /api/v1/schedule
DELETE /api/v1/schedule/{item_id}
GET    /api/v1/schedule/template
POST   /api/v1/schedule/import
GET    /api/v1/schedule/week-type

GET    /api/v1/sessions/today
GET    /api/v1/sessions
GET    /api/v1/sessions/{session_id}
POST   /api/v1/sessions/{session_id}/start
POST   /api/v1/sessions/{session_id}/finish
POST   /api/v1/sessions/{session_id}/snapshots
GET    /api/v1/sessions/{session_id}/attendance

GET    /api/v1/stats/summary
GET    /api/v1/stats/teachers/{teacher_id}
GET    /api/v1/stats/disciplines/{discipline_id}
GET    /api/v1/stats/groups/{group_id}
GET    /api/v1/stats/groups/{group_id}/timeline
```

Recognition:

```text
GET  /health
GET  /streams
POST /streams/start
POST /streams/stop
POST /detect
```

## Модель данных

| Сущность | Назначение |
|---|---|
| `Group` | Учебная группа, курс, факультет и численность |
| `Teacher` | Преподаватель |
| `Discipline` | Дисциплина |
| `Classroom` | Аудитория, вместимость и адрес камеры |
| `Schedule` | Плановое занятие: группа, время, аудитория, неделя и тип занятия |
| `Session` | Конкретное занятие на дату |
| `DetectionSnapshot` | Сырой замер количества людей на кадре |
| `AttendanceRecord` | Агрегированная посещаемость по завершённому занятию |

## Статус

- backend API, модели и миграции реализованы;
- импорт расписания из Excel реализован;
- расчёт белой и зелёной недели реализован;
- recognition-сервис умеет работать с потоком и разовыми изображениями;
- frontend содержит дашборд, расписание и список занятий;
- контейнерная сборка описана через Docker Compose.

## Команда

| Участник | Зона ответственности |
|---|---|
| Балалыкин М. Г. | teamlead, backend |
| Матвейчев И. В. | recognition, backend |
| Плешкова Д. С. | database, backend |
| Попова Ю. А. | frontend |

Проект выполнен в рамках производственной практики.
