# ADR-004: Изоляция Демо

Статус: статический адаптер и browser Worker реализованы; полный стенд требует provision и проверки.

Build-time VITE_STATIC_DATA выбирает синтетический адаптер вместо API.
Browser inference обрабатывает локальный файл, не меняет fixture на якобы результат.
Полный стенд использует отдельные Compose namespace, database, bucket и credentials.

Следствие: переключение demo-ролей не является входом и не доказывает RBAC.
Статические изменения сбрасываются reload. Нельзя добавлять production HTTP
demo-reset или fallback на fixture при ошибке server inference.

Код: [client](../../frontend/src/api/client.ts), [staticClient](../../frontend/src/api/staticClient.ts).
Инструкция: [demo](../demo.md), [D04](../diagrams/rendered/D04.svg).
