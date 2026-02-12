# ✅ 작업 05 완료: Data Pipeline 구축 (Kinesis, Firehose, Glue, S3)

**작업 파일**: [`05_data_pipeline_기본.md`](../work/05_data_pipeline_기본.md)  
**Phase**: 1 (Terraform Base Layer)  
**실행 일시**: 2026-02-12 12:45 - 13:10  
**결과**: ✅ **성공** (자동화 완료 - Provider Downgrade 적용)

---

## 📋 실행 내용

### 1. Terraform 리소스 생성

**위치**: `infrastructure/terraform/environments/dev/base/`

**생성된 파일**:
- `03-kinesis.tf` - Kinesis Data Stream, Firehose 정의
- `04-s3.tf` - Data Lake S3 Bucket 정의
- `05-glue.tf` - Glue Database, Table 정의

---

### 2. Terraform 실행 단계

| 단계 | 명령어 | 결과 | 비고 |
|------|--------|------|------|
| **Init** | `terraform init` | ✅ 성공 | Provider 설치 |
| **Apply (1차)** | `terraform apply` | ❌ 실패 | AWS Provider(Glue) Crash 발생 (v5.100.0) |
| **Auto-Recovery** | 수동 생성 리소스 삭제 후 재배포 (v5.80.0) | ✅ 성공 | 완전 자동화 상태 복구 |
| **Apply (2차)** | `terraform apply` | ❌ 실패 | Firehose Buffer Size 에러 |
| **수정** | Firehose `buffering_size = 64`로 변경 | ✅ 완료 | Parquet 변환 시 최소 64MB 필요 |
| **Apply (3차)** | `terraform apply` | ✅ 성공 | 모든 리소스 생성 완료 |

---

## ✅ 생성된 리소스

| 리소스 | 이름 | 상태 | 용도 |
|--------|------|------|------|
| **S3 Bucket** | `capa-data-lake-827913617635` | ✅ 생성됨 | Raw/Processed 데이터 저장 |
| **Kinesis Stream** | `capa-stream` | ✅ 생성됨 | 실시간 로그 수집 (1 Shard) |
| **Glue Database** | `capa_db` | ✅ 생성됨 | 메타데이터 관리 |
| **Glue Table** | `ad_events_raw` | ✅ 생성됨 | 데이터 스키마 정의 (Parquet) |
| **Kinesis Firehose** | `capa-firehose` | ✅ 생성됨 | Stream → S3 변환 및 전송 |

---

## 🔧 발생한 이슈 및 해결

### 이슈 1: Terraform Provider Crash (Glue)

**증상**: 
```
Error: plugin exited
[DEBUG] provider.stdio: received EOF, stopping recv loop
```

**원인**: 최신 AWS Provider (v5.100.0)의 글루 리소스 처리 관련 버그 추정.

**해결**: 
1. `versions.tf`에서 AWS Provider 버전을 `5.80.0`으로 고정.
2. 기존 State와 충돌 방지를 위해 리소스 정리 후 재배포.

### 이슈 2: Firehose Buffer Size 에러

**증상**:
```
Bs must be at least 64 when data format conversion is enabled
```

**원인**: Firehose에서 Parquet 변환(Data Format Conversion)을 활성화할 경우, 버퍼링 크기가 최소 64MB 이상이어야 함. (기존 5MB 설정)

**해결**:
1. `03-kinesis.tf`의 `extended_s3_configuration` 블록 수정.
2. `buffering_size = 64` 설정 적용.

---

## 📊 검증 결과

### 리소스 확인
```bash
$ aws kinesis list-streams
{
    "StreamNames": [
        "capa-stream"
    ]
}

$ aws firehose list-delivery-streams
{
    "DeliveryStreamNames": [
        "capa-firehose"
    ]
}

$ aws glue get-table --database-name capa_db --name ad_events_raw
# Table Status: ACTIVE
# SerDe: org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe
```

---

## 🎯 작업 완료

Data Pipeline의 핵심 인프라가 모두 구축되었습니다.
- 로그가 `capa-stream`으로 들어오면,
- `capa-firehose`가 이를 받아 Parquet로 변환하고,
- `capa-data-lake-827913617635` S3 버킷에 저장합니다.
- 이 과정의 메타데이터는 `capa_db.ad_events_raw` 테이블이 관리합니다.

---

## 🎯 다음 단계

**Phase 1 계속**:
- [ ] `06_eks_cluster.md` - EKS Cluster 구축
- [ ] `07_alert_system.md` - CloudWatch, SNS

---

**작업 완료 시각**: 2026-02-12 13:10
