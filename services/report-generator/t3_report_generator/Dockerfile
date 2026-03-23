# =====================================================
# Report Generator Dockerfile (T3 Version 통합)
# =====================================================
# 설명: EKS 배포용 공식 이미지 빌드
# 역할: Slack 봇, 정기 리포트 생성, PDF 출력 및 헬스체크
# =====================================================

FROM python:3.11-slim

WORKDIR /app

# 모듈 참조를 위한 환경 변수 설정
ENV PYTHONPATH=/app

# PDF 생성 시 한국어 깨짐 방지를 위한 폰트 설치 (t3_report_generator 기준)
RUN apt-get update && apt-get install -y fonts-nanum && rm -rf /var/lib/apt/lists/*

# T3 폴더의 의존성(라이브러리 목록) 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# T3 폴더의 애플리케이션 코드 (봇 소스코드) 복사
COPY . .

# 헬스체크 제거 (CLI 방식은 필요 없음)

# 리포트 생성 메인 모듈 실행 (기본값: 서버 모드)
# EKS 배포 시 8000번 포트 헬스체크에 응답하기 위해 server 인자를 기본으로 사용합니다.
ENTRYPOINT ["python", "main.py"]
CMD ["server"]
