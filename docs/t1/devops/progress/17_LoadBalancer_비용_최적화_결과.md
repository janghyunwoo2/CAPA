# 💰 Load Balancer 비용 최적화 및 인프라 고도화 보고서

본 문서는 CAPA 프로젝트의 AWS 운영 비용 절감을 위해 수행된 로드밸런서(Load Balancer) 통합 및 인프라 최적화 작업 결과를 기록합니다.

---

## 📅 작업 요약
| 단계 | 작업 항목 | 상태 | 완료 일시 | 주요 성과 |
| :--- | :--- | :---: | :--- | :--- |
| **1단계** | **Report Generator 내부화** | ✅ 완료 | 2026-02-19 09:30 | LB 1개 제거 (월 $18 절감) |
| **2단계** | **LB Controller 및 Ingress 구축** | ✅ 완료 | 2026-02-19 09:40 | 통합 로드밸런싱 기반 마련 |
| **3단계** | **ALB Ingress 통합 (Airflow/Redash)** | ✅ 완료 | 2026-02-19 10:00 | LB 2개 -> 1개 통합 (월 $18 절감) |
| **4단계** | **Terraform 배포 안정화** | ✅ 완료 | 2026-02-19 10:10 | 레이스 컨디션 예외 처리 반영 |

---

## 🔍 [1단계] Report Generator 서비스 타입 전환

### 1) 배경 및 목적
- **현상**: Slack Bot이 내부적으로만 호출하는 `report-generator`가 `LoadBalancer` 타입으로 설정되어 불필요한 공인 IP 및 ALB 비용 발생.
- **목적**: 외부 노출 불필요 서비스의 내부 전용 서비스(`ClusterIP`) 전환을 통한 즉각적 비용 절감.

### 2) 작업 내용
- `11-k8s-apps.tf`: 서비스 타입을 `LoadBalancer` -> `ClusterIP`로 변경.
- `outputs.tf`: 외부 URL 출력 제거 및 내부 DNS 가이드 추가.

### 3) 결과
- **비용**: 월 약 $18 절감 성공.
- **기능**: 클러스터 내부 통신(`http://report-generator.report.svc.cluster.local:8000`)으로 안정적 유지 확인.

---

## 🔍 [2단계] AWS Load Balancer Controller 구축 (고도화)

### 1) 기술적 배경
- EKS에서 하나의 Application Load Balancer(ALB)를 여러 서비스가 공유하려면 **AWS Load Balancer Controller**가 필수적임.
- Standard Ingress 리소스를 실제 AWS ALB 리소스로 변환해주는 역할을 수행.

### 2) 핵심 구현 사항
- **IRSA (IAM Roles for Service Accounts)**: 컨트롤러가 AWS 리소스를 제어할 수 있도록 전용 IAM Policy와 Role을 생성하여 Pod에 주입.
- **Helm Integration**: `12-lb-controller.tf`를 통해 `aws-load-balancer-controller`를 자동 설치하도록 구성.

---

## 🔍 [3단계] ALB Ingress 통합 및 입구 단일화

### 1) 아키텍처 설계
- **통합 방식**: `alb.ingress.kubernetes.io/group.name` 어노테이션을 사용하여 서로 다른 네임스페이스(`airflow`, `redash`)에 있는 Ingress를 하나의 전용 ALB로 병합.
- **경로 기반 라우팅**:
    - `/airflow/*` -> Airflow Webserver (ClusterIP)
    - `/*` (Root) -> Redash Server (ClusterIP)

### 2) 트러블슈팅 및 시행착오 (Trials & Errors)
- **Ingress Class 인식 문제**:
    - **증상**: Ingress 리소스를 생성했으나 ALB가 생성되지 않음.
    - **해결**: 최신 규격에 따라 `spec.ingressClassName: alb`를 명시적으로 추가하여 컨트롤러가 인식하도록 수정.
- **서브넷 자동 감지(Discovery) 실패**:
    - **증상**: 컨트롤러 로그에서 서브넷을 찾을 수 없다는 오류 발생.
    - **해결**: VPC 서브넷에 필수 태그(`kubernetes.io/role/elb = 1`)를 테라폼(`aws_ec2_tag`)으로 강제 주입하여 해결.
- **Airflow Base URL 불일치**:
    - **증상**: `/airflow/` 접속 시 정적 파일(CSS/JS)이 로드되지 않음.
    - **해결**: `airflow.yaml` 설정에 `AIRFLOW__WEBSERVER__BASE_URL`을 인드레스 경로와 일치시켜 리다이렉션 로직 수정.

---

## 🔍 [4단계] Terraform 안정화 (Race Condition 해결)

### 1) 문제 현상
- 로드밸런서가 신규 생성될 때, AWS에서 DNS 주소가 할당되기 전 테라폼이 `outputs`를 읽으려 시도하다가 에러가 발생하며 전체 배포 프로세스가 중단됨.

### 2) 해결 방안
- **`try()` 함수 도입**: `outputs.tf`에서 주소를 가져올 때 에러가 나면 "Still-Provisioning-Wait-2-Min"이라는 문자열을 반환하도록 예외 처리.
- **결과**: 인프라 생성과 정보 출력을 분리하여 재배포 시 끊김 없는(Non-breaking) 자동화 구현.

---

## 📊 최종 결과 비교

| 항목 | 최적화 전 | 최적화 후 | 비고 |
| :--- | :--- | :--- | :--- |
| **총 로드밸런서 수** | 3개 (ALB) | **1개 (ALB)** | 66% 감소 |
| **월간 예상 비용** | ~$54 | **~$18** | **월 $36 절감** |
| **접속 일원화** | 개별 도메인 3개 | **통합 단일 도메인** | 관리 포인트 축소 |

### 🏆 판정: ✅ **Pass & Cost-Optimized**
> 단순히 비용만 줄인 것이 아니라, 기술적으로 고도화된 **Ingress Controller 아키텍처**를 도입하여 향후 서비스 확장에 유연하게 대응할 수 있는 기반을 마련함.
