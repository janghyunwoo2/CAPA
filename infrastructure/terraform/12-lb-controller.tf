# ==============================================================================
# AWS Load Balancer Controller
# ==============================================================================
# 로드 밸런서(ALB/NLB)를 자동으로 관리하는 컨트롤러 설치
# ==============================================================================

resource "helm_release" "aws_lb_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"

  set {
    name  = "clusterName"
    value = aws_eks_cluster.main.name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.aws_lb_controller.arn
  }

  # EKS 클러스터 사양에 맞게 설정
  set {
    name  = "region"
    value = var.aws_region
  }

  set {
    name  = "vpcId"
    value = data.aws_vpc.default.id
  }

  depends_on = [
    aws_eks_node_group.main,
    aws_iam_role_policy_attachment.aws_lb_controller
  ]
}
