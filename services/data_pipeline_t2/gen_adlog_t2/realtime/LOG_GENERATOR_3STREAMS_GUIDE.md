# 로그 생성기 변경 가이드 — Kinesis Streams 3개 + Firehose 3개 연동

본 문서는 로그 생성기(realtime)에서 이벤트 타입별로 Kinesis Data Streams 3개에 전송하도록 변경하는 방법을 정리합니다. Firehose는 각 Stream을 소스로 사용(KinesisStreamAsSource)하여 S3/Parquet 적재를 수행합니다. 이 구조에서는 로그 생성기가 Firehose API를 호출하지 않습니다.

- Kinesis Streams: `capa-knss-imp-00`, `capa-knss-clk-00`, `capa-knss-cvs-00`
- Firehose: `capa-fh-imp-00`, `capa-fh-clk-00`, `capa-fh-cvs-00` (소스: 해당 Kinesis Stream)

## 아키텍처 요약
- Generator → Kinesis Stream(이벤트별): 전송 시 event_type에 따라 Stream 분기
- Firehose(Kinesis as Source) → S3/Parquet: Stream으로부터 pull, 스키마/압축/파티셔닝 처리
- 주의: Firehose가 Kinesis를 소스로 사용할 때는 `firehose.put_record()` 직접 호출이 거부됩니다. Generator는 반드시 `kinesis.put_record()`만 호출합니다.

## 변경 요지
- 이벤트 타입별 스트림 이름을 환경 변수로 관리하고, `boto3.client("kinesis")`의 `put_record()`를 사용합니다.
- 파티션 키는 샤드 분산을 위해 세션/사용자/임프레션 식별자를 활용합니다.
- 내부 계산용 필드(`_internal`)는 전송 전에 제거합니다.

## AS-IS / TO-BE 한눈에 보기
- AS-IS (현재 동작)
    - 전송 대상: Firehose Direct PUT 3개(`capa-fh-imp-00`, `capa-fh-clk-00`, `capa-fh-cvs-00`)
    - 코드 경로: `kinesis_sender.py`의 `FirehoseSender` → `boto3.client('firehose').put_record(DeliveryStreamName, ...)`
    - Kinesis 의존성: 없음(Generator가 Kinesis를 사용하지 않음)
    - 파티션 키: 사용 안 함(샤드 개념 없음)
    - IAM(생성기): `firehose:PutRecord` 필요, `kinesis:*` 불필요
    - Firehose 설정: 소스 미사용(Direct PUT), S3 변환/버퍼링은 Firehose가 담당

- TO-BE (목표 동작)
    - 전송 대상: Kinesis Streams 3개(`capa-knss-imp-00`, `capa-knss-clk-00`, `capa-knss-cvs-00`)
    - 코드 경로: 새 `KinesisStreamSender` 또는 리팩터링된 `EventSender(sink_mode='kinesis')` → `boto3.client('kinesis').put_record(StreamName, Data, PartitionKey)`
    - Firehose 설정: 각 Firehose가 해당 Kinesis Stream을 소스로 Pull(KinesisStreamAsSource)하여 S3/Parquet 적재
    - 파티션 키: 필수(`session_id`→`user_id`→`impression_id`→`event_id` 우선순위 해시)
    - IAM(생성기): `kinesis:PutRecord` 필요, Direct PUT 용 `firehose:PutRecord` 불필요
    - 이점: 다중 소비자 확장(EFO), 이벤트별 독립 스케일링/모니터링, 정확한 파티션 기반 처리량 확보

- 환경 변수 비교
    - AS-IS: `FIREHOSE_IMPRESSION`, `FIREHOSE_CLICK`, `FIREHOSE_CONVERSION`
    - TO-BE: `KINESIS_IMPRESSION`, `KINESIS_CLICK`, `KINESIS_CONVERSION`, `SINK_MODE=kinesis`

- 코드 스니펫 비교(핵심)
    - AS-IS
        - `from kinesis_sender import FirehoseSender`
        - `sender = FirehoseSender(firehose_names={...}, region=..., ...)`
    - TO-BE (옵션 A: 새 파일)
        - `from kinesis_stream_sender import KinesisStreamSender`
        - `sender = KinesisStreamSender(stream_names={...}, region=..., ...)`
    - TO-BE (옵션 B: 겸용 리팩터링)
        - `from kinesis_sender import EventSender`
        - `sender = EventSender(sink_mode='kinesis', stream_or_firehose_names={...}, region=..., ...)`

- 운영 특성
    - AS-IS: 구현 단순, Firehose Direct PUT 비용/버퍼링 이점 있으나 본 아키텍처와 분리(Streams 다중 소비자 부재)
    - TO-BE: Streams 중심 구조로 확장성/유연성 강화, Firehose는 Pull 전용으로 표준화

- 마이그레이션 절차(권장)
    1) 3개 Kinesis Streams 생성/확인: `capa-knss-imp-00`, `capa-knss-clk-00`, `capa-knss-cvs-00`
    2) 3개 Firehose를 각 Stream 소스로 설정(KinesisStreamAsSource) 및 S3/Parquet 옵션 점검
    3) `.env`에 `KINESIS_*`와 `SINK_MODE=kinesis` 추가, 기존 `FIREHOSE_*`는 보존(테스트 전용)
    4) 코드 전환: (A) `KinesisStreamSender` 도입 또는 (B) `kinesis_sender.py`를 `EventSender`로 리팩터링
    5) 스테이징 검증: 파티션 키 분포/처리량/오류재시도/CloudWatch 지표 확인
    6) 운영 반영 후 Direct PUT 경로/권한 정리(`firehose:PutRecord` 최소화 또는 제거)

## 1) 새 전송 모듈 추가: `KinesisStreamSender`
다음 파일을 추가하는 것을 권장합니다. 기존 Firehose 전송 로직은 유지하되, 실행 모드로 선택할 수 있게 분리합니다.

- 파일: services/data_pipeline_t2/log_gen_t2/realtime/kinesis_stream_sender.py
- 역할: 이벤트 타입별로 적절한 Stream에 `put_record()` 수행

예시 구현 스켈레톤:

```python
# kinesis_stream_sender.py
import json
import hashlib
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError


class KinesisStreamSender:
    def __init__(
        self,
        stream_names: Dict[str, str],
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> None:
        self.stream_names = stream_names
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )
        self.client = boto3.client("kinesis", **session_kwargs)
        self.stats = {et: {"success": 0, "error": 0} for et in ("impression", "click", "conversion")}

    def _detect_event_type(self, log: Dict) -> str:
        if log.get("conversion_id"):
            return "conversion"
        elif log.get("click_id"):
            return "click"
        return "impression"

    def _partition_key(self, log: Dict) -> str:
        # 분산 + 세션 일관성 균형: 세션 → 사용자 → 임프레션 순으로 선택
        key = log.get("session_id") or log.get("user_id") or log.get("impression_id") or log.get("event_id")
        # 문자열 보장 및 해싱(키 길이 제한/엔트로피 균형)
        return hashlib.md5(str(key).encode("utf-8")).hexdigest()

    def send(self, log: Dict) -> bool:
        event_type = self._detect_event_type(log)
        stream_name = self.stream_names.get(event_type)
        if not stream_name:
            print(f"[ERROR] Unknown event_type={event_type}")
            return False
        try:
            payload = dict(log)
            payload.pop("_internal", None)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.client.put_record(
                StreamName=stream_name,
                Data=data,
                PartitionKey=self._partition_key(payload),
            )
            self.stats[event_type]["success"] += 1
            print(f"[OK] Sent: {event_type} → {stream_name}")
            return True
        except ClientError as e:
            self.stats[event_type]["error"] += 1
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] Kinesis send failed [{event_type}→{stream_name}] {code}: {msg}")
            return False
        except Exception as e:
            self.stats[event_type]["error"] += 1
            print(f"[ERROR] Kinesis send error [{event_type}]: {type(e).__name__}: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        s = sum(v["success"] for v in self.stats.values())
        e = sum(v["error"] for v in self.stats.values())
        return {"success": s, "error": e, "total": s + e}

    def get_stats_by_type(self) -> Dict[str, Dict[str, int]]:
        return self.stats
```

## 2) 실행 모드와 환경 변수
실행 모드를 Kinesis 우선으로 전환하고, 스트림 이름을 환경 변수로 관리합니다.

- 상위 .env (권장 경로: `services/data_pipeline_t2/.env`)

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=ap-northeast-2

# 이벤트별 Kinesis Stream 이름
KINESIS_IMPRESSION=capa-knss-imp-00
KINESIS_CLICK=capa-knss-clk-00
KINESIS_CONVERSION=capa-knss-cvs-00

# 실행 모드 (kinesis | firehose)
SINK_MODE=kinesis
```

## 3) `main.py` 변경 포인트
- 파일: services/data_pipeline_t2/log_gen_t2/realtime/main.py
- 요지: 기본 전송 대상을 Firehose → Kinesis로 전환하고, 모드 전환 가능하도록 구성

변경 예시(핵심 부분만 발췌):

```python
# 상단 import
from kinesis_stream_sender import KinesisStreamSender  # 새 모듈
from kinesis_sender import FirehoseSender              # 기존(옵션)

class Config:
    SINK_MODE = os.getenv("SINK_MODE", "kinesis")  # 기본 kinesis

    # Kinesis
    KINESIS_IMPRESSION = os.getenv("KINESIS_IMPRESSION", "capa-knss-imp-00")
    KINESIS_CLICK = os.getenv("KINESIS_CLICK", "capa-knss-clk-00")
    KINESIS_CONVERSION = os.getenv("KINESIS_CONVERSION", "capa-knss-cvs-00")

    # Firehose(옵션: Direct PUT용. Kinesis as Source 사용 시 비활성 권장)
    FIREHOSE_IMPRESSION = os.getenv("FIREHOSE_IMPRESSION", "capa-fh-imp-00")
    FIREHOSE_CLICK = os.getenv("FIREHOSE_CLICK", "capa-fh-clk-00")
    FIREHOSE_CONVERSION = os.getenv("FIREHOSE_CONVERSION", "capa-fh-cvs-00")
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# ...

# Sender 초기화
sender = None
if Config.SINK_MODE == "kinesis":
    stream_names = {
        "impression": Config.KINESIS_IMPRESSION,
        "click": Config.KINESIS_CLICK,
        "conversion": Config.KINESIS_CONVERSION,
    }
    sender = KinesisStreamSender(
        stream_names=stream_names,
        region=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )
    print(f"✅ Kinesis 전송 활성화 ({Config.AWS_REGION})")
else:
    firehose_names = {
        "impression": Config.FIREHOSE_IMPRESSION,
        "click": Config.FIREHOSE_CLICK,
        "conversion": Config.FIREHOSE_CONVERSION,
    }
    sender = FirehoseSender(
        firehose_names=firehose_names,
        region=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )
    print(f"✅ Firehose 전송 활성화 ({Config.AWS_REGION})")
```

참고: 현재 저장소 기준으로는 Firehose Direct PUT 구현이 기본입니다. 본 문서대로 Kinesis 우선으로 전환하면, Firehose는 Kinesis를 소스로 하도록 Terraform/콘솔에서 설정해야 합니다.

## 4) 파티션 키 설계 팁
- 목표: 샤드 간 균형 분산과 세션 단위의 순서성 유지 균형
- 권장 우선순위: `session_id` → `user_id` → `impression_id` → `event_id`
- 키는 해시(md5 등)로 균일화하여 편향을 줄입니다.
- 샤드 초과(WriteProvisionedThroughputExceeded) 발생 시: 샤드 증설 또는 배치/백오프 도입

## 5) 실행 방법
사전 준비: 상위 디렉토리에 `.env` 생성 및 자격증명/스트림 이름 설정

```bash
# 가상환경(선택)
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1

# 의존성 설치
pip install -r requirements.txt

# 실행 (기본: Kinesis)
python main.py
```

Docker 사용 시(예):

```bash
# 이미지 빌드
docker build -t realtime-log-generator .

# 상위 .env를 컨테이너에 마운트해 실행
# Windows PowerShell 예시
docker run --rm -v "${PWD}\..\..\.env":/app/../../.env realtime-log-generator
```

## 6) 검증 체크리스트
- IAM 권한: `kinesis:PutRecord`(생성기), `firehose:*`(전송 파이프라인), `s3:PutObject` 등 적절히 부여
- Firehose 설정: 소스가 각 Kinesis Stream으로 지정되어야 함(Direct PUT 아님)
- 레코드 크기: Kinesis 단건 1MB 이하, 초당 샤드 한도 내 전송량 확인
- 파티션 키 분포: 사용자/세션 기반 해시로 편향 방지
- 실패 재시도: 필요 시 지수 백오프/로컬 버퍼링 고려

## 7) 자주 묻는 질문(FAQ)
- Q. Firehose 이름도 이미 있는데, 생성기가 Firehose로 직접 보내야 하나요?
  - A. 본 구조(Streams 3 + Firehose 3, Kinesis as Source)에서는 생성기가 Firehose API를 호출하지 않습니다. Firehose는 각 Stream에서 자동으로 pull합니다.
- Q. 이벤트 타입 필드가 없어도 되나요?
  - A. 현재 스키마는 `conversion_id`/`click_id` 존재 여부로 타입을 판별합니다. 필요 시 `event_type` 필드를 추가해도 무방하나, Stream이 분리되어 있어 필수는 아닙니다.
- Q. 배치 전송(put_records)을 써야 하나요?
  - A. 초기에는 단순성을 위해 `put_record()`로 시작하고, 처리량 요구가 생기면 `put_records()` + 재시도 전략을 도입하세요.

---

문의/후속 작업이 필요하면 알려주세요. 원하시면 위 변경을 코드에 바로 반영해 드릴 수 있습니다.

---

## (대안) 기존 `kinesis_sender.py` 수정으로 겸용 구현하기

새 파일을 추가하지 않고, 현재의 `kinesis_sender.py`를 소폭 리팩터링하여 Kinesis/Firehose 겸용 전송기로 쓰는 방법입니다. 코드 베이스의 변경 폭을 최소화하려는 경우에 적합합니다.

### 1) 유사점과 차이점 요약
- 유사점
  - 이벤트 타입 판별 로직: `conversion_id`/`click_id` 존재 여부로 `conversion`/`click`/`impression` 결정
  - 공통 전처리: `_internal` 필드 제거 후 직렬화(JSON line)
  - 통계 수집: 타입별 성공/실패 카운팅, 전체 합산 통계
- 차이점
  - 사용 클라이언트와 API가 다름: Kinesis(`boto3.client('kinesis')`, `put_record(StreamName, Data, PartitionKey)`) vs Firehose(`boto3.client('firehose')`, `put_record(DeliveryStreamName, Record)`)
  - 대상 리소스 이름: Stream 이름 vs Firehose Delivery Stream 이름
  - 파티션 키 필요 여부: Kinesis는 필수(샤드 분배), Firehose Direct PUT은 불필요

위 관점에서 `send()` 내부의 분기만 잘 정리하면 파일 1개로 겸용이 가능합니다.

### 2) 최소 변경 리팩터링 예시
아래처럼 `FirehoseSender`를 일반화하여 `EventSender`로 바꾸고, `sink_mode`(kinesis|firehose)와 이름 매핑을 모두 받을 수 있게 합니다. 주요 변경 포인트만 발췌합니다.

```python
# kinesis_sender.py (겸용 ver.)
import json
import hashlib
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError


class EventSender:
    def __init__(
        self,
        sink_mode: str,  # "kinesis" | "firehose"
        stream_or_firehose_names: Dict[str, str],
        region: str = "ap-northeast-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        self.sink_mode = sink_mode.lower()
        self.names = stream_or_firehose_names
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update({
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
            })
        client_name = "kinesis" if self.sink_mode == "kinesis" else "firehose"
        self.client = boto3.client(client_name, **session_kwargs)
        self.stats = {t: {"success": 0, "error": 0} for t in ("impression", "click", "conversion")}

    def _detect_event_type(self, log: Dict) -> str:
        if log.get("conversion_id"):
            return "conversion"
        if log.get("click_id"):
            return "click"
        return "impression"

    def _partition_key(self, log: Dict) -> str:
        key = log.get("session_id") or log.get("user_id") or log.get("impression_id") or log.get("event_id")
        return hashlib.md5(str(key).encode("utf-8")).hexdigest()

    def send(self, log: Dict) -> bool:
        et = self._detect_event_type(log)
        target_name = self.names.get(et)
        if not target_name:
            print(f"[ERROR] Unknown event_type={et}")
            return False
        try:
            payload = dict(log)
            payload.pop("_internal", None)
            data_json = json.dumps(payload, ensure_ascii=False)
            if self.sink_mode == "kinesis":
                self.client.put_record(
                    StreamName=target_name,
                    Data=data_json.encode("utf-8"),
                    PartitionKey=self._partition_key(payload),
                )
            else:
                self.client.put_record(
                    DeliveryStreamName=target_name,
                    Record={"Data": data_json + "\n"},
                )
            self.stats[et]["success"] += 1
            print(f"[OK] Sent: {et} → {target_name}")
            return True
        except ClientError as e:
            self.stats[et]["error"] += 1
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"[ERROR] send failed [{et}→{target_name}] {code}: {msg}")
            return False
        except Exception as e:
            self.stats[et]["error"] += 1
            print(f"[ERROR] send error [{et}]: {type(e).__name__}: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        s = sum(v["success"] for v in self.stats.values())
        e = sum(v["error"] for v in self.stats.values())
        return {"success": s, "error": e, "total": s + e}

    def get_stats_by_type(self) -> Dict[str, Dict[str, int]]:
        return self.stats
```

변경 포인트 정리
- 클래스명: `FirehoseSender` → `EventSender`로 일반화(선택). 기존 이름을 유지하고 `sink_mode`만 추가해도 무방합니다.
- 생성자: `sink_mode` 추가, 전달받은 이름 매핑 딕셔너리를 `names`로 통일해 보관
- 클라이언트: `kinesis`/`firehose` 중 선택 생성
- `send()`: 모드 분기하여 각각 `put_record(StreamName, ...)` 또는 `put_record(DeliveryStreamName, ...)` 호출
- 파티션 키: Kinesis 모드일 때만 사용(필수)

### 3) `main.py`에서의 사용 예시
`SINK_MODE`에 따라 매핑과 클래스를 한 번만 바꿔 주면 됩니다.

```python
from kinesis_sender import EventSender  # 리팩터링된 겸용 클래스

sink_mode = os.getenv("SINK_MODE", "kinesis")
if sink_mode == "kinesis":
    names = {
        "impression": os.getenv("KINESIS_IMPRESSION", "capa-knss-imp-00"),
        "click": os.getenv("KINESIS_CLICK", "capa-knss-clk-00"),
        "conversion": os.getenv("KINESIS_CONVERSION", "capa-knss-cvs-00"),
    }
else:
    names = {
        "impression": os.getenv("FIREHOSE_IMPRESSION", "capa-fh-imp-00"),
        "click": os.getenv("FIREHOSE_CLICK", "capa-fh-clk-00"),
        "conversion": os.getenv("FIREHOSE_CONVERSION", "capa-fh-cvs-00"),
    }

sender = EventSender(
    sink_mode=sink_mode,
    stream_or_firehose_names=names,
    region=os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
```

### 4) 장단점
- 장점
    - 변경 최소: 기존 파일 재사용으로 신규 모듈/배포 단위 증가를 방지합니다.
    - 구성 단순화: `SINK_MODE` 스위치만으로 Kinesis↔Firehose 전환이 가능합니다.
    - 운영 유연성: 환경별(로컬/스테이징/운영) 목적에 맞춰 싱크를 선택할 수 있습니다.
    - 코드 재사용: 이벤트 판별/전처리/통계 로직을 한 곳에서 유지합니다.
    - 배포 리스크 감소: 외부 인터페이스 불변으로 `main.py` 등 연쇄 변경을 줄입니다.
- 단점
    - 단일 책임 원칙 위반: 전송 책임이 Kinesis/Firehose로 이원화되어 응집도가 낮아질 수 있습니다.
    - 테스트 복잡도 증가: 두 경로(Kinesis/Firehose) 각각에 대한 단위/통합 테스트가 필요합니다.
    - 장애 격리 약화: 한 파일 변경이 양 모드에 모두 영향을 줄 수 있어 회귀 위험이 커집니다.
    - 설정 오류 리스크: `KINESIS_*` vs `FIREHOSE_*` 이름 매핑 혼동으로 잘못된 대상에 전송할 수 있습니다.
    - 성능 최적화 제약: 모드별로 최적 매개변수(배치 크기/재시도 정책 등) 차별화가 어려울 수 있습니다.
- 완화책(권장)
    - 전략 패턴 적용: `SinkClient` 인터페이스 + `KinesisSink`/`FirehoseSink` 구현으로 분리하고, `EventSender`는 조합만 담당.
    - 명확한 설정 스키마: `.env` 키와 유효 조합을 문서화하고, 애플리케이션 부팅 시 필수 키 검증.
    - 테스트 매트릭스: 모드×이벤트타입(imp/click/conv) 최소 6케이스 자동화, 클라이언트 모킹 분리.
    - 옵저버빌리티: 로그/메트릭에 `mode`/`event_type` 태그 포함, CloudWatch 대시보드 분리.
    - 점진 분리: 운영 정착 후 Firehose 경로를 별 파일로 추출하여 SRP 회복.
- 권장 사용 시나리오
    - 운영: `SINK_MODE=kinesis` 필수(본 구조에서 Firehose는 Kinesis를 소스로 Pull).
    - 로컬/디버그: 필요 시 Firehose Direct PUT 허용하되, 운영에는 적용 금지.
    - 마이그레이션: 기존 Direct PUT 사용 중이면 ① `SINK_MODE=kinesis` 전환 → ② Firehose Source를 Kinesis로 교체 → ③ Direct PUT 변수 제거 순서로 진행.
- 오류/예외 처리 주의
    - Kinesis: `ProvisionedThroughputExceededException` 발생 시 지수 백오프/재시도 및 파티션키 분포 점검.
    - Firehose: `ServiceUnavailableException`/`ThrottlingException` 시 재시도, 필요 시 배치 전송 검토.
    - 공통: 1MB 단건 제한 준수, 직렬화 실패 대비, `_internal` 필드 제거 누락 방지.
- 보안/IAM
    - Kinesis 경로: `kinesis:PutRecord` 최소 권한, 대상 Stream ARN 스코프 제한.
    - Firehose 경로: `firehose:PutRecord`(Direct PUT) 권한은 비권장 구조에서는 제거 또는 개발 환경에 한정.
    - 권한 드리프트 방지: 모드 전환 시 필요 권한 체크리스트로 검증.
- 성능/비용 관점
    - Kinesis: 샤드 수에 비용/처리량이 비례, 파티션키 균형이 처리량에 직결됩니다.
    - Firehose Direct PUT: 건수당 비용과 버퍼링 이점이 있으나, 본 구조에서는 비권장입니다.

Kinesis Streams 3개 + Firehose 3개(Kinesis as Source) 구조에서는 `SINK_MODE=kinesis` 사용이 정석입니다. Firehose Direct PUT 모드는 비활성화하거나, 별도 테스트/로컬 모드에만 사용하세요.
