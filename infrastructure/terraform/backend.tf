# terraform {
#   backend "s3" {
#     bucket         = "capa-terraform-state-827913617635"
#     key            = "dev/base/terraform.tfstate"
#     region         = "ap-northeast-2"
#     dynamodb_table = "capa-terraform-lock"
#     encrypt        = true
#   }
# }

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
