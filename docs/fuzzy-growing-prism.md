# 광고 로그 생성기 구현 계획

## 배경
데이터 파이프라인 시뮬레이션을 위한 광고 로그 생성기. ad_impression과 ad_click 로그를 JSON 형식으로 생성하여 AWS Kinesis(운영) 또는 stdout+파일(개발)로 출력한다.

기술 명세: https://www.notion.so/dableglobal/Tech-Spec-3085bbc0e5c2807e948ceb019e0dcbcd

## 0단계: 환경 설정
```bash
# Python 3.14.3 설치 및 프로젝트 로컬 버전 설정
asdf install python 3.14.3
cd /Users/euigeun/project/private/ad-log-generator
asdf local python 3.14.3

# 가상환경 생성
python -m venv .venv
source .venv/bin/activate

# git 초기화
git init
```

## 1단계: 프로젝트 구조

```
ad-log-generator/
├── .python-version          # asdf 로컬 버전 (3.14.3)
├── .gitignore
├── requirements.txt
├── config.py                # 환경별 설정 (개발/운영)
├── models.py                # 로그 데이터 모델 및 생성 로직
├── output.py                # 출력 핸들러 (Kinesis / stdout+파일)
├── generator.py             # 메인 생성 루프
└── main.py                  # CLI 진입점
```

## 2단계: 의존성 (`requirements.txt`)
```
boto3           # AWS Kinesis 전송용
```
- 표준 라이브러리만으로 대부분 처리 (json, uuid, random, time, argparse, datetime)
- boto3는 운영 환경 Kinesis 전송에만 필요

## 3단계: 설정 (`config.py`)

| 설정 | 개발(dev) | 운영(production) |
|------|-----------|------------------|
| 출력 방식 | stdout + 파일 | Kinesis |
| 기본 실행 시간 | 10초 | 무한 |
| 로그 파일 경로 | `./logs/` | 해당 없음 |

- `--env` 옵션으로 dev/production 선택 (기본값: dev)
- `--duration` 옵션으로 실행 시간(초) 직접 지정 가능

## 4단계: 로그 모델 (`models.py`)

### ad_impression 예시
```json
{
  "event_time": "2026-02-15T11:30:00.123Z",
  "impression_id": "uuid-문자열",
  "user_id": "user_00123",
  "device": "mobile",
  "ip": "192.168.1.100",
  "advertiser_id": "adv_001",
  "campaign_id": "camp_010",
  "creative_id": "cre_100",
  "inventory_id": "inv_005"
}
```

### ad_click 예시 (노출 컬럼 전체 + cpc 추가)
```json
{
  "event_time": "2026-02-15T11:30:01.456Z",
  "impression_id": "위 노출과 동일한 uuid",
  "user_id": "동일",
  "device": "동일",
  "ip": "동일",
  "advertiser_id": "동일",
  "campaign_id": "동일",
  "creative_id": "동일",
  "inventory_id": "동일",
  "cpc": "0.35"
}
```

- 모든 key, value는 **문자열(string)** 타입
- 랜덤 데이터 풀: 광고주 10개, 캠페인 30개, 소재 100개, 지면 20개, 디바이스 종류(mobile/desktop/tablet) 등

## 5단계: 생성 로직 (`generator.py`)

```
매 초마다 반복:
  1. 1~5개를 랜덤으로 정해 ad_impression 생성
  2. 각 노출에 대해 2% 확률로 ad_click 생성 여부 결정
     - 클릭 발생 시 해당 노출과 동일한 impression_id 사용
     - event_time은 노출 이후로 설정 (0.1~3초 랜덤 딜레이)
  3. 출력 핸들러로 전송
  4. 지정된 실행 시간 도달 시 종료
```

- CTR 약 2%: `random.random() < 0.02`로 클릭 여부 결정
- 클릭의 event_time은 반드시 노출보다 뒤 (랜덤 딜레이 추가)

## 6단계: 출력 핸들러 (`output.py`)

### 개발 출력 (DevOutput)
- stdout에 JSON 출력 (노출/클릭 구분 표시)
- `./logs/ad_impression.jsonl`, `./logs/ad_click.jsonl` 파일에 한 줄씩 추가

### 운영 출력 (KinesisOutput)
- boto3 kinesis 클라이언트 사용
- `ad_impression_stream` 스트림에 노출 로그 전송
- `ad_click_log_stream` 스트림에 클릭 로그 전송
- 파티션 키: impression_id

## 7단계: CLI 진입점 (`main.py`)

```bash
# 개발 모드 (기본 10초, stdout+파일)
python main.py

# 운영 모드 (무한 실행, Kinesis)
python main.py --env production

# 실행 시간 직접 지정 (초 단위)
python main.py --duration 60

# 운영 + 1시간
python main.py --env production --duration 3600
```

## 8단계: `.gitignore`
```
.venv/
logs/
__pycache__/
*.pyc
```

## 검증 방법
1. `python main.py` 실행 → 10초간 stdout에 JSON 로그 출력 확인
2. `./logs/` 디렉토리에 노출/클릭 jsonl 파일 생성 확인
3. 클릭 로그의 impression_id가 노출 로그에 존재하는지 확인
4. 클릭 로그의 event_time이 해당 노출보다 뒤인지 확인
5. 전체 CTR(클릭수/노출수 비율)이 약 2% 이내인지 확인
