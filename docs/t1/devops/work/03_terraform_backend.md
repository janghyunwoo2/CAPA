# 작업 03: Terraform Backend 설정

> **Phase**: 1 (Terraform Base Layer)  
> **담당**: Infra Architect  
> **예상 소요**: 10분  
> **선행 작업**: 02_저장소_구조_설정.md

---

## 1. 목표

Terraform State를 안전하게 저장하고 동시 실행을 방지하기 위해 S3 Backend + DynamoDB Locking을 설정합니다.

---

## 2. 왜 필요한가?

| 항목 | Local State | S3 Backend (권장) |
|------|-------------|-------------------|
| **State 저장 위치** | 로컬 PC (`.tfstate` 파일) | S3 Bucket (원격) |
| **팀 협업** | ❌ 공유 불가 | ✅ 팀원 모두 동일 State 사용 |
| **동시 실행 방지** | ❌ 충돌 위험 | ✅ DynamoDB Locking |
| **State 유실** | ❌ PC 고장 시 복구 불가 | ✅ S3 버전 관리 |

---

## 3. 실행 단계

### 3.1 AWS 콘솔에서 S3 Bucket 생성

**방법 1: AWS CLI (권장)**
```powershell
# S3 Bucket 생성
aws s3api create-bucket `
    --bucket capa-terraform-state-<YOUR_ACCOUNT_ID> `
    --region ap-northeast-2 `
    --create-bucket-configuration LocationConstraint=ap-northeast-2

# 버전 관리 활성화
aws s3api put-bucket-versioning `
    --bucket capa-terraform-state-<YOUR_ACCOUNT_ID> `
    --versioning-configuration Status=Enabled

# 암호화 활성화
aws s3api put-bucket-encryption `
    --bucket capa-terraform-state-<YOUR_ACCOUNT_ID> `
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }'
```

**방법 2: Terraform으로 생성 (추천)**
```hcl
# infrastructure/terraform/bootstrap/backend.tf
resource "aws_s3_bucket" "terraform_state" {
  bucket = "capa-terraform-state-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name    = "CAPA Terraform State"
    Project = "CAPA"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_caller_identity" "current" {}
```

### 3.2 DynamoDB Table 생성

```powershell
# DynamoDB Table 생성 (State Locking용)
aws dynamodb create-table `
    --table-name capa-terraform-lock `
    --attribute-definitions AttributeName=LockID,AttributeType=S `
    --key-schema AttributeName=LockID,KeyType=HASH `
    --billing-mode PAY_PER_REQUEST `
    --region ap-northeast-2
```

**Terraform으로 생성**:
```hcl
# infrastructure/terraform/bootstrap/backend.tf (추가)
resource "aws_dynamodb_table" "terraform_lock" {
  name         = "capa-terraform-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  
  attribute {
    name = "LockID"
    type = "S"
  }
  
  tags = {
    Name    = "CAPA Terraform Lock Table"
    Project = "CAPA"
  }
}
```

### 3.3 Terraform Backend 설정 파일 생성

`infrastructure/terraform/environments/dev/base/backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "capa-terraform-state-123456789012"  # YOUR_ACCOUNT_ID로 변경
    key            = "dev/base/terraform.tfstate"
    region         = "ap-northeast-2"
    dynamodb_table = "capa-terraform-lock"
    encrypt        = true
  }
}
```

### 3.4 Backend 초기화

```powershell
cd infrastructure\terraform\environments\dev\base

# Backend 초기화
terraform init

# 예상 출력:
# Initializing the backend...
# Successfully configured the backend "s3"!
```

---

## 4. 검증 방법

### 4.1 S3 Bucket 확인

```powershell
# S3 Bucket 존재 확인
aws s3 ls | Select-String "capa-terraform-state"

# 예상 출력: capa-terraform-state-123456789012
```

### 4.2 DynamoDB Table 확인

```powershell
# DynamoDB Table 확인
aws dynamodb describe-table --table-name capa-terraform-lock --region ap-northeast-2

# 예상 출력: TableStatus: "ACTIVE"
```

### 4.3 Terraform Backend 연결 확인

```powershell
cd infrastructure\terraform\environments\dev\base

# Backend 상태 확인
terraform init

# 성공 시:
# Backend configuration changed!
# Terraform has been successfully initialized!
```

### 4.4 성공 기준

- [ ] S3 Bucket `capa-terraform-state-*` 생성됨
- [ ] S3 버전 관리 활성화됨
- [ ] DynamoDB Table `capa-terraform-lock` 생성됨
- [ ] `terraform init` 성공
- [ ] `.terraform/` 폴더 생성됨

---

## 5. 실패 시 대응

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `BucketAlreadyExists` | S3 Bucket 이름 중복 | Account ID를 suffix로 추가 |
| `AccessDenied` | IAM 권한 부족 | S3, DynamoDB 권한 확인 |
| `Error loading state` | Backend 미설정 | `backend.tf` 파일 확인 |
| `Error locking state` | DynamoDB Table 없음 | Table 생성 확인 |

---

## 6. 추가 설정 (선택사항)

### 6.1 S3 Lifecycle Policy (비용 절감)

```powershell
# 90일 이상 된 State 버전 삭제
aws s3api put-bucket-lifecycle-configuration `
    --bucket capa-terraform-state-<YOUR_ACCOUNT_ID> `
    --lifecycle-configuration '{
        "Rules": [{
            "Id": "DeleteOldVersions",
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 90
            }
        }]
    }'
```

---

## 7. 다음 단계

✅ **Terraform Backend 설정 완료** → `04_iam_roles.md`로 이동

---

## 8. 결과 기록

**실행자**: _______________  
**실행 일시**: _______________  
**결과**: ⬜ 성공 / ⬜ 실패  

**S3 Bucket 이름**: `capa-terraform-state-_______________`  
**DynamoDB Table**: `capa-terraform-lock`

**메모**:
```
(실행 로그, 발생한 이슈 기록)
```
