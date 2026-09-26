# Проверка

Команды ниже описывают существующие проверки, не утверждают, что весь набор
прошёл на текущем HEAD. Результаты интеграционного прогона, CI и готовности ведёт
владелец [общего readiness](production-readiness.md). Тест со stub-моделью, mock API или SQLite не
доказывает настоящий inference, реальные permissions PostgreSQL или deployment.

Текущий backend закрепляет FastAPI 0.141.1 в requirements.txt. Старый pinned
repro является историческим baseline, а не текущим набором зависимостей.

Для текущей подготовки использован native PostgreSQL 14.20 Homebrew arm64;
это не PostgreSQL 16. Сообщённый интеграционный прогон и отдельный pg_dump/pg_restore
не заменяют целевую проверку PG16 в CI. Restore БД с marker/migration version
не подтверждает восстановление S3, которого в локальном стенде нет.

## Сквозной Прогон На Linux

Job `full-stack` в CI использует отдельные PostgreSQL 16 и S3 на GitHub runner.
На рабочем компьютере контейнеры для этого прогона не требуются.
MinIO собирается из закреплённого исходного кода: прежний публичный образ
больше не доступен без авторизации. Тестовый образ не используется при выпуске.

[check_full_stack.py](../scripts/check_full_stack.py) проверяет настоящий HTTP-вход,
cookie/CSRF, загрузку PNG и MP4, повтор запроса с тем же ключом, очередь,
дочерний YOLO-процесс, контрольный JPEG, закрытое S3 и временные ссылки.
Результаты связываются с двумя замерами занятия и попадают в CSV.
Затем процессы останавливаются, выполняются `pg_dump` и зашифрованный restic backup
с объектами S3. Восстановление идёт в другую БД и другой bucket;
через восстановленный API сверяются CSV и байты исходных/размеченных файлов.

Медиа синтетические: пустая сцена должна дать нулевой результат. Это проверка
интеграции, не показатель точности в аудитории. TLS, production IAM, внешнее
хранилище резервных копий и фактическая инфраструктура вуза сюда не входят.

Артефакт `full-stack-evidence` содержит результат и журналы процессов.
Отдельный [Linux sandbox test](../recognition/tests/check_linux_sandbox.py)
проверяет реальный запрет IPv4/IPv6, наследование ограничения дочерним процессом
и лимиты CPU, адресного пространства, размера файла, дескрипторов и core dump.
Если прогон не завершился, его статус нельзя заменять результатами unit-тестов.

## Python

Рабочая директория корень repo. Использовать отдельные окружения с requirements
своего сервиса; установить pytest/httpx для backend, если они не входят в его
набор. Не смешивать три пакета с одинаковым именем `app` в одном процессе.

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
PYTHONPATH=recognition python -m unittest discover -s recognition/tests -v
PYTHONPATH=capture python -m unittest discover -s capture/tests -v
```

Recognition tests используют numpy/OpenCV и stub-детектор в pipeline unit-тестах;
проверки медиа могут требовать FFmpeg/FFprobe. Неподготовленная среда вызывает
import error или skip, не успешную проверку модели. Не устанавливать тяжёлый
ML/container stack только ради documentation-проверки.

| Набор | Что проверяет / чего не доказывает |
| --- | --- |
| backend test_access | Анонимный отказ, роли, teacher scope, CSRF/logout/revocation, audit; без DSN работает SQLite |
| backend test_workflows | Импорт, retry/history и прикладные сценарии на тестовых данных |
| backend test_migrations | Заполненная 0005 до head, сохранение legacy history, alembic check; требует PostgreSQL |
| backend test_queue_maintenance | Восстановление lease, лидерство/GC; PG-часть отдельно |
| recognition/capture test_queue_guards | Контракт SQL и stub-поведение, не конкуренция настоящей БД |
| recognition/capture test_queue_postgres | Реальный PostgreSQL, уникальные тестовые schemas |
| test_worker_security, test_media_safety, test_camera_security | Ограничения worker/медиа/RTSP; не проверка качества модели |

Для реального PostgreSQL использовать только специально выделенную локальную
тестовую БД и учётную запись с CREATE/DROP SCHEMA. Тесты создают/удаляют schemas.
Не направлять эти DSN на production. Backend использует BACKEND_TEST_DSN,
очереди QUEUE_TEST_DSN; задавайте их приватно вне shell history.

```bash
PYTHONPATH=backend python -m pytest backend/tests/test_access.py backend/tests/test_workflows.py backend/tests/test_migrations.py -q
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_queue_maintenance.py -v
PYTHONPATH=recognition python -m unittest discover -s recognition/tests -p test_queue_postgres.py -v
PYTHONPATH=capture python -m unittest discover -s capture/tests -p test_queue_postgres.py -v
```

Без DSN PG-проверки пропускаются; это не pass. До допуска нужны конкурентный claim,
истечение lease, stale writer, cancel/complete race, исчерпание attempts,
неопределённый commit, отказ S3, orphan GC и остановка worker. Точный охват сверять
с тестами: наличие сценария в этом списке не означает его автоматизации.

## Frontend

Из frontend/, после `npm ci`:

```bash
npm run typecheck
npm run lint
npm run check:api
npm test
npm run build
npm run check:bundle
npm run build:demo
npm run check:demo-build
npx playwright install chromium firefox webkit
npm run test:e2e
npm audit
```

Playwright config использует demo-порт 4173 и live-порт 4174. До запуска убедиться,
что там нет посторонних серверов; reuseExistingServer может повторно использовать
процесс. Browser binaries устанавливаются явно, а не в контейнере.
Unit-тесты browserRecognition проверяют preprocessing, output layout, NMS,
limits и жизненный цикл Worker. Mock API login E2E проверяет UI, не backend auth.

После согласованного изменения backend schema выполнить `npm run generate:api`,
проверить diff contracts/openapi.json и generated.ts, затем `npm run check:api`.
Check не должен молча обновлять baseline; он также проверяет совместимость
live/demo типов. BACKEND_PYTHON выбирает Python backend, default ../.venv/bin/python.
Bundle checks проверяют отсутствие fixture в production и загрузку demo под subpath.

E2E создаёт screenshots/trace в test-results и HTML report; synthetic-only.
Проверяются маршруты, отсутствие demo API requests, desktop/mobile overflow,
CSV/табличная альтернатива, focus диалога, роли и axe. Нулевой axe report не
равен WCAG-сертификации. Проверить вручную keyboard-only, 200% zoom, screen reader,
ошибки загрузки/модели и медленные устройства. Настоящий browser inference
smoke на разрешённом материале является отдельной проверкой.

Usability: нужны участники и записанные наблюдения основных задач; агент не
заменяет их синтетическими отзывами. Performance: сохранять размеры бандлов,
условия cold/warm старта и lab measurements. Field Web Vitals без реальных
данных пользователей не заявляются.

## Документация

Из корня repo после установки renderer dependencies:

```bash
npm --prefix docs/diagrams ci
npm --prefix docs/diagrams exec -- playwright install chromium
npm --prefix docs/diagrams run render
npm --prefix docs/diagrams run check
npm --prefix docs/diagrams run links
git diff --check
```

Renderer проверяет синтаксис всех Mermaid, формирует SVG/PNG и manifest hashes.
Check повторно рендерит, сравнивает подписи/структуру SVG и проверяет
source/SVG/PNG hashes manifest, а также непустоту нового растра. Геометрия и
PNG pixels зависят от browser/fonts. Negative tests запускаются через
`npm --prefix docs/diagrams test`. Подробности в [инструкции схем](diagrams/README.md).
Links проверяет локальные файловые ссылки только принадлежащих этому срезу docs,
не remote URLs и не anchors. Визуально открыть каждую схему и проверить подписи,
стрелки и масштаб; hash не заменяет визуальную проверку.

## Настоящий Inference

Отдельные opt-in команды из корня repo, после установки зависимостей соответствующего
сервиса, Chromium, FFmpeg/FFprobe и разрешённых весов:

```bash
node frontend/tests/browserRecognitionSmoke.mjs
node frontend/tests/browserRecognitionUiSmoke.mjs
PYTHONPATH=recognition python recognition/tests/run_model_smoke.py --output /tmp/attendance-model-smoke
```

Server smoke ожидает локальный yolov8n.pt в корне и сверяет recognition/model-manifest.json;
ничего не скачивает вместо отсутствующей модели. Использовать новый output-каталог.
Browser UI smoke собирает приложение в памяти, открывает реальный диалог, проверяет
image/video, ошибку загрузки, cancel/retry, cleanup и отсутствие отправки медиа.
Это отдельные resource-consuming проверки, не обязательный шаг renderer.

## Не Подменять Проверки

S3 и restore требуют настоящего хранилища и чистой изолированной среды. Проверка
PostgreSQL restore не доказывает восстановление S3-объектов и их SQL-ссылок.
Отсутствующий MinIO нельзя заменить mock и объявить full restore успешным.
Real model smoke требует разрешённых весов/материала; fixtures проверяют только UI.
Сохранённые [browser smoke](../frontend/tests/browserRecognition-smoke.json),
[UI image/video smoke](../frontend/tests/browserRecognition-ui-smoke.json) и
[CPU smoke image/video](../recognition/tests/model-smoke-evidence.json) имеют
успешный статус для реального inference на синтетических входах. Это не
count-quality evaluation и не DB/S3 end-to-end тест.
В этой документационной работе тяжёлые контейнеры не запускались.
