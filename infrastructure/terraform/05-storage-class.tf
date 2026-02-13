# Storage Class Configuration
# 작업: 11_airflow_deploy (Phase 3)
# 용도: EBS CSI Driver용 StorageClass 정의
# 참고: 이전 프로젝트 성공 코드 기반 (WaitForFirstConsumer 사용)

resource "kubernetes_storage_class" "gp2" {
  metadata {
    name = "gp2"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }

  storage_provisioner = "ebs.csi.aws.com"
  reclaim_policy      = "Delete"
  parameters = {
    type   = "gp2"
    fsType = "ext4"
  }
  volume_binding_mode = "WaitForFirstConsumer" # 변경: Immediate -> WaitForFirstConsumer (이전 프로젝트 성공 코드)

  depends_on = [
    aws_eks_addon.ebs_csi
  ]
}
