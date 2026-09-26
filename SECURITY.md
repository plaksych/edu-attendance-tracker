# Сообщения о безопасности

Не публиковать exploit с реальными credentials, camera URLs, cookies, персональными данными
или учебными медиа в публичном issue. Использовать Private vulnerability reporting в GitHub
Security, если владелец включил эту возможность; иначе сначала запросить у владельца приватный
канал без передачи чувствительного содержимого. Здесь нет подтверждённого адреса security-team
или обещанного SLA ответа; не придумывать такой контакт.

Передать affected revision, минимальное синтетическое воспроизведение, ожидаемые/фактические
полномочия, воздействие и безопасный способ проверки исправления. Не тестировать живой сервер
без разрешения владельца. Для CORS, signed URLs, RTSP и media scopes указывать только обезличенную цель.

## Release boundary

Production допускается только после auth/object-scope tests, private storage/IAM, fail-closed
configuration, проверенного restore и review известных advisories/licenses. Ветка production
сама по себе не означает поддерживаемый live release. Текущие остаточные риски и статусы указаны
в [операциях](docs/operations.md) и [third-party inventory](THIRD_PARTY_NOTICES.md).

Нельзя открывать БД, storage console или API напрямую для диагностики. Не включать public-read,
demo auth bypass, reset route или broad CORS как временный workaround. Backend runtime не получает
root storage ключей; init и migration выполняются отдельно. Recovery scripts проверяют настоящую
DB identity, mode и namespace, отказываются от восстановления поверх существующих данных.

Secrets: отдельные DB roles, root/init/runtime S3 accounts, Fernet key escrow, TLS key,
restic password/repository credentials. Не включать их в CI logs/config artifacts. При утечке
закрыть затронутый вход, отозвать сессии/keys по scope, сохранить audit и проверить backup escrow;
Fernet rotation требует отдельного плана перешифрования, не простого изменения env.

## Зависимости

Hash locks и Actions SHA фиксируют bytes, но не гарантируют отсутствие уязвимостей.
`make audit` не применяет fixes. Advisory scan обязателен после каждого обновления, а container
scan после сборки. Исключение возможно только отдельным reviewed решением с owner, сроком,
обоснованием exploitability и компенсирующей мерой; в текущем коде blanket allowlist нет.
Не принимать unassessed packages, unavailable scanner или failed download за clean result.
