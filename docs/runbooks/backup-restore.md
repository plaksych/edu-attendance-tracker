# Backup и восстановление

Статус полного drill: **blocked** до доступного S3 и разрешённого отдельного стенда.
Ни успешный `pg_dump`, ни проверенный checksum не равны восстановлению работающего приложения.
RPO 24 часа / RTO 4 часа можно принять как начальные проектные цели, но измерений/SLA здесь нет.

## Подготовка оператора

Нативные инструменты: PostgreSQL client того же major, что сервер (16), `restic`, Python env
с `scripts/ops/locks/ops.txt`. Записать `pg_dump --version`, `pg_restore --version`,
`restic version` в evidence. Скрипт не скачивает MinIO или backup binaries и не запускает Docker.
Указанный владельцем native MinIO URL вернул 410; не заменять его непроверенным mirror/latest.

Создать приватный env по `scripts/ops/backup.env.example`. DB password в 0600 `PGPASSFILE`,
S3/repository credentials в 0600 env, restic password в отдельном 0600 файле. Удалённые DB/S3
только с проверкой TLS; plaintext разрешён лишь через loopback private tunnel. Не публиковать
порты production ради backup. Restic repository должен быть вне исходного хоста; endpoint,
изоляцию аккаунта и retention подтверждает владелец, скрипт не может доказать off-host по URL.

Staging находится на зашифрованном диске, `BACKUP_STAGING_ENCRYPTED=true` только после реальной
проверки владельцем. Скрипт создаёт приватный временный каталог и удаляет его при завершении.
При сбое процесса/потере питания проверить остатки вручную. Никогда не класть backups в git.

## DB marker

Перед миграциями на ПУСТОЙ БД отдельно создать marker:

```sh
python scripts/ops/data.py mark --env-file /secure/demo-ops.env --quiesced
```

В env независимые `OPS_MODE`, `OPS_NAMESPACE`, `OPS_INSTANCE_ID` UUID. Имя DB соответствует
namespace с `_`, bucket равен namespace. `ops_control.identity` создаётся один раз; runtime
роли не имеют к нему доступа. На существующей production БД marker устанавливается только
отдельной рассмотренной DBA-процедурой после инвентаризации; `mark` откажет на непустой схеме.
Backup исключает ops_control, чтобы source marker не превратил restore DB в production/demo.

## Согласованный backup

1. Закрыть ingress, остановить API/scheduler/maintenance/capture/recognition и внешних writers.
2. Приостановить storage lifecycle и внешние cleanup jobs, записать время quiescence.
3. Убедиться, что нет других DB clients. Скрипт это перепроверяет, но новый writer после
   проверки исключается эксплуатационной блокировкой; row counts не обнаруживают все UPDATE.
4. Выполнить команду и ввести точную цель. `--quiesced` является подтверждением этих шагов.

```sh
make backup OPS_ENV_FILE=/secure/prod-ops.env ENV_FILE=/secure/production.env EVIDENCE=/secure/evidence/backup-001.json
```

Состав: PostgreSQL custom-format dump (НЕ копия PGDATA), все текущие объекты bucket,
SHA256 каждого файла, counts таблиц, точка копии, безопасная конфигурация/images/model hash.
Объектные имена не становятся локальными путями; bytes сохраняются под числовыми именами.
Связи bucket/object в DB проверяются перед копированием. Смена inventory/counts прерывает backup.
История удалённых S3 versions не входит в этот current-state backup; при versioning нужен
дополнительный согласованный план. Restic шифрует bundle и возвращает точный snapshot ID.

Fernet/TLS/database/runtime keys НЕ включаются в bundle. Хранить отдельный зашифрованный escrow,
проверять recovery доступ двумя ответственными лицами и записывать key version в release record.
Без Fernet key восстановленные camera credentials непригодны. Не менять key при обычном rollback.

Retention отдельной подтверждаемой командой, не побочным эффектом backup:

```sh
python scripts/ops/data.py retention --env-file /secure/prod-ops.env
```

Политика: 7 daily, 4 weekly, 12 monthly по namespace tag. Сначала утвердить срок хранения данных
и резервных копий; `forget --prune` необратим. Не использовать этот repository для другого приложения.

## Restore drill

Создать отдельные DB/owner/bucket/hostname/keyset, `OPS_MODE=restore`, namespace
`attendance-restore-<drill>`. Пустая public schema и пустой bucket обязательны. Установить marker,
выключить ingress/writers/lifecycle. Команда не принимает `latest` или production target:

```sh
make restore OPS_ENV_FILE=/secure/restore-ops.env SNAPSHOT=<full-64-hex-snapshot> EVIDENCE=/secure/evidence/restore-001.json
```

До записи проверяются checksums. DB восстанавливается в одной транзакции без owner/ACL;
production bucket references переназначаются на restore bucket. Затем проверяются counts,
доступность каждой DB media reference и SHA256 повторно прочитанных S3 bytes. Сбой может оставить
объекты в restore bucket; повторный запуск откажет на непустой цели. Не удалять цель автоматически:
осмотреть, сохранить evidence и подготовить новую пустую среду.

Успешный script пишет только `data_restore_verified`, elapsed seconds, snapshot и restored point.
Restore использует `--no-acl`: после него обязательно выполнить `make role-grants` с конфигурацией
restore namespace и отдельным administrator env. `role-init` выполняется ДО restore на пустой
схеме. `role-grants` передаёт ownership таблиц migration role, отзывает broad/default grants и
восстанавливает конкретные table/sequence privileges; неизвестная таблица блокирует операцию.
Backend получает audit SELECT/INSERT, но не UPDATE/DELETE/TRUNCATE. Capture/recognition не получают
доступ к users/login_sessions/audit. Проверка: `TEST_DATABASE_URL=... make test-roles`.
`application_smoke=not_run` остаётся до восстановления grants/users/keys, запуска совместимых
приложений и реального login/upload/media/inference smoke. Записать полное RTO, потерянный период
RPO, hardware и operator decision отдельно. Только после этого возможен статус OPS-02 passed.
