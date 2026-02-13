# 작업 03: Terraform Backend 설정

> **Phase**: 1 (Terraform Base Layer)  
> **담당**: Infra Architect  
> **예상 소요**: 5분  
> **선행 작업**: 02_저장소_구조_설정.md
> **수정 이력**: 2026-02-13 (Windows 환경 이슈로 Local State 전환)

---

## 1. 목표

개발 환경(Windows)의 안정적인 Terraform 실행을 위해 **Local State**를 사용하도록 설정합니다.
*(기존 S3 + DynamoDB Backend는 Windows 환경에서의 Locking 문제로 인해 보류되었습니다.)*

---

## 2. 왜 Local State인가?

| 항목 | Local State (현재 선택) | S3 Backend (Ops 권장) |
|------|-------------------------|-------------------|
| **State 저장 위치** | 로컬 PC (`.tfstate` 파일) | S3 Bucket (원격) |
| **Windows 호환성** | ✅ 안정적 (파일 락킹) | ❌ 불안정 (Process Hang, Lock 이슈) |
| **팀 협업** | ❌ 공유 불가 (1인 개발 적합) | ✅ 팀원 모두 동일 State 사용 |
| **설정 복잡도** | ✅ 매우 낮음 | ⚠️ 높음 (S3, DynamoDB 필요) |

> **결정 사항**: 1인 개발/DevOps 초기 단계 및 Windows 환경 특성을 고려하여 **Local State**를 기본으로 사용합니다. 향후 운영 환경(Production) 구축 시 Linux 기반 CI/CD에서 S3 Backend로 전환합니다.

---

## 3. 실행 단계

### 3.1 Backend 설정 파일 수정

`infrastructure/terraform/environments/dev/base/backend.tf` 파일을 아래와 같이 작성(또는 수정)합니다. S3 관련 블록은 주석 처리합니다.

```hcl
# infrastructure/terraform/environments/dev/base/backend.tf
terraform {
  # backend "s3" {
  #   bucket         = "capa-terraform-state-827913617635"
  #   key            = "dev/base/terraform.tfstate"
  #   region         = "ap-northeast-2"
  #   dynamodb_table = "capa-terraform-lock"
  #   encrypt        = true
  # }
}
```

### 3.2 Backend 초기화 및 마이그레이션

기존에 S3 Backend를 시도했거나 설정이 남아있다면, Local로 상태를 가져와야 합니다.

```powershell
cd infrastructure\terraform\environments\dev\base

# Backend를 로컬로 마이그레이션 (State 파일 다운로드)
terraform init -migrate-state
```

### 3.3 (옵션) 기존 원격 리소스 정리

이미 생성된 S3 버킷과 DynamoDB 테이블은 비용 절감을 위해 삭제하거나 남겨둘 수 있습니다. (현재는 유지 권장)

---

## 4. 검증 방법

### 4.1 terraform.tfstate 확인

```powershell
# 로컬 디렉토리에 파일 존재 확인
Get-ChildItem terraform.tfstate
```

### 4.2 Terraform 동작 확인

```powershell
terraform validate
terraform plan
```
* 위 명령어 실행 시 `Error acquiring the state lock` 에러 없이 진행되어야 함.

---

## 5. 실패 시 대응 (Windows Lock 이슈)

Local State 사용 중에도 Terraform 프로세스가 비정상 종료되면 Lock이 남을 수 있습니다.

| 오류 | 해결 방법 |
|------|-----------|
| `Error acquiring the state lock` | 1. `Stop-Process -Name terraform -Force` (좀비 프로세스 종료)<br>2. `.terraform.tfstate.lock.info` 파일 삭제 |
| State 파일 유실 | `terraform.tfstate.backup` 파일을 `terraform.tfstate`로 복사하여 복구 |

---

## 6. 다음 단계

✅ **Terraform Backend 설정(Local) 완료** → `04_iam_roles.md`로 이동

