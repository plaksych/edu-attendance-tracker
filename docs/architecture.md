# Архитектура

Система разделена на четыре независимых роли: интерфейс, backend с планировщиком,
запись видеопотока и обработка роликов. PostgreSQL хранит предметные данные и
координирует очереди, MinIO хранит медиафайлы.

[К оглавлению](../README.md) · [Модель данных](data-model.md) · [Эксплуатация](operations.md) · [API](api.md)

## Карта компонентов

```mermaid
flowchart LR
    User["Пользователь"] -->|"HTTPS"| Web["Frontend\nReact + TypeScript"]
    Web -->|"REST /api/v1"| Backend

    subgraph App["Контур приложений"]
        Backend["Backend\nFastAPI :8000"]
        Scheduler["Measurement Scheduler\nинтервал 30 с"]
        Capture["Capture manager\nFFmpeg"]
        Recognition["Recognition worker\nYOLO"]
    end

    Backend --- Scheduler
    Scheduler -->|"занятия, замеры, задания"| DB[("PostgreSQL 16")]
    Backend <-->|"справочники, занятия, статистика"| DB

    Files["Видео и изображения"] -->|"POST /recognition/uploads"| Backend
    Backend -->|"upload + recognition job"| DB
    Backend -->|"исходный файл"| Storage

    Cameras["IP-камеры"] -->|"RTSP"| Capture
    Capture <-->|"claim, lease, status"| DB
    Capture -->|"original.mp4"| Storage[("MinIO")]

    Recognition <-->|"claim, heartbeat, result"| DB
    Recognition -->|"GET original.mp4"| Storage
    Recognition -->|"PUT annotated.jpg"| Storage

    Backend -->|"presigned URL"| Storage
    Web -->|"временная ссылка"| Storage
```

### Границы ответственности

| Компонент | Ответственность | Масштабирование |
| --- | --- | --- |
| `frontend` | визуализация, формы и запросы к REST | статическая сборка или один Nginx-контейнер |
| `backend` | API, импорт, scheduler, агрегация, выдача временных ссылок | обычно один экземпляр scheduler; API можно отделить при дальнейшем развитии |
| `capture-manager` | запись RTSP, загрузка исходного ролика | по сетевым зонам камер через `CAPTURE_GROUP` |
| `recognition-worker` | обработка загруженных файлов и роликов камер, загрузка размеченного кадра | независимое горизонтальное масштабирование |
| PostgreSQL | данные вуза, состояния заданий, lease и результаты | резервное копирование обязательно |
| MinIO | исходные ролики и размеченные кадры | жизненный цикл объектов и резервное копирование |

## Поток одного занятия

```mermaid
sequenceDiagram
    autonumber
    participant S as Scheduler
    participant DB as PostgreSQL
    participant C as Capture manager
    participant M as MinIO
    participant R as Recognition worker
    participant B as Backend
    participant F as Frontend

    S->>DB: Создать session на горизонте 14 дней
    S->>DB: Создать два measurement и camera_capture
    C->>DB: Атомарно claim ближайших camera_capture
    C->>C: Записать RTSP в MP4
    C->>M: Загрузить original.mp4
    C->>DB: Завершить capture и создать recognition_job
    R->>DB: Claim recognition_job и продлевать heartbeat
    R->>M: Скачать original.mp4
    R->>R: Подсчитать людей на кадрах
    R->>M: Загрузить annotated.jpg
    R->>DB: Сохранить recognition_result
    S->>DB: Агрегировать камеры и два замера
    F->>B: Запросить занятие и статистику
    B->>DB: Получить предметные данные
    B->>M: Подписать временные ссылки
    B-->>F: Занятие, результат и ссылки на медиа
```

## Поток загруженного файла

```mermaid
sequenceDiagram
    autonumber
    participant U as Пользователь
    participant B as Backend API
    participant M as MinIO
    participant DB as PostgreSQL
    participant R as Recognition worker

    U->>B: POST /recognition/uploads с видео или изображением
    B->>B: Проверить расширение, Content-Type и размер
    B->>M: Сохранить исходный файл
    B->>DB: Создать recognition_upload и recognition_job
    B-->>U: 202 Accepted и идентификатор задания
    R->>DB: Claim job и продление lease
    R->>M: Скачать исходный файл
    R->>R: Обработать один кадр или выборку кадров
    R->>M: Сохранить annotated.jpg
    R->>DB: Сохранить метрики и статус completed
    U->>B: GET /recognition/uploads/{id}
    B-->>U: Статус, число людей, метрики
```

Подробности работы с этим сценарием приведены в разделе
[«Распознавание»](recognition.md).

## Как формируется посещаемость

1. Scheduler создаёт `session` из недельного расписания.
2. Для занятия создаются два `measurement`: через 15 минут после начала и за
   15 минут до конца. Смещение настраивается через `MEASUREMENT_OFFSET_MINUTES`.
3. На каждый активный источник аудитории создаётся `camera_capture`.
4. После успешной записи создаётся один `recognition_job`.
5. Результаты камер объединяются в итог замера согласно `aggregation_mode` аудитории.
6. Два завершённых замера образуют `attendance_record`. Если доступен только
   один замер, результат сохраняется со статусом `partial`.

## Режимы объединения камер

| Режим | Когда применять | Итог замера |
| --- | --- | --- |
| `single` | одна камера | результат камеры с наивысшим приоритетом |
| `maximum` | зоны камер пересекаются | максимум значений по камерам |
| `sum` | зоны не пересекаются | сумма значений по камерам |
| `primary_backup` | основная камера с резервной | основная; резервная при низкой уверенности или отсутствии основной |

Не используйте `sum`, если одна и та же зона попадает в несколько камер: это
приведёт к двойному учёту людей.

## Состояния очередей

### Запись с камеры

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> claimed: capture-manager забрал задание
    claimed --> recording: начата запись
    recording --> uploading: ролик готов
    uploading --> completed: MP4 в MinIO
    claimed --> pending: штатная остановка до записи
    claimed --> retry_wait: ошибка
    recording --> retry_wait: ошибка
    uploading --> retry_wait: ошибка
    retry_wait --> pending: пауза закончилась
    claimed --> failed: lease истёк, попытки исчерпаны
    recording --> failed: lease истёк, попытки исчерпаны
    uploading --> failed: lease истёк, попытки исчерпаны
```

### Распознавание

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> processing: worker забрал job
    processing --> completed: результат сохранён
    processing --> retry_wait: ошибка обработки
    retry_wait --> pending: пауза закончилась
    processing --> pending: lease истёк, повтор разрешён
    processing --> failed: попытки исчерпаны
```

Для захвата заданий используются `FOR UPDATE SKIP LOCKED`, `worker_id` и
`lease_until`. Это исключает одновременную обработку одного задания двумя
воркерами и возвращает работу в очередь после сбоя процесса.

## Хранение медиа

```text
original/sessions/{session_id}/measurements/{measurement_id}/cameras/{camera_id}.mp4
annotated/sessions/{session_id}/measurements/{measurement_id}/cameras/{camera_id}.jpg
original/uploads/{random_key}.{ext}
annotated/uploads/{upload_id}.jpg
```

Backend не раскрывает постоянные ссылки на бакет. Он выдаёт временные
presigned URL. По умолчанию исходный ролик хранится 30 дней, размеченный кадр
90 дней; значения настраиваются переменными окружения и lifecycle-политикой
бакета.
