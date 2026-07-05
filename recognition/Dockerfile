FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скачиваем веса на этапе сборки, чтобы контейнер стартовал без доступа в интернет
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY app ./app

CMD ["python", "-m", "app.main"]
