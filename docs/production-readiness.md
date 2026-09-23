# Допуск кандидата

Исходный снимок: `cb34254d63c4d7415a86f6af18ffdf5df23cf651`.
Рабочая ветка: `production`. Автоматический merge и deployment не выполняются.
Матрица относится к текущему кандидату, а не к ранее опубликованному сайту.

**Production не допущен.** Локальные проверки не заменяют полный restore,
проверку сетевых ограничений Linux и решение владельца по лицензиям весов.
Проверенный программный срез: `0d515eb` (дальнейшие изменения документации
не меняют этот срез). Итоговый SHA и PR указаны в передаче результата.

## Матрица

`passed` означает пройденную указанную проверку, а не отсутствие любых дефектов.
`blocked` требует внешнего стенда или решения владельца. `not_run` означает,
что доказательства пока нет. Неполный критерий не считается закрытым.

| ID | Реализация и проверка | Статус | Evidence / оставшаяся граница |
| --- | --- | --- | --- |
| GIT-01 | Отдельная `production`, тематические коммиты, main не менялся | passed | Коммиты `8aeb509`…`0d515eb`; PR создаётся без merge/deploy |
| BOOT-01 | Чистый checkout, hash locks, FastAPI/OpenAPI и сборка | passed | На `d43e364`: чистые backend+ops venv, 76 API/DB tests, 46 OpenAPI paths, `npm ci` и production build; не полный серверный стенд |
| AUTH-01 | Cookie session, CSRF, роли, scope преподавателя, отзыв; запреты list/detail/media/CSV | passed | `backend/tests/test_access.py`, `test_media_access.py`, реальные запросы TestClient и PostgreSQL |
| SEC-01 | Декодирование файлов, bounded XLSX, FFprobe, RTSP CIDR, отдельный inference-процесс | blocked | Unit/CPU smoke пройдены; Linux sandbox и фактический network egress не проверены |
| SEC-02 | RTSP не возвращается API; production bundle исключает fixture; секреты вынесены | not_run | Локальные schema/bundle проверки пройдены; полный secret scan CI ещё не получен |
| DATA-01 | Preview/confirm, конфликты, календарь, историческая численность, миграция 0005 | passed | `backend/tests/test_workflows.py`, `test_calculations.py`, `test_migrations.py` |
| DATA-02 | Upload связан с занятием/замером; новые jobs для retry, отдельные корректировки | not_run | Транзакционные API тесты пройдены; полный путь API→S3→worker→отчёт ещё не проверен |
| QUEUE-01 | Claim UUID, действующий lease, CAS, immutable object keys, retry | passed | `capture/tests/test_queue_postgres.py`, `recognition/tests/test_queue_postgres.py`; реальные конкурентные соединения |
| QUEUE-02 | Отдельные scheduler/maintenance, advisory leadership, orphan GC без камер | passed | `backend/tests/test_queue_maintenance.py`; PostgreSQL leadership/reconnect и bounded GC unit tests |
| ML-01 | SHA-256 модели, явные параметры, настоящий image/video CPU smoke | passed | [Серверный smoke](../recognition/tests/model-smoke-evidence.json), [браузерный smoke](../frontend/tests/browserRecognition-smoke.json); синтетический отрицательный вход не измеряет качество |
| DEMO-01 | Синтетический seed/clock, переходы, фильтры, экспорт, no-API static mode | passed | `frontend/e2e/interface.spec.ts`, built-demo checks; три браузерных движка |
| DEMO-02 | Dedicated worker, lazy model, cancel/retry/cleanup и локальный экспорт | passed | [Реальный image/video UI smoke](../frontend/tests/browserRecognition-ui-smoke.json): 36 static GET, 0 upload bytes, настоящий WASM |
| DEMO-03 | Изолированные Compose/namespace/DB marker, защищённый reset | not_run | Отрицательные reset tests пройдены; полный demo stack не запускался |
| UI-01 | Рабочий обзор и переход к материалу без обязательного тура | passed | [Desktop](diagrams/rendered/UI-overview-desktop.png), [mobile](diagrams/rendered/UI-overview-mobile.png) |
| UI-02 | Общие tokens, экраны доступа/расписания/распознавания/аналитики/управления | passed | Playwright desktop/mobile screenshots, визуальное ревью |
| UI-03 | Empty/error/loading, retry, expired auth, недоступное медиа | passed | Component/E2E tests; server failures в UI тестируются явными mocks |
| UI-04 | Экспертный walkthrough | not_run | Приёмка независимым пользователем не проводилась |
| UI-05 | 320–1920 px, Chromium/Firefox/WebKit, axe, keyboard/focus | not_run | Автотесты пройдены; реальный screen reader/устройства и zoom ещё не проверены полностью |
| SHOW-01 | Показ использует те же данные и экраны, fixture явно помечен | passed | Последовательность, Escape, возврат фильтров и fullscreen refusal проверены; [снимки](design-system.md#снимки-интерфейса) |
| PERF-01 | Lazy маршруты/model/chart, worker вне UI thread, bounded media | passed | Build bundle report и actual CPU/browser timings; это lab observations, не field Web Vitals |
| OPS-01 | Production Compose fail-closed, разные DB роли, private storage, ручной выпуск | not_run | Render policy tests пройдены; effective deployment/TLS/IAM на стенде не проверены |
| OPS-02 | Backup/restore tooling и отдельная цель восстановления | blocked | PostgreSQL-only pg_dump/restore пройден; объекты S3 и полный восстановленный стенд не проверены |
| CI-01 | Unit/integration/browser/security/container workflows, ручной promotion | not_run | Локальные результаты есть; удалённый CI run ещё не получен |
| DOC-01 | D01–D14, ERD fragments, pinned renderer, SVG/PNG | passed | [Галерея](diagrams/rendered/index.html), [manifest](diagrams/rendered/manifest.json); 18 схем, визуальная проверка D02/D06 и UI |
| DOC-02 | Quickstart, API, режимы, runbooks, links check | not_run | Clean-checkout install/build и локальные ссылки проверены; полный серверный quickstart с S3/TLS ещё не проверен |
| REL-01 | Notices, dependency audit, release/rollback и ручные approvals | blocked | [Third-party inventory](../THIRD_PARTY_NOTICES.md); требуется решение по модели/AGPL и поддержке storage |

## Выполненная среда

- macOS arm64, Python 3.12.13. Временный PostgreSQL **14.20**, не production 16.
  Только синтетические данные, отдельные схемы/БД, loopback port 55439,
  `shared_buffers=32MB`. Тяжёлые контейнеры не запускались.
- Итоговый `make verify` с настоящими PostgreSQL DSN прошёл: backend **78**,
  capture **9**, recognition **27**, frontend **80** тестов; пропусков не было.
  Включены regression tests времени fixture, исторической численности,
  отдельных account/peer login budgets и подмены forwarded headers.
- Проверены lint, TypeScript, 10 критичных Python-модулей через mypy,
  OpenAPI drift для 46 маршрутов, production build и исключение fixture из bundle.
- Пройдены 35 отрицательных Compose-проверок, 18 ops guards и 15 Playwright
  сценариев в трёх движках. Настоящие role/seed проверки создают отдельные БД.
- Dependency audit закреплённых пакетов: 0 известных advisories. Для CPU wheels
  отдельно проверены upstream версии Torch 2.13.0 / torchvision 0.28.0;
  это не сканирование ОС внутри контейнеров и не юридическое заключение.
- Browser worker: настоящий vendored WASM и модель под subpath, проверенный hash,
  отмена и повтор; trace допускает только static GET, 0 upload bytes.
- CPU pipeline: изображение и видео с синтетической геометрией, один поток,
  сеть запрещена sandbox-профилем macOS. Это не проверка Linux seccomp/S3/БД.
- Первый `make verify` обнаружил dereference symlink Python venv в task runner.
  Ошибка исправлена, закреплена regression test; повторный полный verify прошёл.
- Чистый checkout обнаружил отсутствующую явную зависимость `@types/node`.
  Она добавлена вместе с `types: ["node"]` в отдельную конфигурацию Vite;
  чужие локальные node_modules больше не являются условием сборки.
- Повторный clean-checkout `npm ci`/build прошёл; отдельный чистый Python venv
  установлен из hash locks, 76 backend tests и OpenAPI drift прошли. Два
  предупреждения deprecation Starlette/httpx и AnyIO не скрывались.
- Nginx явно задаёт MIME для `.mjs`/`.wasm` и отдаёт 404 вместо SPA на отсутствующий
  runtime/model. Локально проверен конфигурационный regression test; настоящий
  Nginx smoke добавлен в container CI и локально без контейнеров не выполнялся.

Команда прогона из корня репозитория (DSN только изолированной тестовой БД):

```sh
RECOGNITION_PYTHON="$PWD/.venv/recognition-candidate/bin/python" \
BACKEND_TEST_DSN="$TEST_DATABASE_URL" QUEUE_TEST_DSN="$TEST_DATABASE_URL" \
RESTORE_TEST_DSN="$TEST_DATABASE_URL" make verify
```

В чистом checkout после `make bootstrap` переопределять `RECOGNITION_PYTHON`
не требуется. Настоящие inference smokes запускаются отдельно, по командам
из [testing.md](testing.md); обычные unit tests не подменяют эти прогоны.

## Проверки, Требующие Стенда

1. Поднять изолированный staging по [runbook выпуска](runbooks/release.md):
   согласованные image digests, TLS, DB roles, IAM и модель, без production данных.
2. Проверить полный upload→claim→inference→S3→measurement→CSV и повтор с потерей lease.
3. Выполнить [полный backup/restore](runbooks/backup-restore.md) БД и S3 в новый
   namespace, проверить число записей, checksum объектов и чтение через API.
4. Проверить реальный запрет egress/RTSP вне allowlist и resource limits на Linux.
5. Разметить разрешённые изображения/видео аудиторий отдельно от tuning-набора;
   зафиксировать MAE, распределение ошибки, пропуски и ложные обнаружения.
6. Утвердить лицензии, сроки хранения/доступа к материалам, эксплуатационного
   владельца и repository protections. Пройти usability/screen-reader приёмку.

Камеры остаются опциональным профилем. Отсутствие камер не блокирует обработку
загруженных файлов, но не позволяет заявлять проверенный RTSP на оборудовании вуза.
