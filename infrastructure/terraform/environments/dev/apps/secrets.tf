resource "kubernetes_secret" "slack_bot_secret" {
  metadata {
    name      = "slack-bot-secret"
    namespace = "default" # 슬랙봇이 배포될 네임스페이스
  }

  data = {
    "bot-token" = var.slack_bot_token
    "app-token" = var.slack_app_token
  }

  type = "Opaque"
}
