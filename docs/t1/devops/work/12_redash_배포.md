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

1. **포트 포워딩**:
   ```bash
   kubectl port-forward -n redash svc/redash 5000:5000
   ```
2. **브라우저 접속**: `http://localhost:5000`
3. **관리자 계정 생성**: 초기 설정 화면 진행

### 2.3 Athena 데이터 소스 연결

1. **Settings** -> **Data Sources** -> **New Data Source**
2. **Amazon Athena** 선택
3. **설정값 입력**:
   - AWS Region: `ap-northeast-2`
   - S3 Staging Directory: `s3://capa-athena-results/` (terraform output 참조)
   - Workgroup: `primary` (또는 생성한 workgroup)
   - *Access Key/Secret Key는 IRSA 사용 시 비워둠 (권장)*

## 3. 검증

### 3.1 연결 테스트

Redash 화면에서 "Test Connection" 클릭 -> **Success** 확인

### 3.2 쿼리 실행 테스트

**New Query**:
```sql
SELECT * FROM capa_logs.impressions LIMIT 10;
```
- 결과가 표출되면 성공

## 4. 문제 해결

- **연결 실패 (Permission Denied)**:
  - Redash Pod의 ServiceAccount에 IAM Role이 제대로 연결되었는지 확인
  - `kubectl describe sa -n redash redash-sa`
  - IAM Role의 Trust Policy 확인

---

- **이전 단계**: [11_airflow_배포.md](./11_airflow_배포.md)
- **다음 단계**: [13_report_generator_배포.md](./13_report_generator_배포.md)
