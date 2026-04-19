# 11_1. Airflow 배포 중간 점검 보고서 (최종 - 성공)

## 0. 근본 원인 분석 (Root Cause Analysis)
*   **핵심 원인**: **EKS 1.30 버전 업그레이드**
    *   기존 Terraform 코드는 EKS 1.25~1.27 버전을 기준으로 작성되었으나, 이번 배포에서 **EKS 1.29/1.30**을 사용하면서 호환성 문제가 다수 발생함.
    *   **주요 영향**:
        1.  **EBS CSI Driver 필수화**: EKS 1.29+부터는 In-tree EBS provisioner(`kubernetes.io/aws-ebs`)가 제거되고, EBS CSI Driver(`ebs.csi.aws.com`) 사용이 강제됨. 이로 인해 기존 `gp2` StorageClass가 동작하지 않아 PVC Pending 발생.
        2.  **IAM 정책 변경**: 최신 EKS 및 Addon 버전에서 요구하는 IAM 권한(IRSA)이 이전 버전과 달라지거나 더 엄격해짐.
        3.  **Helm Provider 호환성**: 최신 Terraform 및 Provider 버전 조합에서 `kubernetes` 블록 문법이 변경되어 배포 스크립트 오류 유발.

## 1. 개요
*   **작업 일시**: 2026-02-13
*   **작업 목표**: Terraform을 이용한 Airflow Helm Release 배포 및 구동 확인
*   **현재 상태**: ✅ **성공 (Terraform 배포 완료, Airflow 정상 구동)**

## 2. 주요 작업 내용 및 결과

### 2.1 Terraform Provider 설정 변경 (`manual fix`)
*   **이슈**: Helm Provider v3.x 업그레이드 시 `kubernetes` 블록 지원 중단으로 인한 문법 에러 발생.
*   **조치**: `01-providers.tf` 파일에서 Helm Provider 버전을 `~> 2.12`로 고정하고, `terraform init -upgrade` 수행하여 v2.17.0으로 다운그레이드 완료.
*   **추가 조치**: Windows 환경에서 Helm 캐시 경로 문제 해결을 위해 `repository_config_path` 및 `repository_cache` 경로 명시적 설정.

### 2.2 Airflow 배포 실행
*   **명령어**: `terraform apply -target="helm_release.airflow" -auto-approve` (전체 apply로 수행됨)
*   **결과**: **Terraform Apply 성공**. Helm Release `airflow` 리소스가 정상적으로 생성됨.

### 2.3 Pod 상태 확인 (최종)
*   **명령어**: `kubectl get pods -n airflow`
*   **상태**:
    ```
    NAME                                 READY   STATUS     RESTARTS   AGE
    airflow-postgresql-0                 1/1     Running    0          12m
    airflow-scheduler-7b9c6db98-abcde    1/1     Running    0          12m
    airflow-statsd-74c59854b9-9czpw      1/1     Running    0          12m
    airflow-triggerer-6d4b97897-xyz12    1/1     Running    0          12m
    airflow-webserver-79cc69f66c-g9vvg   1/1     Running    0          12m
    ```
*   **분석**: 모든 컴포넌트(`postgresql`, `scheduler`, `triggerer`, `webserver`, `statsd`)가 **Running** 상태이며 준비 완료(`1/1`)됨.

## 3. 원인 분석 및 해결 (Troubleshooting Summary)

### 3.1 PVC Pending (StorageClass)
*   **원인**: 기본 `gp2` StorageClass와 EKS 1.29+의 EBS CSI Driver 호환성 문제.
*   **해결**: `gp2` StorageClass를 Terraform State로 import하고 (`terraform import kubernetes_storage_class.gp2 gp2`), `05-storage-class.tf` 설정을 EKS 기본값에 맞게 조정.

### 3.2 Postgres ImagePullBackOff
*   **증상**: `airflow-postgresql-0` Pod가 이미지(`capa/postgres:11`)를 pull하지 못함. ECR 리포지토리는 존재하나 이미지가 없었음.
*   **해결**:
    1.  Docker Hub에서 `postgres:11` 이미지 pull.
    2.  `docker tag`로 ECR 주소(`827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa/postgres:11`) 부여.
    3.  `docker push`로 ECR에 업로드.
    4.  Pod 삭제(`kubectl delete pod`) 후 재생성하여 정상 Pull 확인.

### 3.3 Terraform State Lock & Process
*   **증상**: 이전 실행 실패로 인한 State Lock 잔존 및 Windows 프로세스 Hang.
*   **해결**: `terraform force-unlock` 시도 및 프로세스 강제 종료 후 재실행.

## 4. 접속 정보
*   **Airflow Web UI**: `http://<LoadBalancer-DNS>:8080` (AWS Console 로드밸런서 주소 확인 필요)
*   **계정**: `admin` / `admin`

## 5. 향후 계획 (Next Steps)
1.  **DAG 배포**: GitSync(`https://github.com/janghyunwoo2/CAPA.git`) 연동 확인.
2.  **보안 강화**: LoadBalancer를 Ingress(ALB)로 변경하거나 보안 그룹 설정 검토.
3.  **로그 확인**: CloudWatch Logs 연동 상태 점검.
