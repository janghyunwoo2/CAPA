# Athena CSV 파일 생성 원인 분석

**작성일**: 2026-03-14  
**문제**: `.athena-temp/`로 설정했음에도 불구하고 CSV와 metadata 파일이 계속 생성되는 문제

---

## 🔍 근본 원인 (Root Cause)

### 1. AWS Athena Workgroup 설정이 코드 설정을 무시함

#### Terraform 워크그룹 설정 (08-athena.tf)
```hcl
resource "aws_athena_workgroup" "capa" {
  name = "${var.project_name}-workgroup"

  configuration {
    enforce_workgroup_configuration = true  # ❗ 핵심 설정
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.data_lake.bucket}/athena-results/"  # 강제 경로
    }
  }
}
```

#### 문제점
- **`enforce_workgroup_configuration = true`**: 워크그룹 설정을 강제로 적용
- 코드에서 설정한 `OutputLocation`이 무시됨
- 모든 쿼리 결과가 `athena-results/` 경로로 저장됨

---

## 📋 현재 상황 분석

### 1. 코드 설정 (의도한 설정)
```python
# config.py
ATHENA_TEMP_RESULTS_PATH = f"s3://{S3_BUCKET}/.athena-temp/"

# athena_utils.py
ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
```

### 2. 실제 동작 (워크그룹이 강제)
- 워크그룹: `capa-workgroup`
- 강제 출력 경로: `s3://capa-data-lake-827913617635/athena-results/`
- 코드 설정 무시됨

### 3. CSV 파일 생성 시나리오

#### 시나리오 A: ETL 프로세스 실행
1. ETL이 Athena 쿼리 실행
2. 워크그룹 설정에 의해 `athena-results/`에 CSV 저장
3. 매시간 24개, 매일 2개의 파일 생성

#### 시나리오 B: AWS 콘솔에서 직접 쿼리
1. 사용자가 AWS Athena 콘솔에서 쿼리 실행
2. 동일한 워크그룹 사용 → `athena-results/`에 저장
3. 수동 쿼리마다 CSV와 metadata 파일 생성

#### 시나리오 C: Glue 크롤러 실행 후 확인 쿼리
1. Glue 크롤러가 새 테이블 생성/업데이트
2. 사용자가 테이블 확인을 위해 쿼리 실행
3. 역시 `athena-results/`에 결과 저장

---

## ✅ 해결 방안

### 방안 1: 워크그룹 설정 변경 (권장)

#### 옵션 A: 워크그룹 강제 설정 해제
```hcl
# terraform/08-athena.tf 수정
configuration {
  enforce_workgroup_configuration = false  # 변경: true → false
  # ... 나머지 설정
}
```
- **장점**: 코드별로 다른 출력 경로 사용 가능
- **단점**: 중앙 관리 어려움

#### 옵션 B: 워크그룹 출력 경로를 .athena-temp로 변경
```hcl
# terraform/08-athena.tf 수정
result_configuration {
  output_location = "s3://${aws_s3_bucket.data_lake.bucket}/.athena-temp/"  # 변경
}
```
- **장점**: 중앙 관리 유지, CSV 파일 격리
- **단점**: 기존 `athena-results/` 사용하는 코드 영향

### 방안 2: 다중 워크그룹 전략

#### 새로운 워크그룹 생성
```hcl
# ETL 전용 워크그룹
resource "aws_athena_workgroup" "etl" {
  name = "${var.project_name}-etl-workgroup"
  
  configuration {
    enforce_workgroup_configuration = true
    result_configuration {
      output_location = "s3://${aws_s3_bucket.data_lake.bucket}/.athena-temp/"
    }
  }
}

# 기존 워크그룹은 콘솔 사용자용으로 유지
```

#### 코드에서 워크그룹 지정
```python
# athena_utils.py 수정
response = self.client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': database},
    ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH},
    WorkGroup='capa-etl-workgroup'  # 추가
)
```

### 방안 3: S3 라이프사이클 정책 (보완책)

두 경로 모두에 라이프사이클 적용:
```json
{
  "Rules": [
    {
      "Id": "DeleteAthenaResults",
      "Status": "Enabled",
      "Filter": {"Prefix": "athena-results/"},
      "Expiration": {"Days": 7}
    },
    {
      "Id": "DeleteAthenaTempResults",
      "Status": "Enabled", 
      "Filter": {"Prefix": ".athena-temp/"},
      "Expiration": {"Days": 3}
    }
  ]
}
```

---

## 🎯 권장 조치

### 즉시 조치
1. **현재 `athena-results/` 폴더의 CSV 파일 수동 정리**
   ```bash
   aws s3 rm s3://capa-data-lake-827913617635/athena-results/ --recursive --exclude "*.parquet"
   ```

2. **S3 라이프사이클 정책 즉시 적용** (임시 완화)

### 단기 조치 (1주일 내)
1. **방안 1B 적용**: 워크그룹 출력 경로를 `.athena-temp/`로 변경
   - Terraform 코드 수정
   - `terraform plan` & `terraform apply`
   - 영향받는 서비스 확인

2. **모니터링 설정**
   - CloudWatch 알람: S3 폴더별 객체 수 모니터링
   - 일일 1,000개 이상 파일 생성 시 알림

### 장기 개선 (1개월 내)
1. **다중 워크그룹 전략 검토**
   - ETL용, 콘솔용, 분석용 워크그룹 분리
   - 각 워크그룹별 최적화된 설정 적용

2. **UNLOAD 명령으로 전환**
   - CSV 중간 파일 없이 직접 Parquet 저장
   - ETL 성능 향상 및 저장 공간 절약

---

## 📊 영향 분석

### 현재 영향
- **저장 공간**: 일일 약 50개 파일 생성 (월 1,500개)
- **비용**: S3 PUT 요청 비용 및 저장 비용 증가
- **성능**: S3 리스트 작업 시 성능 저하 가능
- **관리**: 파일 정리 작업 필요

### 해결 후 기대 효과
- **저장 공간**: 90% 이상 절감
- **비용**: S3 요청 비용 감소
- **성능**: 폴더 구조 단순화로 성능 향상
- **자동화**: 라이프사이클로 자동 관리

---

## 🔗 관련 문서
- [Summary 폴더 CSV 문제 분석](./2026-03-14-summary-folder-csv-metadata-issue.md)
- [Summary 폴더 경로 설정 현황](./2026-03-14-summary-folder-path-settings.md)
- [AWS Athena Workgroup 문서](https://docs.aws.amazon.com/athena/latest/ug/workgroups.html)