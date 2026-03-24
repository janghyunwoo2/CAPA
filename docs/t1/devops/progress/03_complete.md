# ✅ 작업 03 완료: Terraform Backend 설정

**작업 파일**: [`03_terraform_backend.md`](../work/03_terraform_backend.md)  
**Phase**: 1 (Terraform Base Layer)  
**실행 일시**: 2026-02-12 11:00 - 11:41  
**결과**: ✅ **성공**

---

## 📋 실행 내용

### 1. Bootstrap 디렉토리 생성

**위치**: `infrastructure/terraform/bootstrap/`

**생성된 파일**:
- `main.tf` (99줄) - S3 Bucket, DynamoDB Table 정의
- `README.md` - Bootstrap 사용 방법 문서

---

### 2. Terraform 실행 단계

| 단계 | 명령어 | 결과 | 비고 |
|------|--------|------|------|
| **Init** | `terraform init` | ✅ 성공 | AWS Provider v5.100.0 설치 |
| **Validate** | `terraform validate` | ✅ 성공 | Configuration 유효 |
| **Plan** | `terraform plan` | ✅ 성공 | 5개 리소스 생성 예정 |
| **Apply (1차)** | `terraform apply` | ❌ 실패 | DynamoDB 권한 부족 |
| **권한 추가** | IAM User에 `AmazonDynamoDBFullAccess` 추가 | ✅ 완료 | AWS Console에서 수동 추가 |
| **Apply (2차)** | `terraform apply -auto-approve` | ✅ 성공 | 5개 리소스 생성 완료 |

---

## ✅ 생성된 리소스

| 리소스 | 이름 | 상태 | 용도 |
|--------|------|------|------|
| **S3 Bucket** | `capa-terraform-state-827913617635` | ✅ 생성됨 | Terraform State 저장 |
| **S3 Versioning** | (활성화) | ✅ 적용됨 | State 버전 관리 |
| **S3 Encryption** | AES256 | ✅ 적용됨 | State 암호화 |
| **S3 Public Block** | (차단) | ✅ 적용됨 | Public 접근 차단 |
| **DynamoDB Table** | `capa-terraform-lock` | ✅ 생성됨 | State Locking |

---

## 📊 Terraform Output

```bash
account_id = "827913617635"
dynamodb_table_name = "capa-terraform-lock"
s3_bucket_name = "capa-terraform-state-827913617635"
```

**현재 IAM User**: `ai-en-6` (ARN: `arn:aws:iam::827913617635:user/ai-en-6`)

---

## ✅ 성공 기준 달성

- [x] S3 Bucket `capa-terraform-state-827913617635` 생성됨
- [x] S3 버전 관리 활성화됨
- [x] S3 암호화 설정됨 (AES256)
- [x] S3 Public Access 차단됨
- [x] DynamoDB Table `capa-terraform-lock` 생성됨
- [x] `terraform apply` 성공
- [x] Output 값 확인 완료

---

## 🔧 발생한 이슈 및 해결

### 이슈 1: Terraform Apply 실패 (DynamoDB 권한)

**증상**: 
```
Error: creating DynamoDB Table (capa-terraform-lock): operation error DynamoDB
```

**원인**: IAM User `ai-en-6`에 DynamoDB 권한 없음

**해결**: 
1. AWS Console → IAM → Users → `ai-en-6`
2. `AmazonDynamoDBFullAccess` Policy 추가
3. `terraform apply -auto-approve` 재실행 → ✅ 성공

---

## 🔧 Backend 설정 파일 생성

### 3. backend.tf 생성 및 초기화

**위치**: `infrastructure/terraform/environments/dev/base/backend.tf`

**생성된 파일 내용**:
```hcl
terraform {
  backend "s3" {
    bucket         = "capa-terraform-state-827913617635"
    key            = "dev/base/terraform.tfstate"
    region         = "ap-northeast-2"
    dynamodb_table = "capa-terraform-lock"
    encrypt        = true
  }
}
```

**실행 단계**:

| 단계 | 명령어 | 결과 | 비고 |
|------|--------|------|------|
| **파일 생성** | `backend.tf` 작성 | ✅ 성공 | S3 Backend 설정 |
| **초기화 (1차)** | `terraform init` | ⚠️ 실패 | Backend 변경 감지 |
| **초기화 (2차)** | `terraform init -reconfigure` | ✅ 성공 | Backend 재설정 |
| **검증** | `terraform validate` | ✅ 성공 | Configuration 유효 |

**Backend 연결 확인**:
- ✅ S3 Bucket: `capa-terraform-state-827913617635`
- ✅ State Key: `dev/base/terraform.tfstate`
- ✅ DynamoDB Lock: `capa-terraform-lock`
- ✅ 암호화: AES256

---

## ✅ 최종 성공 기준 달성

### Bootstrap 단계
- [x] S3 Bucket `capa-terraform-state-827913617635` 생성됨
- [x] S3 버전 관리 활성화됨
- [x] S3 암호화 설정됨 (AES256)
- [x] S3 Public Access 차단됨
- [x] DynamoDB Table `capa-terraform-lock` 생성됨
- [x] `terraform apply` 성공
- [x] Output 값 확인 완료

### Backend 설정 단계
- [x] `backend.tf` 파일 생성됨
- [x] `terraform init -reconfigure` 성공
- [x] S3 Backend 연결 확인
- [x] `terraform validate` 성공

---

## 🎯 작업 완료

**Terraform Backend 설정 완료**:
1. ✅ Bootstrap으로 S3 + DynamoDB 생성
2. ✅ `backend.tf` 파일로 S3 Backend 연결
3. ✅ State 원격 저장 활성화

**이제 dev/base 디렉토리에서 작업하면**:
- State가 S3에 자동 저장됨
- 팀원과 State 공유 가능
- DynamoDB Lock으로 동시 실행 방지

---

## 🎯 다음 단계

**Phase 1 계속**:
- [ ] `04_iam_roles.md` - IAM Roles 생성 (IRSA)
- [ ] `05_data_pipeline_기본.md` - Kinesis, S3, Glue
- [ ] `06_eks_cluster.md` - EKS Cluster
- [ ] `07_alert_system.md` - CloudWatch, SNS

---

## 💡 참고 사항

### Bootstrap State 관리
- **Bootstrap State**: 로컬 저장 (`bootstrap/terraform.tfstate`)
- **중요**: Bootstrap State는 Git에 커밋하지 않음 (`.gitignore`에 포함)
- **백업 권장**: `bootstrap/terraform.tfstate`를 안전한 곳에 백업

### 왜 Backend 설정을 따로 하는가?
1. **Bootstrap** (1회): S3와 DynamoDB를 생성 (로컬 State 사용)
2. **Backend 설정** (실제 작업): 생성된 S3/DynamoDB를 Backend로 사용 (원격 State)

이렇게 분리하는 이유는 "닭과 달걀 문제" 때문입니다:
- S3 Backend를 사용하려면 S3가 먼저 있어야 함
- S3를 Terraform으로 만들려면 State 저장소가 필요함
- 따라서 Bootstrap은 로컬 State로 S3를 만들고, 이후 작업은 그 S3를 사용

---

## 📝 실행 로그 요약

```bash
# 사용자 확인
$ aws sts get-caller-identity
{
    "UserId": "AIDA4BQ37IDRX4HUQ674V",
    "Account": "827913617635",
    "Arn": "arn:aws:iam::827913617635:user/ai-en-6"
}

# Terraform Apply (권한 추가 후)
$ terraform apply -auto-approve
...
Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:
account_id = "827913617635"
dynamodb_table_name = "capa-terraform-lock"
s3_bucket_name = "capa-terraform-state-827913617635"
```

---

**작업 완료 시각**: 2026-02-12 11:41
