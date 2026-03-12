#!/usr/bin/env python3
"""summary/ 폴더의 모든 파일 타입 상세 분석"""

import boto3
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / 'services/data_pipeline_t2/.env'
if env_path.exists():
    load_dotenv(env_path)

s3_client = boto3.client('s3', region_name='ap-northeast-2')
bucket = 'capa-data-lake-827913617635'

print("=" * 100)
print("📂 S3 summary/ 폴더 전체 파일 타입 분석")
print("=" * 100)

# 모든 summary 파일 나열
response = s3_client.list_objects_v2(
    Bucket=bucket,
    Prefix='summary/',
    MaxKeys=1000
)

file_stats = {
    'parquet': [],
    'csv': [],
    'metadata': [],
    'txt': [],
    'other': []
}

total_size = 0

if 'Contents' in response:
    print(f"\n총 파일 수: {len(response['Contents'])}\n")
    
    for obj in response['Contents']:
        key = obj['Key']
        size = obj['Size']
        total_size += size
        
        if key.endswith('.parquet'):
            file_stats['parquet'].append((key, size))
        elif key.endswith('.csv'):
            file_stats['csv'].append((key, size))
        elif 'metadata' in key.lower() or key.endswith('.json'):
            file_stats['metadata'].append((key, size))
        elif key.endswith('.txt'):
            file_stats['txt'].append((key, size))
        else:
            file_stats['other'].append((key, size))

# 통계 출력
print("=" * 100)
print("📊 파일 타입별 통계")
print("=" * 100)

for file_type, files in file_stats.items():
    if files:
        total_type_size = sum(size for _, size in files)
        print(f"\n✅ {file_type.upper()}: {len(files)}개 파일 ({total_type_size:,} bytes)")
        
        # 처음 10개만 표시
        for i, (key, size) in enumerate(files[:10]):
            print(f"  {i+1}. {key:80} ({size:,} bytes)")
        
        if len(files) > 10:
            print(f"  ... 그 외 {len(files) - 10}개 파일")

print(f"\n" + "=" * 100)
print(f"💾 전체 summary/ 폴더 크기: {total_size:,} bytes ({total_size / (1024*1024):.2f} MB)")
print("=" * 100)

# 문제 있는 파일 강조
if file_stats['csv']:
    print("\n⚠️  경고: summary/ 폴더에 CSV 파일이 있습니다!")
    print(f"   CSV 파일 {len(file_stats['csv'])}개 발견")
    
if file_stats['metadata']:
    print("\n⚠️  경고: summary/ 폴더에 메타데이터 파일이 있습니다!")
    print(f"   Metadata 파일 {len(file_stats['metadata'])}개 발견")

# 각 하위 폴더별 분석
print(f"\n" + "=" * 100)
print("📁 summary 하위 폴더별 상세 분석")
print("=" * 100)

subfolders = {}
for obj in response.get('Contents', []):
    key = obj['Key']
    # summary/ 다음의 첫 번째 폴더명 추출
    parts = key.replace('summary/', '').split('/')
    if parts:
        subfolder = parts[0]
        if subfolder not in subfolders:
            subfolders[subfolder] = {'total': 0, 'files': 0, 'csv': 0, 'metadata': 0, 'parquet': 0}
        
        subfolders[subfolder]['total'] += obj['Size']
        subfolders[subfolder]['files'] += 1
        
        if key.endswith('.csv'):
            subfolders[subfolder]['csv'] += 1
        elif 'metadata' in key.lower():
            subfolders[subfolder]['metadata'] += 1
        elif key.endswith('.parquet'):
            subfolders[subfolder]['parquet'] += 1

for subfolder, stats in sorted(subfolders.items()):
    print(f"\n📂 {subfolder}:")
    print(f"   - 파일 수: {stats['files']}개")
    print(f"   - CSV: {stats['csv']}개")
    print(f"   - Metadata: {stats['metadata']}개")
    print(f"   - Parquet: {stats['parquet']}개")
    print(f"   - 폴더 크기: {stats['total']:,} bytes ({stats['total'] / (1024*1024):.2f} MB)")
