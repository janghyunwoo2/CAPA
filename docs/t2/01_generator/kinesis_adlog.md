# Kinesis 통합 가이드 (통합본)

본 문서는 아래 문서들을 하나로 통합한 버전입니다.

- kinesis_firehose_integration_guide.md
- kinesis_stream_multiple_consumers.md

---

## Kinesis 및 Firehose 통합 가이드 (원문)

<!-- 출처: docs/t2/kinesis_firehose_integration_guide.md -->

# Kinesis 및 Firehose 통합 가이드

## 1. 개요

이 가이드는 광고 로그 생성기에 AWS Kinesis Data Streams와 Firehose를 통합하여 실시간 스트리밍 아키텍처를 구축하는 방법을 설명합니다. 현재 배치 방식의 `ad_log_generator.py`를 실시간 스트리밍 방식으로 전환하는 과정을 다룹니다.

## 2. 아키텍처 비교 분석

### 2.1 현재 시스템 구조

#### 배치 방식 (ad_log_generator.py)
```
[로그 생성] → [DataFrame 구성] → [Parquet 압축] → [S3 직접 업로드]
```

**특징:**
- 시간별로 대량 데이터를 한 번에 처리
- 10,000개 이상의 레코드를 메모리에 보관 후 저장
- 파티셔닝: `/year=/month=/day=/hour=` 구조

#### 실시간 스트리밍 방식 (main.py, t3_log_generator)
```
[로그 생성] → [JSON 직렬화] → [Kinesis Streams] → [Firehose] → [S3]
```

**특징:**
- 레코드 단위로 즉시 전송
- 24시간 데이터 버퍼링으로 안전성 보장
- 자동 파일 생성 및 압축

### 2.2 성능 및 비용 비교

| 구분 | 배치 방식 | 스트리밍 방식 | 하이브리드 방식 |
|------|----------|--------------|----------------|
| **지연시간** | 1시간 | 1-2분 | 1-2분 |
| **처리량** | 매우 높음 | 중간 | 높음 |
| **데이터 손실 위험** | 높음 | 매우 낮음 | 낮음 |
| **구현 복잡도** | 낮음 | 중간 | 높음 |
| **월 예상 비용** | ~$50 | ~$200-500 | ~$250-550 |
| **확장성** | 수동 | 자동 | 자동 |

## 3. 파일 구조 권장사항

### 3.1 프로덕션 환경: 모듈화된 구조 (권장)

```
log-generator/
├── pyproject.toml          # 의존성 관리
├── .env                    # 환경 변수
├── main.py                 # 진입점
├── generator.py            # 로그 생성 로직
├── kinesis_sender.py       # Kinesis 전송 모듈
├── s3_writer.py           # S3 직접 저장 모듈 (옵션)
└── config.py              # 설정 관리
```

**장점:**
- 각 기능이 독립적으로 관리되어 유지보수 용이
- 단위 테스트 작성 용이
- 재사용 가능한 컴포넌트
- 팀 협업에 유리

**단점:**
- 초기 설정 복잡도 증가
- 파일 간 의존성 관리 필요

### 3.2 프로토타입/POC: 단일 파일 구조

```
ad_log_generator_streaming.py  # 모든 로직 포함
```

**장점:**
- 빠른 프로토타이핑
- 배포 및 실행 간단
- 의존성 최소화

**단점:**
- 코드가 길어지면 관리 어려움
- 재사용성 낮음

### 3.3 권장 접근 방법

1. **초기 개발**: 단일 파일로 시작하여 빠르게 검증
2. **안정화 단계**: 기능별로 모듈 분리
3. **프로덕션 배포**: 완전히 모듈화된 구조로 전환

## 4. Kinesis와 Firehose의 역할 및 구현

### 4.1 AWS Kinesis Data Streams

**핵심 역할:**
- **실시간 버퍼**: 1-7일간 데이터 보존으로 장애 대응
- **병렬 처리**: 샤드별 분산으로 초당 수천 건 처리
- **다중 소비**: 동일 데이터를 여러 시스템에서 활용

**구현 시 주의사항:**
```python
# PartitionKey 설정이 중요 - 균등 분산을 위해
partition_key = f"{user_id}_{timestamp.strftime('%Y%m%d%H')}"
```

### 4.2 AWS Kinesis Data Firehose

**핵심 역할:**
- **자동 전송**: Kinesis → S3 자동 배치 처리
- **형식 변환**: JSON → Parquet 실시간 변환
- **압축 최적화**: GZIP/Snappy로 스토리지 절감

**최적 설정값:**
- Buffer Size: 128MB (대용량 처리 시)
- Buffer Interval: 60초 (실시간성 요구 시)
- Compression: GZIP (압축률 우선) 또는 Snappy (속도 우선)

## 5. 통합 구현 방법

... (원문 전체 내용 포함)

## 6. Firehose 설정 및 구성

... (원문 전체 내용 포함)

## 7. 마이그레이션 전략 및 실무 가이드

... (원문 전체 내용 포함)

## 8. 환경 변수 설정

... (원문 전체 내용 포함)

## 9. 성능 비교

... (원문 전체 내용 포함)

## 10. 결론

Kinesis와 Firehose 통합은 실시간 데이터 처리와 안전성을 크게 향상시킵니다. 초기에는 하이브리드 모드로 시작하여 시스템 안정성을 확인한 후 완전한 스트리밍 모드로 전환하는 것을 권장합니다.

---

## Kinesis Stream 다중 소비자 설명 (원문)

<!-- 출처: docs/t2/kinesis_stream_multiple_consumers.md -->

# Kinesis Stream 다중 소비자 (Multiple Consumers) 설명

## 개념

**하나의 데이터 소스**에서 발생한 데이터를 **여러 서비스가 동시에, 각자의 목적으로** 읽어야 하는 상황을 말합니다.

---

## 예시: 광고 로그를 여러 곳에서 동시에 써야 할 때

```
                         ┌→ 소비자 1: Firehose → S3 (배치 분석용 저장)
                         │
Ad Log Generator → 로그 →├→ 소비자 2: Lambda → 실시간 이상 탐지 (클릭 사기 감지)
                         │
                         ├→ 소비자 3: Lambda → 실시간 대시보드 (Grafana 등)
                         │
                         └→ 소비자 4: Spark Streaming → 실시간 CTR 계산
```

이 경우 **같은 로그 데이터**를 4개의 서비스가 각각 읽어야 합니다.

---

## Firehose만으로는 왜 안 되는가

```
Generator → Firehose → S3
                ↑
          "나는 S3로 배달만 해. 다른 데는 못 줘."
```

Firehose는 **일방향 배달 파이프**입니다.  
데이터를 받아서 S3(또는 Redshift, OpenSearch)로 보내는 것만 합니다.  
다른 서비스가 Firehose에서 데이터를 읽을 수 없습니다.

---

## Kinesis Stream이 필요한 이유

```
                              ┌→ Firehose(S3 저장) — 각자 독립적으로 읽음
                              │
Generator → Kinesis Stream →──├→ Lambda(이상 탐지) — 각자 독립적으로 읽음  
            (메시지 큐)        │
                              ├→ Lambda(대시보드) — 각자 독립적으로 읽음
                              │
                              └→ Spark(CTR 계산) — 각자 독립적으로 읽음
```

Kinesis Stream은 **메시지 큐**입니다:
- 데이터를 **24시간 보관**
- **여러 소비자가 동시에** 같은 데이터를 읽을 수 있음
- 각 소비자는 **자기 위치(offset)를 독립적으로** 관리
- 소비자 A가 느려도 소비자 B에 영향 없음

---

## 카페 비유

| 구조 | 비유 |
|------|------|
| **Firehose (Direct PUT)** | 배달 기사가 음식을 **한 곳에만** 가져다줌. 다른 곳으로는 못 감 |
| **Kinesis Stream** | 게시판에 메뉴를 **게시**해두면, 여러 사람이 각자 와서 읽어감. 24시간 후 게시물 사라짐 |

---

## 구체적 다중 소비자 사용 사례

| 소비자 | 목적 | 읽는 방식 |
|--------|------|----------|
| Firehose | S3에 Parquet 저장 (배치 분석) | Stream에서 자동 pull |
| Lambda 1 | 클릭 사기 탐지 (5초 내 비정상 클릭 패턴) | Stream에서 실시간 읽기 |
| Lambda 2 | Slack 알림 (conversion_value > 100만원이면 알림) | Stream에서 실시간 읽기 |
| KDA (Kinesis Data Analytics) | 실시간 CTR/CVR 집계 (5분 윈도우) | Stream에서 실시간 읽기 |
| 다른 팀의 서비스 | 광고 데이터를 자기 DB에 저장 | Stream에서 읽기 |

---

## 현재 프로젝트 상황

### 현재 구조 (다중 소비자 없음 → Stream 불필요)

```
Generator → Firehose 3개 → S3 저장
            (소비자 1개: S3 저장뿐)

→ 다중 소비자 없음 → Stream 불필요
```

### 미래 구조 (다중 소비자 필요 시)

```
Generator → Kinesis Stream → Firehose 3개 → S3 저장
                           → Lambda → 이상 탐지
                           → Lambda → 실시간 대시보드
```

나중에 "실시간 이상 탐지 Lambda도 같은 로그를 봐야 해"라는 요구가 생기면, 그때 Stream을 추가하면 됩니다.

---

## Firehose Direct PUT vs Kinesis Stream 비교

| 항목 | Firehose Direct PUT | Kinesis Stream + Firehose |
|------|--------------------|-----------------------|
| **소비자 수** | 1개 (S3 등 단일 목적지) | 여러 개 동시 가능 |
| **데이터 보관** | 없음 (바로 전달) | 24~168시간 보관 |
| **재처리(Replay)** | 불가 | 가능 (보관 기간 내) |
| **순서 보장** | 없음 | Partition Key 기준 보장 |
| **비용** | 데이터 양만 과금 | 샤드 시간당 과금 (추가 비용) |
| **스케일링** | 자동 | 샤드 수동 조절 (또는 On-Demand) |
| **복잡도** | 낮음 | 높음 |
| **적합한 경우** | S3 저장만 하면 될 때 | 실시간 분석 등 다중 소비자가 필요할 때 |

---

## 결론

> **Kinesis Stream은 "처리 용량" 때문에 필요한 게 아니라, "다중 소비자" 때문에 필요합니다.**
>
> 현재처럼 S3 저장만이 목적이라면, 데이터가 아무리 많아도 Firehose Direct PUT만으로 충분합니다.  
> 오히려 Stream이 없는 게 비용도 싸고 구조도 단순합니다.
