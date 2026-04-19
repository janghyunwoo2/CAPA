# 디렉토리 구조 마이그레이션 가이드

## 개요

기존 `infra/` 및 `src/` 디렉토리는 유지하고, DevOps 가이드 기준의 새로운 구조(`infrastructure/`, `services/`)를 병행 사용합니다.

## 현재 상태 vs 신규 구조

### 기존 구조 (유지)
```
CAPA/
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       └── modules/
└── src/
    ├── airflow/
    └── log-generator/
```

### 신규 구조 (추가됨)
```
CAPA/
├── infrastructure/
│   ├── helm-values/
│   │   └── README.md
│   ├── terraform/
│   │   ├── modules/
│   │   │   └── README.md
│   │   └── environments/dev/
│   │       ├── base/
│   │       │   └── README.md
│   │       └── apps/
│   │           └── README.md
│   └── README.md
└── services/
    ├── airflow-dags/
    ├── slack-bot/
    ├── vanna-api/
    └── README.md
```

## 마이그레이션 전략

### Phase 1: 준비 단계 (현재 완료 ✅)
- [x] 신규 디렉토리 구조 생성
- [x] 각 디렉토리 README 작성
- [x] 구조 이해 및 팀 공유

### Phase 2: 작업 명세서 작성 (다음 단계)
DevOps Implementation Guide를 기준으로 상세 작업 명세서 작성:
- [ ] Base Layer Terraform 코드 명세
- [ ] Apps Layer Terraform 코드 명세
- [ ] Helm Values 설정 명세
- [ ] CI/CD Pipeline 명세

### Phase 3: 코드 작성 (작업 명세서 승인 후)
1. **Terraform 모듈 개발**
   - `infrastructure/terraform/modules/` 하위 모듈 작성
   - kinesis, s3, glue, eks, iam 모듈

2. **Base Layer 구현**
   - `infrastructure/terraform/environments/dev/base/` 작성
   - AWS 리소스 생성

3. **Apps Layer 구현**
   - `infrastructure/terraform/environments/dev/apps/` 작성
   - Helm Release 배포

4. **Services 마이그레이션**
   - `src/airflow/` → `services/airflow-dags/` 점진적 이동
   - Slack Bot, Vanna API 개발

### Phase 4: 검증 및 전환
- [ ] Base Layer 배포 테스트
- [ ] Apps Layer 배포 테스트
- [ ] 기존 구조 유지 또는 제거 결정

## 주의 사항

### 1. 기존 작업 보호
⚠️ **기존 `infra/` 및 `src/` 디렉토리는 절대 삭제하지 마세요.**
- 기존 작업 내역 보존
- 참고 자료로 활용

### 2. Terraform State 관리
신규 구조로 배포 시:
- 새로운 State 파일 생성 (S3 Backend)
- 기존 State와 충돌 방지

### 3. 팀원 동기화
- 새로운 구조 공유
- README 숙지 필수

## 다음 단계

### 1. 작업 명세서 작성
DevOps Implementation Guide 섹션별로 상세 명세 작성:
- [ ] Kinesis 모듈 명세
- [ ] S3 모듈 명세
- [ ] Glue 모듈 명세
- [ ] EKS 모듈 명세
- [ ] IAM 모듈 명세 (IRSA)

### 2. 명세서 검토 및 승인
- [ ] 팀 리뷰
- [ ] 보안 검토
- [ ] 비용 추정

### 3. 구현 시작
명세서 승인 후 Phase 3 진행

## 참고 문서
- [DevOps Implementation Guide](docs/t1/devops/devops_implementation_guide.md)
- [Infrastructure README](infrastructure/README.md)
- [Base Layer README](infrastructure/terraform/environments/dev/base/README.md)
- [Apps Layer README](infrastructure/terraform/environments/dev/apps/README.md)
