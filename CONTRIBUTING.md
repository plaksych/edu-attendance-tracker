# Изменения и проверка

Работать небольшими тематическими изменениями; не переписывать применённые миграции и не
откатывать чужие незакоммиченные правки. Не публиковать реальные учебные записи, secrets,
cookie или signed URLs. Новые assets требуют происхождения, лицензии и хеша модели.

`make bootstrap` создаёт отдельные Python environments, устанавливает hash-locked зависимости
и выполняет `npm ci`. `make verify` запускает недеструктивные проверки и суммирует провалы.
Backend/capture/recognition имеют одноимённый пакет `app`: тестировать в отдельных процессах
из соответствующих каталогов, не объединять PYTHONPATH. Локально допускается имеющийся `.venv`
или `<SERVICE>_PYTHON`; CI использует только отдельные environments.

```sh
make verify
make audit
TEST_DATABASE_URL=postgresql://attendance_test@127.0.0.1:55439/attendance_test make test-integration
make test-e2e
make test-visual
```

Integration требует отдельный PostgreSQL 16 и `pg_dump/pg_restore` в PATH; backend suite
создаёт временные схемы и две временные БД для restore, поэтому test role нужен CREATEDB.
Не передавать production DSN. S3 проверяется отдельно `scripts/check_integration.py`, только
при наличии настоящего private S3 endpoint. SQLite/mocks не считаются заменой этих проверок.

Обновление Python: изменить owning service requirements, согласовать изменения, затем повторить
команду из заголовка соответствующего `scripts/ops/locks/*.txt` (генератор uv 0.11.16).
Ops lock включает `requirements.txt` + `tooling.txt`; recognition input также закрепляет CPU
torch/torchvision/numpy. Нельзя лечить CVE автоматическим major upgrade без тестов; не добавлять
глобальные audit suppressions. `make audit` сохраняет advisory IDs, lock hashes и реальные коды
возврата. Платформенные пакеты без advisory coverage отмечаются unassessed, не clean.

CI: Python lint/format, critical settings types, pytest и OpenAPI; frontend lint/types/unit,
production/demo builds и browser artifacts; PG/S3 integration; secret/dependency/container scans,
SBOM/licenses, docs/diagrams. Screenshot artifacts не являются принятым visual baseline.
Новый baseline требует отдельного review; не добавлять `--update-snapshots` в обычный CI.

Образы собираются с commit SHA, deployment использует проверенные bytes/digests. Push в main
или production ничего не выкатывает. Публикация Pages и production promotion требуют отдельного
manual workflow/environment approval. Настройки branch protection выполняет repository owner;
наличие YAML не доказывает, что защита включена.

Для PR указать scope, migration/compatibility impact, команды и результаты, ограничения и
evidence. `not_run`, `blocked`, `failed` не заменять словом passed.
Подробности: [эксплуатация](docs/operations.md), [безопасность](SECURITY.md),
[лицензии](THIRD_PARTY_NOTICES.md).
