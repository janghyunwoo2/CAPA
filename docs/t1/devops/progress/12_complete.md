# Task 12: Redash 배포 (Complete)

## 진행 상황 요약
- **작업 일자**: 2026-02-15
- **현재 상태**: **성공 (Success)**
  - 리소스 제한(Requests/Limits)이 적용된 Redash Helm 배포 완료
  - 노드 안정성 확보 및 헬스체크 최적화 완료
  - Athena 연동을 위한 인프라 준비 완료

## 생성된 리소스
| 리소스 타입 | 이름/ID | 상세 내용 |
|---|---|---|
| **EKS Pod** | `redash-server` | 메인 웹 서버 및 API (LoadBalancer 연결) |
| **EKS Pod** | `redash-scheduler` | 백그라운드 작업 스케줄러 |
| **EKS Pod** | `redash-worker-*` | Adhoc, Scheduled, Generic 워커 (Celery) |
| **EKS Pod** | `redash-postgresql-0` | Redash 메타데이터 DB |
| **EKS Pod** | `redash-redis-master-0` | 결과 캐싱 및 큐용 Redis |
| **Service** | `redash` | 외부 접속용 Load Balancer (Port 5000) |

## 구현된 파일
### 1. redash.yaml (리소스 최적화 적용)
```yaml
server:
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 1000m # 초기 부팅 병목 해결을 위해 1 CPU 허용
      memory: 1Gi
  readinessProbe:
    initialDelaySeconds: 30
    timeoutSeconds: 15
```

### 2. 10-applications.tf
```hcl
resource "helm_release" "redash" {
  name       = "redash"
  repository = "https://getredash.github.io/contrib-helm-chart/"
  chart      = "redash"
  # ... 리소스 제한이 반영된 values 파일 참조
  values = [file("${path.module}/../helm-values/redash.yaml")]
}
```

## 검증 결과 (Verification)
### 1. Pod 상태 (1/1 Ready 확인)
```powershell
kubectl get pods -n redash
```
**결과**: `redash-server`, `scheduler`, `workers` 등 모든 구성 요소가 `1/1 Ready` 및 `Running` 상태 유지.

### 2. 서비스 접속
- **URL**: [접속하기](http://a1620c39521084caa9e065908021c701-374052448.ap-northeast-2.elb.amazonaws.com:5000)
- **상태**: 관리자 계정 생성 화면 정상 출력 확인.

## 문제 해결 (Troubleshooting)

### 1. 노드 NotReady (Resource Exhaustion)
- **문제**: Redash 배포 후 노드 한 대가 `NotReady` 상태로 전환되며 시스템 마비.
- **원인**: Redash 파드들에 리소스 가이드(`Requests/Limits`)가 없어 노드 메모리를 과점유함.
- **해결**: 모든 구성 요소에 노드 사양(`t3.medium`)을 고려한 엄격한 메모리 제한 적용.

### 2. Readiness Probe 실패 (0/1 Running)
- **문제**: 파드는 실행 중이나 `0/1 Ready` 상태에서 정체되고 자가 재시작 반복.
- **원인**: CPU Limit(300m)이 너무 낮아 Python 부팅 속도가 지연되면서 헬스체크 타임아웃 발생.
- **해결**: 
  - Server CPU Limit을 **1000m**으로 burst 가능하게 상향.
  - `initialDelaySeconds`와 `timeoutSeconds`를 늘려 안정적인 부팅 시간 확보.

### 3. Terraform State Lock
- **문제**: 배포 중단 및 재시도 과정에서 `Error acquiring the state lock` 발생.
- **해결**: 백그라운드 프로세스 종료 및 `.terraform.tfstate.lock.info` 수동 삭제 후 클린 재배포.

## 향후 계획
### Task 13: Report Generator 배포
- 생성된 데이터 인프라를 활용하여 리포트 생성기 구축

---
**이전 단계**: [11_complete.md](./11_airflow_배포.md)  
**다음 단계**: Task 13 - Report Generator 배포
