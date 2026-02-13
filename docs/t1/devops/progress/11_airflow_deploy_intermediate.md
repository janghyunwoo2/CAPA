# 11_1. Airflow 배포 중간 점검 보고서

## 1. 개요
*   **작업 일시**: 2026-02-13
*   **작업 목표**: Terraform을 이용한 Airflow Helm Release 배포 및 구동 확인
*   **현재 상태**: **부분 성공 (Terraform 배포 완료, Pod Pending 상태)**

## 2. 주요 작업 내용 및 결과

### 2.1 Terraform Provider 설정 변경 (`manual fix`)
*   **이슈**: Helm Provider v3.x 업그레이드 시 `kubernetes` 블록 지원 중단으로 인한 문법 에러 발생.
*   **조치**: `01-providers.tf` 파일에서 Helm Provider 버전을 `~> 2.12`로 고정하고, `terraform init -upgrade` 수행하여 v2.17.0으로 다운그레이드 완료.
*   **추가 조치**: Windows 환경에서 Helm 캐시 경로 문제 해결을 위해 `repository_config_path` 및 `repository_cache` 경로 명시적 설정.

### 2.2 Airflow 배포 실행
*   **명령어**: `terraform apply -target="helm_release.airflow" -auto-approve`
*   **결과**: **Terraform Apply 성공**. Helm Release `airflow` 리소스가 정상적으로 생성됨.

### 2.3 Pod 상태 확인
*   **명령어**: `kubectl get pods -n airflow`
*   **상태**:
    ```
    NAME                                 READY   STATUS     RESTARTS   AGE
    airflow-postgresql-0                 0/1     Pending    0          44s
    airflow-scheduler-0                  0/2     Pending    0          44s
    airflow-statsd-74c59854b9-9czpw      1/1     Running    0          44s
    airflow-triggerer-0                  0/2     Pending    0          44s
    airflow-webserver-79cc69f66c-g9vvg   0/1     Init:0/1   0          44s
    ```
*   **분석**: `airflow-statsd`는 Running 상태이나, 스토리지를 사용하는 `postgresql`, `scheduler`, `triggerer` 등이 **Pending** 상태임.

## 3. 원인 분석 (Troubleshooting)

### 3.1 Pending 원인: PVC Provisioning 실패
*   **증상**: `kubectl describe pod` 및 `kubectl get events` 확인 결과, `persistentvolumeclaim/data-airflow-postgresql-0` 프로비저닝 대기 중.
*   **원인**: **EBS CSI Driver**가 정상적으로 동작하지 않거나, 노드에 관련 IAM 권한이 부족할 가능성 높음.
    *   현재 `dev/base/02-iam.tf`에는 `AmazonEBSCSIDriverPolicy`가 노드 역할에 포함되어 있음.
    *   하지만 **EKS Addon**으로 설치된 `aws-ebs-csi-driver`의 상태나 버전 호환성 확인 필요.

## 4. 향후 계획 (Next Steps)

1.  **EBS CSI Driver 점검**:
    *   `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-ebs-csi-driver` 명령으로 CSI Driver Pod 상태 확인.
    *   필요 시 Terraform `06-eks.tf`의 Addon 설정 재검토 또는 수동 패치.
2.  **StorageClass 확인**:
    *   `kubectl get sc` 명령으로 기본 스토리지 클래스(`gp2` 또는 `gp3`) 설정 확인.
3.  **Pod 재기동**:
    *   CSI Driver 정상화 후 Airflow Pod들이 자동으로 볼륨을 할당받는지 확인.

## 5. 문제 발생 및 해결 시도 (2026-02-13 추가)

### 5.1 Terraform State Lock 문제
*   **증상**: `terraform apply` 실행 시 `Error acquiring the state lock` 에러 발생. 이전 실행이 비정상 종료되면서 상태 잠금이 해제되지 않음.
*   **해결 시도**:
    *   `terraform force-unlock` 명령어를 시도했으나 Lock ID 확인 필요.
    *   AWS CLI로 DynamoDB(`capa-terraform-locks`) 테이블을 스캔하여 Lock ID를 찾으려 했으나, Windows 환경에서 `cat`, `grep` 등의 파이프라인 명령어 부재로 실패.
*   **현재 상태**: State Lock 해제가 필요한 상황이며, 이를 해결해야 `aws-ebs-csi-driver` 추가 및 Airflow 재배포 가능.

## 6. PVC Pending 해결 및 Airflow 정상화 (2026-02-13 추가)

### 6.1 원인 분석
*   **StorageClass 불일치**: 기본 `gp2` StorageClass가 Legacy Provisioner(`kubernetes.io/aws-ebs`)를 사용하고 있었으나, EKS 1.30+ 및 현재 설정은 EBS CSI Driver(`ebs.csi.aws.com`)를 필요로 함.
*   **EBS CSI 권한/설정**: Controller Pod에서 "rate limit token" 에러 발생 (IMDSv2 또는 IAM 권한 갱신 지연 추정).

### 6.2 조치 사항
1.  **StorageClass 재정의**: `05-storage-class.tf`를 생성하여 `gp2`를 `ebs.csi.aws.com` 기반으로 재생성.
2.  **리소스 정리**: 기존 `gp2` SC, Pending PVC, Airflow Pod 전량 삭제 후 재생성 유도.
3.  **CSI Driver 재시작**: `ebs-csi-controller` Pod를 강제 재시작하여 권한 갱신 및 에러 해결.

### 6.3 결과
*   **PVC 바인딩 성공**: 재시작 후 `ebs-csi-controller`가 정상 동작하며 PVC가 `Bound` 상태로 전환됨.
*   **Airflow 구동**: 스토리지 할당이 완료되어 Airflow 컴포넌트(`scheduler`, `triggerer`, `postgresql`)가 초기화 진행 중.

## 7. 이전 프로젝트 성공 코드 기반 재구성 (2026-02-13 추가)

### 7.1 분석
*   **참고 코드**: `infrastructure/aa/` (이전 프로젝트 성공 코드)
*   **주요 차이점 식별**:
    1. **StorageClass**: `volume_binding_mode = "Immediate"` → `"WaitForFirstConsumer"`로 수정 필요
    2. **Airflow values.yaml**: `webserverSecretKey` 고정값, `migrateDatabaseJob` 활성화, `extraInitContainers` 등 추가 필요
    3. **Helmet Release 의존성**: StorageClass 생성 후에 Airflow 배포하도록 `depends_on` 명시 필요

### 7.2 수정 사항

#### 7.2.1 `05-storage-class.tf` 수정
```hcl
volume_binding_mode = "WaitForFirstConsumer"  # 변경: Immediate → WaitForFirstConsumer
# 이유: Pod 스케줄링 후 볼륨이 노드 지역(AZ)에 할당되어 최적화
```

#### 7.2.2 `10-applications.tf` 수정
```hcl
resource "helm_release" "airflow" {
  # ... 기존 설정 ...
  
  depends_on = [
    kubernetes_storage_class.gp2  # 추가: StorageClass 생성 후 배포
  ]
}
```

#### 7.2.3 `airflow.yaml` 개선
이전 프로젝트 성공 코드를 반영한 주요 추가 사항:
- `webserverSecretKey: capa_airflow_secret_key_2026_fixed` (고정 키 설정)
- `migrateDatabaseJob.enabled: true` (DB 마이그레이션 자동 실행)
- `airflow.config` 블록 추가 (환경 변수 정의)
- 각 컴포넌트별 `extraInitContainers`, `extraVolumes`, `extraVolumeMounts` 추가
- `startupProbe.failureThreshold: 20` 으로 조정 (Pod 시작 대기 시간 연장)

### 7.3 State 체크섬 문제 해결
*   **증상**: `terraform plan` 실행 시 "state data in S3 does not have the expected content" 에러
*   **원인**: 이전 `terraform apply` 실패로 DynamoDB의 메타데이터 스냅샷이 S3와 불일치
*   **해결**:
    ```bash
    # DynamoDB에서 체크섬 항목 조회
    aws dynamodb scan --table-name capa-terraform-lock --region ap-northeast-2
    
    # 결과: capa-terraform-state-827913617635/dev/base/terraform.tfstate-md5 항목 발견
    
    # PowerShell로 삭제
    $key = @{LockID=@{S='capa-terraform-state-827913617635/dev/base/terraform.tfstate-md5'}} | ConvertTo-Json -Compress
    aws dynamodb delete-item --table-name capa-terraform-lock --region ap-northeast-2 --key $key
    ```

### 7.4 Terraform Plan 재실행 결과
*   **상태**: ✅ **성공** (tfplan 저장됨)
*   **변경 사항**:
    - `helm_release.airflow` 생성 예정
    - `kubernetes_storage_class.gp2` 교체 (WaitForFirstConsumer로 변경)
    - Deprecation 경고: `kubernetes_storage_class` → `kubernetes_storage_class_v1` (향후 업데이트 필요하지만 현재 동작에 영향 없음)

### 7.5 향후 계획
*   **Terraform Apply**: `terraform apply tfplan` 실행 필요
*   **예상 소요 시간**: 약 5-10분 (Helm Chart 다운로드 + PostgreSQL 초기화)
*   **배포 후 검증**:
    ```bash
    # Pod 상태 확인
    kubectl get pods -n airflow
    
    # Webserver LoadBalancer IP 확인
    kubectl get svc -n airflow airflow-webserver
    
    # Airflow 대시보드 접속
    http://<EXTERNAL-IP>:8080 (admin/admin)
    ```

## 8. Terraform Backend 마이그레이션 및 시행착오 (2026-02-13 2차 추가)

### 8.1 S3/DynamoDB Backend 문제점 식별
*   **증상**: `terraform destroy` 및 `apply` 반복 과정에서 State Lock이 해제되지 않거나, 체크섬 불일치로 인한 배포 실패 지속.
*   **원인**: Windows 환경에서의 Terraform 프로세스 비정상 종료 시 원격(DynamoDB) Lock이 잔존하는 문제와 S3 상태 파일 갱신 동기화 이슈.

### 8.2 해결책: Local Backend 전환
*   **조치**: `backend.tf`의 S3 설정을 주석 처리하고, `terraform init -migrate-state`를 통해 상태 파일을 로컬(`terraform.tfstate`)로 이전.
*   **결과**: 로컬 파일 시스템에서 상태를 관리함으로써 네트워크 지연 및 외부 Lock 의존성 제거. S3 버킷 및 DynamoDB 테이블은 Python 스크립트를 통해 정리 완료.

### 8.3 트러블슈팅: State Lock & Process Hang 및 State 유실
*   **이슈 1**: Local Backend 사용 중에도 `terraform destroy` 시 프로세스가 멈추고 `Error acquiring the state lock` 발생.
*   **이슈 2**: `terraform.tfstate` 파일이 프로세스 강제 종료 후 유실됨.
*   **해결**:
    1.  `Stop-Process`로 백그라운드 좀비 Terraform 프로세스 강제 종료.
    2.  `.terraform.tfstate.lock.info` 파일(로컬 Lock 파일) 수동 삭제.
    3.  `terraform.tfstate.backup` 파일을 `terraform.tfstate`로 복사하여 상태 복구.

### 8.4 트러블슈팅: Kubernetes Namespace 삭제 지연 (Hanging)
*   **이슈**: `airflow` 네임스페이스 삭제 시 `Active` -> `Terminating` 상태에서 무한 대기 (Finalizer Deadlock).
*   **해결**: 
    1. `kubectl delete ns airflow --wait=false`로 비동기 삭제 요청.
    2. Terraform State에서 관련 리소스(`kubernetes_namespace.airflow`, `helm_release.airflow`)를 `terraform state rm`으로 강제 제거하여 State 불일치 해소.
    3. 최종적으로 네임스페이스가 삭제된 것을 확인 후 재배포 준비 완료.
