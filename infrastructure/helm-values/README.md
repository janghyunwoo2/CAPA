# Helm Values 디렉토리

## 목적
Kubernetes 애플리케이션의 Helm Chart 설정 파일을 관리합니다.

## 파일 목록

### `airflow.yaml`
Apache Airflow Helm Chart 설정
- Executor 타입 (KubernetesExecutor)
- Resource 할당 (CPU, Memory)
- PersistentVolumeClaim 크기
- Airflow 환경 변수

### `vanna.yaml`
Vanna AI (Text-to-SQL) Helm Chart 설정
- API 서버 설정
- Database 연결 정보 (Secrets Manager 참조)
- Auto-scaling 설정

## 사용 방법

Terraform에서 참조:
```hcl
resource "helm_release" "airflow" {
  name   = "airflow"
  chart  = "airflow"
  values = [file("../../helm-values/airflow.yaml")]
}
```

## 참고 사항
- 민감 정보(비밀번호, API 키)는 AWS Secrets Manager 사용
- Values 파일에 하드코딩 금지
