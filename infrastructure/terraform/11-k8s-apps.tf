# Kubernetes Native Applications (Non-Helm)
# This file manages Kubernetes resources that are deployed directly without Helm charts.
# Includes: Report Generator

# ---------------------------------------------------------------------------------------------------------------------
# Report Generator Namespace
# ---------------------------------------------------------------------------------------------------------------------

resource "kubernetes_namespace" "report" {
  metadata {
    name = "report"
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# Report Generator - ECR Repository
# ---------------------------------------------------------------------------------------------------------------------

resource "aws_ecr_repository" "report_generator" {
  name                 = "capa-report-generator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = false
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

output "report_generator_repository_url" {
  value       = aws_ecr_repository.report_generator.repository_url
  description = "ECR repository URL for Report Generator"
}

# ---------------------------------------------------------------------------------------------------------------------
# Report Generator - IAM Role (IRSA)
# ---------------------------------------------------------------------------------------------------------------------

resource "aws_iam_role" "report_generator" {
  name = "${var.project_name}-report-generator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:report:report-generator-sa"
          }
        }
      }
    ]
  })

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Report Generator IAM Policy (S3, Athena, CloudWatch)
resource "aws_iam_role_policy" "report_generator" {
  name = "${var.project_name}-report-generator-policy"
  role = aws_iam_role.report_generator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartitions"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------------------------------------------------
# Report Generator - Kubernetes Resources
# ---------------------------------------------------------------------------------------------------------------------

# ServiceAccount (IRSA)
resource "kubernetes_service_account" "report_generator_sa" {
  metadata {
    name      = "report-generator-sa"
    namespace = kubernetes_namespace.report.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.report_generator.arn
    }
  }
}

# Secret for Slack (Needed in the same namespace)
resource "kubernetes_secret" "report_slack_secrets" {
  metadata {
    name      = "slack-bot-secrets"
    namespace = kubernetes_namespace.report.metadata[0].name
  }

  data = {
    slack-bot-token = var.slack_bot_token
  }

  type = "Opaque"
}

# Service
resource "kubernetes_service" "report_generator" {
  metadata {
    name      = "report-generator"
    namespace = kubernetes_namespace.report.metadata[0].name
    labels = {
      app = "report-generator"
    }
  }

  spec {
    selector = {
      app = "report-generator"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }

    type = "ClusterIP" # 내부 전용 (Slack Bot이 클러스터 내부에서 호출)
  }
}

# Deployment
resource "kubernetes_deployment" "report_generator" {
  metadata {
    name      = "report-generator"
    namespace = kubernetes_namespace.report.metadata[0].name
    labels = {
      app = "report-generator"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "report-generator"
      }
    }

    template {
      metadata {
        labels = {
          app = "report-generator"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.report_generator_sa.metadata[0].name

        # [Karpenter] 스팟 노드 배치 허용
        toleration {
          key      = "karpenter.sh/disruption"
          operator = "Exists"
          effect   = "NoSchedule"
        }

        container {
          name              = "report-generator"
          image             = "${aws_ecr_repository.report_generator.repository_url}:latest"
          image_pull_policy = "Always"

          port {
            name           = "http"
            container_port = 8000
            protocol       = "TCP"
          }

          # 환경 변수
          env {
            name  = "ENVIRONMENT"
            value = var.environment
          }
          env {
            name  = "AWS_REGION"
            value = var.aws_region
          }
          env {
            name  = "ATHENA_DATABASE"
            value = "capa_db"
          }
          env {
            name  = "REPORT_S3_BUCKET"
            value = aws_s3_bucket.data_lake.id
          }
          env {
            name  = "VANNA_API_URL"
            value = "http://vanna-api.vanna.svc.cluster.local:8000"
          }
          env {
            name  = "LOG_LEVEL"
            value = "INFO"
          }
          env {
            name = "SLACK_BOT_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.report_slack_secrets.metadata[0].name
                key  = "slack-bot-token"
              }
            }
          }
          env {
            name  = "SLACK_CHANNEL_ID"
            value = var.slack_channel_id
          }

          # 리소스 제한
          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "250m"
              memory = "512Mi"
            }
          }

          # 헬스 체크(복구)
          liveness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 2
          }
        }

        # 노드별 균등 배분 설정
        topology_spread_constraint {
          max_skew           = 1
          topology_key       = "kubernetes.io/hostname"
          when_unsatisfiable = "ScheduleAnyway"
          label_selector {
            match_labels = {
              app = "report-generator"
            }
          }
        }
      }
    }
  }

  depends_on = [kubernetes_service.report_generator]
}

# =====================================================================================================================
# Vanna AI (Text-to-SQL Service)
# =====================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------
# Vanna AI Namespace
# ---------------------------------------------------------------------------------------------------------------------

resource "kubernetes_namespace" "vanna" {
  metadata {
    name = "vanna"
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# Vanna AI - ECR Repository
# ---------------------------------------------------------------------------------------------------------------------

resource "aws_ecr_repository" "vanna_api" {
  name                 = "capa-vanna-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = false
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

output "vanna_api_repository_url" {
  value       = aws_ecr_repository.vanna_api.repository_url
  description = "ECR repository URL for Vanna API"
}

# ---------------------------------------------------------------------------------------------------------------------
# Vanna AI - IAM Role (IRSA)
# ---------------------------------------------------------------------------------------------------------------------

resource "aws_iam_role" "vanna" {
  name = "${var.project_name}-vanna-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:vanna:vanna-sa"
          }
        }
      }
    ]
  })

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Vanna AI IAM Policy (Athena, S3, Glue)
resource "aws_iam_role_policy" "vanna" {
  name = "${var.project_name}-vanna-policy"
  role = aws_iam_role.vanna.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartitions"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------------------------------------------------
# Vanna AI - Kubernetes Resources
# ---------------------------------------------------------------------------------------------------------------------

# ServiceAccount (IRSA)
resource "kubernetes_service_account" "vanna_sa" {
  metadata {
    name      = "vanna-sa"
    namespace = kubernetes_namespace.vanna.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.vanna.arn
    }
  }
}

# Secret (Anthropic API Key, Redash API Key, Internal API Token)
resource "kubernetes_secret" "vanna_secrets" {
  metadata {
    name      = "vanna-secrets"
    namespace = kubernetes_namespace.vanna.metadata[0].name
  }

  data = {
    anthropic-api-key  = var.anthropic_api_key
    redash-api-key     = var.redash_api_key
    internal-api-token = var.internal_api_token
  }

  type = "Opaque"
}

# ---------------------------------------------------------------------------------------------------------------------
# Vanna AI - Kubernetes Resources (이미지 푸시 후 활성화)
# ---------------------------------------------------------------------------------------------------------------------

# Service
resource "kubernetes_service" "vanna_api" {
  metadata {
    name      = "vanna-api"
    namespace = kubernetes_namespace.vanna.metadata[0].name
    labels = {
      app = "vanna-api"
    }
  }

  spec {
    selector = {
      app = "vanna-api"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}
# Deployment
resource "kubernetes_deployment" "vanna_api" {
  metadata {
    name      = "vanna-api"
    namespace = kubernetes_namespace.vanna.metadata[0].name
    labels = {
      app = "vanna-api"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "vanna-api"
      }
    }

    template {
      metadata {
        labels = {
          app = "vanna-api"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.vanna_sa.metadata[0].name

        # [Karpenter] 스팟 노드 배치 허용
        toleration {
          key      = "karpenter.sh/disruption"
          operator = "Exists"
          effect   = "NoSchedule"
        }

        container {
          name              = "vanna-api"
          image             = "${aws_ecr_repository.vanna_api.repository_url}:latest"
          image_pull_policy = "Always"

          port {
            name           = "http"
            container_port = 8000
            protocol       = "TCP"
          }

          # 환경 변수
          env {
            name  = "ENVIRONMENT"
            value = var.environment
          }
          env {
            name  = "AWS_REGION"
            value = var.aws_region
          }
          env {
            name  = "S3_STAGING_DIR"
            value = "s3://${aws_s3_bucket.data_lake.bucket}/athena-results/"
          }
          env {
            name  = "ATHENA_DATABASE"
            value = "capa_db"
          }
          env {
            name  = "CHROMA_HOST"
            value = "chromadb.chromadb.svc.cluster.local"
          }
          env {
            name  = "CHROMA_PORT"
            value = "8000"
          }
          env {
            name = "ANTHROPIC_API_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.vanna_secrets.metadata[0].name
                key  = "anthropic-api-key"
              }
            }
          }
          env {
            name  = "LOG_LEVEL"
            value = "INFO"
          }

          # Redash 연동 ENV (Text-to-SQL)
          env {
            name  = "REDASH_BASE_URL"
            value = "http://redash.redash.svc.cluster.local:5000"
          }
          env {
            name = "REDASH_API_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.vanna_secrets.metadata[0].name
                key  = "redash-api-key"
              }
            }
          }
          env {
            name  = "REDASH_DATA_SOURCE_ID"
            value = "1"
          }
          env {
            name  = "REDASH_ENABLED"
            value = "true"
          }
          env {
            name  = "REDASH_QUERY_TIMEOUT_SEC"
            value = "300"
          }
          env {
            name  = "REDASH_POLL_INTERVAL_SEC"
            value = "3"
          }

          # Athena Workgroup (Text-to-SQL 전용, 1GB 스캔 제한)
          env {
            name  = "ATHENA_WORKGROUP"
            value = aws_athena_workgroup.text2sql.name
          }

          # Matplotlib headless 모드 (차트 생성용)
          env {
            name  = "MPLBACKEND"
            value = "Agg"
          }

          # 내부 서비스 인증 토큰 (SEC-17)
          env {
            name = "INTERNAL_API_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.vanna_secrets.metadata[0].name
                key  = "internal-api-token"
              }
            }
          }

          # Redash 외부 접근 URL (차트 링크 생성용, Minor 6)
          env {
            name  = "REDASH_PUBLIC_URL"
            value = var.redash_public_url
          }

          # 히스토리 저장 경로 (history_recorder.py)
          # NFR-07: emptyDir 마운트 — Pod 재시작 시 이력 소실. 운영환경은 EFS PVC로 교체 필요
          volume_mount {
            name       = "data"
            mount_path = "/data"
          }

          # 리소스 제한 (NFR-07: LLM 추론 메모리 1.5Gi 확보)
          resources {
            requests = {
              cpu    = "200m"
              memory = "768Mi"
            }
            limits = {
              cpu    = "400m"
              memory = "1.5Gi"
            }
          }

          # 헬스 체크(타임아웃 완화)
          liveness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 60
            period_seconds        = 20
            timeout_seconds       = 15
            failure_threshold     = 5
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 10
            failure_threshold     = 3
          }
        }

        # /data emptyDir 볼륨 (NFR-07: 히스토리 저장. 운영환경은 EFS PVC로 교체 필요)
        volume {
          name = "data"
          empty_dir {}
        }

        # 노드별 균등 배분 설정
        topology_spread_constraint {
          max_skew           = 1
          topology_key       = "kubernetes.io/hostname"
          when_unsatisfiable = "ScheduleAnyway"
          label_selector {
            match_labels = {
              app = "vanna-api"
            }
          }
        }
      }
    }
  }

  depends_on = [kubernetes_service.vanna_api, kubernetes_secret.vanna_secrets]
}



# =====================================================================================================================
# Slack Bot (Socket Mode)
# =====================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------
# Slack Bot Namespace
# ---------------------------------------------------------------------------------------------------------------------

resource "kubernetes_namespace" "slack_bot" {
  metadata {
    name = "slack-bot"
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# Slack Bot - ECR Repository
# ---------------------------------------------------------------------------------------------------------------------

resource "aws_ecr_repository" "slack_bot" {
  name                 = "capa-slack-bot"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = false
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

output "slack_bot_repository_url" {
  value       = aws_ecr_repository.slack_bot.repository_url
  description = "ECR repository URL for Slack Bot"
}

# ---------------------------------------------------------------------------------------------------------------------
# Slack Bot - Secrets
# ---------------------------------------------------------------------------------------------------------------------

resource "kubernetes_secret" "slack_bot_secrets" {
  metadata {
    name      = "slack-bot-secrets"
    namespace = kubernetes_namespace.slack_bot.metadata[0].name
  }

  data = {
    slack-bot-token    = var.slack_bot_token
    slack-app-token    = var.slack_app_token
    internal-api-token = var.internal_api_token
  }

  type = "Opaque"
}

# ---------------------------------------------------------------------------------------------------------------------
# Slack Bot - Kubernetes Resources
# ---------------------------------------------------------------------------------------------------------------------

# Service (for Health Check & Internal Access)
resource "kubernetes_service" "slack_bot" {
  metadata {
    name      = "slack-bot"
    namespace = kubernetes_namespace.slack_bot.metadata[0].name
    labels = {
      app = "slack-bot"
    }
  }

  spec {
    selector = {
      app = "slack-bot"
    }

    port {
      name        = "http"
      port        = 3000 # Flask Port
      target_port = 3000
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

# Deployment
resource "kubernetes_deployment" "slack_bot" {
  metadata {
    name      = "slack-bot"
    namespace = kubernetes_namespace.slack_bot.metadata[0].name
    labels = {
      app = "slack-bot"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "slack-bot"
      }
    }

    template {
      metadata {
        labels = {
          app = "slack-bot"
        }
      }

      spec {
        # [Karpenter] 스팟 노드 배치 허용
        toleration {
          key      = "karpenter.sh/disruption"
          operator = "Exists"
          effect   = "NoSchedule"
        }

        container {
          name              = "slack-bot"
          image             = "${aws_ecr_repository.slack_bot.repository_url}:latest"
          image_pull_policy = "Always"

          port {
            name           = "http"
            container_port = 3000
            protocol       = "TCP"
          }

          # 환경 변수 (Secrets)
          env {
            name = "SLACK_BOT_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.slack_bot_secrets.metadata[0].name
                key  = "slack-bot-token"
              }
            }
          }
          env {
            name = "SLACK_APP_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.slack_bot_secrets.metadata[0].name
                key  = "slack-app-token"
              }
            }
          }

          # 환경 변수 (Internal Service URLs)
          env {
            name  = "REPORT_API_URL"
            value = "http://report-generator.report.svc.cluster.local:8000"
          }
          env {
            name  = "VANNA_API_URL"
            value = "http://vanna-api.vanna.svc.cluster.local:8000"
          }

          # 내부 서비스 인증 토큰 (SEC-17, vanna-api 호출용)
          env {
            name = "INTERNAL_API_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.slack_bot_secrets.metadata[0].name
                key  = "internal-api-token"
              }
            }
          }

          # 리소스 제한
          resources {
            requests = {
              cpu    = "50m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "256Mi"
            }
          }

          # 헬스 체크 (/health)
          liveness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            failure_threshold     = 2
          }
        }
      }
    }
  }

  depends_on = [kubernetes_service.slack_bot, kubernetes_secret.slack_bot_secrets]
}

# =====================================================================================================================
# Athena Workgroup (Text-to-SQL 전용)
# 1GB 스캔 제한으로 비용 안전장치 확보 (Design §5.3)
# =====================================================================================================================

resource "aws_athena_workgroup" "text2sql" {
  name = "capa-text2sql-wg"

  configuration {
    enforce_workgroup_configuration = true
    bytes_scanned_cutoff_per_query  = 1073741824 # 1 GB

    result_configuration {
      output_location = "s3://${aws_s3_bucket.data_lake.bucket}/athena-results/text2sql/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = {
    Project     = "CAPA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# =====================================================================================================================
# [제거됨] Cluster Autoscaler
# Karpenter로 대체되었습니다. (15-karpenter.tf 참고)
# IAM Role/Policy (02-iam.tf의 aws_iam_role.cluster_autoscaler)는 삭제 대상이나
# 안전을 위해 terraform state rm 후 수동 정리를 권장합니다.
# =====================================================================================================================

# =====================================================================================================================
# Horizontal Pod Autoscalers (HPA)
# =====================================================================================================================

resource "kubernetes_horizontal_pod_autoscaler_v2" "vanna_api" {
  metadata {
    name      = "vanna-api-hpa"
    namespace = kubernetes_namespace.vanna.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = "vanna-api"
    }

    min_replicas = 1
    max_replicas = 3

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }

  depends_on = [kubernetes_deployment.vanna_api]
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "slack_bot" {
  metadata {
    name      = "slack-bot-hpa"
    namespace = kubernetes_namespace.slack_bot.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = "slack-bot"
    }

    min_replicas = 1
    max_replicas = 3

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }

  depends_on = [kubernetes_deployment.slack_bot]
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "report_generator" {
  metadata {
    name      = "report-generator-hpa"
    namespace = kubernetes_namespace.report.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = "report-generator"
    }

    min_replicas = 1
    max_replicas = 3

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }

  depends_on = [kubernetes_deployment.report_generator]
}
