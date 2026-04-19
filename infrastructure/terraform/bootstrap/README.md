# Bootstrap Backend README

## 목적
Terraform State를 저장할 S3 Bucket과 DynamoDB Lock Table을 생성합니다.

## 사용 방법

```powershell
# 1. 디렉토리 이동
cd infrastructure/terraform/bootstrap

# 2. Terraform 초기화
terraform init

# 3. 리소스 생성 계획 확인
terraform plan

# 4. 리소스 생성
terraform apply

# 5. 출력 확인
terraform output
```

## 생성 리소스

- **S3 Bucket**: `capa-terraform-state-<ACCOUNT_ID>`
  - 버전 관리 활성화
  - AES256 암호화
  - Public Access 차단

- **DynamoDB Table**: `capa-terraform-lock`
  - PAY_PER_REQUEST 과금
  - LockID 기본 키

## 주의사항

⚠️ **이 폴더의 State는 Local에 저장됩니다** (bootstrap 자체는 Backend를 사용하지 않음)

Bootstrap 완료 후, `base/` 및 `apps/` 폴더에서 생성된 Backend를 사용합니다.
