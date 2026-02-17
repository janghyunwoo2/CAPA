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

    type = "LoadBalancer"
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

          # 리소스 제한
          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }

          # 헬스 체크
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

# Secret (Anthropic API Key)
resource "kubernetes_secret" "vanna_secrets" {
  metadata {
    name      = "vanna-secrets"
    namespace = kubernetes_namespace.vanna.metadata[0].name
  }

  data = {
    anthropic-api-key = var.anthropic_api_key
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

          # 리소스 제한
          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "1000m"
              memory = "2Gi"
            }
          }

          # 헬스 체크
          liveness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 60
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 2
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
    slack-bot-token = var.slack_bot_token
    slack-app-token = var.slack_app_token
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
            name  = "VANNA_API_URL"
            value = "http://vanna-api.vanna.svc.cluster.local:8000"
          }
          env {
            name  = "REPORT_API_URL"
            value = "http://report-generator.report.svc.cluster.local:8000"
          }

          # 리소스 제한
          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
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
