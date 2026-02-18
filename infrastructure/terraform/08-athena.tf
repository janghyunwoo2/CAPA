# Amazon Athena Configuration
# 작업: 05_data_pipeline_기본.md (Phase 1)
# 용도: SQL 쿼리 엔진 설정

# TODO: Athena Workgroup
resource "aws_athena_workgroup" "capa" {
  name = "${var.project_name}-workgroup"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.data_lake.bucket}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  force_destroy = true
}
# TODO: Query Result Location
# TODO: Encryption Settings
