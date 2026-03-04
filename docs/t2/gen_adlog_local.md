# 로컬 광고 로그 생성기 통합 가이드

로컬 환경에서 광고 로그 데이터를 생성·검증하고, 필요 시 S3(Parquet/zstd)로 적재하는 전체 가이드입니다. 기존 `gen_adlog_local.md`와 `gen_adlog_local_guide.md`의 중복을 제거하고 핵심 흐름만 정리했습니다.

## 1) 설치와 환경

```powershell
# Windows 권장: venv 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 의존성 설치 (프로젝트 루트 기준 또는 해당 서비스 디렉터리 기준)
pip install -r requirements.txt
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

## 2) 배치형 로그 생성기 사용법

다양한 기간/시간대 옵션으로 배치 데이터를 생성합니다.

```powershell
# 기본: 오늘 날짜 24시간 데이터
python ad_log_generator.py

# 특정 날짜
python ad_log_generator.py --date 2026-02-23

# 날짜 구간
python ad_log_generator.py --start-date 2026-02-20 --end-date 2026-02-22

# 과거 N일
python ad_log_generator.py --days-back 7

# 시간대 지정
python ad_log_generator.py --start-hour 12 --hours 6
python ad_log_generator.py --date 2026-02-20 --start-hour 18 --hours 4
```

백필 예시:
```powershell
# 지난달 전체
python ad_log_generator.py --start-date 2026-01-01 --end-date 2026-01-31

# 특정 주간
python ad_log_generator.py --start-date 2026-02-17 --end-date 2026-02-23
```

## 4) 생성 데이터와 저장 구조

- Impressions: 시간당 대량 생성, 사용자/광고/광고주/상점 풀에서 샘플링
- Clicks: 노출 대비 ~5% (포맷/영역 가중치 반영 가능)
- Conversions: 노출 대비 ~0.5% (클릭 대비 ~10%)

S3 예시 구조:
```
s3://<bucket>/raw/
├── impressions/year=YYYY/month=MM/day=DD/hour=HH/
├── clicks/year=YYYY/month=MM/day=DD/hour=HH/
└── conversions/year=YYYY/month=MM/day=DD/hour=HH/
```

## 5) 트래픽 패턴(배치 생성 시 적용 가능)

- 점심(11-14시): 150-200%
- 저녁(17-21시): 200-300% (피크)
- 주말: 평일 대비 150-200%

## 6) 결과 확인/모니터링

- 완료 통계: 총 노출/클릭/전환, CTR/CVR, 시간대별 로그
- 파일 확인: Parquet/CSV/PNG 산출물 점검

## 7) AWS 반영 포인트(요약)

| 로컬 구성요소 | AWS 전환 지점 |
|---|---|
| 파일 생성기 | Kinesis Producer 또는 컨테이너 |
| 로컬 Parquet | S3(+ Glue Catalog) |
| 집계 스크립트 | Athena SQL/Glue Job(Airflow 스케줄) |
| 분석/시각화 | Redash/QuickSight |

체크리스트: S3/Firehose/Glue/Airflow/Redash(+IAM) 설정 점검.

## 8) 트러블슈팅(핵심)

- ModuleNotFoundError → 가상환경 활성화/의존성 설치 재확인
- PowerShell 실행 정책 → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- 파일 누락 → 이전 단계 출력 경로 확인 후 재실행

## 9) 커스터마이징

- 생성량 조정(이벤트 수), 리포트 Top N, 임계값(threshold) 등 스크립트 파라미터로 제어
- 필요 시 `pyproject.toml + uv`로 의존성 고정 및 재현성 강화