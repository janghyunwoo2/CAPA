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

## 현재 프로젝트에 적용하기

### 1. KubernetesExecutor 설정 확인 (이미 완료)
```yaml
# src/airflow/helm/values.yaml
airflow:
  config:
    AIRFLOW__CORE__EXECUTOR: KubernetesExecutor
```

### 2. DAG별 커스텀 이미지 생성

**예시: data_pipeline_t2 DAG용 Dockerfile**
```dockerfile
# Dockerfile.data_pipeline_t2
FROM apache/airflow:2.7.3

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# DAG 코드 복사
COPY src/data_pipeline_t2/dags/ /opt/airflow/dags/
COPY src/data_pipeline_t2/dags/script/ /opt/airflow/plugins/script/

# 데이터 디렉토리 생성
RUN mkdir -p /opt/airflow/data/{raw,processed,analysis,outputs}

USER airflow
```

### 3. KubernetesPodOperator로 DAG 수정

```python
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'capa-t2',
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
}

with DAG(
    'capa_t2_pipeline_k8s',
    default_args=default_args,
    schedule_interval='@daily',
) as dag:
    
    # 로그 생성 Task - 별도 컨테이너
    generate_logs = KubernetesPodOperator(
        namespace='airflow',
        image='capa/log-generator:latest',
        name='generate-logs',
        task_id='generate_logs',
        cmds=['python', '/app/generate_sample_logs.py'],
        env_vars={
            'DATA_PATH': '/data/raw',
            'LOG_COUNT': '10000'
        },
        volume_mounts=[{
            'name': 'data-volume',
            'mount_path': '/data'
        }],
        volumes=[{
            'name': 'data-volume',
            'persistentVolumeClaim': {
                'claimName': 'airflow-data-pvc'
            }
        }],
        is_delete_operator_pod=True,
        get_logs=True,
    )
    
    # 데이터 처리 Task - 별도 컨테이너
    process_data = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-processor:latest',
        name='process-data',
        task_id='process_data',
        cmds=['python', '/app/processor.py'],
        env_vars={
            'INPUT_PATH': '/data/raw',
            'OUTPUT_PATH': '/data/processed'
        },
        volume_mounts=[{
            'name': 'data-volume',
            'mount_path': '/data'
        }],
        volumes=[{
            'name': 'data-volume',
            'persistentVolumeClaim': {
                'claimName': 'airflow-data-pvc'
            }
        }],
        is_delete_operator_pod=True,
        get_logs=True,
    )
    
    # 분석 Task - 별도 컨테이너
    analyze_data = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-analyzer:latest',
        name='analyze-data',
        task_id='analyze_data',
        cmds=['python', '/app/analyzer.py'],
        resources={
            'request_memory': '1Gi',
            'request_cpu': '500m',
            'limit_memory': '2Gi',
            'limit_cpu': '1000m'
        },
        is_delete_operator_pod=True,
        get_logs=True,
    )
    
    generate_logs >> process_data >> analyze_data
```

### 4. 필요한 쿠버네티스 리소스

**PersistentVolumeClaim (데이터 공유용)**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: airflow-data-pvc
  namespace: airflow
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
```

**ConfigMap (설정 공유)**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pipeline-config
  namespace: airflow
data:
  processing_config.yaml: |
    batch_size: 1000
    output_format: parquet
    compression: snappy
```

## 장단점 분석

### 장점
1. **격리성**: 각 Task가 독립적인 환경에서 실행
2. **확장성**: Task별로 다른 리소스 할당 가능
3. **의존성 관리**: Task별 다른 라이브러리 버전 사용 가능
4. **장애 격리**: 한 Task 실패가 다른 Task에 영향 없음
5. **리소스 효율**: 필요한 만큼만 리소스 사용

### 단점
1. **복잡성 증가**: 이미지 빌드/관리 필요
2. **시작 시간**: Pod 생성에 시간 소요 (Cold Start)
3. **데이터 공유**: Volume 또는 Object Storage 필요
4. **디버깅 어려움**: 로그 수집/모니터링 복잡

## 실제 구현 시 고려사항

### 1. 이미지 빌드 파이프라인
```yaml
# GitHub Actions 예시
name: Build DAG Images
on:
  push:
    paths:
      - 'src/data_pipeline_t2/**'
jobs:
  build:
    steps:
      - name: Build and Push
        run: |
          docker build -f Dockerfile.data_pipeline_t2 -t capa/data-pipeline:${{ github.sha }} .
          docker push capa/data-pipeline:${{ github.sha }}
```

### 2. 리소스 최적화
```python
# Task별 리소스 설정
task = KubernetesPodOperator(
    resources={
        'request_memory': '512Mi',  # 최소 필요 메모리
        'limit_memory': '1Gi',      # 최대 사용 메모리
        'request_cpu': '250m',      # 최소 CPU
        'limit_cpu': '500m'         # 최대 CPU
    }
)
```

### 3. 보안 설정
```python
# ServiceAccount 사용
task = KubernetesPodOperator(
    service_account_name='airflow-worker',
    security_context={
        'runAsUser': 1000,
        'runAsNonRoot': True,
        'fsGroup': 2000
    }
)
```

## 추천 구현 방법

현재 프로젝트 상황을 고려하면:

1. **단기적**: 현재 KubernetesExecutor 설정 유지
   - 이미 작동하는 설정
   - 빠른 배포 가능

2. **중기적**: 무거운 Task만 KubernetesPodOperator로 전환
   - 데이터 처리량이 많은 Task 우선
   - 점진적 마이그레이션

3. **장기적**: 모든 DAG를 개별 컨테이너로
   - 완전한 격리와 확장성
   - 마이크로서비스 아키텍처

이 가이드가 도움이 되었길 바랍니다! 추가 질문이나 구체적인 구현 도움이 필요하시면 알려주세요.