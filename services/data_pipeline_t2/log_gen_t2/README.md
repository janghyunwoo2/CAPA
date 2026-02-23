# 광고 로그 생성기

AWS S3에 Parquet(zstd) 형식으로 광고 로그 데이터를 생성하는 도구입니다.

## 설치

```bash
# Python 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

## 환경 설정

프로젝트 루트의 `.env` 파일에 AWS 자격증명이 설정되어 있어야 합니다:

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-2
```

## 사용 방법

### 기본 실행 (오늘 날짜 24시간 데이터 생성)
```bash
python ad_log_generator.py
```

### 특정 날짜 데이터 생성
```bash
python ad_log_generator.py --date 2026-02-23
```

### 날짜 범위로 여러 날 데이터 생성
```bash
# 2026-02-20부터 2026-02-22까지 3일간 데이터 생성
python ad_log_generator.py --start-date 2026-02-20 --end-date 2026-02-22
```

### 과거 N일간 데이터 생성
```bash
# 오늘 포함 지난 7일간 데이터 생성
python ad_log_generator.py --days-back 7
```

### 특정 시간대만 생성
```bash
# 오늘 12시부터 6시간 데이터 생성
python ad_log_generator.py --start-hour 12 --hours 6

# 특정 날짜의 특정 시간대
python ad_log_generator.py --date 2026-02-20 --start-hour 18 --hours 4
```

### 과거 데이터 백필 예시
```bash
# 지난달 전체 데이터 생성
python ad_log_generator.py --start-date 2026-01-01 --end-date 2026-01-31

# 특정 주간 데이터만 생성
python ad_log_generator.py --start-date 2026-02-17 --end-date 2026-02-23
```

## 생성되는 데이터

### 1. 노출 (Impressions)
- 시간당 기본 10,000건 (트래픽 패턴에 따라 변동)
- 100,000명 사용자, 1,000개 광고, 30개 광고주, 5,000개 상점

### 2. 클릭 (Clicks)
- 노출 대비 최대 5% (광고 포맷별 차등)
- 강남/서초 지역 1.2배 가중치

### 3. 전환 (Conversions)
- 노출 대비 최대 0.5% (클릭 대비 10%)
- 전환 유형별 차등 적용

## S3 저장 구조

```
s3://capa-data-lake-827913617635/raw/
├── impressions/year=2026/month=02/day=23/hour=00/
├── clicks/year=2026/month=02/day=23/hour=00/
└── conversions/year=2026/month=02/day=23/hour=00/
```

## 트래픽 패턴

- **점심 시간 (11-14시)**: 150-200% 트래픽
- **저녁 시간 (17-21시)**: 200-300% 트래픽 (피크)
- **주말**: 평일 대비 150-200% 트래픽

## 모니터링

생성 완료 시 통계 출력:
- 총 노출/클릭/전환 수
- 평균 CTR/CVR
- 시간대별 생성 로그