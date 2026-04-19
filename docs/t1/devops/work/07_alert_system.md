# 07. Alert 시스템 구축 (CloudWatch + SNS)

> **목표**: 시스템 이상 감지 및 알림 체계 구축
> **참조**: [devops_implementation_guide.md](../devops_implementation_guide.md#12-alert-시스템-구성)
> **소요 시간**: 약 15분

## 1. 사전 준비

- [ ] **Terraform 설정 확인**: `terraform/environments/dev/base` 디렉토리
- [ ] **필요 권한**: `CloudWatchFullAccess`, `SNSFullAccess` (Admin 권한 가정)

## 2. 작업 절차

### 2.1 SNS Topic 생성

**Terraform 파일**: `10-sns.tf`

1. `aws_sns_topic` 리소스 정의 (`capa-alerts`)
2. `aws_sns_topic_subscription` 정의 (프로토콜: `email` 또는 `lambda`)
   - 초기에는 이메일로 테스트 권장

```bash
cd infrastructure/terraform/environments/dev/base
terraform apply -target=aws_sns_topic.capa_alerts
```

### 2.2 CloudWatch Alarms 설정

**Terraform 파일**: `09-cloudwatch.tf`

1. **Kinesis 유입량 감시**:
   - Metric: `IncomingRecords` (Namespace: `AWS/Kinesis`)
   - 조건: 5분간 합계 < 100 (예시)
   - Action: SNS Topic으로 알림 전송

2. **EKS 노드 CPU 감시**:
   - Container Insights 활성화 시 사용 가능
   - 또는 EC2 Metric 사용

```bash
terraform apply -target=aws_cloudwatch_metric_alarm.kinesis_low_traffic
```

## 3. 검증

### 3.1 알람 상태 확인

```bash
aws cloudwatch describe-alarms --alarm-names capa-kinesis-low-traffic
```
- `StateValue`가 `OK` 또는 `ALARM`인지 확인 (`INSUFFICIENT_DATA`는 데이터 대기 필요)

### 3.2 알림 수신 테스트

1. 임계값을 강제로 조정하여 알람 유발 (Terraform 수정)
   - 예: `threshold = 1000000` (항상 미달하게 설정)
2. 이메일/Slack으로 알림 수신 확인

## 4. 문제 해결

- **SNS 구독 승인 대기**: 이메일 구독 시 수신된 메일에서 "Confirm subscription" 클릭 필수
- **데이터 부족**: Kinesis에 Log Generator로 데이터 전송 필요

---

- **이전 단계**: [06_eks_cluster.md](./06_eks_cluster.md)
- **다음 단계**: [08_log_generator.md](./08_log_generator.md)
