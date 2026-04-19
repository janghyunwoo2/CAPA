FROM python:3.10-slim

# Prophet 컴파일에 필요한 시스템 의존성
RUN apt-get update && apt-get install -y \
    build-essential \
    libpython3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output

ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/app/output

CMD ["python", "main.py"]
