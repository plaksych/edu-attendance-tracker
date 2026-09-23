# ADR-002: Scheduler И Maintenance

Статус: отдельные процессы реализованы.

API не запускает scheduler в lifespan. Планирование/агрегация и восстановление
очередей имеют отдельные процессы и advisory lock IDs. Блокировка и бизнес-SQL
выполняются на одном выделенном соединении, после потери лидерство приобретается заново.

Maintenance остаётся включённым при upload-only. Его отказ не должен скрываться
здоровым /health API; очередь проверяется отдельными тестами и наблюдением.
Нет отдельного сервиса лидеров или Redis.

Код: [scheduler](../../backend/app/scheduler.py), [maintenance](../../backend/app/maintenance.py).
Схема: [D02](../diagrams/rendered/D02.svg).
