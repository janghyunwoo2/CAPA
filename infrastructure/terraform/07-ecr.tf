# ECR Repositories for CAPA Project
# 용도: Airflow PostgreSQL 등 커스텀/미러링 이미지 저장

resource "aws_ecr_repository" "postgres" {
  name                 = "capa/postgres"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true # 개발 환경이므로 삭제 허용
}

output "postgres_repository_url" {
  value = aws_ecr_repository.postgres.repository_url
}

resource "aws_ecr_repository" "redis" {
  name                 = "capa/redis"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true
}

output "redis_repository_url" {
  value = aws_ecr_repository.redis.repository_url
}
