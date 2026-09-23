FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS build
WORKDIR /build
COPY recognition/requirements.txt .
COPY scripts/ops/locks/recognition.txt lock.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes --extra-index-url https://download.pytorch.org/whl/cpu -r lock.txt -r requirements.txt

FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 ffmpeg libseccomp2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv

# Weights are provisioned separately and mounted read-only; no auto-download.

COPY recognition/app ./app
USER 10001:10001

CMD ["python", "-m", "app.main"]
