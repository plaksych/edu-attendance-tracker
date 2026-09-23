# Эксплуатация

## Граница готовности

Ветка `production`, исходный SHA `cb34254d63c4d7415a86f6af18ffdf5df23cf651`.
Контейнеры и deployment в этой работе не запускались; commits/push не выполнялись.
Compose проверяется через `docker compose config`, а не через запуск стенда.
Это не доказательство совместимости read-only/tmpfs, TLS, IAM или восстановления.

Нативный PostgreSQL 14.20 на `127.0.0.1:55439`, БД/роль `attendance_test`: проверка
`scripts/check_integration.py --existing-db --database-only` действительно прошла:
БД на текущем Alembic head, `alembic check` без новых операций. Скрипт не применял миграции.
Отдельно `scripts/check_roles.py` действительно создал временную БД/роли, применил миграции
под migration owner, дважды применил grants и проверил отказ backend UPDATE/DELETE/TRUNCATE
audit и доступа workers к users/sessions/audit. Временная БД и роли удалены после теста.
Этот native результат не выдаётся за PostgreSQL 16 CI evidence.
Владелец backend отдельно сообщил о 22 успешных PostgreSQL-тестах и сохранении legacy snapshot
при `0005 -> head`; это отдельное свидетельство, не повторный запуск из operational slice.
Нативного MinIO нет: сообщённый официальный URL дистрибутива 2025 вернул HTTP 410.
Полный S3/backup/restore drill остаётся `blocked`, даже если отдельный PostgreSQL restore пройдёт.

## Среда и команды

Нужны Python 3.12, Node 24.3.0, npm с lockfile, FFmpeg, PostgreSQL client 16,
для Compose только Docker Compose >=2.24 (локально проверен renderer 5.0.2).
Backup/restore работают нативно через Python, `pg_dump`, `pg_restore` и установленный `restic`;
версия restic и PostgreSQL client записываются в протоколе drill. Docker им не нужен.
Пример настройки: [.env.example](../.env.example), [операторский env](../scripts/ops/backup.env.example).
Секреты только в файлах вне git с правами 0600; не в command line и не в CI artifacts.

```sh
make bootstrap             # отдельные .venv/backend, capture, recognition, ops; npm ci
make verify                # недеструктивный агрегат; возвращает ненулевой код при любом провале
make ops-check             # effective Compose, policy negatives, reset/restore guards
make audit                 # pinned advisory scans; НИКАКИХ auto-fix/upgrade
make lint
make typecheck
make test
make build                 # production frontend + отсутствие fixtures/reset/secrets
make test-e2e              # npm run test:e2e; реальные браузеры
make test-visual           # subset e2e с screenshot artifacts; не утверждает pixel regression
make diagrams              # существующий pinned docs renderer; новые рендеры требуют review
make diagrams-check        # проверка existing render/source hashes, без обновления baseline
make docs-check
```

Локальный task runner использует `<SERVICE>_PYTHON` (`BACKEND_PYTHON`, `CAPTURE_PYTHON`,
`RECOGNITION_PYTHON`, `OPS_PYTHON`), затем `.venv/<service>/bin/python`, затем существующий
`.venv/bin/python`. Последний fallback запрещён в CI. Каждый `app` импортируется отдельным
процессом из своего каталога; общий `PYTHONPATH` не нужен. CI создаёт отдельные environments.
Linux recognition lock рассчитан на amd64 CPU; отдельный lock есть для macOS arm64 >=14.
Locks используют torch 2.13.0 / torchvision 0.28.0: native image/video CPU smoke с запретом
сети прошёл; Linux runtime ещё не проверен. Evidence и границы advisory scan описаны в
[THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md).
Другие архитектуры требуют отдельного разрешения зависимостей и smoke, а не обещания поддержки.
PowerShell без Make: `python scripts/ops/tasks.py verify`; остальные task names совпадают.

```sh
TEST_DATABASE_URL=postgresql://attendance_test@127.0.0.1:55439/attendance_test \
  .venv/bin/python scripts/check_integration.py --existing-db --database-only
TEST_DATABASE_URL=postgresql://attendance_test@127.0.0.1:55439/attendance_test make test-integration
MODEL_PATH=/secure/models/model.pt make test-inference
```

`TEST_DATABASE_URL` имеет приоритет над `QUEUE_TEST_DSN`. `test-integration` передаёт также
`BACKEND_TEST_DSN`/`RESTORE_TEST_DSN`, запускает все backend pytest tests, включая доступ,
workflows, populated migrations и DB restore. Требуется CREATEDB для временных restore DBs.
`make test-roles` проверяет DB role boundaries в новой временной БД.
Проверка существующей БД не делает
seed/migrate; `--database-only` явно печатает S3 `NOT_RUN`. Создание тестовых схем в queue tests
разрешено только в отдельной test-БД. Полная CI-проверка требует пустой `attendance_test`,
`CI_DISPOSABLE=true`, `CI_S3_ENDPOINT` и тестовых ключей из `docker-compose.test.yml`.

## Production Compose

Всегда `-f docker-compose.yml`, без implicit override. Единственная публикация: TLS gateway
`127.0.0.1:8443` по умолчанию. Изменение bind/port требует согласованной сетевой схемы.
PostgreSQL, MinIO console, API, frontend и workers не публикуют порты. Private network internal;
камера требует `--profile camera` и отдельного firewall egress allowlist.
Upload-only включает `recognition-worker`, `scheduler`, `maintenance` без camera profile.

Обязательные настройки: `ENVIRONMENT=production`, уникальный `COMPOSE_PROJECT_NAME`, совпадающие
DB/bucket namespace, четыре DB DSN/роли, отдельные root/init/runtime S3 accounts, Fernet key,
APP_HOST/MEDIA_HOST, TLS files, MODEL_FILE/SHA256, reviewed image digests, SEMESTER_START/END.
Пример семестра: `2026-09-01` .. `2027-01-31`; конец обязателен, не раньше начала.
Compose принудительно задаёт `SESSION_SECURE=true`, `MINIO_PUBLIC_SECURE=true`,
`SCHEDULER_ENABLED=false`, presign TTL=120 секунд. Внутренний S3 HTTP допустим только в закрытой
docker-сети; внешний hostname HTTPS подписывается отдельно, без переписывания URL.
`MEASUREMENT_INPUT_GRACE_SECONDS=3600` (допустимо 0..604800) задаёт окно для позднего file input
после завершения занятия; общее значение передаётся API, scheduler и maintenance.

`BACKEND_IMAGE` используется также для `python -m app.scheduler`, `python -m app.maintenance`
и одноразового `migrate`. API не запускает scheduler или bucket init. `migrate`/`storage-init`
имеют profile `ops`, не являются зависимостью API. Две реплики scheduler требуют проверки
лидерства PostgreSQL; наличие двух контейнеров само по себе её не доказывает.

```sh
make prod-config-check ENV_FILE=/secure/production.env
make preflight ENV_FILE=/secure/production.env
```

Production env не содержит образов по умолчанию: владелец вносит проверенные registry digests.
Fixture digests `example.invalid/never-pull` существуют только в self-test и не являются образами.
В Dockerfiles закреплены реально разрешённые registry manifest digests; это фиксирует байты,
но НЕ подтверждает отсутствие CVE или пригодность для release. OS packages проверяются по
итоговому container SBOM; apt repositories пока не snapshot-pinned.
PostgreSQL image должен соответствовать Debian UID 999 и PGDATA; MinIO volume должен быть
подготовлен с UID 1000, TLS key читаем UID 101, model читаем UID 10001. Проверить это до старта.

## Dev и demo

Dev: `attendance-dev-<name>`, demo: `attendance-demo-<name>`; DB name заменяет `-` на `_`,
bucket равен project name. Другие credentials, hostnames, volumes и identity UUID обязательны.
Dev overlay публикует только loopback 5432/9000/8000/3000; demo использует TLS gateway без bypass.
Для обоих режимов заранее нужны digest images, локальные сертификаты и scoped accounts.

```sh
make dev ENV_FILE=/secure/dev.env
make demo-static
make demo-full-up ENV_FILE=/secure/demo.env
make demo-full-down ENV_FILE=/secure/demo.env  # НЕ удаляет volumes
make demo-reset OPS_ENV_FILE=/secure/demo-ops.env
```

`demo-reset` требует заранее созданного DB marker, остановленных клиентов и ввода точного имени
цели. Нет HTTP reset, нет `down -v`. Он очищает только demo bucket и public schema, сохраняет
`ops_control`; после reset повторить миграции, grants, seed и provisioning пользователей.
Seed и account bootstrap принадлежат backend, operational code не подменяет их фикстурами.
После reset сначала `role-init` для новой пустой public schema, затем migrate и role-grants.

## Probes и диагностика

Liveness: `/health` только процесс. Readiness: `/health/ready` проверяет PostgreSQL и bucket.
Нельзя рестартовать API только из-за временной недоступности БД. `smoke` проверяет TLS,
frontend, readiness и отказ анонимному API; login/upload/inference остаются отдельным сценарием.
Системные heartbeat scheduler/maintenance/worker и freshness метрик нужно проверять по реальному
runtime; Compose не рисует фиктивный healthy для этих процессов.

Ресурсы: API 1 CPU/512 MiB, worker 2 CPU/3 GiB, tmpfs worker 512 MiB, pids=128,
upload 100 MiB/120 секунд, внутренний лимит worker 2304 MiB. Это стартовые ограничения, не capacity SLA.
JSON logs ограничены 3 x 10 MiB. Gateway не пишет URL access logs, чтобы не раскрывать подписи.
CSP допускает WASM и blob workers; `style-src unsafe-inline` пока нужен текущим chart/styles,
но не разрешены произвольные script sources. Проверка CSP/Range/CORS/cookie в браузере ещё нужна.

Runbooks: [release/rollback](runbooks/release.md), [backup/restore](runbooks/backup-restore.md),
[очередь и S3](runbooks/queue-storage.md). Лицензии и результаты audit:
[THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md).
