# ==============================================================================
# CAPA Infrastructure - IAM Roles & Policies
# ==============================================================================
# 모든 서비스가 참조하는 IAM Role/Policy 정의
# ==============================================================================

data "aws_caller_identity" "current" {}

# ------------------------------------------------------------------------------
# EKS Cluster Role
# ------------------------------------------------------------------------------
resource "aws_iam_role" "eks_cluster" {
  name = "${var.project_name}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

# ------------------------------------------------------------------------------
# EKS Node Group Role
# ------------------------------------------------------------------------------
resource "aws_iam_role" "eks_node" {
  name = "${var.project_name}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node.name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node.name
}

resource "aws_iam_role_policy_attachment" "eks_container_registry" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node.name
}

# ------------------------------------------------------------------------------
# Kinesis 접근 Policy (Fluent Bit, Consumer용)
# ------------------------------------------------------------------------------
resource "aws_iam_policy" "kinesis_access" {
  name        = "${var.project_name}-kinesis-access"
  description = "Kinesis Stream 읽기/쓰기 권한"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord",
          "kinesis:PutRecords",
          "kinesis:GetRecords",
          "kinesis:GetShardIterator",
          "kinesis:DescribeStream",
          "kinesis:DescribeStreamSummary",
          "kinesis:ListShards"
        ]
        Resource = "arn:aws:kinesis:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stream/${var.project_name}-*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_kinesis" {
  policy_arn = aws_iam_policy.kinesis_access.arn
  role       = aws_iam_role.eks_node.name
}

# ------------------------------------------------------------------------------
# Firehose Role (S3 전송용)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "firehose" {
  name = "${var.project_name}-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "firehose_s3" {
  name        = "${var.project_name}-firehose-s3"
  description = "Firehose S3 쓰기 권한"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetBucketLocation",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
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
        Resource = "arn:aws:kinesis:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stream/${var.project_name}-*"
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

resource "aws_iam_role_policy_attachment" "firehose_s3" {
  policy_arn = aws_iam_policy.firehose_s3.arn
  role       = aws_iam_role.firehose.name
}

# ------------------------------------------------------------------------------
# IRSA Role (Consumer & Fluent Bit용)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "app_role" {
  name = "${var.project_name}-app-role"

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
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:default:consumer-sa"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "app_kinesis" {
  policy_arn = aws_iam_policy.kinesis_access.arn
  role       = aws_iam_role.app_role.name
}

resource "aws_iam_role_policy_attachment" "app_s3_read" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
  role       = aws_iam_role.app_role.name
}

# Fluent Bit 로깅에 필요한 기본 권한
resource "aws_iam_role_policy_attachment" "app_cloudwatch" {
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  role       = aws_iam_role.app_role.name
}

# ------------------------------------------------------------------------------
# Cluster Autoscaler Role (IRSA)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "cluster_autoscaler" {
  name = "${var.project_name}-cluster-autoscaler-role"

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
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:cluster-autoscaler"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "cluster_autoscaler" {
  name        = "${var.project_name}-cluster-autoscaler-policy"
  description = "Cluster Autoscaler 권한"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeTags",
          "autoscaling:SetDesiredCapacity",
          "autoscaling:TerminateInstanceInAutoScalingGroup",
          "ec2:DescribeLaunchTemplateVersions"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cluster_autoscaler" {
  policy_arn = aws_iam_policy.cluster_autoscaler.arn
  role       = aws_iam_role.cluster_autoscaler.name
}

# ------------------------------------------------------------------------------
# Airflow Role (IRSA)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "airflow" {
  name = "${var.project_name}-airflow-role"

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
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = [
            "system:serviceaccount:airflow:airflow-sa",
            "system:serviceaccount:airflow:airflow-scheduler",
            "system:serviceaccount:airflow:airflow-webserver",
            "system:serviceaccount:airflow:airflow-triggerer",
            "system:serviceaccount:airflow:airflow-worker"
          ]
        }
      }
    }]
  })
}

# ------------------------------------------------------------------------------
# Workload S3 Access Policy (Airflow, Consumer용)
# ------------------------------------------------------------------------------
# Firehose용 정책과 별도로 관리하여 Workload(Pod) 전용 권한 정의
resource "aws_iam_policy" "workload_s3_access" {
  name        = "${var.project_name}-workload-s3-access"
  description = "S3 Bucket Read/Write and List Permissions for Workloads"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetObject",
          "s3:GetBucketLocation",
          "s3:ListBucket",
          "s3:DeleteObject" # Airflow DAG에서 S3 객체 삭제 권한
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "airflow_s3_access" {
  policy_arn = aws_iam_policy.workload_s3_access.arn
  role       = aws_iam_role.airflow.name
}

# Consumer Role에도 Workload S3 권한 추가 (기존 ReadOnly 대체/보완)
resource "aws_iam_role_policy_attachment" "app_s3_access" {
  policy_arn = aws_iam_policy.workload_s3_access.arn
  role       = aws_iam_role.app_role.name
}

# ------------------------------------------------------------------------------
# CloudWatch Alarm IAM Role (SNS Publish)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "cloudwatch_alarm" {
  name = "${var.project_name}-alarm-role"

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
      Resource = "arn:aws:sns:*:*:${var.project_name}-alerts"
    }]
  })
}

# ------------------------------------------------------------------------------
# EBS CSI Driver IAM Policy for Node Group
# ------------------------------------------------------------------------------
resource "aws_iam_role_policy_attachment" "eks_ebs_csi_driver_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.eks_node.name
}

# ------------------------------------------------------------------------------
# Redash Role (IRSA)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "redash" {
  name = "${var.project_name}-redash-role"

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
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:redash:redash-sa"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "redash_athena" {
  name        = "${var.project_name}-redash-athena"
  description = "Redash Athena Access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:*",
          "glue:GetTable",
          "glue:GetPartitions",
          "glue:GetDatabase",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload",
          "s3:PutObject"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "redash_athena" {
  policy_arn = aws_iam_policy.redash_athena.arn
  role       = aws_iam_role.redash.name
}
