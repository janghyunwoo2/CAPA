# Helm Chart Applications
# This file manages all Helm releases for applications running on EKS.
# For Kubernetes native deployments (non-Helm), see 11-k8s-apps.tf

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

resource "kubernetes_namespace" "chromadb" {
  metadata {
    name = "chromadb"
  }
}

/*
resource "kubernetes_namespace" "ai_apps" {
  metadata {
    name = "ai-apps" # Shared namespace for Vanna, ChromaDB
  }
}
*/

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
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.redash.arn
  }

  # Redis 인증 비활성화 명시 (WRONGPASS 오류 방지)
  set {
    name  = "redis.auth.enabled"
    value = "false"
  }
}

# Data source to retrieve Redash LoadBalancer URL
data "kubernetes_service" "redash" {
  metadata {
    name      = "redash"
    namespace = kubernetes_namespace.redash.metadata[0].name
  }
  depends_on = [helm_release.redash]
}

# ChromaDB (Vector DB for AI)
resource "helm_release" "chromadb" {
  name       = "chromadb"
  repository = "https://amikos-tech.github.io/chromadb-chart/"
  chart      = "chromadb"
  namespace  = kubernetes_namespace.chromadb.metadata[0].name

  values = [
    file("${path.module}/../helm-values/chromadb.yaml")
  ]

  set {
    name  = "persistence.size"
    value = "5Gi" # Plan에 명시된 5Gi 사용
  }

  depends_on = [aws_eks_addon.ebs_csi]
}

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
