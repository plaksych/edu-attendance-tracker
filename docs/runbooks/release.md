# Выпуск и откат

## До допуска

1. Зафиксировать commit SHA, успешный CI run, container artifacts/SBOM, reviewed digests.
2. Пройти native/production-like сценарий и полный restore drill в отдельной среде.
3. Проверить schema/API/worker compatibility, лицензии, vulnerabilities, модель, TLS SAN, CSP,
   storage support и IAM. Непройденный пункт блокирует promotion.
4. Владелец GitHub настраивает required status checks, запрет force-push, review/CODEOWNERS
   operational файлов, protected environments `production` и `github-pages` с required reviewers,
   prevent self-review и разрешёнными ветками main/production. Здесь эти настройки НЕ применялись.

Ни push в `production`, ни push в `main` не запускает deployment. `ci.yml` только проверяет и
сохраняет артефакты. `pages.yml` запускается вручную, повторяет CI на той же ревизии и публикует
тот же demo artifact после environment approval. `PAGES_ENABLED` должен быть `true`;
иначе deploy job skipped, CI build artifacts остаются доступны. Pages владелец включает вручную
в Settings; `PAGES_ADMIN_TOKEN` не нужен и запрещён workflow policy check.

`promotion.yml` только проверяет успешный trusted push CI run/exact SHA и требует environment
approval. Он НЕ подключается к серверу и НЕ доказывает проверку введённого evidence URL.
Окончательный operator review обязателен. Credentials deployment в workflow отсутствуют.

## Контролируемые действия

Загрузить сохранённый CI `image.tar.gz`, сверить checksum/image ID. Владелец отдельно переносит
эти байты в доверенный registry и фиксирует полученный manifest digest; не пересобирать ветку
на сервере. При несовпадении digest/config остановиться. Каждый Python Dockerfile строится
из корня (`docker build -f backend/Dockerfile .` и аналогично workers); frontend из `frontend`.

На новом стенде создать volume ownership, DB owner/runtime roles/grants и три storage account.
Единственный поддерживаемый entry point создания DB roles: `scripts/ops/roles.py`.
Старые SQL-примеры не поддерживаются и не являются инструкцией для deployment.
Имена четырёх ролей начинаются с DB_NAME + `_`, пароль берётся из соответствующего DSN
с URL decoding. Admin connection берётся из отдельного 0600 env: PGHOST/PGPORT/PGDATABASE,
PGUSER=DB_ADMIN_USER, PGPASSFILE, PGSSLMODE (+PGSSLROOTCERT для remote). Пароли/DSN не печатаются.
Миграционная роль отделена от admin, создаётся NOINHERIT/NOSUPERUSER/NOCREATEROLE/NOCREATEDB;
public schema принадлежит ей, application runtime имеет только USAGE, без CREATE/TEMP.
Runtime DB роли не superuser, не owner схемы, не имеют прав на ops_control. Runtime S3 policy:
ListBucket/GetBucketLocation и Get/Put/DeleteObject только своего bucket; никакого IAM,
bucket policy/lifecycle admin. Init account имеет отдельные bucket-management права.
`storage-init` отказывается менять bucket с существующей policy: провести review, а не отключать check.

```sh
make preflight ENV_FILE=/secure/production.env
make infra-up ENV_FILE=/secure/production.env
# На пустой БД до миграций: data.py mark; account/IAM provisioning отдельно.
make role-init ENV_FILE=/secure/production.env ADMIN_ENV_FILE=/secure/db-admin.env
make storage-init ENV_FILE=/secure/production.env
# Обновление: остановить writers, сделать backup, затем совместимая миграция один раз.
make migrate ENV_FILE=/secure/production.env
make role-grants ENV_FILE=/secure/production.env ADMIN_ENV_FILE=/secure/db-admin.env
make deploy ENV_FILE=/secure/production.env APPROVAL_FILE=/secure/approved-release.json
make smoke ENV_FILE=/secure/production.env
```

Содержимое approval JSON: `reviewer`, `revision` (полный SHA), `ci_run`, `backup_snapshot`,
`restore_evidence`, `schema_compatible: true`, `images` (точный map service -> image@sha256 для
ВСЕХ сервисов effective Compose). Это локальная запись решения, не цифровая подпись и не
способ заменить protected environment. Полный `compose config` содержит секреты: не публиковать.
Без готового IAM, проверенного storage image, модели и TLS даже infra-up может быть заблокирован
preflight; это намеренное fail-closed поведение.

После запуска проверить login/logout/CSRF, scopes/media, upload CPU, очередь до terminal state,
scheduler leadership, maintenance без камер, TTL подписей, CORS/Range и отсутствие секретов в logs.
Сохранить время, SHA/digests, результат каждой проверки. При сбое smoke сервисы не откатываются
автоматически; изолировать ingress и принять решение по совместимости схемы.

## Rollback

Подготовить env с предыдущими проверенными image digests и отдельную approval запись, которая
подтверждает совместимость этих приложений с ТЕКУЩЕЙ схемой. Затем:

```sh
make rollback ENV_FILE=/secure/previous-compatible.env APPROVAL_FILE=/secure/approved-rollback.json
```

Команда меняет только приложения, не PostgreSQL/MinIO, не запускает миграции/downgrade и не
пересобирает образы. Если схема несовместима, остановить writers и воспользоваться отдельным
планом восстановления: возможна потеря данных после точки backup. Автоматического destructive
downgrade нет. После подтверждённого incident провести review причин и закрепить regression test.
