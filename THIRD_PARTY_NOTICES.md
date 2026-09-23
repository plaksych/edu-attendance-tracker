# Third-party inventory и допуск

Это инженерная инвентаризация, не юридическое заключение и не разрешение на публикацию.
Владелец утверждает лицензии приложения, pretrained weights, runtime binaries, fonts и media
до распространения. Автоматический SBOM не устанавливает происхождение уже лежащего в repo файла.

## Компоненты

| Компонент | Источник версии | Проверка перед выпуском |
| --- | --- | --- |
| FastAPI, Starlette, SQLAlchemy, Alembic, Pydantic, HTTPX и другие Python packages | service requirements + `scripts/ops/locks/*.txt` | hash install, advisory scan, container license inventory |
| React, Vite, TypeScript, Recharts, Playwright/Vitest и frontend dependencies | `frontend/package-lock.json` | npm ci/audit и SBOM |
| Ultralytics 8.3.132 / YOLO weights | recognition requirements и model-manifest | AGPL/commercial review и происхождение конкретных bytes, не только хеш |
| CPU PyTorch / torchvision | `scripts/ops/recognition.in`, Linux и macOS locks | advisory coverage для local `+cpu` version, CPU smoke, license notices |
| ONNX Runtime JS/WASM | `frontend/public/ort`, browser manifest | сверить version/hash и приложить LICENSE/ThirdPartyNotices из соответствующего release |
| Onest / Golos Text | fontsource dependencies в npm lock | сохранить SIL OFL notices конкретных поставленных fonts |
| MinIO server | явный digest в окружении; CI имеет отдельный resolved digest | лицензия, поддержка/доступность дистрибутива, IAM/lifecycle/restore |
| PostgreSQL, Nginx, Python, Node, FFmpeg, libseccomp и OS packages | base digests + container SBOM | license inventory, codec/build options FFmpeg и security review |
| Фотографии/видео, synthetic fixtures | frontend assets и demo manifests | разрешение владельца данных и отдельное происхождение каждого опубликованного файла |

Ultralytics описывает AGPL-3.0 и Enterprise варианты; выбор и применимость к продукту остаются
за владельцем и юридическим review. Смена `.pt` на ONNX сама по себе не является новой лицензией.
Источник: [Ultralytics licensing](https://www.ultralytics.com/license).
Лицензия MinIO server опубликована отдельно от Python SDK:
[MinIO LICENSE](https://github.com/minio/minio/blob/master/LICENSE).
У ONNX Runtime собственная лицензия и notices, не лицензия модели:
[ONNX Runtime LICENSE](https://github.com/microsoft/onnxruntime/blob/main/LICENSE).

`check_licenses.py` требует непустой Trivy inventory и блокирует AGPL/unknown/unlicensed до
review. Это намеренный release gate, а не утверждение, что AGPL запрещена. В этой работе
лицензионные исключения не добавлены. Container inventory ещё не получен: контейнеры не собирались.

## Проверяемые evidence

Начальный pinned audit действительно выявил 37 backend, 6 capture, 18 recognition и 1 ops
advisory occurrence; npm audit вернул 0. Это сумма записей package/advisory, не число доказанных
эксплуатируемых дефектов приложения. `torch` и `torchvision` `+cpu` были unassessed.
Исходные отчёты сохранены в
[dependency-audit-before](scripts/ops/evidence/dependency-audit-before/summary.json).

Владелец отдельно одобрил security upgrades backend FastAPI/Starlette/multipart/Pillow/cryptography,
worker Pillow/cryptography и pytest ops. Locks должны соответствовать этим изменениям, а не
скрывать advisories. Актуальный повторный отчёт:
[dependency-audit](scripts/ops/evidence/dependency-audit/summary.json).
У отчёта есть время, SHA256 каждого lock и exit code сканера; при изменении lock он устаревает.
Повторный pinned audit после обновлений завершился с exit code 0 для backend/capture/
recognition/ops/frontend. Local `+cpu` версии сохраняются в raw report как недоступные
platform-index scanner; отдельный `pip-audit --no-deps --disable-pip` проверяет точные upstream
имена/версии из lock. Это не исключение advisories: scanner failure или непроверенные пакеты
по-прежнему блокируют команду. Отчёт фиксирует 0 известных advisories на момент проверки,
а не отсутствие всех уязвимостей или проверку бинарных CPU/OS компонентов.

Исходные torch 2.7.0 / torchvision 0.22.0 проверены отдельно:
[upstream audit](scripts/ops/evidence/torch-upstream-audit.json) содержит 14 advisories torch.
Operational locks обновлены до torch 2.13.0 / torchvision 0.28.0 после
[upstream audit без advisories](scripts/ops/evidence/torch-candidate-audit.json) и
[реального native CPU image/video smoke](scripts/ops/evidence/torch213-smoke.json).
Smoke выполнялся на macOS arm64 с запретом сети, не на Linux; synthetic blank frames не
доказывают качество распознавания. Smoke harness только ссылается на отдельный dependency-audit
и не утверждает состояние vulnerability scan самостоятельно.

```sh
make audit
```

Команда закрепляет pip-audit 2.9.0 через ops lock и использует npm audit над npm lock.
Команда не выполняет `audit fix`, `--ignore-vuln`, автоматические upgrades или allowlists.
Advisory DB меняется независимо от lock; сохранять JSON рядом с release evidence.
CI дополнительно создаёт source/container CycloneDX SBOM и Trivy license inventory.

## Остаточные блокеры

Native MinIO не установлен: владелец сообщил HTTP 410 для официального binary URL 2025.
CI MinIO digest был реально разрешён через registry manifest, но pull/run/поддержка не проверены;
это не reviewed production image. Production image env намеренно пуст, fixture digest нельзя
переносить в deployment. Подтвердить доступный источник, checksum/signature и поддержку отдельно.
Нет полного S3 restore, проверки container OS advisories или окончательного model/media/license
допуска. Нельзя объявлять release clean по одному успешному npm audit или DB restore.
