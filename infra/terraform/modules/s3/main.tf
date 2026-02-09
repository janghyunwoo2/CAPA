# S3 Bucket
resource "aws_s3_bucket" "capa_logs" {
  bucket = var.bucket_name

  tags = {
    Name        = var.bucket_name
    Environment = var.environment
  }
}

# 버킷 버전 관리
resource "aws_s3_bucket_versioning" "capa_logs" {
  bucket = aws_s3_bucket.capa_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# 버킷 암호화
resource "aws_s3_bucket_server_side_encryption_configuration" "capa_logs" {
  bucket = aws_s3_bucket.capa_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 버킷 퍼블릭 액세스 차단
resource "aws_s3_bucket_public_access_block" "capa_logs" {
  bucket = aws_s3_bucket.capa_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle 규칙 (오래된 데이터 자동 삭제)
resource "aws_s3_bucket_lifecycle_configuration" "capa_logs" {
  bucket = aws_s3_bucket.capa_logs.id

  rule {
    id     = "delete_old_data"
    status = "Enabled"

    # 90일 후 Glacier로 이동
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # 180일 후 삭제
    expiration {
      days = 180
    }
  }
}
