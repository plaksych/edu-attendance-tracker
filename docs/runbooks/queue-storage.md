# Очередь, S3 и деградация

## Очередь растёт

Сначала проверить heartbeat recognition/maintenance и возраст oldest pending/processing,
число retries/expired leases, duration inference, CPU/RAM/pids/tmpfs и свободное место. Это
данные runtime, а не только `docker compose ps`. Отключённый capture в upload-only не является аварией.
До ручного retry проверить lease/claim token: старый worker не должен публиковать canonical artifact.
Не править status SQL без фиксации incident и проверки владельца job. Автоматическое recovery
принадлежит maintenance, не API и не camera profile.

При OOM или timeout ограничить admission, уменьшить workload/размеры после review; не снимать
лимиты контейнера и запрет egress. Несколько workers требуют capacity test. Duplicate schedules:
остановить лишний scheduler, проверить advisory lock/reconnect и DB uniqueness, не удалять историю.
При отключении PostgreSQL API liveness может оставаться healthy, readiness должен вернуть 503.

## S3 недоступен или медиа не открывается

Проверить private endpoint, TLS на public host, scoped credentials, bucket existence, IAM,
retention и часы сервера. Signature зависит от исходного Host/port/path; не переписывать URL.
Проверить Range и expiry 120 секунд через реальный браузер, CORS только approved origin.
403 не лечить `public-read`: проверить owner scope и подпись. 404 после retention показывается
как истёкшее медиа; retry не создаёт отсутствовавшую запись заново.

Не печатать presigned URLs, object keys реальных записей, cookie, RTSP или секреты в tickets/logs.
Gateway access logs отключены; для диагностики использовать обезличенный request/job ID и status.
При обнаружении публичной bucket policy закрыть ingress, отозвать затронутые keys, сохранить audit,
провести оценку раскрытия и только затем выполнить контролируемую инициализацию.

## Backup просрочен

Начальная цель: backup каждые 24 часа, alert после 26 часов без успешного snapshot; владелец
утверждает реальные значения. Следить за последним успешным snapshot и отдельно за последним
полным restore drill. Не считать backup успешным только по exit коду планировщика.
На disk pressure сначала остановить intake, проверить encrypted staging и off-host repository;
не удалять PostgreSQL volume или действующие media artifacts ради освобождения места.

Monitoring/alert delivery и внешнее расписание backup на сервере не настраивались этой работой.
Каждый alert должен содержать namespace, время, проверенную причину и ответственную команду,
но не secrets/персональные данные. [Backup/restore](backup-restore.md).
