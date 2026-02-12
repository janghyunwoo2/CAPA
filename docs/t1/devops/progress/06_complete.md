# Task 06: EKS Cluster Setup (Complete)

## 진행 상황 요약
- **작업 일자**: 2026-02-12
- **현재 상태**: **성공 (Success)**
  - EKS 클러스터 및 노드 그룹 생성 완료.
  - `access_config` 설정을 통해 클러스터 생성자에게 관리자 권한 자동 부여 완료.
  - `kubectl` 접근 검증 완료.

## 생성된 리소스
| 리소스 타입 | 이름/ID | 상세 내용 |
|---|---|---|
| **EKS Cluster** | `capa-eks-dev` | v1.29, Public/Private Endpoint Enabled, Access Config Analyzed |
| **Node Group** | `capa-node-group-dev` | t3.medium (2 nodes), Ready |
| **OIDC Provider** | - | IRSA 설정 완료 |
| **EKS Addon** | `aws-ebs-csi-driver` | v1.31.0-eksbuild.1 (설치 완료) |

## 문제 해결 (Troubleshooting)
### 1. `aws_eks_access_entry` Terraform 에러
- **원인**: `aws_eks_access_entry` 리소스를 명시적으로 생성하려 했으나, IAM ARN 불일치 문제 발생.
- **해결**:
  - `aws_eks_access_entry` 리소스 제거.
  - `aws_eks_cluster` 리소스 내 `access_config` 블록 추가 (`bootstrap_cluster_creator_admin_permissions = true`).
  - Terraform 재적용 후 정상 작동 확인.

## 검증 결과 (Verification)
### 1. Kubectl Access
```bash
aws eks update-kubeconfig --name capa-eks-dev --region ap-northeast-2
kubectl get nodes
```
**Output:**
```
NAME                                               STATUS   ROLES    AGE   VERSION
ip-172-31-0-xxx.ap-northeast-2.compute.internal    Ready    <none>   16m   v1.29.15-eks-ecaa3a6
ip-172-31-23-xxx.ap-northeast-2.compute.internal   Ready    <none>   16m   v1.29.15-eks-ecaa3a6
```
- 2개의 노드가 `Ready` 상태임을 확인.

## 향후 계획
- Task 07: Alert System (CloudWatch + SNS) 구축 진행.
