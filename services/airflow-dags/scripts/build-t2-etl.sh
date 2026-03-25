#!/bin/bash
# =============================================================================
# T2 ETL Runner 이미지 빌드 & ECR 푸시 (Airflow EKS 전용)
# =============================================================================
# 실행 위치: 프로젝트 루트(CAPA/ 디렉토리)에서 실행
# 사용법: bash services/airflow-dags/scripts/build-t2-etl.sh [TAG]
# =============================================================================

set -e

# 1. 설정
AWS_ACCOUNT_ID="827913617635"
AWS_REGION="ap-northeast-2"
REPO_NAME="capa/airflow-kpo-t2-etl-runner"
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_FULL="${ECR_BASE}/${REPO_NAME}"
VERSION="${1:-latest}"
PLATFORM="linux/amd64"

# 2. 로컬 색깔
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}=== T2 ETL 이미지 빌드 시작: ${VERSION} ===${NC}"

# ECR 로그인
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${ECR_BASE}"

# 레포지토리 자동 생성 (없으면)
aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" > /dev/null 2>&1 || \
  aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}"

# 빌드 (Context: 프로젝트 루트)
docker build \
  --platform="${PLATFORM}" \
  -f services/airflow-dags/docker/t2-etl-runner/Dockerfile \
  -t "${ECR_FULL}:${VERSION}" \
  -t "${ECR_FULL}:latest" \
  .

# 푸시
docker push "${ECR_FULL}:${VERSION}"
docker push "${ECR_FULL}:latest"

echo -e "${GREEN}=== 완료! ===${NC}"