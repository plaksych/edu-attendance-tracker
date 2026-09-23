# ADR-003: Серверные Сессии

Статус: cookie auth, CSRF и teacher scope реализованы.

Для одного учебного заведения используем непрозрачную cookie, hash token в БД,
Argon2 и отзыв через auth_version. Не вводим JWT storage в браузере и внешний IAM.
Teacher scope задаётся grants по группам и проверяется backend, включая media.

Следствие: БД участвует в каждом защищённом запросе; новые raw SQL запросы требуют
явного scope. Короткая signed media URL отзывается не мгновенно, а по TTL.
Прикладной audit не защищает от изменения владельцем БД.

Код: [security](../../backend/app/core/security.py), [access](../../backend/app/core/access.py).
Контракт: [API](../api.md), [D11](../diagrams/rendered/D11.svg).
