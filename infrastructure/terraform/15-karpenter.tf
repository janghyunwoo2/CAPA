# ==============================================================================
# Karpenter - 지능형 노드 자동 프로비저닝
# ==============================================================================
# Cluster Autoscaler를 대체하는 Karpenter를 설치합니다.
# - 파드 Pending 감지 시 20~60초 안에 최적 노드를 직접 AWS에 주문
# - 스팟 인스턴스 회수(Interruption) 알림을 SQS로 수신하여 선제적 파드 이사
# - 부하 해소 시 빈 노드 자동 반납 (Consolidation)
# ==============================================================================

# ------------------------------------------------------------------------------
# Karpenter Controller IAM Role (IRSA)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "karpenter_controller" {
  name = "${var.project_name}-karpenter-controller-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:karpenter"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "karpenter_controller" {
  name        = "${var.project_name}-karpenter-controller-policy"
  description = "Karpenter Controller - EC2 노드 직접 생성/삭제 권한"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowScopedEC2InstanceActions"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
          "ec2:CreateFleet",
          "ec2:CreateLaunchTemplate",
          "ec2:DeleteLaunchTemplate",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeInstanceTypeOfferings",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeImages",
          "ec2:DescribeSpotPriceHistory",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeLaunchTemplateVersions",
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "*"
      },
      {
        Sid      = "AllowIAMPassRole"
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = aws_iam_role.eks_node.arn
      },
      {
        Sid    = "AllowInstanceProfile"
        Effect = "Allow"
        Action = [
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:GetInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:TagInstanceProfile"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowSSMGetParameter"
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        # EKS 최적화 AMI ID를 SSM에서 조회
        Resource = "arn:aws:ssm:${var.aws_region}::parameter/aws/service/*"
      },
      {
        Sid    = "AllowSQSInterruption"
        Effect = "Allow"
        Action = [
          "sqs:DeleteMessage",
          "sqs:GetQueueUrl",
          "sqs:GetQueueAttributes",
          "sqs:ReceiveMessage"
        ]
        Resource = aws_sqs_queue.karpenter_interruption.arn
      },
      {
        Sid      = "AllowPricingAPI"
        Effect   = "Allow"
        Action   = ["pricing:GetProducts"]
        Resource = "*"
      },
      {
        Sid      = "AllowEKS"
        Effect   = "Allow"
        Action   = ["eks:DescribeCluster"]
        Resource = aws_eks_cluster.main.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "karpenter_controller" {
  policy_arn = aws_iam_policy.karpenter_controller.arn
  role       = aws_iam_role.karpenter_controller.name
}

# ------------------------------------------------------------------------------
# Karpenter Interruption Queue (SQS)
# - 스팟 회수 알림, EC2 상태 변경, 예정된 유지보수 이벤트를 수신
# ------------------------------------------------------------------------------
resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${var.project_name}-karpenter-interruption"
  message_retention_seconds = 300

  tags = {
    Name = "${var.project_name}-karpenter-interruption"
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = ["events.amazonaws.com", "sqs.amazonaws.com"] }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.karpenter_interruption.arn
      }
    ]
  })
}

# EventBridge 규칙: 스팟 회수 알림 → SQS
resource "aws_cloudwatch_event_rule" "karpenter_spot_interruption" {
  name        = "${var.project_name}-karpenter-spot-interruption"
  description = "Karpenter Spot Interruption Warning"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
}

resource "aws_cloudwatch_event_target" "karpenter_spot_interruption" {
  rule      = aws_cloudwatch_event_rule.karpenter_spot_interruption.name
  target_id = "KarpenterInterruptionQueue"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

# EventBridge 규칙: EC2 상태 변경 알림 → SQS
resource "aws_cloudwatch_event_rule" "karpenter_instance_state" {
  name = "${var.project_name}-karpenter-instance-state"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
  })
}

resource "aws_cloudwatch_event_target" "karpenter_instance_state" {
  rule      = aws_cloudwatch_event_rule.karpenter_instance_state.name
  target_id = "KarpenterInterruptionQueue"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

# ------------------------------------------------------------------------------
# Karpenter Helm Release
# ------------------------------------------------------------------------------
resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = "1.3.3" # EKS 1.29 호환
  namespace  = "kube-system"

  set {
    name  = "settings.clusterName"
    value = aws_eks_cluster.main.name
  }
  set {
    name  = "settings.clusterEndpoint"
    value = aws_eks_cluster.main.endpoint
  }
  set {
    name  = "settings.interruptionQueue"
    value = aws_sqs_queue.karpenter_interruption.name
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.karpenter_controller.arn
  }

  set {
    name  = "replicas"
    value = "1"
  }

  # Karpenter 컨트롤러를 코어 노드(온디맨드)에 배치
  set {
    name  = "nodeSelector.node-type"
    value = "core"
  }


  # 리소스 제한
  set {
    name  = "controller.resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "controller.resources.requests.memory"
    value = "256Mi"
  }
  set {
    name  = "controller.resources.limits.cpu"
    value = "500m"
  }
  set {
    name  = "controller.resources.limits.memory"
    value = "512Mi"
  }

  depends_on = [
    aws_eks_node_group.core,
    aws_iam_role_policy_attachment.karpenter_controller
  ]
}

# ------------------------------------------------------------------------------
# Karpenter 리소스 (NodePool & EC2NodeClass)
# ------------------------------------------------------------------------------
resource "kubectl_manifest" "karpenter_node_class" {
  yaml_body = <<-YAML
    apiVersion: karpenter.k8s.aws/v1
    kind: EC2NodeClass
    metadata:
      name: default
    spec:
      amiFamily: AL2
      role: "${aws_iam_role.eks_node.name}"
      subnetSelectorTerms:
        - id: "${sort(data.aws_subnets.default.ids)[0]}"
      securityGroupSelectorTerms:
        - tags:
            karpenter.sh/discovery: "${aws_eks_cluster.main.name}"
      amiSelectorTerms:
        - alias: al2@latest
      tags:
        karpenter.sh/discovery: "${aws_eks_cluster.main.name}"
  YAML

  depends_on = [helm_release.karpenter]
}

# ------------------------------------------------------------------------------
# NodePool - 기본 풀 (스팟 우선, 온디맨드 자동 폴백)
# 평상시 스팟 1대로 운영되며, 부하 시 자동 확장
# ------------------------------------------------------------------------------
resource "kubectl_manifest" "karpenter_nodepool_default" {
  yaml_body = <<YAML
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      requirements:
        # 스팟 먼저 시도, 재고 없으면 온디맨드 자동 폴백
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
        # 다양한 인스턴스 타입으로 스팟 회수 리스크 분산
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3a.large", "t3.large", "m5a.large", "m5.large", "t3a.medium", "t3.medium"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
  # 최대 수용 한도 (Karpenter가 자동 관리하는 노드들의 총합)
  # t3a.large (2 vCPU, 8GiB) 기준 최대 2대까지만 허용 (전체 노드 합계 3대 제한)
  limits:
    cpu: "4"
    memory: "16Gi"
  disruption:
    # 비어있거나 리소스 낭비가 심한 노드 자동 반납
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 60s
YAML

  depends_on = [kubectl_manifest.karpenter_node_class]
}
