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

resource "kubernetes_namespace" "ai_apps" {
  metadata {
    name = "ai-apps" # Shared namespace for Vanna, ChromaDB, ReportGen
  }
}

# ---------------------------------------------------------------------------------------------------------------------
# 2. Secrets
# ---------------------------------------------------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------------------------------------------------
# 3. Helm Releases
# ---------------------------------------------------------------------------------------------------------------------

# Airflow
resource "helm_release" "airflow" {
  name       = "airflow"
  repository = "https://airflow.apache.org"
  chart      = "airflow"
  version    = "1.12.0"
  namespace  = kubernetes_namespace.airflow.metadata[0].name
  # create_namespace = true # Managed by resource above

  values = [
    file("${path.module}/../../../../helm-values/airflow.yaml")
  ]

  timeout = 900
}

# Redash
resource "helm_release" "redash" {
  name       = "redash"
  repository = "https://redash.github.io/contrib-helm-chart"
  chart      = "redash"
  version    = "3.0.0"
  namespace  = kubernetes_namespace.redash.metadata[0].name

  values = [
    file("${path.module}/../../../../helm-values/redash.yaml")
  ]
}

# ChromaDB (Vector DB for AI)
resource "helm_release" "chromadb" {
  name       = "chromadb"
  repository = "https://amikos-tech.github.io/helm-charts"
  chart      = "chromadb"
  namespace  = kubernetes_namespace.ai_apps.metadata[0].name

  values = [
    file("${path.module}/../../../../helm-values/chromadb.yaml")
  ]
}

# ---------------------------------------------------------------------------------------------------------------------
# 4. Custom Applications (Generic Service)
# ---------------------------------------------------------------------------------------------------------------------

# Report Generator
resource "helm_release" "report_generator" {
  name      = "report-generator"
  chart     = "${path.module}/../../../../charts/generic-service"
  namespace = kubernetes_namespace.ai_apps.metadata[0].name

  values = [
    file("${path.module}/../../../../helm-values/report-generator.yaml")
  ]
}

# Vanna AI
resource "helm_release" "vanna" {
  name      = "vanna"
  chart     = "${path.module}/../../../../charts/generic-service"
  namespace = kubernetes_namespace.ai_apps.metadata[0].name

  values = [
    file("${path.module}/../../../../helm-values/vanna.yaml")
  ]
}

# Slack Bot
resource "helm_release" "slack_bot" {
  name      = "slack-bot"
  chart     = "${path.module}/../../../../charts/generic-service"
  namespace = "default"

  values = [
    file("${path.module}/../../../../helm-values/slack-bot.yaml")
  ]

  depends_on = [kubernetes_secret.slack_bot_secrets]
}
