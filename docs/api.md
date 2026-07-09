# API

Backend предоставляет REST API с интерактивными схемами запросов и ответов.
После запуска Docker Compose используйте [Swagger UI](http://localhost:8000/docs)
или [ReDoc](http://localhost:8000/redoc).

[К оглавлению](../README.md) · [Распознавание](recognition.md) · [Модель данных](data-model.md)

## Базовые адреса

| Среда | Адрес |
| --- | --- |
| Проверка доступности | `GET /health` |
| Рабочий API | `/api/v1` |
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |

## Группы endpoint-ов

| Назначение | Основные маршруты |
| --- | --- |
| Справочники | `GET/POST /groups`, `/teachers`, `/disciplines`, `/classrooms` |
| Камеры | `GET/POST/PATCH/DELETE /cameras`, `PUT /classrooms/{id}/cameras` |
| Расписание | `GET/POST/DELETE /schedule`, `POST /schedule/import`, `GET /schedule/week-type` |
| Занятия | `GET /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/cancel` |
| Медиа занятия | `GET /captures/{id}/media` |
| Статистика | `GET /stats/summary`, `/stats/groups/{id}`, `/stats/teachers/{id}`, `/stats/disciplines/{id}` |
| Распознавание файлов | `POST /recognition/uploads`, `GET /recognition/uploads` |

## Распознавание файлов

### Создать задание

```bash
curl -X POST http://localhost:8000/api/v1/recognition/uploads \
  -F "file=@auditorium.jpg" \
  -F "confidence_threshold=0.35"
```

Для видео дополнительно укажите частоту выборки кадров:

```bash
curl -X POST http://localhost:8000/api/v1/recognition/uploads \
  -F "file=@lesson.mp4" \
  -F "sample_rate_fps=2" \
  -F "confidence_threshold=0.30"
```

Успешный запрос возвращает `202 Accepted`: файл уже сохранён, а задание ожидает
worker или обрабатывается. Поддерживаются `MP4`, `MOV`, `AVI`, `WebM`, `JPG`,
`PNG` и `WebP`; максимальный размер задаёт `RECOGNITION_UPLOAD_MAX_SIZE_MB`.

### Проверить статус

```bash
curl http://localhost:8000/api/v1/recognition/uploads/42
curl http://localhost:8000/api/v1/recognition/uploads/42/media
```

Первый endpoint возвращает состояние очереди и метрики результата. Второй
выдаёт краткоживущие ссылки на исходный файл и размеченный кадр, когда они
доступны.

## Семантика ошибок

| Код | Значение |
| --- | --- |
| `404` | запрошенная сущность или файл не найдены |
| `409` | операция нарушает правило данных, например повторяющееся имя камеры |
| `413` | загружаемый файл превышает лимит |
| `422` | файл имеет неподдерживаемый тип или параметры запроса не прошли валидацию |
| `503` | объектное хранилище временно недоступно |

## Контракт медиа

API не раскрывает постоянный доступ к MinIO. Endpoint медиа возвращает
presigned URL и время его действия в поле `expires_in_seconds`. После
истечения срока хранения ссылка заменяется текстом причины недоступности.
