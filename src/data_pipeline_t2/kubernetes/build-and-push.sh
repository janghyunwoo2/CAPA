#!/bin/bash

# CAPA T2 Pipeline Docker 이미지 빌드 및 푸시 스크립트

set -e  # 에러 발생 시 중단

# 설정
REGISTRY="docker.io"  # 또는 AWS ECR, GCR 등
NAMESPACE="capa"
VERSION="${1:-latest}"
PLATFORM="linux/amd64"  # 또는 linux/arm64

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== CAPA T2 Pipeline Docker 이미지 빌드 시작 ===${NC}"
echo "Registry: $REGISTRY"
echo "Namespace: $NAMESPACE"
echo "Version: $VERSION"
echo ""

# 프로젝트 루트로 이동
cd "$(dirname "$0")/../../.."

# 1. Log Generator 이미지 빌드
echo -e "${YELLOW}1. Building log-generator image...${NC}"
docker build \
  --platform=$PLATFORM \
  -f kubernetes/docker/Dockerfile.log-generator \
  -t $REGISTRY/$NAMESPACE/log-generator:$VERSION \
  -t $REGISTRY/$NAMESPACE/log-generator:latest \
  .

# 2. Data Processor 이미지 빌드
echo -e "${YELLOW}2. Building data-processor image...${NC}"
docker build \
  --platform=$PLATFORM \
  -f kubernetes/docker/Dockerfile.data-processor \
  -t $REGISTRY/$NAMESPACE/data-processor:$VERSION \
  -t $REGISTRY/$NAMESPACE/data-processor:latest \
  .

# 3. Data Analyzer 이미지 빌드
echo -e "${YELLOW}3. Building data-analyzer image...${NC}"
docker build \
  --platform=$PLATFORM \
  -f kubernetes/docker/Dockerfile.data-analyzer \
  -t $REGISTRY/$NAMESPACE/data-analyzer:$VERSION \
  -t $REGISTRY/$NAMESPACE/data-analyzer:latest \
  .

# 4. Data Visualizer 이미지 빌드
echo -e "${YELLOW}4. Building data-visualizer image...${NC}"
docker build \
  --platform=$PLATFORM \
  -f kubernetes/docker/Dockerfile.data-visualizer \
  -t $REGISTRY/$NAMESPACE/data-visualizer:$VERSION \
  -t $REGISTRY/$NAMESPACE/data-visualizer:latest \
  .

# 5. S3 Uploader 이미지 빌드 (선택사항)
echo -e "${YELLOW}5. Building s3-uploader image...${NC}"
docker build \
  --platform=$PLATFORM \
  -f kubernetes/docker/Dockerfile.s3-uploader \
  -t $REGISTRY/$NAMESPACE/s3-uploader:$VERSION \
  -t $REGISTRY/$NAMESPACE/s3-uploader:latest \
  .

echo -e "${GREEN}=== 빌드 완료 ===${NC}"
echo ""

# 이미지 푸시 확인
read -p "Docker 레지스트리에 이미지를 푸시하시겠습니까? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo -e "${YELLOW}이미지를 레지스트리에 푸시합니다...${NC}"
    
    # 로그인 확인
    echo "Docker 레지스트리에 로그인되어 있는지 확인하세요."
    # docker login $REGISTRY
    
    # 이미지 푸시
    docker push $REGISTRY/$NAMESPACE/log-generator:$VERSION
    docker push $REGISTRY/$NAMESPACE/log-generator:latest
    
    docker push $REGISTRY/$NAMESPACE/data-processor:$VERSION
    docker push $REGISTRY/$NAMESPACE/data-processor:latest
    
    docker push $REGISTRY/$NAMESPACE/data-analyzer:$VERSION
    docker push $REGISTRY/$NAMESPACE/data-analyzer:latest
    
    docker push $REGISTRY/$NAMESPACE/data-visualizer:$VERSION
    docker push $REGISTRY/$NAMESPACE/data-visualizer:latest
    
    docker push $REGISTRY/$NAMESPACE/s3-uploader:$VERSION
    docker push $REGISTRY/$NAMESPACE/s3-uploader:latest
    
    echo -e "${GREEN}=== 푸시 완료 ===${NC}"
else
    echo -e "${YELLOW}이미지 푸시를 건너뜁니다.${NC}"
fi

# 로컬 이미지 크기 확인
echo ""
echo -e "${GREEN}=== 빌드된 이미지 정보 ===${NC}"
docker images | grep "$NAMESPACE" | grep "$VERSION"

echo ""
echo -e "${GREEN}완료! 다음 단계:${NC}"
echo "1. kubectl apply -f kubernetes/manifests/"
echo "2. Airflow DAG 파일 배포"
echo "3. Airflow UI에서 DAG 활성화"