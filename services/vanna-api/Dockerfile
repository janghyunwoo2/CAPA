# =====================================================
# Vanna AI API Dockerfile
# =====================================================
# 설명: Text-to-SQL 자연어 질의 처리 API
# 역할: ChromaDB + Claude를 활용한 SQL 생성
# =====================================================

FROM python:3.11

WORKDIR /app

# 시스템 의존성 설치 (ChromaDB 등 컴파일 필요 라이브러리 지원)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt



# 애플리케이션 코드 복사
COPY src/ .

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
