# Схемы D01–D14

Исходники Mermaid находятся в [src](src/), SVG и PNG в [rendered](rendered/).
Открыть все рендеры: [локальная галерея](rendered/index.html).
Палитра: зелёные предметные компоненты, серые связи, светлый фон; смысл задан
подписями, а не только цветом. Пунктир означает опциональную связь либо явно
указанную проверку/процедуру, не автоматически реализованный поток.

| ID | Схема | Статус и опорный код |
| --- | --- | --- |
| [D01](rendered/D01.svg) | Контекст и доверительные границы | [access](../../backend/app/core/access.py), [camera policy](../../capture/app/camera_security.py) |
| [D02](rendered/D02.svg) | Контейнеры и процессы | [Compose](../../docker-compose.yml), [scheduler](../../backend/app/scheduler.py), [maintenance](../../backend/app/maintenance.py) |
| [D03](rendered/D03.svg) | Production deployment | Конфигурация, не подтверждение deployment: [Compose](../../docker-compose.yml) |
| [D04](rendered/D04.svg) | Три режима демо | [client](../../frontend/src/api/client.ts), [staticClient](../../frontend/src/api/staticClient.ts) |
| [D05](rendered/D05.svg) | ERD: учебный контур | [модели](../../backend/app/models/), [миграции](../../backend/alembic/versions/) |
| [D05a](rendered/D05a.svg) | ERD: обработка и история | Upload, jobs, result и corrections; часть D05 |
| [D05b](rendered/D05b.svg) | ERD: доступ и запросы | Users, grants, audit, previews, idempotency; часть D05 |
| [D05c](rendered/D05c.svg) | ERD: независимые таблицы | Calendar exceptions и login throttle, без FK; часть D05 |
| [D05d](rendered/D05d.svg) | ERD: источники финализации | Точные result/job refs, used_for_count и legacy_unknown; часть D05 |
| [D06](rendered/D06.svg) | Sequence загрузки | [API](../../backend/app/api/v1/recognition.py), [worker DB](../../recognition/app/db.py) |
| [D07](rendered/D07.svg) | Sequence занятия | [scheduler service](../../backend/app/services/scheduler.py), [aggregation](../../backend/app/services/aggregation.py) |
| [D08](rendered/D08.svg) | Browser inference | [Worker](../../frontend/src/workers/browserRecognition.worker.ts), [client](../../frontend/src/lib/browserRecognitionClient.ts) |
| [D09](rendered/D09.svg) | Capture state machine | Опциональный camera-профиль: [capture DB](../../capture/app/db.py) |
| [D10](rendered/D10.svg) | Recognition state machine | [worker DB](../../recognition/app/db.py), [recovery](../../backend/app/services/scheduler.py) |
| [D11](rendered/D11.svg) | Доступ и media | [auth](../../backend/app/api/v1/auth.py), [media](../../backend/app/services/media.py) |
| [D12](rendered/D12.svg) | Выпуск и восстановление | Процедура допуска, не выполненный run: [ops](../../scripts/ops/manage.py), [backup/restore](../../scripts/ops/data.py) |
| [D13](rendered/D13.svg) | Путь пользователя | [App](../../frontend/src/App.tsx), [import API](../../backend/app/api/v1/schedule.py); ограничения подписаны |
| [D14](rendered/D14.svg) | Карта интерфейса | [permissions](../../frontend/src/auth/permissions.ts), [Layout](../../frontend/src/components/Layout.tsx) |

## Воспроизведение

Node.js/npm и локальный headless Chromium; Docker не нужен. Renderer закреплён:
Mermaid 11.17.2, Playwright 1.63.0, package-lock фиксирует npm dependency tree.
Из корня repo:

```bash
npm --prefix docs/diagrams ci
npm --prefix docs/diagrams exec -- playwright install chromium
npm --prefix docs/diagrams run render
npm --prefix docs/diagrams run check
npm --prefix docs/diagrams run links
```

После установки сборка всех схем выполняется одной командой `run render`.
`run check` заново парсит Mermaid, сравнивает SVG с сохранённым, проверяет hashes
источников и сохранённых PNG по manifest, повторно проверяет PNG-рендеринг.
При расхождении завершается с ошибкой, не обновляет файлы. Для CI использовать ту же версию Chromium,
ОС и шрифтов, что в evidence, или обновить рендеры в контролируемой среде.
Включение шага в workflow находится вне этого документационного среза; наличие
команды не означает, что удалённый CI выполнен или настроен.

Можно повторно использовать установленные npm-пакеты и browser без установки
в frontend. Все overrides должны указывать абсолютные пути:

```bash
MERMAID_ROOT=/absolute/node_modules/mermaid \
PLAYWRIGHT_ROOT=/absolute/node_modules/playwright \
CHROMIUM_PATH=/absolute/path/to/chromium \
node docs/diagrams/render.mjs
```

Renderer проверяет версии пакетов, не скачивает runtime, не открывает внешний
сайт и не выполняет модель. Browser version, base Git SHA, размеры и SHA256
источников/рендеров записываются в [manifest](rendered/manifest.json).
Это manifest рабочего дерева, не утверждение о committed release revision.
`render-log.txt` хранит вывод локального прогона; промежуточная ошибка исправляется
в исходнике, а не маскируется статичной картинкой.

## Проверка

Проверить каждую SVG/PNG в галерее: кириллицу, окончания стрелок, отсутствие
обрезанных подписей, достаточный масштаб. ERD разделена на пять схем, чтобы
сохранить читаемость. Размеры в manifest помогают обнаружить пустой canvas,
но не заменяют визуальный просмотр. Локальные ссылки проверяет check-links.mjs;
он не проверяет anchors, HTTP-доступность и документы других владельцев.

README screenshots снимаются только с synthetic demo на localhost:

```bash
node docs/diagrams/capture-demo.mjs http://127.0.0.1:4187
```

Предварительно запустить `npm run dev:demo -- --host 127.0.0.1 --port 4187 --strictPort`
из frontend/. CHROMIUM_PATH поддерживается также этой командой. Скрипт проверяет
метку демо, подписи счётчиков занятий, четыре шага показа, отсутствие API-запросов/page errors
и горизонтального overflow страницы;
это не exhaustive UI audit и не запуск модели. Manifest screenshots хранится отдельно.
