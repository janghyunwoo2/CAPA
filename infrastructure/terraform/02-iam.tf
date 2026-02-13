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
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ])

  policy_arn = each.value
  role       = aws_iam_role.eks_node.name
}

# ============================================
# 3. EBS CSI Driver IAM Role (IRSA)
# ============================================
resource "aws_iam_role" "ebs_csi_driver" {
  name = "capa-ebs-csi-driver-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa",
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ebs_csi_driver_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.ebs_csi_driver.name
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
# 5. Airflow IRSA Role
# ============================================
resource "aws_iam_role" "airflow" {
  name = "capa-airflow-role"

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

resource "aws_iam_policy" "airflow_s3" {
  name        = "capa-airflow-s3-policy"
  description = "Airflow S3 access for data lake"

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
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "airflow_s3" {
  policy_arn = aws_iam_policy.airflow_s3.arn
  role       = aws_iam_role.airflow.name
}

# ============================================
# Note: IRSA Roles (Redash, Vanna, etc.)는 
# EKS OIDC Provider 생성 후 추가 예정 (작업 06 이후)
# ============================================
