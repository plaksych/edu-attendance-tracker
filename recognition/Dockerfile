FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install --no-cache-dir -r requirements.txt

ARG MODEL_PATH=yolov8n.pt
ARG DOWNLOAD_MODEL=true
# Для локального файла весов укажите DOWNLOAD_MODEL=false и подключите его volume-монтажом.
RUN if [ "${DOWNLOAD_MODEL}" = "true" ]; then \
      python -c "from ultralytics import YOLO; YOLO('${MODEL_PATH}')"; \
    fi

COPY app ./app

CMD ["python", "-m", "app.main"]
