# Real-time Ad Impression Anomaly Detector

배달앱 트래픽 패턴의 ad impression 로그를 5분 단위로 모니터링하여
**Prophet + Isolation Forest** 기반으로 이상 징후를 자동 탐지하는 파이프라인입니다.

## 아키텍처

```
MockKinesisSource (2주치 배달앱 트래픽 + 인위적 이상치 3개)
  ↓
FiveMinuteAggregator (5분 Tumbling Window)
  ↓
ProphetDetector + IsolationForestDetector
  ↓
콘솔 로그 + output/ (PNG, HTML, JSONL)
```

## 빠른 시작

### 가상환경 설정

**Windows (PowerShell/CMD):**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Linux/Mac/Git Bash:**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 실행

```bash
# 기본 (가속 모드: 1초당 5분치 처리)
python main.py

# 실시간 모드 (Windows PowerShell)
$env:ACCELERATION_FACTOR=1; python main.py

# 실시간 모드 (Linux/Mac/Git Bash)
ACCELERATION_FACTOR=1 python main.py

# 가상환경 종료
deactivate
```

## 출력 결과

실행 후 `output/` 디렉토리에 생성:

| 파일 | 설명 |
|------|------|
| `anomaly_result.png` | 시계열 + 신뢰구간 + 이상치 정적 그래프 |
| `anomaly_interactive.html` | Plotly 인터랙티브 그래프 (줌/호버) |
| `anomaly_components.png` | Prophet 학습 패턴 (시간대별/요일별 계절성) |
| `anomaly_log.jsonl` | 윈도우별 탐지 결과 JSON Lines |
| `anomaly.log` | 전체 실행 로그 |

### 콘솔 출력 예시

```
[2026-03-04 19:00:00] [ANOMALY!]    Actual:    126 | Predicted:   856 | Range: (642, 1071) | Type: Sudden Drop
[2026-03-06 03:00:00] [ANOMALY!]    Actual:   1568 | Predicted:    19 | Range: (0, 42)     | Type: Sudden Spike
[2026-03-14 12:00:00] [ANOMALY!]    Actual:     56 | Predicted:   840 | Range: (630, 1050) | Type: Sudden Drop
```

## 배달앱 트래픽 패턴

| 시간대 | 배율 | 비고 |
|--------|------|------|
| 11~13시 (점심) | ×3.0 | 점심 피크 |
| 18~22시 (저녁) | ×4.0 | 저녁/야식 피크 |
| 22~24시 | ×1.5 | 야식 후반 |
| 14~17시 (오후) | ×0.4 | 오후 유휴 |
| 2~6시 (새벽) | ×0.1 | 새벽 최저 |
| 금/토/일 | ×1.4 | 주말 부스트 |

## 주입된 이상치

| 시각 | 유형 | 배율 |
|------|------|------|
| 1주차 화요일 19:00 | Sudden Drop | ×0.15 |
| 1주차 목요일 03:00 | Sudden Spike | ×8.0 |
| 2주차 토요일 12:00 | Sudden Drop | ×0.10 |

## 환경 변수

`.env.example`을 복사하여 `.env`로 사용:

```bash
cp .env.example .env
```

주요 설정:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ACCELERATION_FACTOR` | 300 | 가속 배율 (1=실시간) |
| `HISTORY_DAYS` | 14 | 훈련 데이터 기간 |
| `PROPHET_INTERVAL_WIDTH` | 0.95 | 신뢰구간 너비 |
| `LOG_LEVEL` | INFO | 로그 레벨 |

## Docker 실행

```bash
docker build -t t3-anomaly-detector .
docker run -v $(pwd)/output:/app/output t3-anomaly-detector
```

## 테스트

```bash
python -m pytest tests/ -v
```

## 실제 Kinesis로 전환

`mock_kinesis_source.py`만 CloudWatch 폴링 모듈로 교체하면 됩니다.
`main.py`, `aggregator.py`, `models.py`는 변경 불필요.

```python
# 전환 예시
from cloudwatch_source import CloudWatchSource  # 신규 모듈
source = CloudWatchSource(stream_name="ad-impression-stream")
```
