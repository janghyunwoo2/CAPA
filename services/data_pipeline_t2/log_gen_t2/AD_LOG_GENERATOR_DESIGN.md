# 광고 로그 데이터 생성기 설계 문서

## 개요
AWS S3에 Parquet(zstd 압축) 형식으로 저장할 광고 로그 데이터를 생성하는 시스템 설계입니다. 본 시스템은 데이터 파이프라인 테스트 및 분석을 위한 고품질의 합성 데이터를 생성하는 것을 목적으로 합니다.

## 기술 스택 (Technical Stack)

- **Language**: Python 3.14.2+
- **Data Manipulation**: `pandas`, `numpy`
- **File Format & Compression**: `pyarrow`, `apache-parquet`
- **Mock Data Generation**: `Faker` (UA, IP, UUID 생성)
- **Cloud Interface**: `boto3` (AWS S3 업로드)

## 테이블 구조

### 1. 노출 (Impression) 테이블

| 컬럼명 | 타입 | 설명 | 카테고리/범위 |
|--------|------|------|--------------|
| impression_id | string | 고유 노출 ID | UUID v4 |
| timestamp | timestamp | 노출 시간 | 실시간 |
| user_id | string | 사용자 ID | 100,000개 (user_000001 ~ user_100000) |
| ad_id | string | 광고 ID | 1,000개 (ad_0001 ~ ad_1000) |
| campaign_id | string | 캠페인 ID | 5개 (campaign_01 ~ campaign_05) |
| advertiser_id | string | 광고주 ID | 30개 (advertiser_01 ~ advertiser_30) |
| platform | string | 플랫폼 | 5개 (web, app_ios, app_android, tablet_ios, tablet_android) |
| device_type | string | 디바이스 타입 | 4개 (mobile, tablet, desktop, others) |
| os | string | 운영체제 | 4개 (ios, android, macos, windows) |
| delivery_region | string | 배달 지역 | 25개 (강남구, 서초구, 마포구 등 서울 주요 자치구) |
| user_lat | decimal | 사용자 위도 | 37.4 ~ 37.7 (서울 범위) |
| user_long | decimal | 사용자 경도 | 126.8 ~ 127.1 (서울 범위) |
| store_id | string | 상점 ID | 5,000개 (store_0001 ~ store_5000) |
| food_category | string | 음식 카테고리 | 15개 (chicken, pizza, korean, chinese, dessert, etc.) |
| ad_position | string | 광고 위치 | 4개 (home_top_rolling, list_top_fixed, search_ai_recommend, checkout_bottom) |
| ad_format | string | 광고 포맷 | 4개 (display, native, video, discount_coupon) |
| user_agent | string | 사용자 에이전트 | 표준 Mobile UA 문자열 |
| ip_address | string | IP 주소 | 익명화된 IP (XXX.XXX.XXX.0) |
| session_id | string | 세션 ID | UUID v4 |
| keyword | string | 검색 키워드 | 500개 주요 키워드 |
| cost_per_impression | decimal | CPM 비용 | 0.005 ~ 0.10 (배달 앱 특화 단가) |

> [!NOTE]
> **플랫폼 vs 디바이스 타입 구분**
> - **디바이스 타입 (device_type)**: 사용자가 사용하는 **물리적 하드웨어 기기**의 형태를 분류합니다. (예: 스마트폰 휴대 여부, 화면 크기 기준)
> - **플랫폼 (platform)**: 광고가 소비되는 **구체적인 소프트웨어 환경 또는 앱 채널**을 분류하며, OS 정보를 포함하기도 합니다. (예: 동일한 하드웨어라도 웹 브라우저 접속인지 전용 앱 접속인지 구분)

### 2. 클릭 (Click) 테이블

| 컬럼명 | 타입 | 설명 | 카테고리/범위 |
|--------|------|------|--------------|
| click_id | string | 고유 클릭 ID | UUID v4 |
| impression_id | string | 연관된 노출 ID | 노출 테이블 참조 |
| timestamp | timestamp | 클릭 시간 | 노출 후 1~300초 |
| user_id | string | 사용자 ID | 노출 테이블과 동일 |
| ad_id | string | 광고 ID | 노출 테이블과 동일 |
| campaign_id | string | 캠페인 ID | 노출 테이블과 동일 |
| advertiser_id | string | 광고주 ID | 노출 테이블과 동일 |
| platform | string | 플랫폼 | 노출 테이블과 동일 |
| click_position_x | int | 클릭 X 좌표 | 광고 영역 내 |
| click_position_y | int | 클릭 Y 좌표 | 광고 영역 내 |
| landing_page_url | string | 랜딩 페이지 URL | 광고주별 URL |
| cost_per_click | decimal | CPC 비용 | 0.1 ~ 5.0 |

### 3. 전환 (Conversion) 테이블

| 컬럼명 | 타입 | 설명 | 카테고리/범위 |
|--------|------|------|--------------|
| conversion_id | string | 고유 전환 ID | UUID v4 |
| click_id | string | 연관된 클릭 ID | 클릭 테이블 참조 |
| impression_id | string | 연관된 노출 ID | 노출 테이블 참조 |
| timestamp | timestamp | 전환 시간 | 클릭 후 1분~7일 |
| user_id | string | 사용자 ID | 노출 테이블과 동일 |
| ad_id | string | 광고 ID | 노출 테이블과 동일 |
| campaign_id | string | 캠페인 ID | 노출 테이블과 동일 |
| advertiser_id | string | 광고주 ID | 노출 테이블과 동일 |
| conversion_type | string | 전환 유형 | 5개 (purchase, signup, download, view_content, add_to_cart) |
| conversion_value | decimal | 전환 가치 | 1.0 ~ 10000.0 |
| product_id | string | 상품 ID | 10,000개 (prod_00001 ~ prod_10000) |
| quantity | int | 주문/구매 수량 | 1 ~ 10 |
| store_id | string | 상점 ID | 노출 테이블과 동일 |
| delivery_region | string | 배달 지역 | 노출 테이블과 동일 |
| attribution_window | string | 귀속 기간 | 3개 (1day, 7day, 30day) |

  - purchase: 1-3%

## 상세 데이터 생성 로직

### 1. 엔티티 매핑 및 카디널리티 (Cardinality)
- **User & Ad**: 100,000명의 고유 사용자와 1,000개의 광고 풀을 사전 생성하여 실제적인 중복 방문 및 노출 효과를 시뮬레이션합니다.
- **Advertiser & Campaign**: 광고주 한 명당 평균 20개의 광고와 2개의 캠페인을 소유하는 구조로 매핑하여 관계형 분석이 가능하도록 합니다.

### 2. 이벤트 상관관계 (Event Correlation)
- **ID 추적**: `Click` 테이블의 `impression_id`는 생성된 `Impression` 테이블의 ID를 참조하며, `Conversion` 또한 상위 이벤트의 ID를 체인 형태로 유지합니다.
- **시간차 시뮬레이션**: 
  - 클릭은 노출 발생 후 **1초 ~ 5분** 이내에 발생하도록 설정합니다.
  - 전환은 클릭 발생 후 **1분 ~ 7일** 사이의 지연 시간을 가집니다.

### 3. 확률적 생성 알고리즘
- 각 이벤트 생성 시 `random.random()`을 사용하여 설정된 **CTR/CVR 임계값** 이하일 경우에만 하위 이벤트를 생성합니다.
- **지리적 가중치**: `delivery_region`이 강남/서초 등 유동인구가 많은 지역일 경우 노출 대비 클릭 발생 확률을 **1.2배** 가중합니다.
- 플랫폼 및 디바이스 타입에 따른 가중치를 부여하며, 특히 `app_ios/android` 환경에서 더 높은 인터랙션이 발생하도록 설계합니다.

## 트래픽 패턴

### 시간대별 배달 피크 패턴
- **새벽 (00-07시)**: 기준 트래픽의 10-20% (최저)
- **아침 (07-09시)**: 40-60% (간단한 식사 및 카페)
- **오전 (09-11시)**: 30-50%
- **점심 (11-14시)**: **150-200% (점심 피크)**
- **오후 (14-17시)**: 60-80%
- **저녁 (17-21시)**: **200-300% (저녁 피크/골든타임)**
- **밤 (21-24시)**: 100-150% (치킨/야식 수요)

## 데이터 생성 규칙

### 시간대별 트래픽 패턴
- 새벽 (00-06시): 기준 트래픽의 20-40%
- 아침 (06-09시): 60-80%
- 오전 (09-12시): 80-100%
- 점심 (12-14시): 90-110%
- 오후 (14-18시): 100-120%
- 저녁 (18-21시): 110-130%
- 밤 (21-24시): 80-100%

### 요일별 트래픽 패턴
- 월-목: 기준 트래픽의 80-100%
- 금: 120-150% (불금 버프)
- 토: 150-200% (주말 수요 폭증)
- 일: 130-170% (집콕 수요)

    ├── year=2025/month=01/day=01/hour=00/
    │   └── conversions_20250101_00_001.parquet.zstd
```

## 인프라 요구사항 (Infrastructure Requirements)

### 1. AWS 계정 및 권한

#### 1-1. AWS 계정
- **AWS Account ID**: 대상 AWS 계정 ID 확보
- **Region**: `ap-northeast-2` (서울) 또는 기타 리전 선택

#### 1-2. IAM 사용자 / 역할 (IAM User / Role)
**최소 필요 권한:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

**옵션 권한:**
- `s3:DeleteObject`: 테스트 데이터 정리용
- `cloudwatch:PutMetricData`: 메트릭 전송용
- `logs:CreateLogGroup`, `logs:CreateLogStream`: 로깅용

#### 1-3. AWS 자격증명 설정
```bash
# 방법 1: 환경 변수 (개발 환경)
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=ap-northeast-2

# 방법 2: AWS CLI 설정 (~/.aws/credentials)
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key

# 방법 3: IAM Role (EC2/ECS 환경에서 권장)
# EC2 인스턴스 또는 ECS Task에 IAM Role 할당
```

### 2. S3 버킷 설정

#### 2-1. S3 버킷 생성
```bash
aws s3api create-bucket \
  --bucket capa-ad-logs \
  --region ap-northeast-2 \
  --create-bucket-configuration LocationConstraint=ap-northeast-2
```

#### 2-2. 버킷 정책 (선택사항)
- **공개 접근 차단** (Block Public Access) 활성화 권장
- **서버 측 암호화** (SSE-S3) 활성화 권장

#### 2-3. S3 폴더 구조
```
s3://capa-ad-logs/raw/
├── impressions/year=YYYY/month=MM/day=DD/hour=HH/
├── clicks/year=YYYY/month=MM/day=DD/hour=HH/
└── conversions/year=YYYY/month=MM/day=DD/hour=HH/
```

### 3. 개발 환경

#### 3-1. Python 환경
- **Python 버전**: 3.8 이상 (권장: 3.11+)
- **패키지 관리**: pip 또는 conda

#### 3-2. 필수 패키지
```bash
pip install \
  boto3>=1.26.0 \
  pandas>=2.0.0 \
  numpy>=1.24.0 \
  pyarrow>=12.0.0 \
  python-dotenv>=1.0.0 \
  faker>=18.0.0
```

#### 3-3. 환경 설정 파일 (.env)
```bash
# AWS 인증
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_DEFAULT_REGION=ap-northeast-2

# S3 버킷
S3_BUCKET_NAME=capa-data-lake-827913617635
S3_REGION=ap-northeast-2

# 데이터 생성 설정
DAILY_IMPRESSIONS=1000000
TIMEZONE=Asia/Seoul

# 로깅
LOG_LEVEL=INFO
LOG_DIR=./logs
```

### 4. 데이터베이스 (선택사항)

#### 4-1. 마스터 데이터 관리용
- **PostgreSQL** 또는 **MySQL**: 광고주-상점 매핑, 사용자 메타데이터 저장
- **DynamoDB** (AWS): 광고 ID, 캠페인 정보 조회용

#### 4-2 필수 테이블
```sql
-- 광고주-상점 매핑
CREATE TABLE advertiser_store_mapping (
  advertiser_id VARCHAR(20),
  store_id VARCHAR(20),
  store_name VARCHAR(255),
  store_region VARCHAR(50),
  created_date DATE,
  PRIMARY KEY (advertiser_id, store_id)
);

-- 광고 카탈로그
CREATE TABLE ads_catalog (
  ad_id VARCHAR(20) PRIMARY KEY,
  advertiser_id VARCHAR(20),
  campaign_id VARCHAR(20),
  food_category VARCHAR(50),
  created_date DATE
);
```

### 5. 모니터링 및 로깅 (선택사항)

#### 5-1. CloudWatch
- **메트릭**: 시간당 생성 건수, 실패율, 업로드 시간
- **로그**: 생성기 실행 로그, 에러 로그
- **알람**: 생성 실패 또는 비정상 패턴 감지

#### 5-2. 로컬 로깅
```python
# logs/generator_YYYY-MM-DD.log
# logs/upload_YYYY-MM-DD.log
```

### 6. 컴퓨팅 리소스

#### 6-1. 로컬 개발
- **CPU**: 4 Core 이상 권장
- **RAM**: 8GB 이상
- **네트워크**: 5Mbps 이상 (S3 업로드용)

#### 6-2. 클라우드 배포 (선택사항)
- **EC2 t3.medium 이상** 또는
- **Lambda** (시간 제한으로 인해 소량 생성용만 권장) 또는
- **ECS Fargate** (정기적 배치 작업용)

### 7. 설정 체크리스트

- [ ] AWS 계정 생성 및 IAM 사용자 설정
- [ ] S3 버킷 생성 (`capa-ad-logs` 또는 커스텀 명)
- [ ] IAM 정책 할당 (S3 PutObject, GetObject, ListBucket)
- [ ] AWS 자격증명 환경 변수 또는 파일 설정
- [ ] Python 3.8+ 설치
- [ ] 필수 패키지 설치 (`boto3`, `pandas`, `pyarrow` 등)
- [ ] `.env` 파일 작성 및 배치
- [ ] S3 버킷 폴더 구조 생성 (또는 자동 생성)
- [ ] 로그 디렉토리 생성 (`./logs`)
- [ ] (선택) 마스터 데이터 DB 설정
- [ ] (선택) CloudWatch 대시보드 구성

## AWS S3 연동 방식

- **인증 (Authentication)**: `boto3` 세션 생성 시 환경 변수(`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) 또는 IAM Role/Profile을 통해 인증을 수행합니다.
- **업로드 및 멀티파트**: 개별 파일 크기가 100MB 이상일 경우 효율적인 업로드를 위해 멀티파트 업로드 기능을 활용합니다.
- **S3 스토리지 클래스**: 기본적으로 `STANDARD` 클래스를 사용하며, 분석 주기에 따라 수명 주기 정책(Lifecycle Policy)을 설정할 수 있도록 합니다.

## 성능 최적화

## 성능 최적화
- 시간당 파티션으로 분할
- 각 파일 크기: 100-200MB 목표
- zstd 압축 레벨: 3 (속도와 압축률 균형)
- 배치 크기: 10,000 레코드/배치

## 데이터 품질 검증
- 필수 필드 null 체크
- ID 중복 검증
- 타임스탬프 순서 검증
- 참조 무결성 검증 (impression_id, click_id)
- 비율 검증 (CTR, CVR이 최대치 초과 안함)