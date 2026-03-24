# CAPA T2 ETL Runner Dockerfile (Airflow EKS 전용)
# 소스 코드는 'services/data_pipeline_t2/etl_summary_t2'에서 읽어옵니다.

FROM python:3.11-slim

LABEL maintainer="capa-t2-team"
LABEL description="CAPA T2 ETL Runner for KubernetesPodOperator"

WORKDIR /app

# 1. 의존성 설치
RUN pip install --no-cache-dir \
    boto3>=1.26.0 \
    botocore>=1.29.0 \
    pendulum>=3.0.0 \
    python-dotenv>=0.19.0

# 2. ETL 핵심 모듈 복사 (Source of Truth)
# (이미지 빌드 시 프로젝트 루트를 컨텍스트로 사용해야 함)
COPY services/data_pipeline_t2/etl_summary_t2 /app/etl_modules

# 3. 진입점 스크립트 복사
COPY services/airflow-dags/docker/t2-etl-runner/entrypoint.py /app/entrypoint.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["python", "/app/entrypoint.py"]
