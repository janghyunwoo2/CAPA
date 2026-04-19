# Task 07: Alert 시스템 구축 (Complete)

## 진행 상황 요약
- **작업 일자**: 2026-02-12
- **현재 상태**: **성공 (Success)**
  - SNS Topic 및 Subscription 생성 완료
  - CloudWatch Alarms 4개 생성 완료
  - Terraform outputs 업데이트 완료

## 생성된 리소스
| 리소스 타입 | 이름/ID | 상세 내용 |
|---|---|---|
| **SNS Topic** | `capa-alerts-dev` | Alert 알림 전송용 Topic |
| **SNS Subscription** | `admin@example.com` | Email 구독 (PendingConfirmation 상태) |
| **CloudWatch Alarm** | `capa-kinesis-low-traffic-dev` | Kinesis 유입량 감시 (5분간 10개 미만) |
| **CloudWatch Alarm** | `capa-kinesis-high-iterator-age-dev` | Kinesis 처리 지연 감시 (60초 이상) |
| **CloudWatch Alarm** | `capa-firehose-delivery-failure-dev` | Firehose S3 전송 실패 감시 (15분 이상 지연) |
| **CloudWatch Alarm** | `capa-eks-node-cpu-high-dev` | EKS 노드 CPU 사용률 감시 (80% 이상) |

## 구현된 파일
### 1. 10-sns.tf
```hcl
# SNS Topic 및 Subscription 구현
- aws_sns_topic.capa_alerts
- aws_sns_topic_policy.capa_alerts
- aws_sns_topic_subscription.email_alerts
```

### 2. 09-cloudwatch.tf
```hcl
# CloudWatch Alarms 구현
- aws_cloudwatch_metric_alarm.kinesis_low_traffic
- aws_cloudwatch_metric_alarm.kinesis_high_iterator_age
- aws_cloudwatch_metric_alarm.firehose_delivery_failure
- aws_cloudwatch_metric_alarm.eks_node_cpu_high
```

### 3. variables.tf
```hcl
# Alert 이메일 주소 변수 추가
- variable "alert_email"
```

### 4. outputs.tf
```hcl
# Alert 시스템 관련 outputs 추가
- output "sns_topic_arn"
- output "sns_topic_name"
- output "cloudwatch_alarm_*"
```

## 검증 결과 (Verification)
### 1. CloudWatch Alarms 상태
```bash
aws cloudwatch describe-alarms --alarm-name-prefix "capa-" --region ap-northeast-2
```

**결과**:
| Alarm 이름 | Metric | 상태 |
|-----------|--------|------|
| `capa-kinesis-low-traffic-dev` | IncomingRecords | INSUFFICIENT_DATA |
| `capa-kinesis-high-iterator-age-dev` | GetRecords.IteratorAgeMilliseconds | INSUFFICIENT_DATA |
| `capa-firehose-delivery-failure-dev` | DeliveryToS3.DataFreshness | INSUFFICIENT_DATA |
| `capa-eks-node-cpu-high-dev` | CPUUtilization | INSUFFICIENT_DATA |

> **참고**: `INSUFFICIENT_DATA` 상태는 정상입니다. 아직 충분한 메트릭 데이터가 수집되지 않았음을 의미합니다.
> Task 08 (Log Generator)에서 데이터를 전송하면 `OK` 또는 `ALARM` 상태로 변경됩니다.

### 2. SNS Subscription 상태
```bash
aws sns list-subscriptions --region ap-northeast-2
```

**결과**:
| Topic | Protocol | Endpoint | Status |
|-------|----------|----------|--------|
| `capa-alerts-dev` | email | `admin@example.com` | **PendingConfirmation** |

> **⚠️ 중요**: 이메일 구독은 수동 승인이 필요합니다. AWS에서 발송된 "AWS Notification - Subscription Confirmation" 이메일을 확인하고 "Confirm subscription" 링크를 클릭해야 알림을 받을 수 있습니다.

### 3. Terraform Outputs
```bash
terraform output
```

**Alert System Outputs** (Task 07에서 추가):
- `sns_topic_arn`: `arn:aws:sns:ap-northeast-2:827913617635:capa-alerts-dev`
- `sns_topic_name`: `capa-alerts-dev`
- `cloudwatch_alarm_kinesis_low_traffic`: Kinesis 유입량 알람 ARN
- `cloudwatch_alarm_kinesis_high_iterator_age`: Kinesis 지연 알람 ARN
- `cloudwatch_alarm_firehose_delivery_failure`: Firehose 실패 알람 ARN

**추가 정리된 Outputs**:
Task 07 진행 중 `outputs.tf` 파일에 기존 리소스들의 outputs도 함께 정리함:
- Data Pipeline: Kinesis, S3, Glue, Firehose (7개)
- IAM Roles: EKS Cluster, EKS Node, Firehose (3개)
- EKS outputs는 `06-eks.tf`에 이미 정의됨 (4개)

> **참고**: 전체 18개 outputs 목록은 `terraform output` 명령으로 확인 가능

## 핵심 설정 사항
### 1. SNS Topic Policy
- CloudWatch Alarms가 SNS Topic에 메시지를 게시할 수 있도록 권한 부여
- Principal: `cloudwatch.amazonaws.com`
- Action: `SNS:Publish`

### 2. CloudWatch Alarm 임계값
| Alarm | Threshold | 설명 |
|-------|-----------|------|
| Kinesis Low Traffic | < 10 records/5min | 5분간 10개 미만 유입 시 알림 |
| Kinesis High Iterator Age | > 60,000 ms | 처리 지연 60초 이상 시 알림 |
| Firehose Delivery Failure | > 900 sec | S3 전송 15분 이상 지연 시 알림 |
| EKS Node CPU High | > 80% | CPU 사용률 80% 이상 시 알림 |

### 3. treat_missing_data 설정
- 모든 Alarm에 `treat_missing_data = "notBreaching"` 설정
- 데이터가 없을 때는 정상으로 간주 (불필요한 알림 방지)

## 다음 단계 준비사항
### Task 08: Log Generator 배포
Alert 시스템이 정상 작동하는지 확인하려면 실제 데이터가 필요합니다.

**확인할 사항**:
1. Log Generator → Kinesis Stream으로 데이터 전송
2. CloudWatch Alarm 상태가 `INSUFFICIENT_DATA` → `OK`로 변경
3. 임계값 테스트 (의도적으로 알림 발생)
4. SNS → Email 알림 수신 확인

## 문제 해결 (Troubleshooting)
### 1. Terraform 중복 Output 정의 오류 (실제 발생)
- **문제**: `terraform plan` 실행 시 오류 발생
  ```
  Error: Duplicate output definition
  on outputs.tf line 8:
  output "eks_cluster_endpoint" {
  An output named "eks_cluster_endpoint" was already defined at 06-eks.tf:96,1-30.
  ```
- **원인**: `06-eks.tf` 파일에 이미 EKS 관련 outputs가 정의되어 있었음
  - `eks_cluster_endpoint`
  - `eks_cluster_name`
  - `eks_cluster_certificate_authority_data`
- **해결**:
  - `outputs.tf` 파일에서 중복된 EKS outputs 제거
  - Alert 시스템 관련 outputs만 유지
  - 각 Terraform 파일이 자신의 리소스에 대한 output만 정의하도록 구조 정리
- **교훈**: 
  - 여러 `.tf` 파일에 output이 분산되어 있을 수 있으므로 추가 전에 확인 필요
  - `grep -r "^output" *.tf` 명령으로 기존 output 검색 권장

### 2. Email Subscription 승인
- **문제**: 이메일을 받지 못함
- **해결**:
  - 스팸 폴더 확인
  - variables.tf의 `alert_email` 변수를 실제 이메일 주소로 변경
  - Terraform 재적용: `terraform apply`

### 3. CloudWatch Alarms 상태 확인
- **문제**: Alarm이 생성되지 않음
- **해결**:
  ```bash
  aws cloudwatch describe-alarms --alarm-names capa-kinesis-low-traffic-dev
  ```
  - 리소스 이름 확인
  - Terraform state 확인: `terraform state list | grep cloudwatch`

### 4. SNS Topic 권한 확인
- **문제**: CloudWatch에서 SNS로 알림 전송 실패
- **해결**:
  - Topic Policy 확인
  - CloudWatch Service가 Principal에 포함되어 있는지 확인

## 향후 계획
### Task 08: Log Generator 배포
- Python 스크립트로 샘플 광고 로그 생성
- Kinesis Stream으로 전송
- CloudWatch Alarm 동작 확인

### Task 09: Athena 데이터 검증
- S3에 Parquet 파일 생성 확인
- Athena SELECT 쿼리 실행
- Glue Catalog 테이블 확인

## 리소스 정리 (필요 시)
```bash
# Alert 시스템 리소스만 삭제
terraform destroy \
  -target=aws_cloudwatch_metric_alarm.kinesis_low_traffic \
  -target=aws_cloudwatch_metric_alarm.kinesis_high_iterator_age \
  -target=aws_cloudwatch_metric_alarm.firehose_delivery_failure \
  -target=aws_cloudwatch_metric_alarm.eks_node_cpu_high \
  -target=aws_sns_topic_subscription.email_alerts \
  -target=aws_sns_topic.capa_alerts
```

---

## 요약
✅ **7개 리소스 생성 완료**
- SNS Topic, Subscription, Policy
- CloudWatch Alarms 4개

✅ **검증 완료**
- 모든 Alarm이 INSUFFICIENT_DATA 상태 (정상)
- SNS Subscription이 PendingConfirmation 상태

⚠️ **추가 작업 필요**
- Email Subscription 승인 (수동)
- Log Generator로 실제 데이터 전송하여 Alarm 동작 확인

---

**이전 단계**: [06_complete.md](./06_complete.md)  
**다음 단계**: Task 08 - Log Generator 배포
