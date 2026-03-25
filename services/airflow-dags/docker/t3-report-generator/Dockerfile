FROM python:3.11-slim

USER root

# weasyprint 시스템 의존성 + 한글 폰트
RUN apt-get update && apt-get install -y \
    fonts-nanum \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgobject-2.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 모듈 파일 복사 (services/report-generator/t3_report_generator/ 기준)
COPY main.py .
COPY athena_client.py .
COPY markdown_builder.py .
COPY pdf_exporter.py .
COPY slack_notifier.py .
