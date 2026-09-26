# Допуск кандидата

Исходный снимок: `cb34254d63c4d7415a86f6af18ffdf5df23cf651`.
Рабочая ветка: `production`. Автоматический merge и deployment не выполняются.
Матрица относится к текущему кандидату, а не к ранее опубликованному сайту.

**Production не допущен.** Сквозной сценарий и восстановление прошли на тестовом
Linux runner, но не заменяют приёмку инфраструктуры вуза и лицензионное решение.
Обновлено 25.09.2026: программный срез `6db50e2`,
[CI 36135748298](https://github.com/plaksych/edu-attendance-tracker/actions/runs/36135748298):
12 jobs прошли, три серверных образа остановлены security/license gate.
[PR #6](https://github.com/plaksych/edu-attendance-tracker/pull/6) открыт без auto-merge.

## Матрица

`passed` означает пройденную указанную проверку, а не отсутствие любых дефектов.
`blocked` требует внешнего стенда или решения владельца. `not_run` означает,
что доказательства пока нет. Неполный критерий не считается закрытым.

| ID | Реализация и проверка | Статус | Evidence / оставшаяся граница |
| --- | --- | --- | --- |
| GIT-01 | Отдельная `production`, тематические коммиты, main не менялся | passed | [PR #6](https://github.com/plaksych/edu-attendance-tracker/pull/6), без merge/deploy; remote main остался на исходном SHA |
| BOOT-01 | Чистый checkout, hash locks, FastAPI/OpenAPI и сборка | passed | На `d43e364`: чистые backend+ops venv, 76 API/DB tests, 46 OpenAPI paths, `npm ci` и production build; не полный серверный стенд |
| AUTH-01 | Cookie session, CSRF, роли, scope преподавателя, отзыв; запреты list/detail/media/CSV | passed | `backend/tests/test_access.py`, `test_media_access.py`, реальные запросы TestClient и PostgreSQL |
| SEC-01 | Декодирование файлов, bounded XLSX, FFprobe, RTSP CIDR, отдельный inference-процесс | blocked | Реальный Linux seccomp запрещает IPv4/IPv6 и наследуется дочерним процессом; проверены rlimits. Сеть камер и контейнерные ограничения целевого сервера ещё не проверены |
| SEC-02 | RTSP не возвращается API; production bundle исключает fixture; секреты вынесены | passed | Schema/bundle проверки, Gitleaks и Trivy source scan прошли в указанном CI; это не доказательство отсутствия любых утечек |
| DATA-01 | Preview/confirm, конфликты, календарь, историческая численность, миграция 0005 | passed | `backend/tests/test_workflows.py`, `test_calculations.py`, `test_migrations.py` |
| DATA-02 | Upload связан с занятием/замером; новые jobs для retry, отдельные корректировки | passed | `full-stack`: настоящий HTTP, PNG/MP4, YOLO, S3, два замера, CSV, retry и replay; закрытые source refs и CSV не изменились |
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
| OPS-02 | Совместный backup/restore БД и S3 в отдельный namespace | passed | PostgreSQL 16, restic/S3, checksum объектов и CSV через восстановленный API в CI; off-host backup и процедуры целевого сервера требуют отдельной приёмки |
| CI-01 | Unit/integration/browser/security/container workflows, ручной promotion | failed | [Run 36135748298](https://github.com/plaksych/edu-attendance-tracker/actions/runs/36135748298): 12 jobs passed, 3 server container jobs failed на CVE/license gates; обходов нет |
| DOC-01 | D01–D14, ERD fragments, pinned renderer, SVG/PNG | passed | [Галерея](diagrams/rendered/index.html), [manifest](diagrams/rendered/manifest.json); 18 схем, визуальная проверка D02/D06 и UI |
| DOC-02 | Quickstart, API, режимы, runbooks, links check | not_run | Clean-checkout install/build и локальные ссылки проверены; полный серверный quickstart с S3/TLS ещё не проверен |
| REL-01 | Notices, dependency audit, release/rollback и ручные approvals | blocked | [Third-party inventory](../THIRD_PARTY_NOTICES.md); требуется решение по модели/AGPL и поддержке storage |

## Проверено 25 Сентября

- `full-stack` выполняет реальный вход с cookie/CSRF и загрузку изображения/видео
  через HTTP. Настоящий recognition worker забирает задания из PostgreSQL 16,
  выполняет YOLO и публикует JPEG в закрытое S3. Проверены signed links и запрет
  анонимного чтения, привязка к двум замерам занятия и CSV.
- Повтор создаёт новый результат; replay не создаёт третью попытку. Источники
  закрытых замеров и CSV остаются прежними.
- `pg_dump` и restic сохраняют БД с объектами S3; восстановление идёт в новую БД
  и новый bucket. Восстановленный API возвращает тот же CSV и байты медиа.
  Это тестовый S3 на том же CI runner, не проверка off-host инфраструктуры вуза.
- Рабочий размер входа модели **960**, `MEMORY_LIMIT_MB=2304`, один поток.
  В рабочий child, а не только smoke harness, добавлен общий лимит потоков
  PyTorch/OpenCV/Ultralytics. Проверка Linux seccomp и resource limits прошла.
- Официальный `.pt` скачан отдельно, SHA-256 совпал с manifest. Это подтверждает
  происхождение байтов, не разрешает их распространение и не доказывает точность.
- Недоступный registry MinIO заменён только в CI на checksum-pinned source build.
  Корневой Docker context ограничен исходниками и lockfiles; локальные окружения,
  отчёты, настройки и медиа в него не входят.
- Новая находка `CVE-2026-93990` в frontend `libexpat` устранена обновлением Alpine:
  frontend container scan и license gate прошли, high/critical findings: **0**.
- Серверные образы: **213 package findings**, **47 уникальных CVE** на образ,
  один Critical `CVE-2026-6653` в libxml2. Сканер не указывает исправленных версий.
  Debian также [отмечает уязвимой стабильную версию](https://security-tracker.debian.org/tracker/CVE-2026-6653).
  `liblzma5: none`, Ultralytics/THOP AGPL остаются на проверке владельца.

Evidence: [сквозной прогон](../scripts/ops/evidence/full-stack-20260925.json),
[сводка контейнеров](../scripts/ops/evidence/container-scan-20260925.json).
Первый push-прогон сквозного теста остановился на HTTP 500 скачивания официальных
весов. Повторный [push-прогон, attempt 2](https://github.com/plaksych/edu-attendance-tracker/actions/runs/36135743956)
успешно выполнил full-stack на точном HEAD `6db50e2`; его JSON сохранён выше.
Из публикуемого JSON удалены внутренние `claim_token` временной очереди;
измерения и результаты проверок не изменены. Экспорт новых отчётов также
убирает эти поля. Gitleaks проверяет остальную историю без исключений:
в `.gitleaksignore` указаны только две строки старого коммита `f885365`
с UUID уже удалённой тестовой БД, которые сканер принял за API-ключи.
PR-прогон тоже прошёл и относится к техническому merge-tree `9d7ac98`,
не к слиянию в main. Общий CI остаётся красным из-за трёх серверных образов.

## Проверки 23 Сентября

- macOS arm64, Python 3.12.13. Временный PostgreSQL **14.20**, не production 16.
  Только синтетические данные, отдельные схемы/БД, loopback port 55439,
  `shared_buffers=32MB`. Тяжёлые контейнеры не запускались.
- Итоговый `make verify` с настоящими PostgreSQL DSN прошёл: backend **78**,
  capture **9**, recognition **27**, frontend **80** тестов; пропусков не было.
  Включены regression tests времени fixture, исторической численности,
  отдельных account/peer login budgets и подмены forwarded headers.
- Проверены lint, TypeScript, 10 критичных Python-модулей через mypy,
  OpenAPI drift для 46 маршрутов, production build и исключение fixture из bundle.
- Пройдены 35 отрицательных Compose-проверок, 20 ops guards и 15 Playwright
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
  runtime/model. Настоящий Nginx smoke, сборка и сканирование frontend-контейнера
  прошли на GitHub runner; локально контейнеры не запускались.

## Предыдущий CI

[Проверенный run](https://github.com/plaksych/edu-attendance-tracker/actions/runs/35916443483)
относится к head `18e5b1777c2da9574b79c37af35f8a3176b1a343` и PR merge-tree
`65555bd351f1d0b2e58b57bc85214cf80336b716`. Merge-tree создан GitHub только для
проверки; main не изменён. На Ubuntu 24.04/Python 3.12.14 прошли:

- backend/capture/recognition Python jobs и все три PostgreSQL/S3 integration jobs;
- frontend, browser E2E, operations, diagrams, source security scan;
- сборка, HTTP smoke, CVE/license scan frontend-образа.

Три серверных образа собираются, но их выпуск остановлен CVE/license gates.
После перехода с Bookworm на закреплённый Trixie и установки доступных обновлений
backend/capture/recognition имеют по 208 High/Critical package findings,
44 уникальных CVE.
Один Critical: `libxml2 / CVE-2026-6653`; Trivy не указывает исправленную версию
для этих находок в данном дистрибутиве. Счётчик packages не равен числу независимых
уязвимостей, а scanner severity не доказывает достижимость конкретного exploit.
Отключать gate или добавлять общее исключение нельзя: нужен исправленный runtime
либо отдельный проверяемый и утверждённый разбор применимости находок.

License gate также требует разбора `liblzma5: none` и AGPL-3.0-or-later у
`ultralytics` / `ultralytics-thop` в recognition.
`none` здесь означает неполную классификацию сканера, а не установленный запрет
использования. Владелец должен подтвердить условия, включая Ultralytics/веса.
Постоянная [сводка сканирования](../scripts/ops/evidence/container-scan-summary.json)
содержит SHA-256 отчётов, image ID и список CVE. Полные
`vulnerabilities.json`, `licenses.json` и SBOM сохранены в artifacts
`container-inspection-*` указанного run; срок хранения 14 дней. Временные ошибки
первого CI (Node types, CPU index, окружение live E2E, шрифты и installer Trivy)
исправлены, повторные соответствующие jobs прошли.

Команда прогона из корня репозитория (DSN только изолированной тестовой БД):

```sh
RECOGNITION_PYTHON="$PWD/.venv/recognition-candidate/bin/python" \
BACKEND_TEST_DSN="$TEST_DATABASE_URL" QUEUE_TEST_DSN="$TEST_DATABASE_URL" \
RESTORE_TEST_DSN="$TEST_DATABASE_URL" make verify
```

В чистом checkout после `make bootstrap` переопределять `RECOGNITION_PYTHON`
не требуется. Настоящие inference smokes запускаются отдельно, по командам
из [testing.md](testing.md); обычные unit tests не подменяют эти прогоны.

## Осталось До Выпуска

1. Закрыть CVE/license gates серверных образов, затем поднять изолированный
   staging по [runbook выпуска](runbooks/release.md):
   согласованные image digests, TLS, DB roles, IAM и модель, без production данных.
2. Повторить проверенный в CI upload→claim→inference→S3→measurement→CSV на целевом
   стенде с его scoped IAM, runtime roles, TLS и реальными квотами.
3. Настроить внешнее хранилище копий и выполнить [backup/restore](runbooks/backup-restore.md)
   на целевой инфраструктуре; восстановить ключи и применить DB grants.
4. Проверить реальный запрет egress/RTSP вне allowlist и resource limits на Linux.
5. Разметить разрешённые изображения/видео аудиторий отдельно от tuning-набора;
   зафиксировать MAE, распределение ошибки, пропуски и ложные обнаружения.
6. Утвердить лицензии, сроки хранения/доступа к материалам, эксплуатационного
   владельца и repository protections. Пройти usability/screen-reader приёмку.

Камеры остаются опциональным профилем. Отсутствие камер не блокирует обработку
загруженных файлов, но не позволяет заявлять проверенный RTSP на оборудовании вуза.
