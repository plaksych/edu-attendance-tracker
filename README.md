# Educational Attendance Tracker

Информационная система контроля посещаемости занятий студентами на основе компьютерного зрения (YOLOv8).

---

## Содержание

- [Educational Attendance Tracker](#educational-attendance-tracker)
  - [Содержание](#содержание)
  - [Функционал системы](#функционал-системы)
  - [Архитектура](#архитектура)
  - [Стек технологий](#стек-технологий)
        - [Frontend](#frontend)
        - [Backend](#backend)
        - [Recognition](#recognition)
        - [Database](#database)
        - [Infrastructure](#infrastructure)
  - [Структура репозитория](#структура-репозитория)
  - [Модель данных](#модель-данных)
  - [Требования](#требования)
  - [Быстрый старт](#быстрый-старт)
  - [Переменные окружения](#переменные-окружения)
  - [API](#api)
  - [Статус разработки](#статус-разработки)
  - [Команда](#команда)

---

## Функционал системы

- **Распознавание** количества студентов с видеофрагмента / потокового видео с IP-камеры аудитории (количество + confidence), YOLOv8
- **Хранение и обработка данных** — backend на FastAPI + PostgreSQL, хранение фрагментов кадров, на которых производилось считывание
- **Веб-дашборд статистики** — вывод посещаемости по преподавателям / группам / дисциплинам, загрузка расписания из Excel

---

## Архитектура

Три независимых сервиса + база данных, поднимаются через Docker Compose:

```
┌─────────────┐      REST/JSON       ┌──────────────────┐
│  Frontend   │ ───────────────────► │     Backend        │
│  (React/TS) │ ◄─────────────────── │   (FastAPI)         │
└─────────────┘                      │  + PostgreSQL       │
                                      └─────────┬───────────┘
                                                │ REST/HTTP
                                      ┌─────────▼───────────┐
                                      │ Recognition Service   │
                                      │  (FastAPI + YOLOv8)    │
                                      │  обработка потока камер│
                                      └────────────────────────┘
```

**Backend** — единственная точка доступа к БД. Хранит справочники (группы, преподаватели, дисциплины, аудитории), расписание, факты занятий и результаты распознавания. Отдаёт агрегированную статистику для дашборда.

**Recognition Service** — stateless-исполнитель. Не хранит список камер самостоятельно: получает от backend `rtsp_url`/`camera_ip` и `session_id` при старте потока, прогоняет кадры через YOLOv8, отправляет результаты (`person_count`, ссылка на кадр) обратно в backend через REST.

**Frontend** — дашборд, потребляет `/api/v1/stats/*`, позволяет загружать расписание из Excel.

Хранение фрагментов кадров — на первом этапе через общий Docker volume (backend отдаёт файлы как статику), с возможностью перехода на MinIO (S3-совместимое хранилище) при масштабировании.

---

## Стек технологий

##### Frontend
- React
- TypeScript

##### Backend
- Python
- FastAPI
- SQLAlchemy + Alembic (миграции)

##### Recognition
- Python
- YOLOv8 (Ultralytics)
- OpenCV

##### Database
- PostgreSQL
- MinIO — рассматривается для хранения видеофрагментов при масштабировании (на старте — Docker volume)

##### Infrastructure
- Docker / Docker Compose

---

## Структура репозитория

```
smart-attendance/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # роутеры
│   │   ├── models/           # SQLAlchemy-модели
│   │   ├── schemas/           # Pydantic-схемы
│   │   ├── services/           # бизнес-логика
│   │   ├── core/                 # конфигурация, БД
│   │   └── main.py
│   ├── alembic/                     # миграции БД
│   ├── requirements.txt
│   └── Dockerfile
├── recognition/
│   ├── app/
│   │   ├── worker.py         # обработка RTSP-потока + инференс
│   │   ├── model/              # веса YOLOv8
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   └── ...
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Модель данных

| Сущность | Описание |
|---|---|
| `Group` | Учебная группа (название, курс, факультет) |
| `Teacher` | Преподаватель |
| `Discipline` | Дисциплина |
| `Classroom` | Аудитория (номер, `camera_ip`/`rtsp_url`, вместимость) |
| `Schedule` | Расписание (группа, преподаватель, дисциплина, аудитория, день недели, время) |
| `Session` | Конкретное проведённое занятие (дата, статус: scheduled / in_progress / finished) |
| `DetectionSnapshot` | Сырой замер от recognition-service (timestamp, person_count, ссылка на кадр) |
| `AttendanceRecord` | Агрегированная посещаемость по занятию (expected_count, detected_avg, attendance_rate) |

---

## Требования

- Docker, Docker Compose
- Python 3.11+ (для локальной разработки без контейнеров)
- Node.js 18+ (для frontend без контейнеров)
- (опционально) NVIDIA GPU + CUDA / nvidia-container-toolkit — для ускорения инференса YOLOv8. На CPU nano-версия модели также работает приемлемо при интервале снятия кадров ~20-30 сек

---

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repo_url>
cd smart-attendance

# 2. Настроить переменные окружения
cp .env.example .env
# заполнить .env своими значениями

# 3. Запустить все сервисы
docker-compose up -d

# 4. Применить миграции БД (при первом запуске)
docker-compose exec backend alembic upgrade head
```

После запуска:
- Backend API: `http://localhost:8000`
- Swagger-документация: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`

---

## Переменные окружения

| Переменная | Описание |
|---|---|
| `DB_HOST` | Хост PostgreSQL |
| `DB_PORT` | Порт PostgreSQL |
| `DB_NAME` | Имя базы данных |
| `DB_USER` | Пользователь БД |
| `DB_PASSWORD` | Пароль БД |
| `DATABASE_URL` | Полная строка подключения (для backend) |
| `BACKEND_URL` | Адрес backend (используется recognition-service для отправки результатов) |
| `SNAPSHOT_INTERVAL` | Интервал между кадрами для распознавания, сек |

---

## API

Полная спецификация доступна через Swagger UI (`/docs`) после запуска backend. Основные группы эндпоинтов:

```
# Справочники
GET  /api/v1/groups
GET  /api/v1/teachers
GET  /api/v1/disciplines
GET  /api/v1/classrooms

# Расписание и занятия
GET  /api/v1/schedule
GET  /api/v1/sessions/today
POST /api/v1/sessions/{id}/start
POST /api/v1/sessions/{id}/finish

# Приём данных от recognition-service
POST /api/v1/sessions/{id}/snapshots
GET  /api/v1/sessions/{id}/attendance

# Аналитика для дашборда
GET  /api/v1/stats/teachers/{id}
GET  /api/v1/stats/disciplines/{id}
GET  /api/v1/stats/groups/{id}
GET  /api/v1/stats/groups/{id}/timeline
GET  /api/v1/stats/summary
```

---

## Статус разработки

- [x] Проектирование архитектуры и API-контрактов
- [ ] Backend: справочники, расписание, миграции
- [ ] Recognition service: обработка RTSP + инференс YOLOv8
- [ ] Приём и агрегация данных посещаемости
- [ ] Frontend: дашборд статистики
- [ ] Загрузка расписания из Excel
- [ ] Docker Compose: полная сборка всех сервисов

---

## Команда

- Балалыкин М.Г. — teamlead, backend
- Матвейчев И. В. - recognition, backend
- Плешкова Д. С. - database, backend
- Попова Ю. А. - frontend

---

*Проект выполнен в рамках производственной практики.*