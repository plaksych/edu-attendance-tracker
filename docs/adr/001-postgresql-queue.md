# ADR-001: Очередь PostgreSQL

Статус: реализована в worker SQL; интеграционный допуск отдельно.

Оставляем PostgreSQL очередью, поскольку он уже хранит jobs и предметные связи.
Claim использует SKIP LOCKED, lease и token попытки. Heartbeat/завершение сверяют
владение; status и result фиксируются одной транзакцией. Отдельный брокер не добавлен.

Следствие: вычисления могут повторяться после lease expiry. S3 PUT не атомарен
с SQL, поэтому ключи артефактов относятся к попытке, orphan очищаются отдельно.
Это не exactly-once processing и не HA без резервирования БД.

Код: [recognition DB](../../recognition/app/db.py), [capture DB](../../capture/app/db.py).
Схема: [D10](../diagrams/rendered/D10.svg). Проверки: [testing](../testing.md).
