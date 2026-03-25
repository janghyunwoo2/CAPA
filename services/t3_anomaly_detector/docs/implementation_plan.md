# Real-time Ad Impression Anomaly Detector (AI 툴 기반 개발 데모)

**역할**: 구현 계획서
**관련 파일**: `AI 툴 기반 개발 데모.md` (요구사항 및 아이디어)

본 문서는 실시간으로 들어오는 `ad impression` 로그 데이터를 5분 단위로 모니터링하며, 머신러닝 모델(Prophet + Isolation Forest)을 활용하여 이상 패턴(Anomaly)을 감지하는 프로그램의 구현 계획입니다.

**현재 단계는 AI 데모 및 검증 목적**이므로, 실제 Kinesis 연동 대신 Kinesis Consumer 인터페이스를 추상화하고, **배달앱 트래픽 특징을 갖는 Mock 데이터**를 생성하여 실험을 진행합니다.

## Proposed Changes

### 기술 스택 및 아키텍처
- **Language**: Python 3
- **Data Source**: Mock Data Generator (배달앱 패턴 반영)
  - 향후 실제 Kinesis 연동을 고려한 인터페이스 추상화
- **Anomaly Detection Model**: 
  - `Prophet` (시계열 트렌드 및 계절성 분석 기반 정상 범주 예측)
  - `Isolation Forest` (단순 점 이상치 및 극단값 탐지 보완)
  - **Output & Real-time Update**:
    - **자동 갱신**: 매 5분(윈도우) 데이터가 쌓일 때마다 `anomaly_result.png`와 `anomaly_interactive.html` 파일을 최신 데이터로 **자동 덮어쓰기**하여 갱신.
    - **데모 가속 모드**: 실제 5분을 기다리지 않고, 설정에 따라 **1초마다 5분치 데이터를 처리**하는 가속 모드 지원 (2주치 데이터를 빠르게 훑고 실시간 탐지 확인 가능)
    - **Visualization (Prophet & Plotly)**: 예측 구간, 실제값, 이상치 강조 및 인터랙티브 조작 지원.

### 1. `services/t3_anomaly_detector` 폴더 구조 및 컴포넌트

이 폴더에 다음 파일들이 생성될 예정입니다:

#### [NEW] requirements.txt
- Python 의존성 관리
- prophet, plotly, scikit-learn, pandas, numpy, boto3 등

#### [NEW] Dockerfile
- 컨테이너화 (report-generator와 일관성 유지)
- Python 3.10+ 기반, requirements.txt 설치

#### [NEW] .env.example
- 환경변수 템플릿
- `DATA_SOURCE`, `ACCELERATION_FACTOR`, `LOG_LEVEL` 등

#### [NEW] tests/ 디렉토리
- `test_mock_kinesis_source.py` — Mock 데이터 생성 검증
- `test_aggregator.py` — 5분 윈도우 집계 테스트
- `test_models.py` — Prophet, IsolationForest 모델 검증

#### [NEW] README.md
- 프로젝트 실행 가이드 및 설명서

#### [NEW] config.py
- 하이퍼파라미터(Prophet Interval, Isolation Forest 오염도 등) 및 실행 환경(로컬 모의 데이터 모드, 기간 설정) 관리

#### [NEW] mock_kinesis_source.py
- **배달앱 기준의 2주치 Mock 트래픽 시계열 데이터 생성기**
  - **특징 반영:** 점심시간(11시~13시) 및 저녁/야식시간(18시~22시) 트래픽 증가. 주말에 전반적인 트래픽 및 저녁 피크타임 확대 등. 
  - **이상치 주입:** 피크 타임 급락, 유휴 시간 급증 등 인위적 Anomaly 데이터 2~3회 포함
- 추후 실제 Kinesis/CloudWatch 폴링 리퍼런스와 동일하게 동작하는 Iterator 인터페이스 제공 (스트리밍 시뮬레이션)

#### [NEW] aggregator.py
- 스트리밍되는 Mock 데이터를 받아 5분 단위의 `impression` 객수로 롤링(Tumbling Window) 집계 수행

#### [NEW] models.py
- **ProphetDetector**: `Prophet`을 사용하여 시계열 예측 수행. 현재 윈도우 값이 예측된 신뢰 구간(`yhat_lower`, `yhat_upper`)을 벗어날 경우 이상치로 플래그.
- **IsolationForestDetector**: 스태틱한 임계값을 잡지 못하는 아웃라이어 패턴 보완용 ML 모델.

#### [NEW] main.py
- 메인 파이프라인:
  1. 2주치의 배달앱 Mock 데이터를 백그라운드에서 생성.
  2. 스트리밍 데이터를 5분 단위로 집계.
  3. Prophet을 훈련/업데이트 시키면서 실시간 추론 수행.
  4. 콘솔에 로그와 결과를 지속적으로 파싱하여 출력.
  5. 특정 주기 혹은 완료 시점에 그래프(`anomaly_result.png`) 생성 및 저장.

## Verification Plan

### Automated Test / Simulation
1. `main.py` 프로세스를 실행합니다.
2. 콘솔에 출력되는 아래의 형식의 로그를 확인합니다:
   ```
   [2026-03-10 18:05:00] [NORMAL] Actual: 1450 | Predicted: 1440 | Range: (1300, 1580)
   [2026-03-10 18:10:00] [ANOMALY!] Actual: 250 | Predicted: 1450 | Type: Sudden Drop
   ```
3. **실시간/가속 업데이트 확인**: 데모 실행 중 또는 완료 후 생성된 결과물(`png`, `html`)이 매 윈도우(5분 단위)마다 자동 갱신되는지 확인합니다.
   - **인터랙티브 분석 (`anomaly_interactive.html`)**: 브라우저에서 파일을 열어 마우스 호버로 상세 수치를 확인하고, 구간 확대(Zoom) 기능을 통해 배달앱 피크 타임을 상세 분석합니다.
   - **학습 패턴 확인 (`anomaly_components.png`)**: Prophet이 학습한 배달앱의 **시간대별/요일별** 계절성 패턴이 실제 비즈니스 로직과 일치하는지 확인합니다.
   - **가속 모드**: 가속 배속 설정에 따라 전체 시계열 그래프가 빠르게 그려지며 이상(Anomaly) 지점이 실시간으로 빨간 점으로 찍히는 과정을 확인합니다.

---

## 코딩 구조 및 데이터 흐름

### 폴더 구조

```
services/t3_anomaly_detector/
├── README.md                    # 실행 가이드
├── requirements.txt             # Python 의존성
├── Dockerfile                   # 컨테이너화
├── .env.example                 # 환경변수 템플릿
├── config.py                    # 하이퍼파라미터 & 설정
│   └── Prophet interval, Isolation Forest 오염도, 재훈련 주기 등
├── mock_kinesis_source.py       # Mock 데이터 생성
│   └── 2주치 배달앱 트래픽 패턴 + 인위적 이상치 주입
├── aggregator.py                # 5분 단위 집계
│   └── 스트리밍 데이터 → 5분 윈도우 롤링 집계
├── models.py                    # ML 모델
│   ├── ProphetDetector         # 시계열 예측 (신뢰 구간 기반)
│   └── IsolationForestDetector # 점 이상치 탐지
├── main.py                      # 메인 파이프라인
│   ├── 1. Mock 데이터 생성
│   ├── 2. 5분 단위 집계
│   ├── 3. 초기 Prophet 훈련 (2주치 데이터)
│   ├── 4. 이상 탐지 & 콘솔 출력 (주기적 재훈련)
│   └── 5. 그래프 자동 갱신 (png, html)
└── tests/                       # 자동화 테스트
    ├── test_mock_kinesis_source.py
    ├── test_aggregator.py
    └── test_models.py
```

### 데이터 흐름

```
Mock Data Generator
  ↓ (2주치 데이터 스트리밍)
Aggregator (5분 단위 집계)
  ↓
Models (Prophet + IsolationForest)
  ├→ 콘솔 로그 출력
  │  [2026-03-10 18:05:00] [NORMAL] Actual: 1450 | Predicted: 1440
  │  [2026-03-10 18:10:00] [ANOMALY!] Actual: 250 | Predicted: 1450
  │
  └→ 자동 갱신
     ├ anomaly_result.png (시계열 + 이상치)
     ├ anomaly_interactive.html (인터랙티브)
     └ anomaly_components.png (Prophet 학습 패턴)
```

### 주요 포인트

- **Mock 데이터**: 실제 Kinesis 없이 배달앱 패턴 가상 생성
- **인터페이스 추상화**: 추후 CloudWatch 폴링으로 교체 가능하도록 설계
- **가속 모드**: 2주치를 빠르게 실행하면서 이상 탐지 확인 가능
- **자동 시각화**: 매 5분마다 결과물(png, html) 자동 갱신

---

## 실제 Kinesis로의 전환 전략

### 데이터 소스 추상화 원칙

현재 `mock_kinesis_source.py`는 **데이터 소스의 구현 세부사항을 감싸는 인터페이스**로 설계됩니다.

- **인터페이스**: 5분 단위로 데이터를 제공하는 일관된 방식 정의
  - Mock: 가상 데이터 생성 + Iterator 방식 제공
  - 실제: CloudWatch API 폴링 결과를 동일한 형식으로 변환

- **의존성 분리**: `main.py`, `aggregator.py`, `models.py`는 데이터 소스를 알 필요 없음
  - 오직 인터페이스만 의존

### 전환 단계

1. **현재**: Mock 데이터 → `mock_kinesis_source` → aggregator → models
2. **전환**: Mock 대신 CloudWatch 폴링 코드로 교체
3. **결과**: `main.py` 코드는 전혀 변경 불필요

### 주의사항

- Mock과 실제 Kinesis의 데이터 포맷이 동일해야 함
- 5분 단위 집계 로직은 동일하게 작동해야 함
- 환경 변수로 데이터 소스를 선택하는 구조 필요

---

## 설계 보완 사항

### 1. Prophet 재훈련 전략 (중요)

**선택: 초기 훈련 후 주기적 재훈련 방식**

```python
# config.py
RETRAIN_INTERVAL = 288  # 매 N 윈도우마다 재훈련 (288 = 24시간)
```

**동작:**
1. 초기 2주치 데이터로 Prophet 모델 훈련 (1회, main.py 시작 시)
2. 이후 각 5분 윈도우는 **예측만 수행** (훈련 X)
3. 24시간마다(288 윈도우) 누적 데이터로 재훈련하여 계절성 업데이트

**이유:** 매 윈도우마다 재훈련하면 느리고, 재훈련 없으면 데이터 드리프트에 약함. 24시간 주기가 균형잡힘.

### 2. config.py 설정값 (전체 리스트)

```python
# ============ Prophet 모델 파라미터 ============
PROPHET_INTERVAL_WIDTH = 0.95  # 예측 신뢰 구간 (95%)
PROPHET_YEARLY_SEASONALITY = True
PROPHET_WEEKLY_SEASONALITY = True
PROPHET_DAILY_SEASONALITY = True

# ============ Isolation Forest 파라미터 ============
ISOLATION_FOREST_CONTAMINATION = 0.05  # 이상치 비율 추정 (5%)
ISOLATION_FOREST_RANDOM_STATE = 42

# ============ 파이프라인 설정 ============
WINDOW_SIZE_MINUTES = 5  # 집계 윈도우
HISTORY_DAYS = 14  # 초기 훈련 데이터 기간
RETRAIN_INTERVAL = 288  # 24시간(=288×5분) 주기로 재훈련
ACCELERATION_FACTOR = 1  # 1=실시간, 300=가속(5분→1초)
DATA_SOURCE = "mock"  # "mock" | "cloudwatch" (향후 확장)

# ============ 출력 설정 ============
OUTPUT_DIR = "./output"
LOG_LEVEL = "INFO"  # DEBUG | INFO | WARNING | ERROR
SAVE_PNG = True  # anomaly_result.png 저장
SAVE_HTML = True  # anomaly_interactive.html 저장
SAVE_COMPONENTS = True  # anomaly_components.png 저장

# ============ Slack 알림 (선택) ============
SLACK_ENABLED = False  # True로 설정 시 Slack 알림 활성화
SLACK_WEBHOOK_URL = ""  # 환경변수에서 로드
SLACK_ALERT_THRESHOLD = 1  # 이상치 탐지 시 즉시 알림
```

### 3. 탐지 결과 저장 (데이터 지속성)

```
output/
├── anomaly_result.png  # 시계열 그래프
├── anomaly_interactive.html  # Plotly 인터랙티브
├── anomaly_components.png  # Prophet 계절성 분석
└── anomaly_log.jsonl  # 각 윈도우별 탐지 결과 (JSON Lines)
    # 예: {"timestamp": "2026-03-10T18:05:00", "actual": 1450, "predicted": 1440, "status": "NORMAL", ...}
```

### 4. 로깅 및 에러 핸들링

**로깅:**
- Python `logging` 모듈 사용
- 콘솔 + 파일(`output/anomaly.log`) 동시 기록
- 레벨: DEBUG (개발) → INFO (프로덕션)

**에러 시나리오:**
- Prophet 훈련 실패 → 기본값 재훈련 후 재시도, 실패 시 경고 로그
- 데이터 누락(None/NaN) → 이전 값으로 포워드필 또는 스킵
- 메모리 부족 → 최근 N일만 보관하는 슬라이딩 윈도우

### 5. Slack 알림 (선택 사항)

```python
# models.py - AnomalyDetector 클래스 내
if self.slack_enabled and is_anomaly:
    send_slack_alert(f"[ANOMALY] {timestamp}: {anomaly_type}")
```

(report-generator의 Slack 인프라 재사용 가능)

---

## Verification Plan
