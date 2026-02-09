# EKS 모듈 출력

output "cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "EKS 클러스터 이름"
}

output "cluster_arn" {
  value       = aws_eks_cluster.main.arn
  description = "EKS 클러스터 ARN"
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "EKS 클러스터 엔드포인트"
}

output "cluster_ca_certificate" {
  value       = aws_eks_cluster.main.certificate_authority[0].data
  sensitive   = true
  description = "클러스터 CA 인증서"
}

output "cluster_version" {
  value       = aws_eks_cluster.main.version
  description = "Kubernetes 버전"
}

output "node_group_id" {
  value       = aws_eks_node_group.main.id
  description = "Node Group ID"
}

output "node_security_group" {
  value       = aws_security_group.cluster_sg.id
  description = "클러스터 보안 그룹"
}
