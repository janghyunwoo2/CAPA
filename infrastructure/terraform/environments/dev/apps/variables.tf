variable "slack_bot_token" {
  description = "Slack Bot Token (xoxb-...)"
  type        = string
  sensitive   = true
}

variable "slack_app_token" {
  description = "Slack App Token (xapp-...)"
  type        = string
  sensitive   = true
}

variable "cluster_name" {
  description = "EKS Cluster Name"
  type        = string
  default     = "capa-eks-dev"
}
