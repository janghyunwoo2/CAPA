# CAPA T2 Pipeline Kubernetes 배포 가이드

## 개요
이 가이드는 CAPA T2 데이터 파이프라인을 쿠버네티스 환경에서 각 Task를 독립적인 컨테이너로 실행하는 방법을 설명합니다.

## 사전 요구사항
- Kubernetes 클러스터 (1.20+)
- kubectl 설치 및 설정
- Docker 또는 Podman
- Helm 3.x (Airflow 배포용)
- 충분한 클러스터 리소스 (최소 4 vCPU, 8GB RAM)

## 1. 네임스페이스 생성
```bash
kubectl create namespace airflow
kubectl config set-context --current --namespace=airflow
```

## 2. 스토리지 설정
### 2.1 PersistentVolume 생성
```bash
kubectl apply -f kubernetes/manifests/persistent-volume.yaml
```

### 2.2 PVC 확인
```bash
kubectl get pvc airflow-data-pvc
# STATUS가 Bound인지 확인
```

## 3. ConfigMap 및 Secret 생성
### 3.1 ConfigMap 배포
```bash
kubectl apply -f kubernetes/manifests/configmap.yaml
```

### 3.2 Secret 생성 (실제 값으로 수정 필요)
```bash
# secrets 파일 수정
vim kubernetes/manifests/configmap.yaml

# 배포
kubectl apply -f kubernetes/manifests/configmap.yaml
```

## 4. Docker 이미지 빌드 및 푸시
### 4.1 빌드 스크립트 실행
```bash
# 실행 권한 부여
chmod +x kubernetes/build-and-push.sh

# 빌드 실행 (버전 지정)
./kubernetes/build-and-push.sh v1.0.0
```

### 4.2 수동 빌드 (선택사항)
```bash
# 개별 이미지 빌드
docker build -f kubernetes/docker/Dockerfile.log-generator -t capa/log-generator:v1.0.0 .
docker build -f kubernetes/docker/Dockerfile.data-processor -t capa/data-processor:v1.0.0 .
# ... 나머지 이미지들
```

## 5. Airflow 배포
### 5.1 Helm으로 Airflow 설치
```bash
# Airflow Helm 차트 추가
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# 커스텀 values 파일로 설치
helm install airflow apache-airflow/airflow \
  -f ../airflow/helm/values.yaml \
  --namespace airflow \
  --create-namespace
```

### 5.2 Airflow 상태 확인
```bash
# Pod 상태 확인
kubectl get pods -n airflow

# Airflow 웹서버 접속
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
# http://localhost:8080 접속
```

## 6. DAG 배포
### 6.1 ConfigMap으로 DAG 배포
```bash
# DAG 파일을 ConfigMap으로 생성
kubectl create configmap airflow-dags \
  --from-file=kubernetes/dag_k8s_example.py \
  -n airflow
```

### 6.2 Git-Sync 사용 (권장)
```yaml
# values.yaml에 git-sync 설정 추가
gitSync:
  enabled: true
  repo: https://github.com/your-org/capa-dags.git
  branch: main
  subPath: src/data_pipeline_t2/kubernetes
```

## 7. 실행 및 모니터링
### 7.1 DAG 활성화
1. Airflow UI 접속
2. `capa_t2_pipeline_kubernetes` DAG 찾기
3. 토글 스위치로 활성화

### 7.2 수동 실행
```bash
# CLI로 실행
kubectl exec -it airflow-scheduler-0 -- airflow dags trigger capa_t2_pipeline_kubernetes

# 또는 UI에서 "Trigger DAG" 버튼 클릭
```

### 7.3 로그 확인
```bash
# Task Pod 로그 확인
kubectl logs -l dag_id=capa_t2_pipeline_kubernetes

# Airflow 스케줄러 로그
kubectl logs airflow-scheduler-0

# 실시간 로그 모니터링
kubectl logs -f <pod-name>
```

## 8. 트러블슈팅

### 8.1 Pod가 시작되지 않는 경우
```bash
# Pod 상세 정보 확인
kubectl describe pod <pod-name>

# 이벤트 확인
kubectl get events --sort-by=.metadata.creationTimestamp
```

### 8.2 이미지 Pull 실패
```bash
# ImagePullBackOff 에러 시
# 1. 레지스트리 자격 증명 확인
kubectl create secret docker-registry regcred \
  --docker-server=docker.io \
  --docker-username=<username> \
  --docker-password=<password>

# 2. ServiceAccount에 추가
kubectl patch serviceaccount default -p '{"imagePullSecrets": [{"name": "regcred"}]}'
```

### 8.3 권한 문제
```bash
# RBAC 설정
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: airflow
  name: airflow-worker
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["get", "list"]
EOF

kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: airflow-worker-binding
  namespace: airflow
subjects:
- kind: ServiceAccount
  name: default
  namespace: airflow
roleRef:
  kind: Role
  name: airflow-worker
  apiGroup: rbac.authorization.k8s.io
EOF
```

## 9. 성능 최적화

### 9.1 리소스 최적화
```yaml
# Task별 리소스 조정
resources:
  requests:
    memory: "512Mi"  # 최소 보장
    cpu: "250m"
  limits:
    memory: "1Gi"    # 최대 사용
    cpu: "500m"
```

### 9.2 노드 어피니티
```python
# CPU 집약적 작업은 compute 노드로
node_selector={'workload-type': 'compute'}

# 메모리 집약적 작업은 memory 노드로
node_selector={'workload-type': 'memory'}
```

### 9.3 병렬 처리
```python
# 동적 Task 생성으로 병렬 처리
from airflow.operators.python import PythonOperator

# 파티션 수 결정
partition_count = Variable.get("partition_count", 4)

# 동적 Task 생성
for i in range(partition_count):
    process_task = KubernetesPodOperator(
        task_id=f'process_partition_{i}',
        # ... 설정
    )
```

## 10. 프로덕션 체크리스트

- [ ] 모든 이미지가 버전 태그 사용 (latest 금지)
- [ ] 리소스 limits/requests 적절히 설정
- [ ] PodDisruptionBudget 설정
- [ ] 모니터링 및 알림 설정 (Prometheus, Grafana)
- [ ] 로그 수집 설정 (ELK, Fluentd)
- [ ] 백업 및 복구 계획
- [ ] 보안 스캔 (이미지, 설정)
- [ ] 네트워크 정책 설정
- [ ] 비밀 정보 관리 (Sealed Secrets, Vault)
- [ ] 자동 스케일링 설정 (HPA, VPA)

## 11. 롤백 절차

### 11.1 DAG 롤백
```bash
# 이전 버전으로 롤백
kubectl rollout undo deployment airflow-scheduler

# 특정 버전으로 롤백
kubectl rollout undo deployment airflow-scheduler --to-revision=2
```

### 11.2 이미지 롤백
```bash
# DAG 파일에서 이미지 태그 수정
image='capa/data-processor:v0.9.0'  # 이전 버전

# ConfigMap 업데이트
kubectl create configmap airflow-dags \
  --from-file=kubernetes/dag_k8s_example.py \
  -o yaml --dry-run=client | kubectl apply -f -
```

이 가이드를 따라 CAPA T2 파이프라인을 쿠버네티스 환경에서 성공적으로 배포할 수 있습니다!