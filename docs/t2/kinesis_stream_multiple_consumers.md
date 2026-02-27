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
