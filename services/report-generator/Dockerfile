# =====================================================
# Report Generator Dockerfile (T3 Version 통합)
# =====================================================
# 설명: EKS 배포용 공식 이미지 빌드
# 역할: Slack 봇, 정기 리포트 생성, PDF 출력 및 헬스체크
# =====================================================

FROM python:3.11-slim

WORKDIR /app

# PDF 생성 시 한국어 깨짐 방지를 위한 폰트 설치 (t3_report_generator 기준)
RUN apt-get update && apt-get install -y fonts-nanum && rm -rf /var/lib/apt/lists/*

# T3 폴더의 의존성(라이브러리 목록) 복사 및 설치
COPY t3_report_generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# T3 폴더의 애플리케이션 코드 (봇 소스코드) 복사
COPY t3_report_generator/ .

# 헬스체크 (bot.py의 8000포트 FastAPI 서버 확인)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Slack 봇 및 헬스체크 통합 실행
CMD ["python", "bot.py"]
