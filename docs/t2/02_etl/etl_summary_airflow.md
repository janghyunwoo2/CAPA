# Airflow 가이드 (통합본)

본 문서는 아래 문서들을 하나로 통합한 버전입니다.

- airflow_dag_design.md
- airflow_kubernetes_deployment.md
- aiflow_redash.md (철자 보정: Airflow Redash)

---

## Airflow DAG 설계 (원문)

<!-- 출처: docs/t2/airflow_dag_design.md -->

# Airflow DAG 설계: Hourly / Daily Summary

## 1. 설계 결정 사항

### Q1. 파일을 2개로 만들 것인가, 1개로 만들 것인가?

**결론: 2개 파일로 분리**

| 기준 | 1개 파일 | 2개 파일 (채택) |
|------|----------|----------------|
| schedule 관리 | 한 파일에 다른 주기 혼재 → 복잡 | 파일당 1 DAG, 주기 명확 |
| 배포/수정 | hourly 수정 시 daily에도 영향 | 독립적 배포 가능 |
| 모니터링 | Airflow UI에서 구분 어려움 | 개별 DAG 상태 확인 용이 |
| 커뮤니티 표준 | - | 파일당 1 DAG이 Airflow 표준 패턴 |

### Q2. 일 단위 summary 생성 전략

**비교 대상:**
- (A) 원천 로그 3개(impression, click, conversion)를 한번에 합침
- (B) hourly summary(impression+click) 재집계 + conversion만 원천에서 조인

**결론: (B) hourly summary 재집계 + conversion 조인**

| 기준 | (A) 원천 3개 한번에 | (B) hourly 재집계 + conversion (채택) |
|------|---------------------|--------------------------------------|
| Athena 스캔량 | 하루치 impression+click+conversion 전체 스캔 | hourly summary(소량) + conversion만 스캔 |
| 비용 | 높음 (대량 원천 데이터 재스캔) | **낮음** (이미 집계된 데이터 활용) |
| 속도 | 느림 | **빠름** (hourly summary는 24개 파티션, 집계 완료 상태) |
| 데이터 일관성 | 원천에서 직접 계산하므로 일관적 | hourly와 daily가 동일 소스 기반으로 일관적 |
| 중복 계산 | impression+click 조인을 다시 수행 | 조인은 hourly에서 이미 완료 |

### Q3. Conversion도 1시간 단위로 미리 summary할 것인가? (DAG 3개 체제)

**결론: 하지 않음 → DAG 2개 유지**

근거 (회의록 기반):
- "CVR(전환율)은 시간 단위 집계에서는 적용 X" — 시간 단위 conversion 집계는 비즈니스 의미가 없음
- "전환 로그의 특성: 노출/클릭 대비 늦게 발생하는 경향" — hourly로 자르면 데이터 누락 위험
- conversion 로그는 impression/click 대비 양이 매우 적음 (CVR 20% 가정 시 click의 20%)
- DAG 3개는 운영 복잡도만 증가시킴 (모니터링 포인트 증가, 의존성 관리 복잡)

## 2. 최종 아키텍처

... (원문 전체 내용 포함)

---

## Airflow 쿠버네티스 배포 (원문)

<!-- 출처: docs/t2/airflow_kubernetes_deployment.md -->

# Airflow DAG 쿠버네티스 컨테이너 배포 가이드

## 구현 가능성
✅ **완전히 가능합니다!** Airflow는 쿠버네티스 환경에서 DAG를 개별 컨테이너로 실행하는 여러 방법을 제공합니다.

## 주요 구현 방법

### 1. KubernetesExecutor 사용 (현재 프로젝트에 이미 설정됨)
```yaml
# 이미 values.yaml에 설정되어 있음
AIRFLOW__CORE__EXECUTOR: KubernetesExecutor
```

**작동 방식:**
- 각 Task가 독립적인 Pod로 실행됨
- Task 완료 후 Pod는 자동 종료
- 리소스 효율적, 자동 스케일링

### 2. KubernetesPodOperator 사용
각 Task를 커스텀 컨테이너로 실행하는 방법:

```python
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator

# DAG 내에서 사용
task1 = KubernetesPodOperator(
    namespace='airflow',
    image='your-custom-image:latest',
    name='process-data-task',
    task_id='process_data',
    is_delete_operator_pod=True,
    in_cluster=True,
    get_logs=True,
)
```

### 3. CeleryKubernetesExecutor (하이브리드)
빠른 작업은 Celery로, 무거운 작업은 K8s Pod로 실행:

```python
# airflow.cfg 설정
executor = CeleryKubernetesExecutor

# DAG에서 지정
@task.kubernetes(
    image='data-processing:latest',
    namespace='airflow'
)
def heavy_processing():
    # 이 작업은 별도 Pod에서 실행됨
    pass
```
