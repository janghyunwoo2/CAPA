#!/usr/bin/env python3
"""
summary/ 폴더의 CSV/metadata 파일 정리
ad_combined_log* 폴더는 제외하고, 최상위 CSV/metadata만 삭제
"""

import boto3
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path('.') / 'services/data_pipeline_t2/.env'
if env_path.exists():
    load_dotenv(env_path)

s3 = boto3.client('s3', region_name='ap-northeast-2')
bucket = 'capa-data-lake-827913617635'

print("=" * 80)
print("📂 summary/ 폴더 CSV/metadata 파일 정리")
print("=" * 80)

# summary 폴더의 파일 목록 조회
response = s3.list_objects_v2(
    Bucket=bucket,
    Prefix='summary/'
)

files_to_delete = []

# CSV 또는 metadata 파일 && ad_combined_log* 폴더 제외
for obj in response.get('Contents', []):
    key = obj['Key']
    
    # summary/ 직접 아래의 CSV/metadata만 삭제 (하위 폴더의 파일은 제외)
    if (key.endswith('.csv') or key.endswith('.csv.metadata')) and \
       'ad_combined_log' not in key and \
       key.count('/') == 1:  # summary/xxx.csv (슬래시가 1개만)
        files_to_delete.append(key)

print(f"\n삭제할 파일: {len(files_to_delete)}개\n")

if files_to_delete:
    # 삭제 전 확인
    for f in files_to_delete[:5]:
        print(f"  - {f}")
    
    if len(files_to_delete) > 5:
        print(f"  ... 그 외 {len(files_to_delete) - 5}개")
    
    # 사용자 확인
    response = input("\n위 파일들을 삭제하시겠습니까? (y/n): ")
    
    if response.lower() == 'y':
        deleted_count = 0
        for key in files_to_delete:
            try:
                s3.delete_object(Bucket=bucket, Key=key)
                print(f"  ✅ Deleted: {key}")
                deleted_count += 1
            except Exception as e:
                print(f"  ❌ Failed to delete {key}: {str(e)}")
        
        print(f"\n" + "=" * 80)
        print(f"✅ 총 {deleted_count}개 파일 삭제 완료")
        print("=" * 80)
    else:
        print("삭제 취소됨")
else:
    print("❌ 삭제할 CSV/metadata 파일이 없습니다")
    print("\n현재 summary/ 폴더의 파일 상태:")
    
    # 현재 상태 출력
    csv_count = 0
    meta_count = 0
    for obj in response.get('Contents', []):
        key = obj['Key']
        if key.endswith('.csv') and 'ad_combined_log' not in key:
            csv_count += 1
        elif key.endswith('.csv.metadata') and 'ad_combined_log' not in key:
            meta_count += 1
    
    print(f"  CSV 파일: {csv_count}개")
    print(f"  Metadata 파일: {meta_count}개")
