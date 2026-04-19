# 로컬 광고 로그 생성기 통합 가이드

로컬 환경에서 광고 로그 데이터를 생성·검증하고, 필요 시 S3(Parquet/zstd)로 적재하는 전체 가이드입니다. 폴더 전용 가이드 내용을 통합하여 중복을 제거했습니다.

관련 파일/위치
- 소스: [services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py](services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py)
- 요구사항: [services/data_pipeline_t2/gen_adlog_t2/local/requirements.txt](services/data_pipeline_t2/gen_adlog_t2/local/requirements.txt)
- Athena 쿼리 모음: [services/data_pipeline_t2/gen_adlog_t2/local/ATHENA_QUERIES.md](services/data_pipeline_t2/gen_adlog_t2/local/ATHENA_QUERIES.md)

## 1) 설치와 환경

```powershell
# Windows 권장: venv 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 의존성 설치 (둘 중 택1)
# 1) 프로젝트 루트 표준 requirements
pip install -r requirements.txt
# 2) 로컬 생성기 전용 requirements
pip install -r services/data_pipeline_t2/gen_adlog_t2/local/requirements.txt
```

필수 환경변수(.env):
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-2
```

선택: uv 사용 시 더 빠르게 설치/실행 가능합니다.
```powershell
pip install uv
uv sync
uv run python <script_path>.py
```

필수 환경변수(.env):
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-2
```

참고: S3 버킷 이름은 스크립트 상수로 고정되어 있습니다.
- 기본값: `capa-data-lake-827913617635`
- 변경하려면 [services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py](services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py) 내 `S3_BUCKET_NAME`을 수정하세요.

## 2) 배치형 로그 생성기 사용법

다양한 기간/시간대 옵션으로 배치 데이터를 생성합니다.

```powershell
# 기본: 오늘 날짜 24시간 데이터
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py

# 특정 날짜
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --date 2026-02-23

# 날짜 구간
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --start-date 2026-02-20 --end-date 2026-02-22

# 과거 N일
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --days-back 7

# 시간대 지정
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --start-hour 12 --hours 6
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --date 2026-02-20 --start-hour 18 --hours 4
```

백필 예시:
```powershell
# 지난달 전체
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --start-date 2026-01-01 --end-date 2026-01-31

# 특정 주간
python services/data_pipeline_t2/gen_adlog_t2/local/ad_log_generator.py --start-date 2026-02-17 --end-date 2026-02-23
```

## 3) 출력(S3) 구조

경로 구조:
```
s3://<bucket>/raw/
├── impressions/year=YYYY/month=MM/day=DD/hour=HH/
├── clicks/year=YYYY/month=MM/day=DD/hour=HH/
└── conversions/year=YYYY/month=MM/day=DD/hour=HH/
```

파일명 패턴: `<table>_YYYYMMDD_HH_<8자리랜덤>.parquet.zstd`
테이블: `impressions`, `clicks`, `conversions`

## 4) 데이터 스키마(요약)

- Impressions
	- 식별/컨텍스트: `impression_id`, `timestamp`, `user_id`, `ad_id`, `campaign_id`, `advertiser_id`
	- 디바이스/플랫폼: `platform`, `device_type`, `os`, `user_agent`, `ip_address`
	- 위치/매장: `delivery_region`, `user_lat`, `user_long`, `store_id`, `food_category`
	- 광고 메타: `ad_position`, `ad_format`, `keyword`, `session_id`, `cost_per_impression`

- Clicks
	- `click_id`, `impression_id`, `timestamp`, `user_id`, `ad_id`, `campaign_id`, `advertiser_id`
	- `click_position_x`, `click_position_y`, `landing_page_url`, `cost_per_click`

- Conversions
	- `conversion_id`, `click_id`, `impression_id`, `timestamp`, `user_id`, `ad_id`, `campaign_id`, `advertiser_id`
	- `conversion_type`, `conversion_value`, `product_id`, `quantity`, `store_id`, `delivery_region`, `attribution_window`

## 5) 트래픽/전환 로직(요약)

- 점심(11-14시): 150-200%
- 저녁(17-21시): 200-300% (피크)
- 주말: 평일 대비 150-200%
 - CTR: 포맷별 범위 적용, 지역 가중치(강남/서초 +20%)
 - CVR: 전환유형별 확률(예: `purchase` ~1–3%)
 - 전환 시간: 클릭 후 1분~7일 사이 무작위 지연

### 5.1 노출/클릭/전환 확률의 상세 로직
- 노출(Impressions)
	- 기본 노출 수는 base_impressions(기본값 10000)이며, target_datetime의 시간대와 요일에 따라 traffic_multiplier를 곱해 결정됩니다.
	- traffic_multiplier는 시간대(hour)별 패턴(hour_mult)과 요일(day_mult)를 곱한 값으로 계산됩니다. 예를 들어 점심시간대나 주말에 증가하는 흐름을 반영합니다.
	- 따라서 특정 시점의 노출 수는 정적으로 결정되며, 실제로는 int(base_impressions * traffic_multiplier)로 산출됩니다.

- 클릭(Clicks)
	- 각 노출마다 클릭 확률은 광고 포맷별 CTR_RATES에서 정의된 범위에서 무작위로 추출된 CTR 값으로 결정됩니다.
	- CTR은 ad_format에 따라
		- display: 0.01~0.03, native: 0.02~0.04, video: 0.03~0.05, discount_coupon: 0.025~0.045
	- 지역 가중치가 적용됩니다. delivery_region이 강남구 또는 서초구인 경우 CTR이 1.2배 증가합니다.
	- 각 노출에 대해 rand() < CTR이 성립하면 클릭이 생성됩니다.
	- 생성되는 클릭은 click_id, timestamp, landing_page_url 등 클릭 관련 필드를 포함합니다.

- 전환(Conversions)
	- 클릭이 존재하는 행에 대해 전환 확률이 결정됩니다. 먼저 conversion_type을 CONVERSION_TYPES에서 무작위로 선택합니다.
	- 각 전환 유형에 대해 CVR_RATES는 (min, max) 형태의 값으로 정의됩니다.
	- 현재 구현은 각 클릭 행에 대해 random.random() < cvr_max를 사용하여 전환 여부를 결정합니다. 즉, 전환 확률은 전환 유형의 최대값(cvr_max)으로 간주됩니다.
	- 전환이 발생하면 전환 지연 시간은 클릭 시점으로부터 60초(1분)에서 7일 사이의 무작위 지연으로 계산됩니다.
	- 전환 정보에는 conversion_type, conversion_value, product_id, quantity, store_id, attribution_window 등이 포함됩니다.

- 요약 예시
	- ad_format이 video이고 CTR 범위가 0.03~0.05라면 평균적으로 약 4%의 노출에서 클릭이 발생합니다(지역 가중치 적용 시 약 4.8%까지 증가 가능).
	- 10000건의 노출 중 약 400건의 클릭이 예상되고, 이 중 conversion_type이 purchase일 경우 CVR 최대값(여기서는 예를 들어 0.03)을 확률로 사용한다면 약 12건의 전환이 발생할 수 있습니다. 실제 수치는 난수에 따라 달라집니다.

- 주의 및 개선 제안
	- 현재 CVR 계산은 각 전환 유형의 cvr_max를 확률 임계값으로 사용합니다. 이 값을 실제 CVR 범위로 샘플링하여 사용하도록 개선하는 것이 더 현실적인 분포를 제공합니다.
	- 예: cvr = random.uniform(cvr_min, cvr_max); if random.random() < cvr: 생성

## 6) 결과 확인/모니터링

- 완료 통계: 총 노출/클릭/전환, CTR/CVR, 시간대별 로그
- 파일 확인: Parquet/CSV/PNG 산출물 점검

## 7) Athena 연동

- Glue Crawler 또는 테이블 생성으로 파티션(`year`, `month`, `day`, `hour`) 등록
- 빠른 분석 템플릿: [services/data_pipeline_t2/gen_adlog_t2/local/ATHENA_QUERIES.md](services/data_pipeline_t2/gen_adlog_t2/local/ATHENA_QUERIES.md)

## 8) AWS 반영 포인트(요약)

| 로컬 구성요소 | AWS 전환 지점 |
|---|---|
| 파일 생성기 | Kinesis Producer 또는 컨테이너 |
| 로컬 Parquet | S3(+ Glue Catalog) |
| 집계 스크립트 | Athena SQL/Glue Job(Airflow 스케줄) |
| 분석/시각화 | Redash/QuickSight |

체크리스트: S3/Firehose/Glue/Airflow/Redash(+IAM) 설정 점검.

## 9) 트러블슈팅(핵심)

- ModuleNotFoundError → 가상환경 활성화/의존성 설치 재확인
- PowerShell 실행 정책 → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- 파일 누락 → 이전 단계 출력 경로 확인 후 재실행
 - 인증 오류 → `.env`의 자격증명과 버킷 권한 확인(put_object)
 - 파티션 조회 안 됨 → Glue Crawler 실행 또는 파티션 추가 후 Athena에서 `MSCK REPAIR TABLE`

## 10) 커스터마이징

- 생성량 조정(이벤트 수), 리포트 Top N, 임계값(threshold) 등 스크립트 파라미터로 제어
- 필요 시 `pyproject.toml + uv`로 의존성 고정 및 재현성 강화

## 참고/연계

- 실시간 생성기: [docs/t2/gen_adlog_realtime.md](docs/t2/gen_adlog_realtime.md)