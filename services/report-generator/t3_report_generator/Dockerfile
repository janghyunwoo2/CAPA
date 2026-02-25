FROM python:3.11-slim

WORKDIR /app

# 기본 한글 폰트 설치 (PDF 생성 시 깨짐 방지용)
RUN apt-get update && apt-get install -y fonts-nanum && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 컨테이너 실행 시 bot.py 가동
CMD ["python", "bot.py"]
