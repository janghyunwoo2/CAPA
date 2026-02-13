# 10_1. Terraform 계층 통합 및 문서 현행화 작업 내역

## 1. 개요
*   **작업 일시**: 2026-02-13
*   **작업 목표**: Terraform `base`와 `apps` 계층을 통합하여 단일 `terraform apply`로 인프라와 애플리케이션을 한 번에 배포할 수 있도록 구조 개선 및 문서 현행화.

## 2. 주요 작업 내용

### 2.1 Terraform 구조 개편 (Unified Architecture)
*   **기존**: `base` (EKS, VPC)와 `apps` (Helm Releases)가 분리되어 있어 두 번의 배포 과정 필요.
*   **변경**: `infrastructure/terraform/environments/dev/base` 디렉토리로 통합.
    *   `apps/` 디렉토리 삭제.
    *   `base/10-applications.tf` 파일 생성: 모든 Helm Release (Airflow, Redash, Vanna, Slack Bot, Report Generator 등) 리소스를 이 파일 하나로 통합.
    *   `base/01-providers.tf` 수정: Helm 및 Kubernetes Provider가 EKS 클러스터 정보를 참조하도록 설정.
    *   `base/variables.tf` 수정: Slack Bot/App Token 등 애플리케이션 배포에 필요한 변수 추가 (`sensitive = true`).

### 2.2 Generic Service Helm Chart 개발
*   **경로**: `infrastructure/charts/generic-service`
*   **내용**: 사용자 정의 애플리케이션(Slack Bot, Vanna AI, Report Generator)을 위한 범용 Helm Chart 템플릿 생성.
*   **장점**: 개별 애플리케이션마다 Chart를 만들 필요 없이, `values.yaml` 설정만으로 다양한 마이크로서비스 배포 가능.

### 2.3 문서 현행화 (Documentation Updates)
변경된 배포 구조에 맞춰 관련 문서들을 모두 업데이트함.

*   **`00_작업_전체_로드맵.md`**: 배포 단계를 `Base` + `Apps` 2단계에서 `Unified Base` 1단계로 수정.
*   **`06_eks_cluster.md`**: Terraform 실행 경로 및 절차 수정.
*   **`10_helm_values_준비.md`**: `generic-service` 차트를 사용하는 앱(Slack Bot, Vanna, Report Gen)의 Values 설정 가이드 업데이트.
*   **배포 가이드 (`11` ~ `15`)**:
    *   `11_airflow_배포.md`
    *   `12_redash_배포.md`
    *   `13_report_generator_배포.md`
    *   `14_vanna_ai_배포.md`
    *   `15_slack_bot_echo.md`
    *   모든 가이드의 Terraform 실행 경로를 `infrastructure/terraform/environments/dev/base`로 통일하고, `target` 옵션을 사용한 개별 배포 방법 안내.

## 3. 향후 계획
*   **전체 배포 테스트**: `infrastructure/terraform/environments/dev/base`에서 `terraform apply` 실행.
*   **E2E 검증**: 배포된 서비스들의 연동 및 정상 동작 확인 (Log Generator -> Kinesis -> S3 -> Athena -> Redash/Slack Bot).
