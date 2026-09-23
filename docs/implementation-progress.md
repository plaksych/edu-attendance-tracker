# Ход реализации

Ветка: `production`. Исходный снимок: `cb34254` (`main`).
Основание: техническое задание владельца от 23.09.2026.
Программный срез: `0d515eb`; далее оформляется документация и передача PR.

## Сделано

- Backend: сессии/CSRF/роли/область групп, проверка загрузок, idempotency,
  история попыток и корректировок, preview/confirm расписания, календарь,
  snapshots, отмена связанных заданий и взвешенные показатели.
- Миграции `0006`–`0010`: сохранение старой истории, snapshots камер,
  точные ссылки на источники замера с RESTRICT.
- Очередь: UUID claim, проверка действующего lease, неизменяемые ключи попыток,
  отдельные scheduler/maintenance, ограниченный дочерний процесс inference.
- Frontend: светлый адаптивный интерфейс, роли, аналитика, администрирование,
  синтетическое демо, режим показа, контракты OpenAPI.
- Браузерная обработка: отдельный worker, реальные runtime/model, отмена,
  повтор, освобождение ресурсов; PNG и видео проверены через настоящий UI.
- Эксплуатация: разные DB роли, guarded demo seed/reset, private storage,
  backup/restore tooling, hash locks, CI и ручной promotion.
- Документация: API, runbooks, дизайн-система, 18 отрисованных схем, screenshots.

## Проверки

Итоговый `make verify` с PostgreSQL DSN прошёл: backend 78, capture 9,
recognition 27, frontend 80 тестов, без пропусков.
Lint, TS, mypy критичных модулей, OpenAPI drift, production build,
18 ops guards и 35 отрицательных Compose cases прошли.
Playwright: 15 сценариев в трёх движках.

Native PostgreSQL 14.20: миграция заполненной схемы `0005`, лидерство/reconnect,
stale claims, точные FK, отдельный PostgreSQL-only dump/restore.
Проверки SQL grants и demo seed создают/удаляют только отдельные временные БД.

Настоящий CPU smoke на Torch 2.13.0: синтетическое изображение и короткое видео.
Браузерный UI smoke: реальный WASM, cancel/retry/export, 0 upload bytes.
Это проверка исполнения, не оценка точности на аудиториях.
Аудит закреплённых зависимостей: 0 известных advisories; container OS scan отдельно.

## Передача

Тематические коммиты: `8aeb509`, `6ec7319`, `72c4aec`, `84d755d`,
`86db076`, `8933e0a`, `b6602a1`, `5f388a6`, `d43e364`, `0d515eb`.
Чистый checkout обнаружил пропущенную зависимость `@types/node`; исправлено,
`npm ci`/build и чистый backend+ops venv на hash locks проверены повторно.
Последний общий verify прошёл. Следующие действия: документационный commit,
push и PR `production → main`, проверка удалённого CI.
Merge, Pages/deploy и изменение main не выполняются автоматически.

Полный S3 restore, Linux runtime/egress, эксплуатационные TLS/IAM,
размеченная выборка, лицензии весов и человеческая приёмка остаются отдельными
условиями допуска. Точные статусы: [матрица готовности](production-readiness.md).

Тяжёлые контейнеры локально не запускались. Временный PostgreSQL:
`/tmp/attendance-production-pg`, loopback port 55439, только синтетические данные.
После окончательной проверки: `pg_ctl -D /tmp/attendance-production-pg stop`.
Документы практики, исходные XLSX, секреты, .claude и приватные медиа не публикуются.
