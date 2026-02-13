# S3 Data Lake
# 작업: 05_data_pipeline_기본.md (Phase 1)
# 용도: Parquet 데이터 저장소

# ============================================
# Account ID 조회 (Bucket 이름에 사용)
# ============================================
data "aws_caller_identity" "current" {}

# ============================================
# 1. S3 Bucket
# ============================================
resource "aws_s3_bucket" "data_lake" {
  bucket = "${var.project_name}-data-lake-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-data-lake"
  }
}

# ============================================
# 2. Versioning (데이터 보호)
# ============================================
resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ============================================
# 3. Lifecycle Policy (비용 절감)
# ============================================
resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    expiration {
      days = 90 # 90일 후 삭제
    }
  }
}
