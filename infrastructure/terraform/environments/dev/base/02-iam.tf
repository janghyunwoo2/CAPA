# IAM Roles for CAPA Project
# 작업: 04_iam_roles.md (Phase 1)
# 용도: EKS Cluster, Node, Firehose, IRSA Roles 정의

# ============================================
# 1. EKS Cluster IAM Role
# ============================================
resource "aws_iam_role" "eks_cluster" {
  name = "capa-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

# ============================================
# 2. EKS Node Group IAM Role
# ============================================
resource "aws_iam_role" "eks_node" {
  name = "capa-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  ])

  policy_arn = each.value
  role       = aws_iam_role.eks_node.name
}

# ============================================
# 3. Kinesis Firehose IAM Role
# ============================================
resource "aws_iam_role" "firehose" {
  name = "capa-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "firehose_policy" {
  name = "capa-firehose-policy"
  role = aws_iam_role.firehose.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::capa-data-lake-*",
          "arn:aws:s3:::capa-data-lake-*/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:GetShardIterator",
          "kinesis:GetRecords",
          "kinesis:ListShards"
        ]
        Resource = "arn:aws:kinesis:*:*:stream/capa-stream"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetTable",
          "glue:GetTableVersion",
          "glue:GetTableVersions",
          "glue:GetDatabase"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================
# 4. CloudWatch Alarm IAM Role (SNS Publish)
# ============================================
resource "aws_iam_role" "cloudwatch_alarm" {
  name = "capa-alarm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "cloudwatch.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "alarm_policy" {
  name = "alarm-sns-policy"
  role = aws_iam_role.cloudwatch_alarm.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sns:Publish"
      Resource = "arn:aws:sns:*:*:capa-alerts"
    }]
  })
}

# ============================================
# Note: IRSA Roles (Airflow, Redash, Vanna, etc.)는 
# EKS OIDC Provider 생성 후 추가 예정 (작업 06 이후)
# ============================================
