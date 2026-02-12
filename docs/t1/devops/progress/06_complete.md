# Task 06: EKS Cluster Setup & Upgrade (Complete)

## 진행 상황 요약
- **작업 일자**: 2026-02-12
- **현재 상태**: **성공 (Success)**
  - EKS 클러스터를 v1.29에서 **v1.30**으로 업그레이드 완료.
  - 노드 그룹의 OS를 Amazon Linux 2(AL2)에서 **Amazon Linux 2023(AL2023)**으로 전환 완료.
  - EKS 코어 애드온(`vpc-cni`, `kube-proxy`, `coredns`)을 1.30 버전에 최적화된 버전으로 고정(Pinning) 완료.
  - `access_config` 설정을 통해 관리자 권한 자동 부여 및 `kubectl` 접근 검증 완료.

## 생성된 리소스 (최종 상태)
| 리소스 타입 | 이름/ID | 상세 내용 |
|---|---|---|
| **EKS Cluster** | `capa-eks-dev` | **v1.30**, Public/Private Endpoint Enabled |
| **Node Group** | `capa-node-group-dev` | t3.medium (2 nodes), **AL2023 (Latest)**, Ready |
| **VPC CNI Addon** | `vpc-cni` | `v1.20.4-eksbuild.2` (EKS 1.30 compatible) |
| **Kube-proxy Addon** | `kube-proxy` | `v1.30.14-eksbuild.20` (Optimized) |
| **CoreDNS Addon** | `coredns` | `v1.11.1-eksbuild.8` (Stabilized) |
| **EBS CSI Addon** | `aws-ebs-csi-driver` | `v1.31.0-eksbuild.1` |

## 문제 해결 (Troubleshooting)
### 1. `aws_eks_access_entry` Terraform 에러
- **원인**: `aws_eks_access_entry` 리소스와 클러스터 생성자 권한 간의 ARN 불일치.
- **해결**: `access_config` 블록의 `bootstrap_cluster_creator_admin_permissions = true` 설정을 사용하여 해결.

### 2. EKS Addon Version Skew 경고
- **상황**: 클러스터 v1.30 업그레이드 후, EKS 콘솔에서 `kube-proxy` 등 애드온의 버전 불일치 경고 발생.
- **해결**: 
  - AWS 공식 지원 버전을 조사하여 `06-eks.tf`에 애드온 버전을 명시적으로 선언.
  - `terraform apply`를 통해 모든 코어 애드온을 v1.30 최적화 버전으로 업데이트.

## 검증 결과 (Verification)
### 1. Node & Version Check
```bash
kubectl get nodes -o wide
```
**Output Summary:**
- VERSION: `v1.30.14-eks-70ce843`
- OS-IMAGE: `Amazon Linux 2023.10.20260202`
- STATUS: `Ready`

### 2. Addon Status Check
```bash
aws eks list-addons --cluster-name capa-eks-dev
```
- 모든 애드온이 `ACTIVE` 상태이며 최신 1.30 호환 버전이 적용됨을 확인.

## 향후 계획
- Task 07: Alert System (CloudWatch + SNS) 및 애플리케이션 레이어 배포 진행.
