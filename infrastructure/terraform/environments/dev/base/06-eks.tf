# ============================================
# 1. 기본 VPC 및 Subnet 조회 (기존 리소스 사용)
# ============================================
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ============================================
# 2. EKS Cluster
# ============================================
resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-eks-${var.environment}"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.30"

  vpc_config {
    subnet_ids              = data.aws_subnets.default.ids
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator"]

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy
  ]
}

# ============================================
# 3. EKS Node Group
# ============================================
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-node-group-${var.environment}"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = data.aws_subnets.default.ids

  instance_types = ["t3.medium"]
  capacity_type  = "ON_DEMAND"
  ami_type       = "AL2023_x86_64_STANDARD"

  scaling_config {
    desired_size = 2
    max_size     = 4
    min_size     = 2
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_eks_cluster.main,
    aws_iam_role_policy_attachment.eks_node_policies
  ]
}

# ============================================
# 4. OIDC Provider (IRSA 전제조건)
# ============================================
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# ============================================
# 5. EKS Addons
# ============================================
resource "aws_eks_addon" "vpc_cni" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "vpc-cni"
  addon_version = "v1.20.4-eksbuild.2"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "kube-proxy"
  addon_version = "v1.30.14-eksbuild.20"
}

resource "aws_eks_addon" "coredns" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "coredns"
  addon_version = "v1.11.1-eksbuild.8"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "aws-ebs-csi-driver"
  addon_version = "v1.31.0-eksbuild.1"

  depends_on = [aws_eks_node_group.main]
}

# ============================================
# 7. Outputs
# ============================================
output "eks_cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "eks_cluster_oidc_issuer" {
  value = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

output "eks_cluster_name" {
  value = aws_eks_cluster.main.name
}

output "eks_cluster_certificate_authority_data" {
  value = aws_eks_cluster.main.certificate_authority[0].data
}
