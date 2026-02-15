# Applications Deployment
# This file manages all Helm releases for applications running on EKS.
# It uses the "generic-service" chart for custom applications and standard charts for open-source tools.

# ---------------------------------------------------------------------------------------------------------------------
# 1. Namespaces
# ---------------------------------------------------------------------------------------------------------------------

resource "kubernetes_namespace" "airflow" {
  metadata {
    name = "airflow"
  }
}

resource "kubernetes_namespace" "redash" {
  metadata {
    name = "redash"
  }
}

resource "kubernetes_namespace" "report" {
  metadata {
    name = "report"
  }
}

/*
resource "kubernetes_namespace" "ai_apps" {
  metadata {
    name = "ai-apps" # Shared namespace for Vanna, ChromaDB, ReportGen
  }
}
*/

# Report Generator ServiceAccount (IRSA)
resource "kubernetes_service_account" "report_generator_sa" {
  metadata {
    name      = "report-generator-sa"
    namespace = kubernetes_namespace.report.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.report_generator.arn
    }
  }
}

# Report Generator Service
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

# Report Generator Deployment
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

# =======================================================================
# Report Generator IAM & ECR
# =======================================================================

# ECR Repository (Report Generator)
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

# Report Generator IAM Role
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
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults"
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
# 2. Secrets
# ---------------------------------------------------------------------------------------------------------------------

/*
# Slack Bot Secrets
resource "kubernetes_secret" "slack_bot_secrets" {
  metadata {
    name      = "slack-bot-secret"
    namespace = "default" # Bot deployed to default or specific namespace
  }

  data = {
    bot-token = var.slack_bot_token
    app-token = var.slack_app_token
  }

  type = "Opaque"
}
*/

# ---------------------------------------------------------------------------------------------------------------------
# 3. Helm Releases
# ---------------------------------------------------------------------------------------------------------------------

# Airflow
resource "helm_release" "airflow" {
  name       = "airflow"
  repository = "https://airflow.apache.org"
  chart      = "airflow"
  version    = "1.15.0"
  namespace  = kubernetes_namespace.airflow.metadata[0].name
  # create_namespace = true # Managed by resource above

  values = [
    file("${path.module}/../helm-values/airflow.yaml")
  ]

  # IRSA: 각 컴포넌트에 IAM Role 주입 (이전 프로젝트 패턴)
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.airflow.arn
  }
  set {
    name  = "scheduler.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.airflow.arn
  }
  set {
    name  = "webserver.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.airflow.arn
  }
  set {
    name  = "triggerer.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.airflow.arn
  }
  set {
    name  = "workers.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.airflow.arn
  }

  timeout = 900
  wait    = true

  # StorageClass 및 IAM Role dependency 명시
  depends_on = [
    kubernetes_storage_class.gp2,
    aws_iam_role_policy_attachment.airflow_s3_access
  ]
}



# Data source to retrieve Airflow Webserver LoadBalancer URL
data "kubernetes_service" "airflow_webserver" {
  metadata {
    name      = "airflow-webserver"
    namespace = kubernetes_namespace.airflow.metadata[0].name
  }
  depends_on = [helm_release.airflow]
}


# Redash
resource "helm_release" "redash" {
  name       = "redash"
  repository = "https://getredash.github.io/contrib-helm-chart/"
  chart      = "redash"
  version    = "3.0.0"
  namespace  = kubernetes_namespace.redash.metadata[0].name

  values = [
    file("${path.module}/../helm-values/redash.yaml")
  ]

  set_sensitive {
    name  = "postgresql.postgresqlPassword"
    value = var.redash_postgresql_password
  }

  set_sensitive {
    name  = "redash.cookieSecret"
    value = var.redash_cookie_secret
  }

  set_sensitive {
    name  = "redash.secretKey"
    value = var.redash_secret_key
  }

  set {
    name  = "redash.databaseUrl"
    value = "postgresql://redash:${var.redash_postgresql_password}@redash-postgresql/redash"
  }

  set {
    name  = "redash.redisUrl"
    value = "redis://redash-redis-master:6379/0"
  }

  set {
    name  = "redash.env.REDASH_DATABASE_URL"
    value = "postgresql://redash:${var.redash_postgresql_password}@redash-postgresql/redash"
  }

  set {
    name  = "redash.env.REDASH_REDIS_URL"
    value = "redis://redash-redis-master:6379/0"
  }
}

/*
# ChromaDB (Vector DB for AI)
resource "helm_release" "chromadb" {
  name       = "chromadb"
  repository = "https://amikos-tech.github.io/helm-charts"
  chart      = "chromadb"
  namespace  = kubernetes_namespace.ai_apps.metadata[0].name

  values = [
    file("${path.module}/../helm-values/chromadb.yaml")
  ]
}
*/

# ---------------------------------------------------------------------------------------------------------------------
# 4. Custom Applications (Generic Service)
# ---------------------------------------------------------------------------------------------------------------------

/*
# Report Generator
resource "helm_release" "report_generator" {
  name      = "report-generator"
  chart     = "${path.module}/../charts/generic-service"
  namespace = kubernetes_namespace.ai_apps.metadata[0].name

  values = [
    file("${path.module}/../helm-values/report-generator.yaml")
  ]
}

# Vanna AI
resource "helm_release" "vanna" {
  name      = "vanna"
  chart     = "${path.module}/../charts/generic-service"
  namespace = kubernetes_namespace.ai_apps.metadata[0].name

  values = [
    file("${path.module}/../helm-values/vanna.yaml")
  ]
}

# Slack Bot
resource "helm_release" "slack_bot" {
  name      = "slack-bot"
  chart     = "${path.module}/../charts/generic-service"
  namespace = "default"

  values = [
    file("${path.module}/../helm-values/slack-bot.yaml")
  ]

  depends_on = [kubernetes_secret.slack_bot_secrets]
}
*/
