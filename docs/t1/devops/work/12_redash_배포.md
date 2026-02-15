# 12. Redash 배포 (Dashboard)

> **목표**: 데이터 시각화를 위한 Redash 대시보드 구축 및 Athena 연결
> **참조**: [devops_implementation_guide.md](../devops_implementation_guide.md#13-dashboard-구성-redash)
> **소요 시간**: 약 20분

## 1. 사전 준비

- [ ] **EKS 접속 권한 확인**: `kubectl get nodes`
- [ ] **Athena Workgroup 확인**: `base` 배포 시 생성됨
- [ ] **Helm Values 준비**: `helm-values/redash.yaml` (Step 10에서 완료)

## 2. 작업 절차

### 2.1 Helm 배포

**Terraform 파일**: `infrastructure/terraform/environments/dev/base/10-applications.tf`
**Values 파일**: `infrastructure/helm-values/redash.yaml`

```powershell
# Base 디렉토리로 이동
cd infrastructure\terraform\environments\dev\base

# Redash 모듈만 타겟팅하여 배포
terraform apply -target=helm_release.redash
```

### 2.2 접속 및 초기 설정

1. **외부 접속**: 
   - AWS LoadBalancer를 통해 직접 접속이 가능합니다.
   - **주소**: [http://a312731fa19694e56a1e8aec234ada93-547846460.ap-northeast-2.elb.amazonaws.com:5000](http://a312731fa19694e56a1e8aec234ada93-547846460.ap-northeast-2.elb.amazonaws.com:5000)
2. **관리자 계정 생성**: 초기 설정 화면 진행

### 2.3 Athena 데이터 소스 연결

(기존 내용 유지)

## 3. 검증

### 3.1 연결 테스트
- 모든 파드 정상 실행 확인 (`kubectl get pods -n redash`)
- LoadBalancer 접속 및 로그인 화면 출력 확인

## 4. 문제 해결 (Troubleshooting)

- **ImagePullBackOff (Redis/Postgres)**: 
  - 공인 ECR 이미지 접근 문제로 인해 Private ECR(`capa/redis`, `capa/postgres`)로 복사하여 사용.
- **Internal Server Error (DB Connection)**:
  - Redash가 유닉스 소켓으로 접속 시도하는 문제 해결을 위해 `REDASH_DATABASE_URL`을 명시적으로 설정.
- **DB 초기화 오류**:
  - `python manage.py database create_tables` 명령을 통해 수동으로 테이블 초기화 완료.

---

- **이전 단계**: [11_airflow_배포.md](./11_airflow_배포.md)
- **다음 단계**: [13_report_generator_배포.md](./13_report_generator_배포.md)
