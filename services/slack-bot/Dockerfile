FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# 헬스 체크용 포트 노출
EXPOSE 3000

CMD ["python", "app.py"]
