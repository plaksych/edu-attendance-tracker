# ADR-005: История Upload И Связь С Занятием

Статус: история jobs/corrections и upload-источник открытого замера реализованы.

Upload принадлежит owner и может ссылаться на session/measurement. Job всё ещё
имеет ровно один источник. Ручной retry создаёт новую job вместо удаления raw
result; correction хранится отдельной записью с автором и причиной.

Следствие: latest job и history являются разными представлениями. Evaluation
summary учитывает последнюю job upload, только если она completed. Связь session_id
не заменяет measurement_id. На замер разрешён один upload, смешение с capture
отклоняется. Scheduler агрегирует upload только в открытый замер без captures;
retry/correction не пересчитывают уже терминальный замер или готовый attendance.
С 0010 финализация хранит точные result ID в measurement_result_sources с
used_for_count. Для legacy без доказанного источника остаётся legacy_unknown.

Код: [recognition API](../../backend/app/api/v1/recognition.py),
[requests](../../backend/app/models/requests.py), [aggregation](../../backend/app/services/aggregation.py).
Схема: [D05a](../diagrams/rendered/D05a.svg).
