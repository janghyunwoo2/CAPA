FROM python:3.10-slim

LABEL description="이상치탐지 (Click Anomaly Detection)"
LABEL service="capa-click"

# Prophet 컴파일에 필요한 시스템 의존성
RUN apt-get update && apt-get install -y \
    build-essential \
    libpython3-dev \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# .env 파일 이미지 내 통합
COPY .env /app/.env

COPY . .

RUN mkdir -p /app/output

ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/app/output

CMD ["python", "main.py"]
