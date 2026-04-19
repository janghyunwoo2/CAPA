# S3 summary 폴더에 30분마다 CSV 파일이 생성되는 문제

**작성일**: 2026-03-16  
**문제**: 30분마다 summary 폴더에 CSV/metadata 파일이 자동 생성됨

---

## 🎯 원인 분석

### 🔴 확인된 원인: vanna-api의 Athena 쿼리 결과 저장 경로 문제

**1. Terraform 설정 문제**
```terraform
# infrastructure/terraform/11-k8s-apps.tf (Line 548)
env {
  name  = "S3_STAGING_DIR"
  value = "s3://${aws_s3_bucket.data_lake.bucket}/athena-results/"  # ❌ 문제
}
```

**2. Athena WorkGroup 강제 설정**
```terraform
# infrastructure/terraform/08-athena.tf
enforce_workgroup_configuration = true  # 모든 쿼리 결과가 athena-results/로 강제
output_location = "s3://bucket/athena-results/"
```

**결과**: vanna-api 사용 시 모든 쿼리 결과가 summary 폴더에 CSV로 저장되고 있음

---

## ✅ 즉시 실행 가능한 해결 방법

### 1. PowerShell로 즉시 정리 (Windows)

```powershell
# 즉시 실행 - summary 폴더의 CSV와 metadata 파일 삭제
$bucket = "capa-data-lake-827913617635"  # 실제 버킷명

# 삭제할 파일 확인
aws s3 ls "s3://$bucket/summary/" --recursive | 
Where-Object { $_ -match '\.(csv|metadata)$' } |
ForEach-Object {
    $key = ($_ -split '\s+')[-1]
    Write-Host "삭제 중: $key"
    aws s3 rm "s3://$bucket/$key"
}
```

### 2. 자동화 (Windows 작업 스케줄러)

```powershell
# cleanup-summary.ps1 파일 생성
$script = @'
$bucket = "capa-data-lake-827913617635"
aws s3 ls "s3://$bucket/summary/" --recursive | 
Where-Object { $_ -match '\.(csv|metadata)$' } |
ForEach-Object {
    $key = ($_ -split '\s+')[-1]
    aws s3 rm "s3://$bucket/$key"
}
'@

# 스크립트 저장
$script | Out-File -FilePath "C:\scripts\cleanup-summary.ps1"

# Windows 작업 스케줄러에서 30분마다 실행 설정
# Win+R → taskschd.msc → 작업 만들기 → 트리거: 30분마다
```

---

## 🔧 근본 해결 방법

### 1. vanna-api 수정 (WorkGroup 설정 추가)
```python
# services/vanna-api/src/main.py
response = self.athena_client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={"Database": self.athena_database},
    ResultConfiguration={"OutputLocation": self.s3_staging_dir},
    WorkGroup='primary'  # ✅ 추가: Terraform 워크그룹 회피
)
```

### 2. Terraform 환경변수 수정
```terraform
# infrastructure/terraform/11-k8s-apps.tf
env {
  name  = "S3_STAGING_DIR"  
  value = "s3://${aws_s3_bucket.data_lake.bucket}/.athena-temp/"  # ✅ 격리된 경로로 변경
}
```

### 3. Athena WorkGroup 설정 변경
```terraform
# infrastructure/terraform/08-athena.tf
configuration {
  enforce_workgroup_configuration = false  # ✅ 강제 적용 해제
}
```

---

## 📋 요약

**문제**: vanna-api 사용 시 30분마다 summary 폴더에 CSV/metadata 파일 생성

**원인**: Terraform의 Athena WorkGroup이 모든 쿼리 결과를 athena-results/로 강제 지정

**해결**:
1. **즉시 조치**: PowerShell로 CSV 파일 정리
2. **근본 해결**: vanna-api와 Terraform 설정 수정
