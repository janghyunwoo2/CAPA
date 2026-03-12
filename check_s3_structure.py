#!/usr/bin/env python3
"""S3 summary 폴더 구조 확인"""

import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path(__file__).parent / 'services/data_pipeline_t2/.env'
if env_path.exists():
    load_dotenv(env_path)

s3_client = boto3.client('s3', region_name='ap-northeast-2')
bucket = 'capa-data-lake-827913617635'

print("=" * 80)
print("📂 S3 Summary 폴더 구조 분석")
print("=" * 80)

# 1. summary/ad_combined_log 폴더 파일 목록
print("\n1️⃣  summary/ad_combined_log/ 파일 목록 (처음 50개):")
print("-" * 80)

response = s3_client.list_objects_v2(
    Bucket=bucket,
    Prefix='summary/ad_combined_log/',
    MaxKeys=100
)

file_types = {'csv': [], 'metadata': [], 'parquet': [], 'other': []}

if 'Contents' in response:
    for i, obj in enumerate(response['Contents'][:50]):
        key = obj['Key']
        size = obj['Size']
        
        if key.endswith('.csv'):
            file_types['csv'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes) [CSV]")
        elif 'metadata' in key.lower() or key.endswith('.json'):
            file_types['metadata'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes) [METADATA]")
        elif key.endswith('.parquet'):
            file_types['parquet'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes) [PARQUET]")
        else:
            file_types['other'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes)")

# 2. athena-results 폴더 파일 목록
print("\n" + "=" * 80)
print("2️⃣  athena-results/ 폴더 파일 목록 (처음 30개):")
print("-" * 80)

response2 = s3_client.list_objects_v2(
    Bucket=bucket,
    Prefix='athena-results/',
    MaxKeys=50
)

athena_files = {'csv': [], 'metadata': [], 'other': []}

if 'Contents' in response2:
    for i, obj in enumerate(response2['Contents'][:30]):
        key = obj['Key']
        size = obj['Size']
        
        if key.endswith('.csv'):
            athena_files['csv'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes) [CSV]")
        elif 'metadata' in key.lower() or key.endswith('.json'):
            athena_files['metadata'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes) [METADATA]")
        else:
            athena_files['other'].append((key, size))
            print(f"  {i+1}. {key:80} ({size:,} bytes)")

# 3. 통계
print("\n" + "=" * 80)
print("📊 통계")
print("-" * 80)

print("\n✅ summary/ad_combined_log/:")
print(f"  - Parquet 파일: {len(file_types['parquet'])}개")
print(f"  - CSV 파일: {len(file_types['csv'])}개")
print(f"  - Metadata 파일: {len(file_types['metadata'])}개")
print(f"  - 기타: {len(file_types['other'])}개")

print("\n✅ athena-results/:")
print(f"  - CSV 파일: {len(athena_files['csv'])}개")
print(f"  - Metadata 파일: {len(athena_files['metadata'])}개")
print(f"  - 기타: {len(athena_files['other'])}개")

# 4. 의심스러운 CSV/Metadata 파일 경고
if file_types['csv']:
    print("\n⚠️  WARNING: summary/ad_combined_log/ 폴더에 CSV 파일이 있습니다!")
    print("  이것은 Glue Crawler가 이 폴더를 스캔하고 테이블을 자동 생성할 수 있습니다.")
    
if file_types['metadata']:
    print("\n⚠️  WARNING: summary/ad_combined_log/ 폴더에 메타데이터 파일이 있습니다!")
