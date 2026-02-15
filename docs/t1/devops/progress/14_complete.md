# Task 14: Vanna AI 배포 완료 보고서 (Complete)

## 📋 최종 작업 요약
- **작업 완료 일자**: 2026-02-15
- **현재 상태**: **완료 (Done)** 🚀
- **주요 결과물**:
  - Vanna AI API 서비스 배포 (FastAPI + ChromaDB + Claude 3.5 Sonnet)
  - ECR 리포지토리 및 IAM Role (IRSA) 설정 완료
  - Kubernetes 리소스 (Namespace, Deployment, Service, Secret) 구축 완료
  - 자연어-to-SQL 질의 및 Athena 연동 환경 구성 완료

## 🛠️ 작업 내용 상세

### 1. 애플리케이션 개발 및 아키텍처
- **Vanna API 구현**: `services/vanna-api/src/main.py`
  - 자연어 질문을 받아 SQL을 생성하고 Athena에서 실행하는 인터페이스 제공
  - ChromaDB를 벡터 저장소로 사용하여 학습 데이터 관리
- **버전 최적화**: 
  - Vanna AI `2.0.x` 버전의 대규모 아키텍처 변경으로 인한 `ModuleNotFoundError` 해결을 위해 안정적인 `0.7.9` 버전으로 고정
  - `requirements.txt`: `vanna[chromadb]==0.7.9` 명시

### 2. 인프라 구축 (Infrastructure as Code)
- **AWS ECR**: `capa-vanna-api` 리포지토리 생성 및 이미지 관리
- **IAM Role (IRSA)**: `capa-vanna-role`을 통해 파드가 Athena 및 S3에 안전하게 접근 (Access Key 불필요)
- **Kubernetes**:
  - **Namespace**: `vanna` 독립 네임스페이스 사용
  - **Deployment**: 리소스 제한 (CPU 250m~1000m, Memory 512Mi~2Gi) 및 헬스 체크 설정
  - **Secret**: `vanna-secrets`를 통해 Anthropic API Key 안전하게 주입

### 3. CI/CD 및 배포 과정
- **빌드 및 푸시**: Python 3.11 풀 베 이미지 기반의 Docker 최적화
- **Terraform 연동**: 리팩토링 과정에서 발생한 리소스 충돌 문제를 `import` 및 `target apply` 전략으로 해결

## 🚧 이슈 및 트러블슈팅

| 이슈 | 원인 | 해결 방법 |
| :--- | :--- | :--- |
| **ChromaDB 빌드 실패** | C++ 컴파일러 및 의존성 라이브러리 부재 | Dockerfile 베이스 이미지를 Full 버전으로 변경 및 `build-essential` 설치 |
| **ModuleNotFoundError** | Vanna AI 2.0 버전의 아키텍처 파편화 | `vanna==0.7.9` 버전 고정으로 모듈 호환성 복구 |
| **Resource Already Exists** | Terraform State 유실 및 수동 생성 충돌 | `terraform import` 명령어를 통해 기존 리소스를 테라폼 관리하에 등록 |
| **CrashLoopBackOff** | API Key 누락 및 모듈 로딩 실패 | `terraform.tfvars`에 API Key 반영 및 이미지 재빌드 후 배포 |

## ✅ 최종 검증 결과
- **Pod 상태**: `Running` (vanna-api-xxxx)
- **Health Check**: `GET /health` -> `{"status":"ok","service":"vanna-api"}` 확인 완료
- **권한 확인**: Pod 내부에서 AWS Athena/S3 접근 권한(IRSA) 정상 작동 확인

## 🔗 관련 자원
- **ECR**: `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-vanna-api`
- **Internal API**: `http://vanna-api.vanna.svc.cluster.local:8000`
- **Source Code**: `services/vanna-api/`
- **Terraform Config**: `infrastructure/terraform/11-k8s-apps.tf`
