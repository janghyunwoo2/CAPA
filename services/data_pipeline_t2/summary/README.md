# Ad Summary ETL

광고 로그 데이터를 집계하여 summary 테이블을 생성하는 ETL 스크립트입니다.

## 개요

- **Hourly ETL**: 매시간 impression + click 로그를 조인하여 `ad_combined_log` 생성
- **Daily ETL**: 24시간 ad_combined_log + conversion을 집계하여 `ad_combined_log_summary` 생성

## 설치

```bash
pip install -r requirements.txt
```

## 설정

`config.py`에서 AWS 및 S3 설정을 확인하고 필요시 수정:

```python
AWS_REGION = "ap-northeast-2"
S3_BUCKET = "capa-data-lake-827913617635"
DATABASE = "capa_ad_logs"
```

## 사용법

### 1. Hourly ETL 실행

이전 시간의 데이터를 처리:
```bash
python run_etl.py hourly
```

특정 시간 지정:
```bash
python run_etl.py hourly --target-hour 2026-02-24-14
```

### 2. Daily ETL 실행

어제 데이터를 처리:
```bash
python run_etl.py daily
```

특정 날짜 지정:
```bash
python run_etl.py daily --target-date 2026-02-24
```

### 3. 과거 데이터 백필

시간별 백필:
```bash
python run_etl.py backfill --start-date 2026-02-20 --end-date 2026-02-24 --type hourly
```

일별 백필:
```bash
python run_etl.py backfill --start-date 2026-02-20 --end-date 2026-02-24 --type daily
```

## 개별 스크립트 실행

각 ETL을 개별적으로 실행할 수도 있습니다:

```bash
# Hourly ETL
python hourly_etl.py --target-hour 2026-02-24-14

# Daily ETL
python daily_etl.py --target-date 2026-02-24
```

## 출력 경로

- **ad_combined_log**: `s3://버킷/summary/ad_combined_log/dt=YYYY-MM-DD-HH/`
- **ad_combined_log_summary**: `s3://버킷/summary/ad_combined_log_summary/dt=YYYY-MM-DD/`

## 테이블 스키마

### ad_combined_log (Hourly)
- impression_id: 노출 이벤트 ID
- user_id: 사용자 ID
- ad_id: 광고 ID
- campaign_id: 캠페인 ID
- advertiser_id: 광고주 ID
- platform: 플랫폼
- device_type: 디바이스 타입
- timestamp: 이벤트 시간 (milliseconds)
- is_click: 클릭 여부 (boolean)
- click_timestamp: 클릭 시간

### ad_combined_log_summary (Daily)
- campaign_id: 캠페인 ID
- ad_id: 광고 ID
- advertiser_id: 광고주 ID
- device_type: 디바이스 타입
- impressions: 노출수
- clicks: 클릭수
- conversions: 전환수
- ctr: 클릭률 (%)
- cvr: 전환율 (%)

## 주의사항

1. **AWS 권한**: 실행 환경에 Athena, S3, Glue 접근 권한이 필요합니다.
2. **데이터 의존성**: 
   - Hourly ETL은 해당 시간의 raw 데이터가 있어야 실행 가능
   - Daily ETL은 24시간의 hourly 데이터가 있어야 실행 가능
3. **시간대**: 모든 시간은 UTC 기준입니다.

## 로그

실행 로그는 콘솔에 출력되며, 다음 정보를 포함합니다:
- 처리 중인 파티션
- Athena 쿼리 ID
- 스캔한 데이터 크기
- 처리된 레코드 수
- CTR/CVR 등 주요 지표

## 문제 해결

1. **파티션이 인식되지 않는 경우**:
   ```sql
   MSCK REPAIR TABLE ad_log.ad_combined_log;
   MSCK REPAIR TABLE ad_log.ad_combined_log_summary;
   ```

2. **쿼리 타임아웃**:
   `config.py`에서 `QUERY_TIMEOUT_SECONDS` 값을 늘립니다.

3. **권한 오류**:
   AWS 자격 증명과 IAM 권한을 확인합니다.