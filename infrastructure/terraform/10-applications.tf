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

# T3 Report Generator - Slack Secret (for KubernetesPodOperator DAG)
resource "kubernetes_secret" "t3_report_slack" {
  metadata {
    name      = "t3-report-secret"
    namespace = kubernetes_namespace.airflow.metadata[0].name
  }

  data = {
    SLACK_BOT_TOKEN  = var.slack_bot_token
    SLACK_CHANNEL_ID = var.slack_channel_id
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

  timeout = 600
  wait    = false # Karpenter가 비동기로 노드를 프로비저닝하므로 Terraform이 대기하지 않음

  # 배포 순서: 인프라(NodePool) 완료 후 애플리케이션 배포
  depends_on = [
    kubernetes_storage_class.gp2,
    aws_iam_role_policy_attachment.airflow_s3_access,
    kubectl_manifest.karpenter_nodepool_default # 스팟 노드 준비 후 배포
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

  # Server 리소스 및 프로브 최적화 (Target 12 기록 기반)
  set {
    name  = "server.resources.limits.cpu"
    value = "1000m"
  }

  set {
    name  = "server.resources.limits.memory"
    value = "1Gi"
  }

  set {
    name  = "server.readinessProbe.initialDelaySeconds"
    value = "60"
  }

  set {
    name  = "server.readinessProbe.timeoutSeconds"
    value = "15"
  }
  wait = false # Karpenter 비동기 노드 프로비저닝 대응

  # 배포 순서: 인프라(NodePool) 완료 후 배포
  depends_on = [
    kubectl_manifest.karpenter_nodepool_default
  ]
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
    value = "5Gi"
  }

  set {
    name  = "env.IS_PERSISTENT"
    value = "TRUE"
  }

  set {
    name  = "env.PERSIST_DIRECTORY"
    value = "/data"
  }

  set {
    name  = "env.CHROMA_SERVER_AUTH_PROVIDER"
    value = ""
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
